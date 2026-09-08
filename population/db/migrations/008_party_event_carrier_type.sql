-- ============================================================================
-- Migration 008 — extend party_event vocabulary for the carrier tier.
-- Target DB: thingdaddy_population.  Cycle 2 · Core.
--
-- The carrier tier (POST /asset/:id/carrier) emits a new provenance event,
-- 'carrier_declared'. Migration 003's closed CHECK (widened once by 006) would
-- reject it (23514). This re-states the constraint with the carrier event added
-- — same "closed vocabulary, enforced" rule, widened by one member.
--
-- Additive to the vocabulary, mutates no data. All existing rows hold prior-vocab
-- types, every one still valid, so the re-ADD validates clean. Idempotent.
--
-- Apply: psql -v ON_ERROR_STOP=1 -d thingdaddy_population -f db/migrations/008_party_event_carrier_type.sql
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
      'asset_minted',
      'carrier_declared'      -- Cycle 2: carrier profile declared on an asset.
    ));
END $$;
