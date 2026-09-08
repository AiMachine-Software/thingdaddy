-- 013 · the harvest ancestor on the run party
--
-- promote_harvest_to_stage.py writes party.stage_ancestor = the harvest
-- company_key the prefix came from, so WHERE a prefix came from is recordable
-- by construction (audit A2 asked for HOW; company_prefix.root_method holds
-- that). Production's party.stage_ancestor is a bigint pointing at a run
-- company_prefix row; here the ancestor is the harvest's own key, which is
-- text. Same name, one hop earlier, same meaning: the row this row descends from.
--
-- Nullable: every party already in the run predates this column and has no
-- harvest ancestor to name. Nothing is backfilled and nothing is guessed.
--
-- Apply to thingdaddy_run:  psql thingdaddy_run -f population/migrations/013_run_party_stage_ancestor.sql

BEGIN;
ALTER TABLE party ADD COLUMN IF NOT EXISTS stage_ancestor text;
COMMENT ON COLUMN party.stage_ancestor IS
  'harvest_company.company_key this party''s prefix was promoted from (promote_harvest_to_stage.py). NULL = predates the promoter or not yet promoted.';
COMMIT;
