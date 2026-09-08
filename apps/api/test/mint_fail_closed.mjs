// ============================================================================
// mint_fail_closed.mjs — the MINT seam, FAIL CLOSED. The companion to
// gate_guard.mjs Part C: that file proves an unreachable *verifier* never
// promotes a party; this one proves an unreachable *engine* never mints a thing.
//
// "A caller MUST treat non-zero / unparseable stdout as NOT minted — never
// fabricate a URN on our silence." (mint_cli.py). This test is that sentence,
// executable. Both mint routes reach the engine BEFORE they open a transaction
// (server.js:782 then 787; server.js:835 then 844), so an unreachable engine
// must leave the database exactly as it found it.
//
//   Part A  POST /party/:id/asset   — engine unreachable → 502 mint_unavailable,
//           ZERO asset rows and ZERO 'asset_minted' events written. Two ways of
//           being unreachable: a dead interpreter (PYTHON) and a real
//           interpreter pointed at a directory with no shim in it (MINT_PY_DIR)
//           — the route reads both (server.js:748-749).
//   Part B  POST /asset/:id/carrier — same engine, same door → 502
//           gate_unavailable, ZERO carrier rows and ZERO 'carrier_declared'
//           events. A carrier profile is NEVER declared on the engine's silence.
//   Part C  the OTHER refusal: engine REACHABLE and it answers no → 422
//           carrier_refused. 502 and 422 must stay distinguishable — "could not
//           answer" is not "answered no" (CONTRIBUTING §5.1).
//
// Every negative case is preceded by the SAME call succeeding, so a refusal can
// never be confused with a route that was never going to write anything.
//
// Each case saves and restores the env var it overrides in a `finally`, so a
// thrown assertion can never leak a dead interpreter into the next case.
//
// Run against scratch (migrations 005+007+008 applied), python3 on PATH:
//   PGDATABASE=thingdaddy_population_test node apps/api/test/mint_fail_closed.mjs
// ============================================================================
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
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
const post = (p, b) => fetch(`${base}${p}`, { method: 'POST', headers: authH, body: JSON.stringify(b) });

// Run `fn` with `vars` applied to process.env, then put the environment back
// EXACTLY as it was — deleting the keys that were previously unset rather than
// writing "undefined" over them (gate_guard.mjs:94-107, generalized so each case
// below restores even if an assertion throws mid-flight).
async function withEnv(vars, fn) {
  const saved = Object.fromEntries(Object.keys(vars).map((k) => [k, process.env[k]]));
  Object.assign(process.env, vars);
  try { return await fn(); } finally {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k]; else process.env[k] = v;
    }
  }
}

// A real, existing directory that contains no mint_cli.py: python3 starts fine
// and exits non-zero because it cannot open the script. Proves "unreachable"
// covers a mislocated shim, not just a missing interpreter.
const emptyDir = fs.mkdtempSync(path.join(os.tmpdir(), 'td-no-shim-'));

const cleanup = [];
const client = await pool.connect();

// The write ledger for a party: how many things exist, and how much provenance.
// Note bigint ids arrive from node-pg as STRINGS; count(*)::int arrives as a number.
async function ledger(partyId, assetId) {
  const a = await client.query(`SELECT count(*)::int AS n FROM asset WHERE party_id = $1`, [partyId]);
  const c = assetId == null
    ? { rows: [{ n: 0 }] }
    : await client.query(`SELECT count(*)::int AS n FROM carrier WHERE asset_id = $1`, [assetId]);
  const e = await client.query(
    `SELECT event_type, count(*)::int AS n FROM party_event WHERE party_id = $1 GROUP BY 1`, [partyId]);
  const ev = Object.fromEntries(e.rows.map((r) => [r.event_type, r.n]));
  return { assets: a.rows[0].n, carriers: c.rows[0].n,
           minted: ev.asset_minted || 0, declared: ev.carrier_declared || 0 };
}
const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);

const DEAD_PY = '/nonexistent/definitely-not-python';

try {
  // ── Part A: POST /party/:id/asset ─────────────────────────────────────────
  const APREFIX = '0999891';
  await client.query(`DELETE FROM party WHERE prefix = $1`, [APREFIX]);              // defensive
  const ap = await client.query(
    `INSERT INTO party (legal_name, prefix, mo, state, source)
     VALUES ('Mint Fail Closed Co', $1, 'GS1 US', 'verified', 'test') RETURNING id`, [APREFIX]);
  const APARTY = ap.rows[0].id; cleanup.push(APARTY);

  console.log('[asset] baseline — the engine IS reachable, so this route DOES write');
  let r = await post(`/party/${APARTY}/asset`, { component: '4471', source: 'test' });
  let b = await r.json();
  ok('happy mint → 201', r.status === 201);
  ok('URN is engine-constructed', b.asset?.urn === `urn:epc:id:giai:${APREFIX}.4471`);
  const ASSET_ID = b.asset?.id;
  const afterHappy = await ledger(APARTY, ASSET_ID);
  ok('one asset row + one asset_minted event now exist',
     afterHappy.assets === 1 && afterHappy.minted === 1);

  console.log('[asset] A1 dead interpreter (PYTHON) → 502, nothing minted');
  const beforeA1 = await ledger(APARTY, ASSET_ID);
  const a1 = await withEnv({ PYTHON: DEAD_PY }, async () => {
    const res = await post(`/party/${APARTY}/asset`, { component: '5001', source: 'test' });
    return { status: res.status, body: await res.json() };
  });
  ok('A1 status 502', a1.status === 502);
  ok("A1 error = 'mint_unavailable'", a1.body.error === 'mint_unavailable');
  ok('A1 detail names the unreachable shim', /mint shim unavailable/.test(a1.body.detail || ''));
  const afterA1 = await ledger(APARTY, ASSET_ID);
  ok('A1 ZERO rows written — ledger unchanged', same(beforeA1, afterA1));
  let probe = await client.query(
    `SELECT 1 FROM asset WHERE party_id = $1 AND giai_component = '5001'`, [APARTY]);
  ok('A1 no asset carries the refused component (no URN fabricated on silence)', probe.rows.length === 0);

  console.log('[asset] A2 real python3, no shim at MINT_PY_DIR → 502, nothing minted');
  const beforeA2 = await ledger(APARTY, ASSET_ID);
  const a2 = await withEnv({ MINT_PY_DIR: emptyDir }, async () => {
    const res = await post(`/party/${APARTY}/asset`, { component: '5002', source: 'test' });
    return { status: res.status, body: await res.json() };
  });
  ok('A2 status 502', a2.status === 502);
  ok("A2 error = 'mint_unavailable'", a2.body.error === 'mint_unavailable');
  const afterA2 = await ledger(APARTY, ASSET_ID);
  ok('A2 ZERO rows written — ledger unchanged', same(beforeA2, afterA2));
  probe = await client.query(
    `SELECT 1 FROM asset WHERE party_id = $1 AND giai_component = '5002'`, [APARTY]);
  ok('A2 no asset carries the refused component', probe.rows.length === 0);

  console.log('[asset] A3 the env is restored — the route mints again');
  r = await post(`/party/${APARTY}/asset`, { component: '5003', source: 'test' });
  ok('A3 mint → 201 (A1/A2 refused because the ENGINE was gone, not the route)', r.status === 201);

  // ── Part B: POST /asset/:id/carrier ───────────────────────────────────────
  console.log('[carrier] baseline — the gate IS reachable, so this route DOES write');
  r = await post(`/asset/${ASSET_ID}/carrier`, { carrier_type: 'DL', source: 'test' });
  b = await r.json();
  ok('happy declare DL → 201', r.status === 201);
  ok("carrier lands 'candidate' with value NULL", b.carrier?.state === 'candidate' && b.carrier?.value === null);
  const afterDL = await ledger(APARTY, ASSET_ID);
  ok('one carrier row + one carrier_declared event now exist',
     afterDL.carriers === 1 && afterDL.declared === 1);

  console.log('[carrier] B1 dead interpreter (PYTHON) → 502, nothing declared');
  const beforeB1 = await ledger(APARTY, ASSET_ID);
  const b1 = await withEnv({ PYTHON: DEAD_PY }, async () => {
    const res = await post(`/asset/${ASSET_ID}/carrier`, { carrier_type: 'RAIN-96', source: 'test' });
    return { status: res.status, body: await res.json() };
  });
  ok('B1 status 502', b1.status === 502);
  ok("B1 error = 'gate_unavailable' (the carrier route's own label)", b1.body.error === 'gate_unavailable');
  const afterB1 = await ledger(APARTY, ASSET_ID);
  ok('B1 ZERO rows written — ledger unchanged', same(beforeB1, afterB1));
  probe = await client.query(
    `SELECT 1 FROM carrier WHERE asset_id = $1 AND carrier_type = 'RAIN-96'`, [ASSET_ID]);
  ok('B1 no RAIN-96 profile exists (admissibility was never affirmed)', probe.rows.length === 0);

  console.log('[carrier] B2 the env is restored — the gate admits again');
  r = await post(`/asset/${ASSET_ID}/carrier`, { carrier_type: 'RAIN-96', source: 'test' });
  ok('B2 declare RAIN-96 → 201 (B1 refused because the ENGINE was gone)', r.status === 201);

  // ── Part C: reachable engine that ANSWERS NO → 422, not 502 ───────────────
  // 502 means "the engine could not answer"; 422 means "the engine answered no".
  // Collapsing them would hide an outage as a business refusal, so prove they
  // stay apart. The engine refuses a non-numeric prefix (MintError, per
  // td_engine_ref.mint) — and `asset.prefix` is the one place that state is
  // reachable, because migration 005 puts a digits-only backstop on
  // `giai_component` (asset_component_numeric) but NOT on `asset.prefix`, while
  // party.prefix has one (party_prefix_digits_only). So the row below is legal
  // today. Seeded directly on purpose: POST /party/:id/asset copies the party's
  // digits-only prefix, so the API itself cannot produce this asset.
  //
  // NOTE FOR THE AUTHOR: that asymmetry is reported, NOT fixed — it is your call
  // whether asset.prefix should carry the same backstop. If you add one, this
  // case becomes unreachable and should be DELETED, not weakened.
  //
  // (carrier_tier.mjs:16-20 says the carrier_refused branch "can't be tripped
  // from a stored asset today" — true for the component, not for the prefix.)
  console.log('[carrier] C1 engine reachable and REFUSES → 422 carrier_refused');
  const CPREFIX = '0999893';
  await client.query(`DELETE FROM party WHERE prefix = $1`, [CPREFIX]);              // defensive
  const cp = await client.query(
    `INSERT INTO party (legal_name, prefix, mo, state, source)
     VALUES ('Refusal Root Co', $1, 'GS1 US', 'verified', 'test') RETURNING id`, [CPREFIX]);
  const CPARTY = cp.rows[0].id; cleanup.push(CPARTY);
  const badAsset = await client.query(
    `INSERT INTO asset (party_id, prefix, giai_component, urn, state, source)
     VALUES ($1,'ABC1234','4471','urn:epc:id:giai:ABC1234.4471','candidate','test') RETURNING id`,
    [CPARTY]);
  const BAD_ID = badAsset.rows[0].id;

  const beforeC1 = await ledger(CPARTY, BAD_ID);
  r = await post(`/asset/${BAD_ID}/carrier`, { carrier_type: 'DL', source: 'test' });
  b = await r.json();
  ok('C1 status 422 — a refusal, NOT a 502 outage', r.status === 422);
  ok("C1 error = 'carrier_refused'", b.error === 'carrier_refused');
  ok("C1 the engine's own verdict is surfaced, not invented",
     b.kind === 'MintError' && /prefix must be numeric/.test(b.detail || ''));
  const afterC1 = await ledger(CPARTY, BAD_ID);
  ok('C1 ZERO rows written — ledger unchanged', same(beforeC1, afterC1));
  ok('C1 no carrier profile on the refused asset', afterC1.carriers === 0);

  // NOT COVERED, deliberately: the asset route's own 422 (`mint_refused`). Every
  // input that reaches the engine from POST /party/:id/asset is already numeric
  // on both sides — the prefix by the DB CHECK party_prefix_digits_only, the
  // component by the route's own R9 guard (server.js:773) — so no request can
  // make td_engine_ref.mint raise. The branch is defensive, for Pom's richer
  // engine. Faking it with a stub engine would test the stub, not the route.
} finally {
  for (const id of cleanup) await client.query(`DELETE FROM party WHERE id = $1`, [id]); // cascades asset → carrier + events
  client.release();
  await pool.end();
  fs.rmSync(emptyDir, { recursive: true, force: true });
  await new Promise((r) => server.close(r));
}
console.log(failures ? `\n${failures} FAILED` : '\nmint_fail_closed: ALL PASS');
process.exit(failures ? 1 : 0);
