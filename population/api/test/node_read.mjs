// ============================================================================
// node_read.mjs — Cycle 3 · Core: GET /node/:id + GET /node/:id/associations.
// Seeds party+party2+edge (fixture), runs the real 011 backfill, reads the spine
// via the endpoints, asserts parity with the legacy source, self-cleans.
//   PGDATABASE=thingdaddy_population_test node api/test/node_read.mjs
// ============================================================================
import { pool } from '../db.js';
import { app } from '../server.js';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BACKFILL_SQL = readFileSync(path.resolve(__dirname, '../../db/migrations/011_backfill_spine.sql'), 'utf8');

let failures = 0; function ok(l, c) { console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}`); if (!c) failures++; }
const server = app.listen(0); await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;
const get = (p) => fetch(`${base}${p}`);
const client = await pool.connect();
const A = '0700010', B = '0700011';
const clean = async () => {
  await client.query(`DELETE FROM node_event WHERE source='fixture'`);
  await client.query(`DELETE FROM association WHERE source='fixture'`);
  await client.query(`DELETE FROM node WHERE source='fixture'`);
  await client.query(`DELETE FROM party WHERE prefix IN ($1,$2)`, [A, B]);
};
try {
  await clean();
  const owner  = (await client.query(`INSERT INTO party (legal_name,prefix,mo,state,source) VALUES ('Read Owner',$1,'GS1 US','verified','fixture') RETURNING id`, [A])).rows[0].id;
  const object = (await client.query(`INSERT INTO party (legal_name,prefix,state,source) VALUES ('Read Object',$1,'verified','fixture') RETURNING id`, [B])).rows[0].id;
  await client.query(`INSERT INTO edge (subject_party_id,rel,object_label,object_party_id,state,source) VALUES ($1,'supplies','Read Object',$2,'candidate','fixture')`, [owner, object]);
  await client.query(BACKFILL_SQL);
  const ownerNode = (await client.query(`SELECT id FROM node WHERE legacy->>'party_id'=$1`, [String(owner)])).rows[0].id;

  console.log('[node] GET /node/:id — parity with legacy party');
  let r = await get(`/node/${ownerNode}`); let b = await r.json();
  ok('GET node → 200', r.status === 200);
  ok('legal_name parity', b.node?.legal_name === 'Read Owner');
  ok('prefix parity', b.node?.prefix === A);
  ok("key_type='pgln'", b.node?.key_type === 'pgln');
  ok('state parity (verified)', b.node?.state === 'verified');
  r = await get(`/node/99999999`); ok('missing node → 404', r.status === 404);

  console.log('[node] GET /node/:id/associations — one-hop, bounded');
  r = await get(`/node/${ownerNode}/associations`); b = await r.json();
  ok('associations → 200', r.status === 200);
  const out = (b.associations || []).find((a) => a.rel === 'supplies' && a.direction === 'out');
  ok('outbound supplies association present', !!out);
  ok('neighbor object = object party (legal_name)', out?.object_legal_name === 'Read Object');
  ok('edge object_label preserved in attributes', out?.attributes?.object_label === 'Read Object');
  ok('default bound = 100', b.bounded_at === 100);
  r = await get(`/node/99999999/associations`); ok('associations missing node → 404', r.status === 404);
} finally {
  await clean(); client.release(); await pool.end(); server.close();
}
console.log(failures ? `\n${failures} FAILED` : '\nnode_read: ALL PASS');
process.exit(failures ? 1 : 0);
