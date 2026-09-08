-- ============================================================================
-- Migration 011 — backfill legacy rows into the graph spine (Cycle 3 · Core).
--
-- NON-DESTRUCTIVE: reads party/asset/edge/party_event, writes node/association/
-- node_event. Legacy tables are UNTOUCHED (kept until a later cutover PR).
-- IDEMPOTENT: re-run safe via `legacy`-ref NOT EXISTS guards.
--
-- Every spine row carries a `legacy` jsonb — the Legacy-ID provenance back to its
-- source row, and the idempotency key.
--
-- DEFERRED (open decisions — counted, NOT migrated here):
--   * carrier — node vs association attribute (open item 4). Left in place.
--   * unresolved edges (object_party_id IS NULL) — need the stub-node call.
--     Resolved edges (object_party_id set) migrate clean.
--   * party key_type — all mapped 'pgln' (registrant/org); location-only 'gln'
--     refinement deferred.
--
-- Apply to SCRATCH first:
--   psql -v ON_ERROR_STOP=1 -d thingdaddy_population_test -f db/migrations/011_backfill_spine.sql
-- ============================================================================

ALTER TABLE node        ADD COLUMN IF NOT EXISTS legacy jsonb;
ALTER TABLE association ADD COLUMN IF NOT EXISTS legacy jsonb;
ALTER TABLE node_event  ADD COLUMN IF NOT EXISTS legacy jsonb;
CREATE INDEX IF NOT EXISTS ix_node_legacy        ON node        USING gin (legacy);
CREATE INDEX IF NOT EXISTS ix_association_legacy ON association USING gin (legacy);
CREATE INDEX IF NOT EXISTS ix_node_event_legacy  ON node_event  USING gin (legacy);

-- 1) party -> node (organizations, PGLN). party has no URN -> NULL; prefix gate carried.
INSERT INTO node (urn, key_type, prefix, legal_name, gln, lei, mo, state, source, exception_reason, first_seen, last_updated, legacy)
SELECT NULL, 'pgln', p.prefix, p.legal_name, p.gln, p.lei, p.mo, p.state, p.source, p.exception_reason, p.first_seen, p.last_updated,
       jsonb_build_object('party_id', p.id::text)
FROM party p
WHERE NOT EXISTS (SELECT 1 FROM node n WHERE n.legacy->>'party_id' = p.id::text);

-- 2) asset -> node (GIAI, with engine URN).
INSERT INTO node (urn, key_type, prefix, label, state, source, first_seen, last_updated, legacy)
SELECT a.urn, 'giai', a.prefix, a.label, a.state, a.source, a.first_seen, a.last_updated,
       jsonb_build_object('asset_id', a.id::text)
FROM asset a
WHERE NOT EXISTS (SELECT 1 FROM node n WHERE n.legacy->>'asset_id' = a.id::text);

-- 2b) asset -> association (asset_node -owned_by-> party_node).
INSERT INTO association (subject_node_id, object_node_id, rel, state, source, first_seen, legacy)
SELECT an.id, pn.id, 'owned_by', a.state, a.source, a.first_seen, jsonb_build_object('asset_id', a.id::text)
FROM asset a
JOIN node an ON an.legacy->>'asset_id' = a.id::text
JOIN node pn ON pn.legacy->>'party_id' = a.party_id::text
WHERE NOT EXISTS (SELECT 1 FROM association s WHERE s.legacy->>'asset_id' = a.id::text AND s.rel = 'owned_by')
ON CONFLICT (subject_node_id, object_node_id, rel, source) DO NOTHING;

-- 3) resolved edges -> association (subject_party_node -rel-> object_party_node).
--    object_label + doc preserved in attributes. Unresolved (object_party_id NULL) deferred.
INSERT INTO association (subject_node_id, object_node_id, rel, attributes, state, inferred, source, first_seen, legacy)
SELECT sn.id, onode.id, e.rel,
       jsonb_strip_nulls(jsonb_build_object('object_label', e.object_label, 'doc', e.doc)),
       e.state, e.inferred, e.source, e.first_seen, jsonb_build_object('edge_id', e.id::text)
FROM edge e
JOIN node sn    ON sn.legacy->>'party_id'    = e.subject_party_id::text
JOIN node onode ON onode.legacy->>'party_id' = e.object_party_id::text
WHERE e.object_party_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM association s WHERE s.legacy->>'edge_id' = e.id::text)
ON CONFLICT (subject_node_id, object_node_id, rel, source) DO NOTHING;

-- 4) party_event -> node_event (threaded to the party's node; node_id XOR association_id holds).
INSERT INTO node_event (node_id, event_type, from_state, to_state, detail, source, actor, at, legacy)
SELECT pn.id, pe.event_type, pe.from_state, pe.to_state, pe.detail, pe.source, pe.actor, pe.at,
       jsonb_build_object('party_event_id', pe.id::text)
FROM party_event pe
JOIN node pn ON pn.legacy->>'party_id' = pe.party_id::text
WHERE NOT EXISTS (SELECT 1 FROM node_event ne WHERE ne.legacy->>'party_event_id' = pe.id::text);
