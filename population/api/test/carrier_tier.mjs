// ============================================================================
// carrier_tier.mjs — Cycle 2 · Core: POST /asset/:id/carrier (declare a carrier).
//
// A carrier is a GATED PROFILE, not a fabricated encoding. This proves:
//   * token-gated (401 without).
//   * closed carrier vocabulary — an unknown carrier_type → 422.
//   * asset must exist — carrier on a nonexistent asset → 404.
//   * a valid declaration goes THROUGH THE ENGINE gate (mint_cli re-affirms the
//     URN is admissible on the carrier) and lands a `candidate` profile with
//     value NULL — the encoding is the seam Pom's engine fills; we never
//     hand-build one. A 'carrier_declared' provenance event is written.
//   * one profile per carrier per asset — a duplicate (asset, type) → 409.
//   * both a numeric-safe carrier (RAIN-96) and a text carrier (DL) admit — the
//     gate routes through the one door for each.
//
// NOTE: the endpoint's `carrier_refused` (422) branch is DEFENSIVE — the asset
// component is numeric by DB CHECK (asset_component_numeric), so the RAIN-96
// numeric gate can't be tripped from a stored asset today. That refusal path
// exists for Pom's richer per-carrier rules. Engine-level carrier refusal is
// covered by the engine's own tests (alpha + RAIN-96 → CarrierError).
//
// Run against scratch (migrations 005+007+008 applied), engine shim reachable:
//   PGDATABASE=thingdaddy_population_test node api/test/carrier_tier.mjs
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
  const PREFIX = '0817090';
  const URN = `urn:epc:id:giai:${PREFIX}.4471`;
  await client.query(`DELETE FROM party WHERE prefix = $1`, [PREFIX]);            // defensive (cascades assets)
  const vp = await client.query(
    `INSERT INTO party (legal_name, prefix, mo, state, source)
     VALUES ('Carrier Root Co', $1, 'GS1 US', 'verified', 'test') RETURNING id`, [PREFIX]);
  const VID = vp.rows[0].id; cleanup.push(VID);
  // an asset to hang carriers off (component numeric per R9 — the DB CHECK).
  const ap = await client.query(
    `INSERT INTO asset (party_id, prefix, giai_component, urn, state, source)
     VALUES ($1,$2,'4471',$3,'candidate','test') RETURNING id`, [VID, PREFIX, URN]);
  const AID = ap.rows[0].id;

  console.log('[carrier] auth + validation');
  let r = await post(`/asset/${AID}/carrier`, { carrier_type: 'DL' }, { 'content-type': 'application/json' });
  ok('no token → 401', r.status === 401);
  r = await post(`/asset/${AID}/carrier`, { carrier_type: 'QR-CODE' });
  ok('unknown carrier_type → 422 invalid_carrier_type', r.status === 422 && (await r.json()).error === 'invalid_carrier_type');
  r = await post(`/asset/99999999/carrier`, { carrier_type: 'DL' });
  ok('nonexistent asset → 404', r.status === 404);

  console.log('[carrier] engine-gated profile → candidate + provenance');
  r = await post(`/asset/${AID}/carrier`, { carrier_type: 'DL', source: 'test' });
  let b = await r.json();
  ok('declare DL → 201', r.status === 201);
  ok("carrier.state = 'candidate' (nothing mints verified)", b.carrier?.state === 'candidate');
  ok('carrier.value is NULL (encoding is Pom\'s seam, never hand-built)', b.carrier?.value === null);
  ok("carrier.carrier_type = 'DL'", b.carrier?.carrier_type === 'DL');
  const ev = await client.query(
    `SELECT detail FROM party_event WHERE party_id=$1 AND event_type='carrier_declared'`, [VID]);
  ok("'carrier_declared' provenance event written", ev.rows.length >= 1);
  ok('provenance carries the asset URN', ev.rows[0]?.detail?.urn === URN);

  console.log('[carrier] RAIN-96 gate admits a numeric asset');
  r = await post(`/asset/${AID}/carrier`, { carrier_type: 'RAIN-96', source: 'test' });
  ok('declare RAIN-96 on numeric component → 201 (engine gate passed)', r.status === 201);

  console.log('[carrier] one profile per carrier, once');
  r = await post(`/asset/${AID}/carrier`, { carrier_type: 'DL', source: 'test' });
  ok('duplicate (asset, DL) → 409', r.status === 409);
} finally {
  for (const id of cleanup) await client.query(`DELETE FROM party WHERE id = $1`, [id]); // cascades assets → carriers + events
  client.release();
  await pool.end();
  server.close();
}
console.log(failures ? `\n${failures} FAILED` : '\ncarrier_tier: ALL PASS');
process.exit(failures ? 1 : 0);
