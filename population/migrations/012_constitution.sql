-- 012_constitution.sql — five laws from the Foundation that production could not enforce.
-- Found 6 Sep 2026 by reading 001_scaffold.sql (22 Jul) against \d party / \d node / \d party_event.
--
-- MEASURED FIRST, 6 Sep 11:50 BKK:
--   party_event with no actor ........ 0    -> party_event_has_actor VALIDATES today
--   verified node with no urn ........ 20   -> node_verified_has_urn stays NOT VALID.
--                                             20 verified identities with nothing to resolve to.
--                                             Reported here. Fixed by resolving the rows, never
--                                             by forcing the constraint.
--
-- A constraint added NOT VALID and never validated conceals a population (audit A4, 976 rows).
-- So every NOT VALID here is either validated in this file or named as a finding with its count.

BEGIN;

-- Foundation 14.2 · INV-4: key type follows the ACCOUNTING ROLE, not the object.
-- Needs a column. Nullable; the fill is tomorrow (classify() from 002_admit.sql).
ALTER TABLE node ADD COLUMN IF NOT EXISTS accounting_role text;
COMMENT ON COLUMN node.accounting_role IS
  'INV-4: finished good (seller) | capital asset (owner) | component | raw material | returnable. Drives key_type.';

-- Foundation Part 7.4 step 9 · every transition records the AUTHORITY and the RULESET in force.
-- Today both live inside detail jsonb, sometimes. A column is a promise; a jsonb key is a habit.
ALTER TABLE party_event ADD COLUMN IF NOT EXISTS authority text;
ALTER TABLE party_event ADD COLUMN IF NOT EXISTS ruleset_version text;
COMMENT ON COLUMN party_event.authority IS
  'The authority cited for this transition: Verified by GS1 | GUDID | GLEIF | hand-read | ... Never GEPIR (retired 31 Dec 2023).';
COMMENT ON COLUMN party_event.ruleset_version IS
  'Foundation + standards versions in force at issuance, e.g. foundation=1.0;genspecs=25.0;tds=2.1;epcis=2.0';

-- Foundation Part 13 · only a NAMED actor may act. 003_promote.sql had _is_named_actor() in
-- the database; production had --i-am-kj in a script. This is the database half.
ALTER TABLE party_event ADD CONSTRAINT party_event_has_actor
  CHECK (actor IS NOT NULL AND btrim(actor) <> '') NOT VALID;
ALTER TABLE party_event VALIDATE CONSTRAINT party_event_has_actor;   -- 0 rows fail. Validated.

-- 001_scaffold thing_verified_has_urn · a VERIFIED identity carries its minted URN.
-- node_urn_has_provenance says IF urn THEN provenance. This says IF verified THEN urn.
-- NOT VALID: 20 rows fail today. Listed by the query below. Validate when it returns 0.
ALTER TABLE node ADD CONSTRAINT node_verified_has_urn
  CHECK (state <> 'verified' OR urn IS NOT NULL) NOT VALID;

COMMIT;

-- THE 20 — run this, resolve them, then: ALTER TABLE node VALIDATE CONSTRAINT node_verified_has_urn;
-- SELECT id, key_type, legal_name, prefix, source FROM node WHERE state='verified' AND urn IS NULL ORDER BY id;
