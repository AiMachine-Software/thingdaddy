// ============================================================================
// write_auth.mjs — the shared-secret guard on the mutating endpoints.
//
// requireWriteToken protects POST /ingest and POST /gate. Proves:
//   * FAIL CLOSED   — INGEST_TOKEN unset on the server → 503 on any write
//                     (an unconfigured server is DISABLED, never open).
//   * caller token  — absent or wrong → 401 unauthorized.
//   * valid token   — request reaches the handler: /ingest → 201; /gate with a
//                     valid token but no vbg → 422 prefix_unconfirmed (auth passed,
//                     the prefix guard still holds and the row stays candidate).
// Reads/writes go through the REAL app over HTTP (ephemeral port). Committed rows
// (the 201 ingest + the /gate seed) are deleted in the finally.
//
// Run against the scratch DB:
//   PGDATABASE=thingdaddy_population_test node api/test/write_auth.mjs
// ============================================================================
import { pool } from '../db.js';
import { app } from '../server.js';

let failures = 0;
function ok(label, cond) {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`);
  if (!cond) failures++;
}

const server = app.listen(0);
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${server.address().port}`;
const TOKEN = 'test-write-secret';

function post(path, { token, body } = {}) {
  const headers = { 'content-type': 'application/json' };
  if (token) headers.authorization = `Bearer ${token}`;
  return fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body || {}) });
}
const oneRow = { rows: [{ legal_name: 'Auth Test Co', source: 'test' }] };

const cleanupIds = [];
const client = await pool.connect();
const savedTok = process.env.INGEST_TOKEN;
try {
  // ── FAIL CLOSED: server has NO token configured → writes disabled (503) ────
  delete process.env.INGEST_TOKEN;
  console.log('[unconfigured] no INGEST_TOKEN on the server → 503 on writes');
  let r = await post('/ingest', { token: TOKEN, body: oneRow });
  ok('/ingest, server token unset → 503 write_auth_unconfigured',
     r.status === 503 && (await r.json()).error === 'write_auth_unconfigured');
  r = await post('/gate/1', { token: TOKEN, body: { prefix: '0702054' } });
  ok('/gate, server token unset → 503', r.status === 503);

  // ── token configured on the server from here on ───────────────────────────
  process.env.INGEST_TOKEN = TOKEN;

  console.log('[missing / wrong] caller token absent or wrong → 401');
  r = await post('/ingest', { body: oneRow }); // no Authorization header
  ok('/ingest, no Authorization → 401 unauthorized',
     r.status === 401 && (await r.json()).error === 'unauthorized');
  r = await post('/ingest', { token: 'WRONG-TOKEN', body: oneRow });
  ok('/ingest, wrong token → 401', r.status === 401);
  r = await post('/gate/1', { body: { prefix: '0702054' } }); // no Authorization header
  ok('/gate, no Authorization → 401', r.status === 401);

  // /claim is a mutating route too: a tokenless claim must not reach the handler,
  // so it can never flip candidate → exception (the claim_held path).
  const claimSeed = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Claim Auth Co','candidate','test')
     RETURNING id`);
  const claimId = claimSeed.rows[0].id; cleanupIds.push(claimId);
  r = await post(`/claim/${claimId}`, { body: { prefix: '0702054' } }); // no Authorization header
  ok('/claim, no Authorization → 401', r.status === 401 && (await r.json()).error === 'unauthorized');
  const claimState = await client.query('SELECT state FROM party WHERE id = $1', [claimId]);
  ok("/claim row still 'candidate' (tokenless claim did NOT mutate)",
     claimState.rows[0].state === 'candidate');

  console.log('[valid] correct token reaches the handler');
  r = await post('/ingest', { token: TOKEN, body: oneRow });
  const jb = await r.json();
  ok('/ingest, valid token → 201 ingested=1', r.status === 201 && jb.ingested === 1);
  if (jb.results?.[0]?.id) cleanupIds.push(jb.results[0].id);

  // seed a candidate, then hit /gate with a valid token but no vbg → 422 (past
  // auth, the prefix guard rejects; the row must stay 'candidate').
  const seed = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Auth Gate Co','candidate','test')
     RETURNING id`);
  const gid = seed.rows[0].id; cleanupIds.push(gid);
  r = await post(`/gate/${gid}`, { token: TOKEN, body: { prefix: '0702054' } });
  ok('/gate, valid token, no vbg → 422 prefix_unconfirmed (auth passed, guard held)',
     r.status === 422 && (await r.json()).error === 'prefix_unconfirmed');
  const st = await client.query('SELECT state FROM party WHERE id = $1', [gid]);
  ok("/gate row still 'candidate' (auth-passed request did NOT promote)",
     st.rows[0].state === 'candidate');
} finally {
  if (savedTok === undefined) delete process.env.INGEST_TOKEN; else process.env.INGEST_TOKEN = savedTok;
  for (const id of cleanupIds) {
    await client.query('DELETE FROM party_event WHERE party_id = $1', [id]).catch(() => {});
    await client.query('DELETE FROM party WHERE id = $1', [id]).catch(() => {});
  }
  client.release();
  await new Promise((r) => server.close(r));
  await pool.end();
}

console.log(failures === 0
  ? '\nALL WRITE-AUTH ASSERTIONS PASS'
  : `\n${failures} ASSERTION(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
