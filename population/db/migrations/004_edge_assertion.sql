-- ============================================================================
-- Migration 004 — edge assertion stamp (asserter + validity window)
-- Target DB: thingdaddy_population
--
-- Cycle 1 · Core. Role stamps and co-reference (sameAs) are typed edges asserted
-- by someone, at some time, sometimes for a bounded period. The edge table already
-- carries rel / state / source / inferred / doc; this adds WHO asserted it and
-- WHEN it is valid, so an asserted edge is self-provenanced:
--   * asserter    — the accountable node that asserted this edge (a GSRN, or
--                   'manual'). Distinct from `source` (the connector/feed). NULL
--                   for pre-existing rows and legacy loads.
--   * valid_from  — start of the assertion's validity window (NULL = open start).
--   * valid_to    — end of the window (NULL = still valid / open-ended).
--
-- registrar-does-not-adjudicate: this migration does NOT change edge state rules.
-- Asserted edges land `candidate` (enforced by the API, not here); nothing here
-- promotes or merges. Additive only.
--
-- Isolation: owned by population/. Does not touch platform/. Additive only.
-- Idempotent: ADD COLUMN IF NOT EXISTS — re-applying is a no-op.
--
-- Apply:  psql -v ON_ERROR_STOP=1 -d thingdaddy_population -f db/migrations/004_edge_assertion.sql
-- ============================================================================

ALTER TABLE edge
  ADD COLUMN IF NOT EXISTS asserter   text;         -- accountable node (GSRN / 'manual'); NULL until known.
ALTER TABLE edge
  ADD COLUMN IF NOT EXISTS valid_from timestamptz;  -- start of validity window; NULL = open start.
ALTER TABLE edge
  ADD COLUMN IF NOT EXISTS valid_to   timestamptz;  -- end of validity window; NULL = still valid.

COMMENT ON COLUMN edge.asserter IS
  'The accountable node that asserted this edge (a GSRN, or ''manual''). Distinct from source (the feed). NULL for legacy/loader rows.';
COMMENT ON COLUMN edge.valid_from IS
  'Start of this assertion''s validity window. NULL = open start.';
COMMENT ON COLUMN edge.valid_to IS
  'End of this assertion''s validity window. NULL = still valid / open-ended.';

-- Time-sliced relationship queries (currently-valid edges) stay cheap.
CREATE INDEX IF NOT EXISTS ix_edge_validity ON edge (valid_from, valid_to);
