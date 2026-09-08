-- ============================================================================
-- Migration 003 — enforce the party_event type vocabulary
-- Target DB: thingdaddy_population
--
-- Turns the event_type "vocabulary" from a source comment into an enforced RULE
-- (integrity by construction, not by diligence). Adds a CHECK constraint that
-- restricts party_event.event_type to the closed set the API actually emits:
--
--   candidate_staged | updated        (POST /ingest)
--   verified                          (POST /gate)
--   exception                         (POST /ingest, POST /claim held path)
--   prefix_claimed | origin_linked    (POST /claim promote path)
--   claim_held                        (POST /claim authority-unconfirmed path)
--
-- Additive + closed-vocabulary only: it ADDS a constraint, mutates no data, and
-- every existing row already satisfies it (real data holds only candidate_staged
-- / exception / verified). ADD CONSTRAINT validates the table on apply, so a
-- dirty row would abort the migration rather than half-apply.
--
-- Isolation: owned by population/. Does not touch platform/. Additive only.
-- Idempotent: the named CHECK is guarded by a pg_constraint existence test, so
-- re-applying is a genuine no-op (same pattern as migration 002).
--
-- Apply:  psql -v ON_ERROR_STOP=1 -d thingdaddy_population -f db/migrations/003_party_event_type_check.sql
-- ============================================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'party_event_type_check' AND conrelid = 'party_event'::regclass
  ) THEN
    ALTER TABLE party_event
      ADD CONSTRAINT party_event_type_check
      CHECK (event_type IN (
        'candidate_staged',
        'updated',
        'verified',
        'exception',
        'prefix_claimed',
        'origin_linked',
        'claim_held'
      ));
  END IF;
END $$;
