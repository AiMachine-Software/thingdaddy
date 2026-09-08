-- ============================================================================
-- Migration 001 — party.duns (cross-reference identifier)
-- Target DB: thingdaddy_population
--
-- Adds a nullable DUNS column to `party`. DUNS (Dun & Bradstreet) is a
-- cross-reference identifier we preserve at ingest and use LATER to verify a
-- candidate (D&B matching), the same way `lei` feeds the GLEIF LEI-to-prefix
-- bridge. It is NOT a GS1 prefix and NEVER promotes a row on its own — the gate
-- (party_gate_prefix_required) still has the final word.
--
-- Isolation: owned by population/. Does not touch platform/. Additive only.
-- Idempotent: safe to re-apply (ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS).
--
-- Apply:  psql -v ON_ERROR_STOP=1 -d thingdaddy_population -f db/migrations/001_party_add_duns.sql
-- ============================================================================

ALTER TABLE party
  ADD COLUMN IF NOT EXISTS duns text;   -- Dun & Bradstreet number, if known. NULL until known.

COMMENT ON COLUMN party.duns IS
  'D&B DUNS cross-reference identifier (verification seed). Not a GS1 prefix.';

-- Non-unique: a DUNS may repeat across candidate rows before de-duplication, and
-- it is only a matching seed. Indexed so D&B-match lookups by DUNS stay cheap.
CREATE INDEX IF NOT EXISTS ix_party_duns ON party (duns) WHERE duns IS NOT NULL;
