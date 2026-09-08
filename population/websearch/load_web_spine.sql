-- load_web_spine.sql — load web-discovered GTINs (spine_gtin_web.csv) into <db>.node
-- source=WEB. Same one-spine door as load_spine_v1.sql (the 4.5M GUDID export),
-- additive, collision-tolerant (dedup on urn), restartable. \copy is client-side,
-- so run from the folder holding spine_gtin_web.csv.
--   psql -v ON_ERROR_STOP=1 -d <db> -f load_web_spine.sql
\set ON_ERROR_STOP on

CREATE UNLOGGED TABLE IF NOT EXISTS _spine_load_web (
  urn text, key_type text, prefix text, gln text, mo text, state text, source text
);
TRUNCATE _spine_load_web;

\copy _spine_load_web (urn, key_type, prefix, gln, mo, state, source) FROM 'spine_gtin_web.csv' WITH (FORMAT csv)

\echo -- staged web rows:
SELECT count(*) staged,
       count(*) FILTER (WHERE prefix IS NOT NULL AND prefix <> '') with_prefix
FROM _spine_load_web;

-- Promote into the one spine. ux_node_urn dedupes against anything already present
-- (GUDID export, GDSN backfill, prior web runs). prefix stays NULL for every web
-- row (never derived); mo carried through as a lawful candidate fact.
INSERT INTO node (urn, key_type, prefix, gln, mo, state, source)
SELECT urn, lower(key_type),
       NULLIF(prefix,''), NULLIF(gln,''), NULLIF(mo,''),
       COALESCE(NULLIF(state,''),'candidate'),
       COALESCE(NULLIF(source,''),'WEB')
FROM _spine_load_web
ON CONFLICT (urn) WHERE urn IS NOT NULL DO NOTHING;

\echo -- node (source=WEB) after load:
SELECT count(*) total,
       count(*) FILTER (WHERE prefix IS NOT NULL) with_prefix,
       count(*) FILTER (WHERE prefix IS NULL)     pending
FROM node WHERE source = 'WEB';

DROP TABLE _spine_load_web;
