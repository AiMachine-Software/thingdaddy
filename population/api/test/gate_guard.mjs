// ============================================================================
// gate_guard.mjs — the POST /gate authority+length GUARD, end to end.
//
// Three layers, matching how the guard is built:
//   Part A  pure/subprocess : isPlainDigits + resolvePrefixAuthority (fail closed
//                             against the REAL common/verify.py — no DB).
//   Part B  DB half         : promoteGate() called directly, in a tx that is
//                             ROLLED BACK — nothing persists (mirrors claim_promote).
//   Part C  route           : the ACTUAL POST /gate/:id over HTTP, proving a
//                             guessed/unconfirmed prefix is refused (422) AND the
//                             row stays 'candidate' — the guess never promotes;
//                             and a verifier-unreachable call is refused (502)
//                             with the row still 'candidate'. Route seeds are
//                             committed (the route uses its own tx), so they are
//                             deleted in the finally.
//
// Run against the scratch DB (needs python3 on PATH for Parts A/C):
//   PGDATABASE=thingdaddy_population_test node api/test/gate_guard.mjs
// ============================================================================
import { pool } from '../db.js';
import { app, promoteGate, resolvePrefixAuthority, isPlainDigits } from '../server.js';

let failures = 0;
function ok(label, cond) {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`);
  if (!cond) failures++;
}

// Boot the app on an ephemeral port for Part C. Importing server.js does NOT
// auto-listen (main-module guard), so we listen explicitly and close in finally.
const server = app.listen(0);
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;

// /gate now requires the shared write token (requireWriteToken). Configure it for
// this process and present it on the route-level calls below — this test exercises
// the PREFIX guard, not the auth guard (that lives in write_auth.mjs).
const TOKEN = process.env.INGEST_TOKEN || 'test-write-secret';
process.env.INGEST_TOKEN = TOKEN;
const authHeaders = { 'content-type': 'application/json', authorization: `Bearer ${TOKEN}` };

const routeSeedIds = []; // committed rows to delete at the end
const client = await pool.connect();
try {
  // ── Part A0: format precheck (pure) ───────────────────────────────────────
  console.log('[precheck] isPlainDigits');
  ok("'0702054' is plain digits", isPlainDigits('0702054') === true);
  ok("'0DEMO123' rejected (DEMO placeholder has letters)", isPlainDigits('0DEMO123') === false);
  ok("'' rejected", isPlainDigits('') === false);
  ok('undefined rejected', isPlainDigits(undefined) === false);

  // ── Part A: authority + length via common/verify.py (FAIL CLOSED) ─────────
  console.log('[authority] resolvePrefixAuthority via common/verify.py');
  const confirmed = await resolvePrefixAuthority({
    prefix: '0702054', derived_source: 'manual',
    vbg_confirm: { licensee: 'Telular Corporation', length: 7, country: 'US' },
  });
  ok('VbG confirmation → confirmed:true', confirmed.confirmed === true);
  ok('resolved length surfaced (7)', confirmed.length === 7);

  const derived = await resolvePrefixAuthority({
    prefix: '0702054', derived_source: 'gudid', vbg_confirm: null });
  ok('derived-only, no VbG → confirmed:false, status candidate',
     derived.confirmed === false && derived.status === 'candidate');

  const noSource = await resolvePrefixAuthority({
    prefix: '0702054', derived_source: 'manual', vbg_confirm: null });
  ok('no source, no VbG → confirmed:false, status exception',
     noSource.confirmed === false && noSource.status === 'exception');

  // ── Part C: the REAL route guard (proves a guess does not promote) ────────
  // C1 — guessed/unconfirmed prefix → 422 prefix_unconfirmed, row STILL candidate.
  console.log('[route] C1 guessed prefix → 422 prefix_unconfirmed, no promotion');
  const c1 = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Guess Co','candidate','manual')
     RETURNING id`);
  const c1id = c1.rows[0].id; routeSeedIds.push(c1id);
  const r1 = await fetch(`${base}/gate/${c1id}`, {
    method: 'POST', headers: authHeaders,
    body: JSON.stringify({ prefix: '0702054', actor: 'guess-test' }), // no vbg → cannot confirm
  });
  const b1 = await r1.json();
  ok('C1 route status 422', r1.status === 422);
  ok("C1 error = 'prefix_unconfirmed'", b1.error === 'prefix_unconfirmed');
  const s1 = await client.query('SELECT state FROM party WHERE id = $1', [c1id]);
  ok("C1 row STILL 'candidate' — the guess did NOT promote", s1.rows[0].state === 'candidate');

  // C2 — verifier unreachable → 502 verifier_unavailable, row STILL candidate.
  console.log('[route] C2 verifier unreachable → 502, no promotion');
  const c2 = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Unreachable Co','candidate','manual')
     RETURNING id`);
  const c2id = c2.rows[0].id; routeSeedIds.push(c2id);
  const savedPy = process.env.PYTHON;
  process.env.PYTHON = '/nonexistent/definitely-not-python'; // force execFile ENOENT
  let r2, b2;
  try {
    r2 = await fetch(`${base}/gate/${c2id}`, {
      method: 'POST', headers: authHeaders,
      // even WITH a vbg payload, an unreachable verifier must refuse (fail closed):
      body: JSON.stringify({ prefix: '0702054', actor: 'unreachable-test',
                             vbg: { licensee: 'X', length: 7, country: 'US' } }),
    });
    b2 = await r2.json();
  } finally {
    if (savedPy === undefined) delete process.env.PYTHON; else process.env.PYTHON = savedPy;
  }
  ok('C2 route status 502', r2.status === 502);
  ok("C2 error = 'verifier_unavailable'", b2.error === 'verifier_unavailable');
  const s2 = await client.query('SELECT state FROM party WHERE id = $1', [c2id]);
  ok("C2 row STILL 'candidate' — unreachable verifier did NOT promote", s2.rows[0].state === 'candidate');

  // C3 — HAPPY PATH end to end: valid token + valid vbg → 200, row verified. This
  // is the ONLY path that mutates to 'verified' through the live route (auth →
  // verify.py confirms → promoteGate). It commits (the route runs its own tx), so
  // the row is cleaned up in the finally. A distinctive prefix avoids colliding
  // with any real verified seed on ux_party_prefix; pre-deleted defensively.
  console.log('[route] C3 valid token + vbg → 200 promoted, row verified');
  const HAPPY_PREFIX = '0999777001';
  await client.query('DELETE FROM party WHERE prefix = $1', [HAPPY_PREFIX]);
  const c3 = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Happy Gate Co','candidate','test')
     RETURNING id`);
  const c3id = c3.rows[0].id; routeSeedIds.push(c3id);
  const r3 = await fetch(`${base}/gate/${c3id}`, {
    method: 'POST', headers: authHeaders,
    body: JSON.stringify({ prefix: HAPPY_PREFIX, actor: 'happy-test', mo: 'GS1 US',
                           vbg: { licensee: 'Happy Gate Co', length: 10, country: 'US' } }),
  });
  const b3 = await r3.json();
  ok('C3 route status 200', r3.status === 200);
  ok('C3 promoted:true', b3.promoted === true);
  ok("C3 response party.state = 'verified'", b3.party?.state === 'verified');
  ok(`C3 response party.prefix = ${HAPPY_PREFIX}`, b3.party?.prefix === HAPPY_PREFIX);
  ok('C3 response prefix_length = 10', b3.prefix_length === 10);
  const s3 = await client.query('SELECT state, prefix FROM party WHERE id = $1', [c3id]);
  ok("C3 row is 'verified' in DB with the claimed prefix",
     s3.rows[0].state === 'verified' && s3.rows[0].prefix === HAPPY_PREFIX);
  const ev3 = await client.query(
    `SELECT event_type, detail FROM party_event WHERE party_id = $1 ORDER BY id DESC LIMIT 1`, [c3id]);
  ok("C3 'verified' event appended with prefix_length in detail",
     ev3.rows[0].event_type === 'verified' && ev3.rows[0].detail?.prefix_length === 10);

  // ── Part B: promoteGate (the DB half), everything ROLLED BACK ─────────────
  await client.query('BEGIN');

  console.log('[promoteGate] happy path — verified + prefix + verified_at + event(length)');
  const seed = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Gate Test Co','candidate','manual')
     RETURNING id, state, prefix`);
  const before = seed.rows[0];
  const after = await promoteGate(client, before, {
    prefix: '0702054', mo: 'GS1 US', actor: 'gate-test', length: 7, citation: 'VbG:Telular|len=7' });
  ok('state = verified', after.state === 'verified');
  ok("prefix = '0702054'", after.prefix === '0702054');
  ok('verified_at is set', !!after.verified_at);

  const ev = await client.query(
    `SELECT event_type, detail FROM party_event WHERE party_id = $1 ORDER BY id DESC LIMIT 1`,
    [before.id]);
  ok("'verified' event appended", ev.rows[0].event_type === 'verified');
  ok('event detail carries prefix_length = 7', ev.rows[0].detail?.prefix_length === 7);

  console.log('[backstop] promoteGate with no prefix → DB CHECK 23514');
  const seed2 = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('No Prefix Co','candidate','manual')
     RETURNING id, state, prefix`);
  let checkErr = null;
  try {
    await client.query('SAVEPOINT g1');
    await promoteGate(client, seed2.rows[0], { prefix: null, actor: 't' });
  } catch (e) { checkErr = e; await client.query('ROLLBACK TO SAVEPOINT g1'); }
  ok('prefix-less promote rejected by DB CHECK (23514)', !!checkErr && checkErr.code === '23514');

  await client.query('ROLLBACK'); // nothing from Part B persists, even in scratch.
  console.log('\n(Part B transaction rolled back — no rows persisted)');
} finally {
  await client.query('ROLLBACK').catch(() => {}); // in case a real error left a tx open
  for (const id of routeSeedIds) {              // clean up the committed Part C seeds
    await client.query('DELETE FROM party_event WHERE party_id = $1', [id]).catch(() => {});
    await client.query('DELETE FROM party WHERE id = $1', [id]).catch(() => {});
  }
  client.release();
  await new Promise((r) => server.close(r));
  await pool.end();
}

console.log(failures === 0
  ? '\nALL GATE-GUARD ASSERTIONS PASS'
  : `\n${failures} ASSERTION(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
