// ============================================================================
// epcis_surface.mjs — Cycle 2 · Core: GET /party/:id/epcis (EPCIS projection).
//
// The endpoint is a READ PROJECTION of the provenance ledger into EPCIS 2.0
// ObjectEvent shape — NOT a stored/authored EPCIS document. This proves:
//   * a party's URN-bearing thing-events (asset_minted, carrier_declared) project
//     to ObjectEvents carrying the exact EPC (urn) and a bizStep.
//   * registry lifecycle events with no EPC (candidate_staged) are NOT projected
//     — EPCIS describes THINGS, not legal parties — and are counted, not dropped
//     silently.
//   * the response is explicitly flagged `projection: true` so no caller mistakes
//     it for a conformant stored EPCIS document.
//   * a nonexistent party → 404.
//
// Events are seeded directly into party_event so the projection is tested in
// isolation from the asset/carrier write paths.
//
// Run against scratch (base schema applied):
//   PGDATABASE=thingdaddy_population_test node api/test/epcis_surface.mjs
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
  const PREFIX = '0817091';
  const URN = `urn:epc:id:giai:${PREFIX}.4471`;
  await client.query(`DELETE FROM party WHERE prefix = $1`, [PREFIX]);            // defensive
  const p = await client.query(
    `INSERT INTO party (legal_name, prefix, mo, state, source)
     VALUES ('EPCIS Root Co', $1, 'GS1 US', 'verified', 'test') RETURNING id`, [PREFIX]);
  const PID = p.rows[0].id; cleanup.push(PID);

  // three ledger rows: one registry-only (no EPC), two URN-bearing thing-events.
  await client.query(
    `INSERT INTO party_event (party_id, event_type, to_state, detail, source, actor) VALUES
       ($1,'candidate_staged','candidate','{}'::jsonb,'test','manual'),
       ($1,'asset_minted','candidate',$2::jsonb,'asset','manual'),
       ($1,'carrier_declared','candidate',$3::jsonb,'carrier','manual')`,
    [PID, JSON.stringify({ urn: URN, asset_id: 1 }), JSON.stringify({ urn: URN, carrier_type: 'DL' })]);

  console.log('[epcis] projection shape');
  let r = await get(`/party/${PID}/epcis`);
  let b = await r.json();
  ok('GET → 200', r.status === 200);
  ok('flagged projection:true (not a stored EPCIS doc)', b.projection === true);
  ok('isA EPCISDocument, schemaVersion 2.0', b.isA === 'EPCISDocument' && b.schemaVersion === '2.0');

  const list = b.epcisBody?.eventList || [];
  ok('two thing-events projected (asset_minted + carrier_declared)', list.length === 2);
  ok('every projected event is an ObjectEvent', list.every((e) => e.eventType === 'ObjectEvent'));
  ok('every projected event carries the exact EPC in epcList', list.every((e) => Array.isArray(e.epcList) && e.epcList[0] === URN));

  const mint = list.find((e) => e['thingdaddy:registryEventType'] === 'asset_minted');
  ok('asset_minted → bizStep commissioning (CBV)', mint?.bizStep === 'urn:epcglobal:cbv:bizstep:commissioning');
  ok('asset_minted → action ADD', mint?.action === 'ADD');
  const carr = list.find((e) => e['thingdaddy:registryEventType'] === 'carrier_declared');
  ok('carrier_declared → TD-namespaced bizStep (honest: not a CBV step)', carr?.bizStep === 'urn:thingdaddy:bizstep:encoding');

  console.log('[epcis] registry events are not projected (counted, not dropped)');
  ok('candidate_staged NOT in eventList (no EPC)', !list.some((e) => e['thingdaddy:registryEventType'] === 'candidate_staged'));
  ok('registryEventsOmitted counts the non-EPC event', b.registryEventsOmitted === 1);

  console.log('[epcis] missing party');
  r = await get(`/party/99999999/epcis`);
  ok('nonexistent party → 404', r.status === 404);
} finally {
  for (const id of cleanup) await client.query(`DELETE FROM party WHERE id = $1`, [id]); // cascades events
  client.release();
  await pool.end();
  server.close();
}
console.log(failures ? `\n${failures} FAILED` : '\nepcis_surface: ALL PASS');
process.exit(failures ? 1 : 0);
