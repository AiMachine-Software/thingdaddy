-- ============================================================================
-- Step 4 scale load: ~4,000,000 SYNTHETIC candidate rows.
--   source = 'synthetic'   (never confusable with real data)
--   state  = 'candidate'   (ingest law)
--   prefix = NULL          (law 3: no fabricated prefixes -> can never verify)
-- ============================================================================
\timing on
\echo '=== dropping GIN indexes for fast bulk load ==='
DROP INDEX IF EXISTS ix_party_legal_name_trgm;
DROP INDEX IF EXISTS ix_party_search_tsv;

SET maintenance_work_mem = '1GB';
SET synchronous_commit = off;   -- session-local; faster load, DB stays crash-safe on restart

\echo '=== loading 4,000,000 synthetic rows in 8 batches of 500k ==='
DO $$
DECLARE
  batch     int := 500000;
  batches   int := 8;
  b         int;
  nouns  text[] := ARRAY['Robotics','Semiconductor','Systems','Logistics','Dynamics','Instruments','Automation','Materials','Networks','Sensors','Photonics','Devices'];
  adjs   text[] := ARRAY['Acme','Globex','Initech','Umbrella','Soylent','Vertex','Nakatomi','Stark','Wayne','Tyrell','Cyberdyne','Massive','Pied','Hooli','Aperture','Wonka'];
  sufs   text[] := ARRAY['LLC','Inc','GmbH','Corp','Ltd','N.V.','S.A.','K.K.'];
  mos    text[] := ARRAY['GS1 US','GS1 Korea','GS1 Germany','GS1 Netherlands','GS1 Japan','GS1 UK'];
  ctys   text[] := ARRAY['US','KR','DE','NL','JP','GB'];
  citys  text[] := ARRAY['Chicago','Suwon','Munich','Veldhoven','Tokyo','London','Boise','Austin'];
BEGIN
  FOR b IN 0 .. batches - 1 LOOP
    INSERT INTO party (legal_name, city, country, mo, state, source)
    SELECT
      adjs[1 + (n % array_length(adjs,1))] || ' ' ||
      nouns[1 + ((n / 7) % array_length(nouns,1))] || ' ' ||
      sufs[1 + ((n / 13) % array_length(sufs,1))] || ' #' || n::text,
      citys[1 + (n % array_length(citys,1))],
      ctys[1 + (n % array_length(ctys,1))],
      mos[1 + (n % array_length(mos,1))],
      'candidate',
      'synthetic'
    FROM generate_series(b*batch + 1, (b+1)*batch) AS g(n);
    RAISE NOTICE 'batch % / % done (% rows loaded)', b+1, batches, (b+1)*batch;
  END LOOP;
END $$;

\echo '=== rebuilding GIN indexes (bulk build) ==='
CREATE INDEX ix_party_legal_name_trgm ON party USING gin (legal_name gin_trgm_ops);
CREATE INDEX ix_party_search_tsv      ON party USING gin (search_tsv);

\echo '=== ANALYZE (planner stats for sub-second search) ==='
ANALYZE party;

\echo '=== load complete ==='
SELECT count(*) AS total_rows FROM party;
