// ============================================================================
// asset_tier.mjs — Cycle 2 · Core: POST /party/:id/asset (mint a GIAI instance).
//
// Proves the seam is production-correct:
//   * token-gated (401 without).
//   * R9 at the door — component must be engine-mintable digits; alpha → 422.
//   * prefix-is-root — a party with no prefix cannot root an asset → 422.
//   * a valid mint goes THROUGH THE ENGINE: the URN is exactly what the engine
//     constructed (urn:epc:id:giai:<prefix>.<component>), never hand-built; the
//     asset lands `candidate` and writes an 'asset_minted' provenance event.
//   * one identity, once — a duplicate URN is rejected (409).
//
// MAP NOTE: mint routes through the reference-engine shim (mint_cli.py); Pom's
// authoritative engine replaces it behind the same contract — this test is the
// contract he builds to.
//
// Run against scratch (migration 005 applied), engine shim reachable:
//   PGDATABASE=thingdaddy_population_test node api/test/asset_tier.mjs
// ============================================================================
import { pool } from '../db.js';
import { app } from '../server.js';

let failures = 0;
function ok(label, cond) { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) failures++; }

const server = app.listen(0);
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;
const TOKEN = process.env.INGEST_TOKEN || 'test-write-secret';
process.env.INGEST_TOKEN = TOKEN;
const authH = { 'content-type': 'application/json', authorization: `Bearer ${TOKEN}` };
const post = (p, b, h = authH) => fetch(`${base}${p}`, { method: 'POST', headers: h, body: JSON.stringify(b) });

const cleanup = [];
const client = await pool.connect();
try {
  // verified, prefix-rooted party — can root an asset
  const VPREFIX = '0817089';
  await client.query(`DELETE FROM party WHERE prefix = $1`, [VPREFIX]);            // defensive
  const vp = await client.query(
    `INSERT INTO party (legal_name, prefix, gln, mo, state, source)
     VALUES ('Asset Root Co', $1, '0817089000001', 'GS1 US', 'verified', 'test') RETURNING id`, [VPREFIX]);
  const VID = vp.rows[0].id; cleanup.push(VID);
  // candidate party WITHOUT a prefix — cannot root an asset
  const cp = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('No Prefix Co','candidate','test') RETURNING id`);
  const CID = cp.rows[0].id; cleanup.push(CID);

  console.log('[asset] auth + validation');
  let r = await post(`/party/${VID}/asset`, { component: '4471' }, { 'content-type': 'application/json' });
  ok('no token → 401', r.status === 401);
  r = await post(`/party/${VID}/asset`, { component: 'INSTR-1' });
  ok('alpha component → 422 invalid_component', r.status === 422 && (await r.json()).error === 'invalid_component');
  r = await post(`/party/99999999/asset`, { component: '4471' });
  ok('nonexistent party → 404', r.status === 404);

  console.log('[asset] prefix-is-root');
  r = await post(`/party/${CID}/asset`, { component: '4471' });
  ok('no-prefix party → 422 no_root_prefix', r.status === 422 && (await r.json()).error === 'no_root_prefix');

  console.log('[asset] engine mint → candidate + provenance');
  r = await post(`/party/${VID}/asset`, { component: '4471', label: 'DZ-Lite c270', source: 'test' });
  const b = await r.json();
  ok('mint → 201', r.status === 201);
  ok("asset.state = 'candidate' (nothing mints verified)", b.asset?.state === 'candidate');
  ok('URN is engine-constructed, not hand-built', b.asset?.urn === `urn:epc:id:giai:${VPREFIX}.4471`);
  ok('component numeric (R9)', /^[0-9]+$/.test(b.asset?.giai_component || ''));
  const ev = await client.query(`SELECT 1 FROM party_event WHERE party_id=$1 AND event_type='asset_minted'`, [VID]);
  ok("'asset_minted' provenance event written", ev.rows.length >= 1);

  console.log('[asset] one identity, once');
  r = await post(`/party/${VID}/asset`, { component: '4471', source: 'test' });
  ok('duplicate URN → 409', r.status === 409);
} finally {
  for (const id of cleanup) await client.query(`DELETE FROM party WHERE id = $1`, [id]); // cascades assets + events
  client.release();
  await pool.end();
  server.close();
}
console.log(failures ? `\n${failures} FAILED` : '\nasset_tier: ALL PASS');
process.exit(failures ? 1 : 0);
