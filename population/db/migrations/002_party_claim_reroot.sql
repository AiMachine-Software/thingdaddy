-- ============================================================================
-- Migration 002 — claim / re-root path (Model A, in-place re-root)
-- Target DB: thingdaddy_population
--
-- The keystone screen-1 mechanism: a DEMO/candidate party row is re-rooted
-- IN PLACE onto a verified GS1 prefix (id stays stable, so its edges and event
-- history follow), and its pre-claim identity is frozen into an append-only
-- `party_origin` ledger — the immutable "caterpillar" record the "butterfly"
-- links back to (Caterpillar->Butterfly / TD-M-50).
--
-- Ratified decisions encoded here:
--   * Model A: re-root in place; NO separate butterfly row.
--   * party_origin OMITS origin_party_id — the origin is a snapshot ON the same
--     row (origin_urn / origin_prefix), not a link to a distinct row.
--   * prefix CHECK is DIGITS-ONLY (^[0-9]+$) with NO length band — true prefix
--     length stays authority-confirmed (Verified by GS1 / GEPIR), never a
--     static bound. This is the structural DEMO exclusion: a '0DEMO...' string
--     contains letters, so it can never occupy `prefix`, so it can never satisfy
--     the gate (party_gate_prefix_required). Un-verifiable by construction.
--   * party_demo_not_verified: an is_demo row can never be `verified` — the
--     coherence backstop to the digits-only guard.
--   * write-once enforcement is by TRIGGER (a CHECK cannot compare prior values):
--       - party_origin is append-only (no UPDATE, no DELETE, ever).
--       - a verified party's prefix is immutable (the identity anchor is fixed).
--
-- Isolation: owned by population/. Does not touch platform/. Additive only.
-- Idempotent: ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS /
--   CREATE OR REPLACE FUNCTION / DROP TRIGGER IF EXISTS + CREATE / named CHECKs
--   guarded by a pg_constraint existence test. Safe to re-apply as a no-op.
--
-- Apply:  psql -v ON_ERROR_STOP=1 -d thingdaddy_population -f db/migrations/002_party_claim_reroot.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) party columns — the DEMO structural marker + the recorded placeholder.
-- ----------------------------------------------------------------------------
ALTER TABLE party
  ADD COLUMN IF NOT EXISTS is_demo  boolean NOT NULL DEFAULT false;  -- true = DEMO-staged candidate (TD-M-50 staging).
ALTER TABLE party
  ADD COLUMN IF NOT EXISTS demo_urn text;                            -- the 0DEMO... URN the platform displayed; recorded, never copied into prefix.

COMMENT ON COLUMN party.is_demo IS
  'DEMO structural marker: a pre-populated DEMO-staged candidate. Flipped false when the row is claimed/re-rooted. An is_demo row can never be verified (party_demo_not_verified).';
COMMENT ON COLUMN party.demo_urn IS
  'The 0DEMO... EPC URN the platform staged this row under. Captured so the placeholder is preserved at claim time. NEVER copied into party.prefix.';

-- ----------------------------------------------------------------------------
-- 2) CHECK — prefix is digits-only (the structural DEMO exclusion).
--    NO length band: true company-prefix length is authority-confirmed, not a
--    static bound. A '0DEMO...' string has letters, so it cannot live here.
--    (Existing data: all real prefixes are digits, all candidates are NULL —
--    validates cleanly, breaks nothing.)
-- ----------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'party_prefix_digits_only' AND conrelid = 'party'::regclass
  ) THEN
    ALTER TABLE party
      ADD CONSTRAINT party_prefix_digits_only
      CHECK (prefix IS NULL OR prefix ~ '^[0-9]+$');
  END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 3) CHECK — demo coherence backstop: an is_demo row can never be verified.
--    The claim tx flips is_demo->false and state->'verified' atomically, so
--    there is no ordering where a demo-flagged row is verified.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'party_demo_not_verified' AND conrelid = 'party'::regclass
  ) THEN
    ALTER TABLE party
      ADD CONSTRAINT party_demo_not_verified
      CHECK (NOT is_demo OR state <> 'verified');
  END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 4) party_origin — append-only immutable origin ledger (the frozen caterpillar).
--    Model A: origin is a snapshot on the SAME row, so there is no
--    origin_party_id. One re-root per party (ux_party_origin_party). The party
--    cannot be deleted out from under its origin (ON DELETE RESTRICT).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party_origin (
  id             bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  party_id       bigint      NOT NULL REFERENCES party (id) ON DELETE RESTRICT,  -- the re-rooted (butterfly) row.
  origin_urn     text,                       -- the DEMO EPC URN this row re-rooted from (snapshot of party.demo_urn).
  origin_prefix  text,                       -- the pre-claim prefix, if any (may be a 0DEMO placeholder or NULL). NOT constrained: it records the placeholder verbatim.
  claimed_prefix text        NOT NULL,       -- the real GS1 prefix it re-rooted onto (snapshot of the promoted party.prefix).
  authority      jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- evidence captured at claim: { gepir, lei, doc }.
  actor          text,                       -- the claimant identity.
  at             timestamptz NOT NULL DEFAULT now(),

  -- One origin per party: a row can be re-rooted exactly once. A second claim
  -- attempt hits this unique index (23505) -> the API surfaces a 409 conflict.
  CONSTRAINT ux_party_origin_party UNIQUE (party_id)
);

COMMENT ON TABLE party_origin IS
  'Append-only immutable origin ledger (Caterpillar->Butterfly / TD-M-50). One row per re-root, written once by POST /claim inside the promotion tx. Never updated or deleted (trg_party_origin_immutable). Model A: origin is a snapshot on the same party row, so there is no origin_party_id.';

CREATE INDEX IF NOT EXISTS ix_party_origin_party ON party_origin (party_id);

-- ----------------------------------------------------------------------------
-- 5) TRIGGER — party_origin is append-only. A CHECK cannot express "write once"
--    (it cannot see the prior value); forbidding the mutation verbs can.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION party_origin_is_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'party_origin is append-only: % on id % is not permitted',
    TG_OP, COALESCE(OLD.id, NEW.id)
    USING ERRCODE = 'raise_exception';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_party_origin_immutable ON party_origin;
CREATE TRIGGER trg_party_origin_immutable
  BEFORE UPDATE OR DELETE ON party_origin
  FOR EACH ROW EXECUTE FUNCTION party_origin_is_append_only();

-- ----------------------------------------------------------------------------
-- 6) TRIGGER — a verified party's prefix is immutable (the identity anchor is
--    fixed once earned). Promotion is allowed (OLD.state='candidate'); only a
--    prefix CHANGE on an already-verified row is rejected. Re-ingest is safe:
--    it never sets prefix, and ON CONFLICT (prefix) matches the same value.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION party_verified_prefix_immutable() RETURNS trigger AS $$
BEGIN
  IF OLD.state = 'verified' AND OLD.prefix IS NOT NULL
     AND NEW.prefix IS DISTINCT FROM OLD.prefix THEN
    RAISE EXCEPTION 'verified prefix is immutable: party % prefix %->% not permitted',
      OLD.id, OLD.prefix, NEW.prefix
      USING ERRCODE = 'raise_exception';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_party_verified_prefix_immutable ON party;
CREATE TRIGGER trg_party_verified_prefix_immutable
  BEFORE UPDATE ON party
  FOR EACH ROW EXECUTE FUNCTION party_verified_prefix_immutable();
