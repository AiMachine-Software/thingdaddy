-- ============================================================================
-- Migration 010 — the unified graph spine (Cycle 3 · Core). node + association
-- + node_event. Additive ONLY: creates new tables, touches NOTHING existing.
-- Backfill from party/asset/edge/carrier/party_event and endpoint rewiring come
-- in later migrations/PRs — this is the schema, applyable and reviewable.
--
-- DECIDED (KJ 2026-07-17): unified node model; migrate into ONE spine.
-- THE LAW: no limits on topology, strict on truth — every node + association
-- lands `candidate`, engine-minted, verified-or-exception. "Think" = candidate.
--
-- Apply: psql -v ON_ERROR_STOP=1 -d thingdaddy_population_test -f db/migrations/010_node_association.sql
-- ============================================================================

-- node: every engine-minted identity is one row (PGLN/GLN/GTIN/GIAI/GRAI/GSRN/GDTI/CPID/LGTIN).
CREATE TABLE IF NOT EXISTS node (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  urn              text,                          -- engine-minted URN; NULL until minted/rooted (candidates have none)
  key_type         text NOT NULL,                 -- pgln|gln|gtin|giai|grai|gsrn|gdti|cpid|lgtin
  kind             text,                          -- optional sub-type (gdti: driver|protocol|document)
  prefix           text,                          -- root prefix; NULL until rooted
  legal_name       text,                          -- carried from party for org/location nodes
  gln              text,
  lei              text,
  mo               text,
  label            text,
  standard         text,                          -- governing standard (SiLA-2-FDL|Allotrope-AFO|21CFR|…)
  state            text NOT NULL DEFAULT 'candidate',
  source           text NOT NULL,
  exception_reason text,
  first_seen       timestamptz NOT NULL DEFAULT now(),
  last_updated     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT node_state_valid CHECK (state IN ('candidate','verified','exception')),
  -- prefix-is-root gate, carried from party: nothing is verified without a prefix.
  CONSTRAINT node_gate_prefix CHECK (state <> 'verified' OR prefix IS NOT NULL)
);
-- one URN once (partial: many candidates hold NULL urn).
CREATE UNIQUE INDEX IF NOT EXISTS ux_node_urn    ON node (urn)    WHERE urn IS NOT NULL;
-- one verified company prefix once, for organization nodes.
CREATE UNIQUE INDEX IF NOT EXISTS ux_node_prefix ON node (prefix) WHERE prefix IS NOT NULL AND key_type = 'pgln';
CREATE INDEX IF NOT EXISTS ix_node_key_type ON node (key_type);
CREATE INDEX IF NOT EXISTS ix_node_state    ON node (state);
CREATE INDEX IF NOT EXISTS ix_node_prefix   ON node (prefix);

-- association: any node -> any node. "things connected to things, no limits."
CREATE TABLE IF NOT EXISTS association (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  subject_node_id bigint NOT NULL REFERENCES node (id) ON DELETE CASCADE,
  object_node_id  bigint NOT NULL REFERENCES node (id) ON DELETE CASCADE,
  rel             text NOT NULL,                  -- open vocab + conventions: part_of|component_of|driver_of|protocol_of|document_of|sameAs|carrier_of|…
  attributes      jsonb NOT NULL DEFAULT '{}'::jsonb,  -- BOM ordinality, CAD placement, carrier profile, rule refs
  state           text NOT NULL DEFAULT 'candidate',
  inferred        boolean NOT NULL DEFAULT false,      -- agent-proposed = "things we THINK are connected"
  source          text NOT NULL,
  first_seen      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT association_state_valid CHECK (state IN ('candidate','verified','exception'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_association ON association (subject_node_id, object_node_id, rel, source);
CREATE INDEX IF NOT EXISTS ix_association_subject ON association (subject_node_id);
CREATE INDEX IF NOT EXISTS ix_association_object  ON association (object_node_id);
CREATE INDEX IF NOT EXISTS ix_association_rel     ON association (rel);

-- node_event: append-only provenance thread — the training substrate for the generative tier.
CREATE TABLE IF NOT EXISTS node_event (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  node_id        bigint REFERENCES node (id) ON DELETE CASCADE,
  association_id bigint REFERENCES association (id) ON DELETE CASCADE,  -- exactly one of node_id/association_id set
  event_type     text NOT NULL,                  -- node_minted|associated|verified|exception|claimed|rule_fired|…
  from_state     text,
  to_state       text,
  detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
  source         text NOT NULL,
  actor          text,
  at             timestamptz NOT NULL DEFAULT now(),

  -- provenance always threads to exactly one subject: a node OR an association.
  CONSTRAINT node_event_one_subject CHECK ((node_id IS NOT NULL) <> (association_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_node_event_node ON node_event (node_id);
CREATE INDEX IF NOT EXISTS ix_node_event_assoc ON node_event (association_id);
CREATE INDEX IF NOT EXISTS ix_node_event_type ON node_event (event_type);
CREATE INDEX IF NOT EXISTS ix_node_event_at   ON node_event (at);
