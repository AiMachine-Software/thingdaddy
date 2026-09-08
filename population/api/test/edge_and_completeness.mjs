// ============================================================================
// edge_and_completeness.mjs — Cycle 1 · Core: POST /party/:id/edge (role stamps
// + sameAs) and GET /party/:id/completeness.
//
// Proves:
//   * edge write is token-gated (401 without) and validates (400 on missing rel).
//   * an asserted edge ALWAYS lands `candidate` — registrar-does-not-adjudicate;
//     sameAs is never auto-merged/verified. It carries its asserter, shows up in
//     /record, and appends an 'updated' party_event (provenance spine).
//   * re-asserting the same (subject, rel, object, source) is idempotent (upsert,
//     no duplicate edge).
//   * completeness is computed-only, state-aware: a candidate is incomplete with
//     the gaps listed; a verified row with the base fields is complete. 404 for
//     a missing party. classification is a Cycle 1 stub, never faked.
//
// Run against the scratch DB (migration 004 must be applied):
//   PGDATABASE=thingdaddy_population_test node api/test/edge_and_completeness.mjs
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
const TOKEN = process.env.INGEST_TOKEN || 'test-write-secret';
process.env.INGEST_TOKEN = TOKEN;
const authH = { 'content-type': 'application/json', authorization: `Bearer ${TOKEN}` };
const post = (path, body, headers = authH) =>
  fetch(`${base}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });

const cleanupIds = [];
const client = await pool.connect();
try {
  // ── seed subjects ─────────────────────────────────────────────────────────
  const subj = await client.query(
    `INSERT INTO party (legal_name, state, source) VALUES ('Edge Subject Co','candidate','test')
     RETURNING id`);
  const SID = subj.rows[0].id; cleanupIds.push(SID);

  const VPREFIX = '0955111';
  await client.query(`DELETE FROM party WHERE prefix = $1`, [VPREFIX]); // defensive
  const vp = await client.query(
    `INSERT INTO party (legal_name, prefix, gln, mo, state, source)
     VALUES ('Complete Co', $1, '0955111000005', 'GS1 US', 'verified', 'test') RETURNING id`, [VPREFIX]);
  const VID = vp.rows[0].id; cleanupIds.push(VID);

  // ── POST /party/:id/edge — auth + validation ──────────────────────────────
  console.log('[edge] auth + validation');
  let r = await post(`/party/${SID}/edge`, { rel: 'located_at', object_label: 'Plant 5' }, { 'content-type': 'application/json' });
  ok('no token → 401', r.status === 401);
  r = await post(`/party/${SID}/edge`, { object_label: 'Plant 5' });        // missing rel
  ok('missing rel → 400', r.status === 400);
  r = await post(`/party/99999999/edge`, { rel: 'located_at', object_label: 'Plant 5' });
  ok('nonexistent party → 404', r.status === 404);

  // ── role stamp — lands candidate, carries asserter, shows in /record ──────
  console.log('[edge] role stamp → candidate + provenance');
  r = await post(`/party/${SID}/edge`, { rel: 'located_at', object_label: 'Plant 5, Phoenix',
    asserter: 'agent:TD-A-01', source: 'manual' });
  const eb = await r.json();
  ok('role stamp → 201', r.status === 201);
  ok("edge.state = 'candidate' (registrar does not adjudicate)", eb.edge?.state === 'candidate');
  ok("edge.asserter = 'agent:TD-A-01'", eb.edge?.asserter === 'agent:TD-A-01');
  const rec = await (await fetch(`${base}/record/${SID}`)).json();
  ok('edge appears in /record with asserter',
     rec.edges?.some((e) => e.rel === 'located_at' && e.asserter === 'agent:TD-A-01' && e.state === 'candidate'));
  const evt = await client.query(
    `SELECT event_type, detail FROM party_event WHERE party_id=$1 ORDER BY id DESC LIMIT 1`, [SID]);
  ok("'updated' party_event appended for the edge", evt.rows[0].event_type === 'updated'
     && evt.rows[0].detail?.via === 'POST /party/:id/edge');

  // ── sameAs — co-reference, unadjudicated (candidate), never merged ────────
  console.log('[edge] sameAs stays candidate (unadjudicated)');
  r = await post(`/party/${SID}/edge`, { rel: 'same_as', object_label: 'Edge Subject Corporation',
    asserter: 'manual' });
  const sb = await r.json();
  ok('sameAs → 201', r.status === 201);
  ok("sameAs edge.state = 'candidate' (never auto-merged)", sb.edge?.state === 'candidate');

  // ── re-assert is idempotent (upsert on the unique key, no duplicate) ──────
  console.log('[edge] re-assert idempotent');
  r = await post(`/party/${SID}/edge`, { rel: 'located_at', object_label: 'Plant 5, Phoenix',
    asserter: 'agent:TD-A-01', source: 'manual', doc: 'work-order-42' });
  ok('re-assert → 201 (upsert)', r.status === 201);
  const cnt = await client.query(
    `SELECT count(*)::int AS n FROM edge WHERE subject_party_id=$1 AND rel='located_at'
       AND object_label='Plant 5, Phoenix' AND source='manual'`, [SID]);
  ok('exactly 1 edge for that (subject,rel,object,source) — no duplicate', cnt.rows[0].n === 1);

  // ── GET /party/:id/completeness — computed, state-aware ───────────────────
  console.log('[completeness] candidate incomplete, verified complete');
  const c1 = await (await fetch(`${base}/party/${SID}/completeness`)).json();
  ok('candidate → complete:false', c1.complete === false && c1.state === 'candidate');
  ok('candidate missing lists prefix/gln/mo', ['prefix', 'gln', 'mo'].every((f) => c1.missing.includes(f)));
  ok("candidate present includes legal_name", c1.present.includes('legal_name'));
  ok('classification is a stub', c1.classification?.status === 'stub' && c1.classification?.key === null);

  const c2 = await (await fetch(`${base}/party/${VID}/completeness`)).json();
  ok('verified + base fields → complete:true', c2.complete === true && c2.state === 'verified');
  ok('verified missing = []', Array.isArray(c2.missing) && c2.missing.length === 0);

  const c404 = await fetch(`${base}/party/99999999/completeness`);
  ok('nonexistent party → 404', c404.status === 404);
} finally {
  for (const id of cleanupIds) {
    await client.query(`DELETE FROM party WHERE id = $1`, [id]).catch(() => {}); // cascades edges + events
  }
  client.release();
  await new Promise((r) => server.close(r));
  await pool.end();
}

console.log(failures === 0 ? '\nALL EDGE + COMPLETENESS ASSERTIONS PASS'
  : `\n${failures} ASSERTION(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
