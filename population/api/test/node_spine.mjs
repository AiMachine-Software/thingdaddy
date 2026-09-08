// ============================================================================
// node_spine.mjs — Cycle 3 · Core: backfill (migration 011) correctness.
//
// Closes the coverage gap: scratch has no assets/edges, so the asset→giai,
// asset→owned_by, and resolved-edge→association branches of the backfill never
// ran against real rows. This test SEEDS a fixture (owner party + object party +
// asset + resolved edge), RUNS the actual 011 migration SQL (idempotent — it
// picks up the fixture), and asserts every branch projected correctly. Then it
// cleans up (spine rows have no FK to legacy, so we delete by source='fixture').
//
// Run against scratch (010 + 011 applied):
//   PGDATABASE=thingdaddy_population_test node api/test/node_spine.mjs
// ============================================================================
import { pool } from '../db.js';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BACKFILL_SQL = readFileSync(path.resolve(__dirname, '../../db/migrations/011_backfill_spine.sql'), 'utf8');

let failures = 0;
function ok(label, cond) { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) failures++; }

const client = await pool.connect();
const A = '0700000', B = '0700001';
const clean = async () => {
  await client.query(`DELETE FROM node_event  WHERE source='fixture'`);
  await client.query(`DELETE FROM association WHERE source='fixture'`);
  await client.query(`DELETE FROM node        WHERE source='fixture'`);
  await client.query(`DELETE FROM party WHERE prefix IN ($1,$2)`, [A, B]); // cascades asset + edge
};
try {
  await clean(); // defensive: clear any prior fixture

  // ---- seed: owner party + object party + asset(owned) + resolved edge ----
  const owner  = (await client.query(`INSERT INTO party (legal_name,prefix,mo,state,source) VALUES ('Fixture Owner',$1,'GS1 US','verified','fixture') RETURNING id`, [A])).rows[0].id;
  const object = (await client.query(`INSERT INTO party (legal_name,prefix,mo,state,source) VALUES ('Fixture Object',$1,'GS1 US','verified','fixture') RETURNING id`, [B])).rows[0].id;
  const URN = 'urn:epc:id:giai:0700000.5551';
  const asset = (await client.query(`INSERT INTO asset (party_id,prefix,giai_component,urn,label,state,source) VALUES ($1,$2,'5551',$3,'Fixture Unit','candidate','fixture') RETURNING id`, [owner, A, URN])).rows[0].id;
  const edge  = (await client.query(`INSERT INTO edge (subject_party_id,rel,object_label,object_party_id,state,source) VALUES ($1,'supplies','Fixture Object',$2,'candidate','fixture') RETURNING id`, [owner, object])).rows[0].id;

  // ---- run the REAL backfill migration (idempotent; picks up the fixture) ----
  await client.query(BACKFILL_SQL);

  // ---- branch 1: asset → giai node ----
  const giai = (await client.query(`SELECT urn,key_type FROM node WHERE legacy->>'asset_id' = $1`, [String(asset)])).rows;
  ok('asset → giai node created', giai.length === 1);
  ok('giai node carries the engine URN (not hand-built)', giai[0]?.urn === URN);
  ok("giai node key_type='giai'", giai[0]?.key_type === 'giai');

  // ---- branch 2: asset → owned_by association → owner party node ----
  const owned = (await client.query(
    `SELECT pn.legacy->>'party_id' AS owner_party FROM association s
       JOIN node pn ON pn.id = s.object_node_id
      WHERE s.legacy->>'asset_id' = $1 AND s.rel='owned_by'`, [String(asset)])).rows;
  ok('asset → owned_by association created', owned.length === 1);
  ok('owned_by object = the OWNER party node', owned[0]?.owner_party === String(owner));

  // ---- branch 3: resolved edge → association (subject/object/rel/attrs) ----
  const ea = (await client.query(
    `SELECT s.rel, sn.legacy->>'party_id' AS subj, on2.legacy->>'party_id' AS obj, s.attributes
       FROM association s JOIN node sn ON sn.id=s.subject_node_id JOIN node on2 ON on2.id=s.object_node_id
      WHERE s.legacy->>'edge_id' = $1`, [String(edge)])).rows;
  ok('resolved edge → association created', ea.length === 1);
  ok('edge assoc subject = subject party node', ea[0]?.subj === String(owner));
  ok('edge assoc object = object party node', ea[0]?.obj === String(object));
  ok("edge rel carried ('supplies')", ea[0]?.rel === 'supplies');
  ok('edge object_label preserved in attributes', ea[0]?.attributes?.object_label === 'Fixture Object');

  // ---- the gate holds across the whole spine ----
  const gate = (await client.query(`SELECT count(*)::int AS n FROM node WHERE state='verified' AND prefix IS NULL`)).rows[0].n;
  ok('gate holds: zero verified nodes without a prefix', gate === 0);

  // ---- global parity (party + party_event across all of scratch) ----
  const p = (await client.query(`
    SELECT (SELECT count(*) FROM party) AS party,
           (SELECT count(*) FROM node WHERE key_type='pgln') AS node_pgln,
           (SELECT count(*) FROM party_event) AS pe,
           (SELECT count(*) FROM node_event WHERE legacy ? 'party_event_id') AS ne`)).rows[0];
  ok('parity: every party → a pgln node', Number(p.party) === Number(p.node_pgln));
  ok('parity: every party_event → a node_event', Number(p.pe) === Number(p.ne));
} finally {
  await clean();
  client.release();
  await pool.end();
}
console.log(failures ? `\n${failures} FAILED` : '\nnode_spine: ALL PASS');
process.exit(failures ? 1 : 0);
