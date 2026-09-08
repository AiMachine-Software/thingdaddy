-- Step 4: prove the gate STILL holds at 4M scale (raw SQL path).
-- Rolled back so no test row persists.
\set ON_ERROR_STOP off
BEGIN;
DO $$
BEGIN
  INSERT INTO party (legal_name, state, source, prefix)
  VALUES ('Scale BadVerified Inc', 'verified', 'synthetic', NULL);
  RAISE EXCEPTION 'GATE BROKEN: verified + NULL prefix was ACCEPTED at 4M scale';
EXCEPTION
  WHEN check_violation THEN
    RAISE NOTICE 'gate holds at 4M: verified + NULL prefix REJECTED by %',
                 (regexp_match(SQLERRM, 'party_gate_prefix_required'))[1];
END $$;
ROLLBACK;
