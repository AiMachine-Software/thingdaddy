-- ============================================================================
-- test_gate.sql — proves the inviolable gate AND the migration-002 seam guards.
--
-- The original gate (schema.sql):
--   (a) candidate + NULL prefix  → SUCCEEDS
--   (b) verified  + prefix       → SUCCEEDS
--   (c) verified  + NULL prefix  → FAILS (party_gate_prefix_required)
--
-- The claim/re-root guards (migration 002 — REQUIRES 002 applied):
--   1. prefix digits-only:  (d) '0DEMO...' REJECTED   (e) real digit prefix ACCEPTED
--   2. demo coherence:      (f) is_demo can't verify   (g) after is_demo→false CAN verify
--   3. party_origin:        (h) insert ACCEPTED  (i) UPDATE REJECTED  (j) DELETE REJECTED
--
-- Everything runs inside a transaction and is ROLLED BACK — no test rows persist.
-- Prefixes '999xxxx' below are throwaway TEST values (rolled back), not claims.
-- Run:  psql -d thingdaddy_population -f test_gate.sql
-- ============================================================================
\set ON_ERROR_STOP off

BEGIN;

-- ── (a) candidate with NULL prefix — the gate does not apply; must succeed. ──
INSERT INTO party (legal_name, state, source, prefix)
VALUES ('Test Candidate LLC', 'candidate', 'synthetic', NULL);
\echo '(a) candidate + NULL prefix .......... INSERT OK   => PASS (expected)'

-- ── (b) verified WITH a prefix — the gate is satisfied; must succeed. ──
INSERT INTO party (legal_name, state, source, prefix)
VALUES ('Test Verified Inc', 'verified', 'synthetic', '9990001');
\echo '(b) verified  + prefix ............... INSERT OK   => PASS (expected)'

-- ── (c) verified with NULL prefix — the gate must REJECT this. ──
DO $$
BEGIN
  INSERT INTO party (legal_name, state, source, prefix)
  VALUES ('Test BadVerified Inc', 'verified', 'synthetic', NULL);
  RAISE EXCEPTION '(c) verified + NULL prefix was ACCEPTED  => GATE BROKEN';
EXCEPTION
  WHEN check_violation THEN
    RAISE NOTICE '(c) verified  + NULL prefix .......... REJECTED by % => PASS (gate holds)',
                 (regexp_match(SQLERRM, 'party_gate_prefix_required'))[1];
END $$;

-- ════════════════════════════════════════════════════════════════════════════
-- MIGRATION 002 — claim / re-root seam guards
-- ════════════════════════════════════════════════════════════════════════════

-- ── GUARD 1: prefix is digits-only (structural DEMO exclusion) ──────────────
-- (d) a '0DEMO...' prefix must be REJECTED by party_prefix_digits_only.
DO $$
DECLARE v_con text;
BEGIN
  INSERT INTO party (legal_name, state, source, prefix)
  VALUES ('Test Demo Candidate', 'candidate', 'synthetic', '0DEMO001');
  RAISE EXCEPTION '(d) 0DEMO prefix was ACCEPTED  => DEMO EXCLUSION BROKEN';
EXCEPTION
  WHEN check_violation THEN
    GET STACKED DIAGNOSTICS v_con = CONSTRAINT_NAME;
    RAISE NOTICE '(d) 0DEMO... prefix .................. REJECTED by % => PASS', v_con;
END $$;

-- (e) a real all-digit prefix must be ACCEPTED (the positive direction).
DO $$
BEGIN
  INSERT INTO party (legal_name, state, source, prefix)
  VALUES ('Test Real Digit Prefix', 'candidate', 'synthetic', '9990010');
  RAISE NOTICE '(e) real digit prefix ''9990010'' ..... INSERT OK   => PASS';
EXCEPTION
  WHEN others THEN
    RAISE NOTICE '(e) real digit prefix was REJECTED by % => FAIL', SQLERRM;
END $$;

-- ── GUARD 2: an is_demo row can never be verified (party_demo_not_verified) ──
-- (f) is_demo=true promoted to verified (WITH a real prefix, so the gate is
--     satisfied and ONLY the demo guard can fire) must be REJECTED.
DO $$
DECLARE v_id bigint; v_con text;
BEGIN
  INSERT INTO party (legal_name, state, source, prefix, is_demo)
  VALUES ('Test Demo Row', 'candidate', 'synthetic', '9990011', true)
  RETURNING id INTO v_id;
  UPDATE party SET state = 'verified' WHERE id = v_id;
  RAISE EXCEPTION '(f) is_demo row verified  => DEMO COHERENCE BROKEN';
EXCEPTION
  WHEN check_violation THEN
    GET STACKED DIAGNOSTICS v_con = CONSTRAINT_NAME;
    RAISE NOTICE '(f) is_demo=true → verified .......... REJECTED by % => PASS', v_con;
END $$;

-- (g) after is_demo→false the SAME kind of row CAN verify (positive direction).
DO $$
DECLARE v_id bigint;
BEGIN
  INSERT INTO party (legal_name, state, source, prefix, is_demo)
  VALUES ('Test Demo Then Claimed', 'candidate', 'synthetic', NULL, true)
  RETURNING id INTO v_id;
  -- the claim tx: flip demo off, root on a real prefix, promote — atomically.
  UPDATE party SET is_demo = false, prefix = '9990012', state = 'verified' WHERE id = v_id;
  RAISE NOTICE '(g) is_demo→false then verify ........ UPDATE OK   => PASS';
EXCEPTION
  WHEN others THEN
    RAISE NOTICE '(g) is_demo→false verify was REJECTED by % => FAIL', SQLERRM;
END $$;

-- ── GUARD 3: party_origin is append-only (write-once) ───────────────────────
-- (h) a fresh party_origin row CAN be inserted; (i) UPDATE and (j) DELETE
--     must both be REJECTED by trg_party_origin_immutable.
DO $$
DECLARE v_party bigint; v_origin bigint;
BEGIN
  -- a verified party to hang the origin off of.
  INSERT INTO party (legal_name, state, source, prefix)
  VALUES ('Test Butterfly', 'verified', 'synthetic', '9990013')
  RETURNING id INTO v_party;

  -- (h) insert the origin snapshot — must succeed.
  BEGIN
    INSERT INTO party_origin (party_id, origin_urn, origin_prefix, claimed_prefix, authority, actor)
    VALUES (v_party, 'urn:epc:id:sgln:0DEMO013.0.0', '0DEMO013', '9990013',
            '{"gepir":"confirmed","doc":"test"}'::jsonb, 'test-actor')
    RETURNING id INTO v_origin;
    RAISE NOTICE '(h) party_origin INSERT .............. INSERT OK   => PASS';
  EXCEPTION WHEN others THEN
    RAISE NOTICE '(h) party_origin INSERT was REJECTED by % => FAIL', SQLERRM;
  END;

  -- (i) UPDATE must be rejected (append-only trigger, ERRCODE raise_exception).
  BEGIN
    UPDATE party_origin SET actor = 'tamper' WHERE id = v_origin;
    RAISE NOTICE '(i) party_origin UPDATE was ACCEPTED  => APPEND-ONLY BROKEN => FAIL';
  EXCEPTION
    WHEN raise_exception THEN
      RAISE NOTICE '(i) party_origin UPDATE .............. REJECTED (append-only) => PASS';
  END;

  -- (j) DELETE must be rejected too.
  BEGIN
    DELETE FROM party_origin WHERE id = v_origin;
    RAISE NOTICE '(j) party_origin DELETE was ACCEPTED  => APPEND-ONLY BROKEN => FAIL';
  EXCEPTION
    WHEN raise_exception THEN
      RAISE NOTICE '(j) party_origin DELETE .............. REJECTED (append-only) => PASS';
  END;
END $$;

ROLLBACK;

\echo '--- gate + migration-002 tests complete (all changes rolled back) ---'
