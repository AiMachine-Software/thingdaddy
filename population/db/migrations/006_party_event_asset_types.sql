-- ============================================================================
-- Migration 006 — extend the party_event vocabulary for the asset tier.
-- Target DB: thingdaddy_population.  Cycle 2 · Core.
--
-- Migration 003 froze party_event.event_type to a closed set. The asset tier
-- (POST /party/:id/asset) emits a new provenance event, 'asset_minted', which
-- that CHECK would reject (23514). This migration re-states the constraint with
-- the asset event type added — keeping the "closed vocabulary, enforced" rule,
-- just widened by one member.
--
-- Additive to the vocabulary, mutates no data. Every existing row holds an
-- old-vocab type, all of which remain valid, so the re-ADD validates clean.
-- Idempotent: DROP IF EXISTS + ADD converges to the same final constraint on
-- re-apply (same net effect as migration 003's guarded add).
--
-- Apply: psql -v ON_ERROR_STOP=1 -d thingdaddy_population -f db/migrations/006_party_event_asset_types.sql
-- ============================================================================
DO $$
BEGIN
  ALTER TABLE party_event DROP CONSTRAINT IF EXISTS party_event_type_check;
  ALTER TABLE party_event
    ADD CONSTRAINT party_event_type_check
    CHECK (event_type IN (
      'candidate_staged',
      'updated',
      'verified',
      'exception',
      'prefix_claimed',
      'origin_linked',
      'claim_held',
      'asset_minted'          -- Cycle 2: asset (GIAI) mint provenance.
    ));
END $$;
