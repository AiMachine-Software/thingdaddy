// ============================================================================
// node_resolve.mjs — Cycle 3 UI-support: GET /node/by-legacy/party/:partyId.
// The party_id → spine node resolver the workspace needs. Proves: 404 before
// backfill (honest "not on the spine yet"), 200 after (correct node), 404 for a
// nonexistent party. Self-cleaning.
//   PGDATABASE=thingdaddy_population_test node api/test/node_resolve.mjs
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
const P = '0700020';
const clean = async () => {
  await client.query(`DELETE FROM node WHERE source='fixture'`);
  await client.query(`DELETE FROM party WHERE prefix=$1`, [P]);
};
try {
  await clean();
  const party = (await client.query(`INSERT INTO party (legal_name,prefix,mo,state,source) VALUES ('Resolve Co',$1,'GS1 US','verified','fixture') RETURNING id`, [P])).rows[0].id;

  console.log('[resolve] before backfill → honest 404');
  let r = await get(`/node/by-legacy/party/${party}`);
  ok('un-backfilled party → 404 (not on the spine yet)', r.status === 404);

  console.log('[resolve] after backfill → the party node');
  await client.query(BACKFILL_SQL);
  r = await get(`/node/by-legacy/party/${party}`); const b = await r.json();
  ok('backfilled party → 200', r.status === 200);
  ok('resolves the correct node (legal_name)', b.node?.legal_name === 'Resolve Co');
  ok("key_type='pgln'", b.node?.key_type === 'pgln');
  ok('carries the legacy ref back to the party', String(b.node?.legacy?.party_id) === String(party)); // semantic id equality (jsonb number vs bigint-as-string in JS)

  console.log('[resolve] nonexistent party → 404');
  r = await get(`/node/by-legacy/party/99999999`);
  ok('nonexistent party → 404', r.status === 404);
} finally {
  await clean(); client.release(); await pool.end(); server.close();
}
console.log(failures ? `\n${failures} FAILED` : '\nnode_resolve: ALL PASS');
process.exit(failures ? 1 : 0);
