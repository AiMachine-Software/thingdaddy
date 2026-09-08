-- Step 4: timed name searches against the full 4M. Each mirrors the /search
-- shape (filter -> ORDER BY id -> LIMIT 20). \timing reports wall time; the
-- EXPLAIN blocks show the chosen index + execution time.
\timing on

\echo '################ candidate counts for the test terms ################'
SELECT 'ILIKE %Photonics%'  AS term, count(*) FROM party WHERE legal_name ILIKE '%Photonics%';
SELECT 'ILIKE %Cyberdyne%'  AS term, count(*) FROM party WHERE legal_name ILIKE '%Cyberdyne%';

\echo '################ A) similarity operator %  (what /search uses today) ################'
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT id, legal_name FROM party WHERE legal_name % 'Photonics' ORDER BY id LIMIT 20;

\echo '################ B) trigram-accelerated ILIKE substring (indexed by gin_trgm_ops) ################'
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT id, legal_name FROM party WHERE legal_name ILIKE '%Photonics%' ORDER BY id LIMIT 20;

\echo '################ C) full-text tsvector (uses ix_party_search_tsv) ################'
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT id, legal_name FROM party WHERE search_tsv @@ plainto_tsquery('simple','Photonics') ORDER BY id LIMIT 20;

\echo '################ D) selective term ILIKE (Cyberdyne) ################'
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT id, legal_name FROM party WHERE legal_name ILIKE '%Cyberdyne%' ORDER BY id LIMIT 20;

\echo '################ E) real verified record by name (Samsung) ################'
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT id, legal_name, prefix, state FROM party WHERE legal_name ILIKE '%Samsung%' ORDER BY id LIMIT 20;
