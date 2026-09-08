// ============================================================================
// asset_carrier_read.mjs — Cycle 2 · UI-support reads:
//   GET /party/:id/assets      — a party's minted GIAI assets
//   GET /asset/:id/carriers    — an asset's carrier profiles
//
// Read-only surfaces the UI drawer needs. Proves:
//   * a party with no assets returns [] (honest empty, not faked).
//   * assets come back with the engine-built URN + candidate state.
//   * carriers come back with value NULL for a declared-but-unencoded profile
//     (the encoding is Pom's engine seam) — the read never invents a value.
//   * missing party / missing asset → 404.
//
// Run against scratch (migrations 005+007 applied):
//   PGDATABASE=thingdaddy_population_test node api/test/asset_carrier_read.mjs
// ============================================================================
import { pool } from '../db.js';
import { app } from '../server.js';

let failures = 0;
function ok(label, cond) { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) failures++; }

const server = app.listen(0);
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;
const get = (p) => fetch(`${base}${p}`);

const cleanup = [];
const client = await pool.connect();
try {
  const PREFIX = '0817092';
  const URN = `urn:epc:id:giai:${PREFIX}.4471`;
  await client.query(`DELETE FROM party WHERE prefix = $1`, [PREFIX]);            // defensive
  const vp = await client.query(
    `INSERT INTO party (legal_name, prefix, mo, state, source)
     VALUES ('Read Root Co', $1, 'GS1 US', 'verified', 'test') RETURNING id`, [PREFIX]);
  const VID = vp.rows[0].id; cleanup.push(VID);

  console.log('[reads] party with no assets → honest empty');
  let r = await get(`/party/${VID}/assets`);
  let b = await r.json();
  ok('GET assets → 200', r.status === 200);
  ok('no assets → assets: [] (not faked)', Array.isArray(b.assets) && b.assets.length === 0);

  // mint an asset + two carrier profiles directly (read test, not the write path)
  const ap = await client.query(
    `INSERT INTO asset (party_id, prefix, giai_component, urn, label, state, source)
     VALUES ($1,$2,'4471',$3,'DZ-Lite c270','candidate','test') RETURNING id`, [VID, PREFIX, URN]);
  const AID = ap.rows[0].id;
  await client.query(
    `INSERT INTO carrier (asset_id, carrier_type, value, state, source) VALUES
       ($1,'DL',null,'candidate','test'),
       ($1,'GS1-128',null,'candidate','test')`, [AID]);

  console.log('[reads] assets list');
  r = await get(`/party/${VID}/assets`);
  b = await r.json();
  ok('one asset returned', b.assets?.length === 1);
  ok('URN is the engine-built value', b.assets?.[0]?.urn === URN);
  ok("asset state candidate", b.assets?.[0]?.state === 'candidate');
  ok('label surfaced', b.assets?.[0]?.label === 'DZ-Lite c270');

  console.log('[reads] carriers list');
  r = await get(`/asset/${AID}/carriers`);
  b = await r.json();
  ok('two carrier profiles returned', b.carriers?.length === 2);
  ok('carrier value is NULL (encoding pending the engine)', b.carriers?.every((c) => c.value === null));
  ok('carrier types present', b.carriers?.map((c) => c.carrier_type).sort().join(',') === 'DL,GS1-128');

  console.log('[reads] missing party / asset → 404');
  r = await get(`/party/99999999/assets`);
  ok('missing party → 404', r.status === 404);
  r = await get(`/asset/99999999/carriers`);
  ok('missing asset → 404', r.status === 404);
} finally {
  for (const id of cleanup) await client.query(`DELETE FROM party WHERE id = $1`, [id]); // cascades assets → carriers
  client.release();
  await pool.end();
  server.close();
}
console.log(failures ? `\n${failures} FAILED` : '\nasset_carrier_read: ALL PASS');
process.exit(failures ? 1 : 0);
