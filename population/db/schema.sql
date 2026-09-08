-- ============================================================================
-- ThingDaddy Population Database — schema (Step 2)
-- Target DB: thingdaddy_population   (see apply.sh)
--
-- Isolation: this file is owned by population/. It NEVER touches platform code.
-- The gate is inviolable: a row may only be `verified` if it carries a prefix.
-- Ingest lands candidates only. No fabricated prefixes. Synthetic rows carry
-- source = 'synthetic'.
--
-- Idempotent: safe to re-apply (IF NOT EXISTS / CREATE OR REPLACE / DROP..IF EXISTS).
-- ============================================================================

-- Trigram search over legal_name (fuzzy namesake matching, entity resolution).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ----------------------------------------------------------------------------
-- party — the population spine. Every physical/legal party candidate lands here.
-- Prefix-is-root: a party is only VERIFIED when a GS1 company prefix is present.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  prefix           text,                      -- GS1 company prefix (root). NULL until known.
  gln              text,                      -- Global Location Number, if known.
  legal_name       text        NOT NULL,      -- the resolved legal entity name.
  city             text,
  country          text,
  mo               text,                      -- GS1 Member Organization band (e.g. 'GS1 US').
  lei              text,                      -- Legal Entity Identifier (GLEIF authority step).
  state            text        NOT NULL DEFAULT 'candidate',
  source           text        NOT NULL,      -- provenance of this row (connector / 'synthetic' / 'manual').
  exception_reason text,                      -- required narrative when state = 'exception'.
  verified_at      timestamptz,               -- set when the party crosses to 'verified'.
  first_seen       timestamptz NOT NULL DEFAULT now(),
  last_updated     timestamptz NOT NULL DEFAULT now(),
  search_tsv       tsvector,                  -- kept in sync by trg_party_search_tsv.

  -- state is a closed vocabulary (verified-or-exception; candidate is first-class).
  CONSTRAINT party_state_valid
    CHECK (state IN ('candidate', 'verified', 'exception')),

  -- ══ THE GATE (inviolable) ══
  -- Nothing mints on a guess: a party may only be VERIFIED if it roots in a prefix.
  CONSTRAINT party_gate_prefix_required
    CHECK (state <> 'verified' OR prefix IS NOT NULL)
);

-- ----------------------------------------------------------------------------
-- Indexes
-- ----------------------------------------------------------------------------
-- One verified prefix, once. Partial-unique so many candidates can sit at NULL.
CREATE UNIQUE INDEX IF NOT EXISTS ux_party_prefix
  ON party (prefix) WHERE prefix IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_party_gln    ON party (gln);
CREATE INDEX IF NOT EXISTS ix_party_state  ON party (state);
CREATE INDEX IF NOT EXISTS ix_party_mo     ON party (mo);
CREATE INDEX IF NOT EXISTS ix_party_source ON party (source);

-- Full-text search over the maintained tsvector.
CREATE INDEX IF NOT EXISTS ix_party_search_tsv
  ON party USING gin (search_tsv);

-- Fuzzy / namesake matching over the raw legal name (pg_trgm).
CREATE INDEX IF NOT EXISTS ix_party_legal_name_trgm
  ON party USING gin (legal_name gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- search_tsv sync trigger — legal_name weighted highest, then locality + MO band.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION party_search_tsv_update() RETURNS trigger AS $$
BEGIN
  NEW.search_tsv :=
      setweight(to_tsvector('simple', coalesce(NEW.legal_name, '')), 'A')
    || setweight(to_tsvector('simple', coalesce(NEW.city,       '')), 'C')
    || setweight(to_tsvector('simple', coalesce(NEW.country,    '')), 'C')
    || setweight(to_tsvector('simple', coalesce(NEW.mo,         '')), 'D');
  -- keep last_updated honest on every mutation.
  NEW.last_updated := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_party_search_tsv ON party;
CREATE TRIGGER trg_party_search_tsv
  BEFORE INSERT OR UPDATE ON party
  FOR EACH ROW EXECUTE FUNCTION party_search_tsv_update();

-- ----------------------------------------------------------------------------
-- edge — typed relationships between a subject party and an object (which may or
-- may not itself be a registered party). Mirrors the fleet's Loop-B relationship
-- model (parent_of / supplies / award_recipient / registered_as / related_to …).
-- Edges carry their own verified/candidate/exception state and provenance.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edge (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  subject_party_id bigint      NOT NULL REFERENCES party (id) ON DELETE CASCADE,
  rel              text        NOT NULL,      -- relationship kind (parent_of, supplies, …).
  object_label     text        NOT NULL,      -- object's resolved name.
  object_prefix    text,                      -- object's prefix, if it has one (NULL otherwise).
  object_party_id  bigint      REFERENCES party (id) ON DELETE SET NULL,  -- set once the object resolves to a party row.
  state            text        NOT NULL DEFAULT 'candidate',
  source           text        NOT NULL,      -- connector / 'synthetic' / 'manual'.
  inferred         boolean     NOT NULL DEFAULT false,
  doc              text,                      -- documentary reference backing the edge.
  first_seen       timestamptz NOT NULL DEFAULT now(),
  last_updated     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT edge_state_valid
    CHECK (state IN ('candidate', 'verified', 'exception'))
);

CREATE INDEX IF NOT EXISTS ix_edge_subject ON edge (subject_party_id);
CREATE INDEX IF NOT EXISTS ix_edge_object  ON edge (object_party_id);
CREATE INDEX IF NOT EXISTS ix_edge_rel     ON edge (rel);
CREATE INDEX IF NOT EXISTS ix_edge_state   ON edge (state);
-- de-dupe the same asserted relationship from the same source.
CREATE UNIQUE INDEX IF NOT EXISTS ux_edge_assertion
  ON edge (subject_party_id, rel, object_label, source);

-- ----------------------------------------------------------------------------
-- party_event — append-only provenance ledger. Every state change, claim, and
-- exception is written here once and never overwritten (the provenance spine).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party_event (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  party_id   bigint      NOT NULL REFERENCES party (id) ON DELETE CASCADE,
  event_type text        NOT NULL,            -- 'candidate_staged' | 'verified' | 'exception' | 'prefix_claimed' | 'updated' | …
  from_state text,
  to_state   text,
  detail     jsonb       NOT NULL DEFAULT '{}'::jsonb,
  source     text        NOT NULL,
  actor      text,                            -- agent GSRN or 'manual'.
  at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_party_event_party ON party_event (party_id);
CREATE INDEX IF NOT EXISTS ix_party_event_type  ON party_event (event_type);
CREATE INDEX IF NOT EXISTS ix_party_event_at    ON party_event (at);
