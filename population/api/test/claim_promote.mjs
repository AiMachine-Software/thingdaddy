// ============================================================================
// claim_promote.mjs — direct in-process test of the CLAIM PROMOTE BRANCH.
//
// It calls the REAL promoteClaim() exported by server.js and NEVER touches
// authorityCheck — so the live authority gate stays fail-closed globally; this
// only exercises what happens AFTER authority would have confirmed. Importing
// server.js does not boot the API (main-module guard). Everything runs in one
// transaction and is ROLLED BACK, so nothing persists even in the scratch DB.
//
// Run against the scratch DB:
//   PGDATABASE=thingdaddy_population_test node api/test/claim_promote.mjs
// ============================================================================
import { pool } from '../db.js';
import { promoteClaim } from '../server.js';

let failures = 0;
function ok(label, cond) {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`);
  if (!cond) failures++;
}

const client = await pool.connect();
try {
  await client.query('BEGIN');

  // ── seed a demo-staged candidate to promote ──────────────────────────────
  const seed = await client.query(
    `INSERT INTO party (legal_name, state, source, is_demo, demo_urn)
     VALUES ('Promote Test Co', 'candidate', 'simulation', true, 'urn:epc:id:sgln:0DEMO999.0.0')
     RETURNING id, state, prefix, is_demo, demo_urn`);
  const before = seed.rows[0];

  // ── the promote branch, called DIRECTLY (authorityCheck not consulted) ────
  console.log('[promote] happy path — verified + prefix + is_demo=false + origin + events');
  const res = await promoteClaim(client, before, {
    prefix: '0702054', gln: null, mo: 'GS1 US',
    authority: { gepir: 'confirmed(test)', lei: 'TEST-LEI' }, actor: 'promote-test',
  });

  const p = res.party;
  ok('party.state = verified', p.state === 'verified');
  ok("party.prefix = '0702054'", p.prefix === '0702054');
  ok('party.verified_at is set', !!p.verified_at);
  // is_demo is not in PARTY_COLS (internal, not exposed in API responses), so
  // assert the flip against the DB directly — the source of truth.
  const demoChk = await client.query('SELECT is_demo FROM party WHERE id = $1', [before.id]);
  ok('party.is_demo = false in DB', demoChk.rows[0].is_demo === false);

  const po = await client.query('SELECT * FROM party_origin WHERE party_id = $1', [before.id]);
  ok('exactly one party_origin row', po.rows.length === 1);
  const o = po.rows[0] || {};
  ok("origin.claimed_prefix = '0702054'", o.claimed_prefix === '0702054');
  ok('origin.origin_urn frozen from demo_urn', o.origin_urn === 'urn:epc:id:sgln:0DEMO999.0.0');
  ok('origin.origin_prefix = pre-claim value (NULL)', o.origin_prefix === null);

  const ev = await client.query(
    'SELECT event_type FROM party_event WHERE party_id = $1 ORDER BY at, id', [before.id]);
  const types = ev.rows.map((r) => r.event_type);
  ok('prefix_claimed event present', types.includes('prefix_claimed'));
  ok('origin_linked event present', types.includes('origin_linked'));

  // ── conflict path 1: reused prefix → 23505 (ux_party_prefix) ──────────────
  console.log('[conflict] reused prefix → 23505');
  const seed2 = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Second Co', 'candidate', 'simulation')
     RETURNING id, state, prefix, is_demo, demo_urn`);
  let uniqueErr = null;
  try {
    await client.query('SAVEPOINT sp1');
    await promoteClaim(client, seed2.rows[0], { prefix: '0702054', authority: {}, actor: 't' });
  } catch (e) { uniqueErr = e; await client.query('ROLLBACK TO SAVEPOINT sp1'); }
  ok('reused prefix rejected with PG code 23505 (route maps → 409)',
     !!uniqueErr && uniqueErr.code === '23505');

  // ── conflict path 2: anchor mismatch → httpStatus 409 anchor_conflict ─────
  console.log('[conflict] anchor mismatch → 409 anchor_conflict');
  const seed3 = await client.query(
    `INSERT INTO party (legal_name, state, source, prefix)
     VALUES ('Anchored Co', 'candidate', 'simulation', '0888888')
     RETURNING id, state, prefix, is_demo, demo_urn`);
  let anchorErr = null;
  try {
    await client.query('SAVEPOINT sp2');
    await promoteClaim(client, seed3.rows[0], { prefix: '0999999', authority: {}, actor: 't' });
  } catch (e) { anchorErr = e; await client.query('ROLLBACK TO SAVEPOINT sp2'); }
  ok('anchor mismatch → httpStatus 409 / code409 anchor_conflict',
     !!anchorErr && anchorErr.httpStatus === 409 && anchorErr.code409 === 'anchor_conflict');

  await client.query('ROLLBACK'); // nothing persists, even in the scratch DB.
  console.log('\n(transaction rolled back — no rows persisted)');
} finally {
  client.release();
  await pool.end();
}

console.log(failures === 0
  ? '\nALL PROMOTE-BRANCH ASSERTIONS PASS'
  : `\n${failures} ASSERTION(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
