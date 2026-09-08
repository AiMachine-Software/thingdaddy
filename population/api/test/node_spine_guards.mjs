// ============================================================================
// node_spine_guards.mjs — migration 010's two CHECKs, exercised. The graph spine
// has "no limits on topology, strict on truth"; these are the truth half, and
// they live in SQL, so this test talks to the DB directly rather than through a
// route (nothing is wired to node/association/node_event yet — the backfill and
// the endpoints come later, and these guards must already hold when they do).
//
//   Part A  node_gate_prefix       CHECK (state <> 'verified' OR prefix IS NOT NULL)
//           Prefix-is-root, carried from party: nothing is VERIFIED without a
//           prefix. Note what it actually binds — only the verified state. A
//           candidate with no prefix is legal and expected ("candidates have
//           none", 010:18), so that is asserted too, not assumed.
//   Part B  node_event_one_subject CHECK ((node_id IS NOT NULL) <> (association_id IS NOT NULL))
//           An XOR, not a NOT-NULL: provenance threads to EXACTLY ONE subject.
//           Both failure directions are asserted — neither subject AND both —
//           because a plain "at least one" check would still pass the first.
//
// Each refusal is asserted on the Postgres error itself (SQLSTATE 23514 + the
// constraint NAME), not on "something threw" — a NOT NULL violation or a typo'd
// column would also throw, and neither would mean the guard held.
//
// Every valid counterpart is inserted FIRST, so a refusal can never be confused
// with an insert that was never going to succeed.
//
// Writes are contained twice over: the whole body runs in ONE transaction that
// is ROLLED BACK (gate_guard.mjs Part B), and every row carries the marker in
// `source` so the finally can sweep by marker if a real error broke the tx.
//
// Run against scratch (migration 010 applied):
//   PGDATABASE=thingdaddy_population_test node population/api/test/node_spine_guards.mjs
// ============================================================================
import { pool } from '../db.js';

let failures = 0;
function ok(label, cond) { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) failures++; }

const MARK = 'node-spine-guards-test';
const client = await pool.connect();

// Attempt a write that MUST be refused. Returns the pg error, or null if the
// statement succeeded — and rolls the attempt back either way, so a guard that
// has been removed leaves no residue but is still reported as null.
async function refused(sql, params) {
  let err = null;
  await client.query('SAVEPOINT guard');
  try { await client.query(sql, params); } catch (e) { err = e; }
  await client.query('ROLLBACK TO SAVEPOINT guard');
  return err;
}
const marked = async (table) => (await client.query(
  `SELECT count(*)::int AS n FROM ${table} WHERE source = $1`, [MARK])).rows[0].n;

try {
  await client.query('BEGIN');

  // ── Part A: node_gate_prefix ──────────────────────────────────────────────
  console.log('[node] verified requires a prefix');
  const rooted = await client.query(
    `INSERT INTO node (key_type, state, source, prefix) VALUES ('pgln','verified',$1,'0999881')
     RETURNING id, state, prefix`, [MARK]);
  ok("A1 verified WITH a prefix inserts (the guard is not blanket-refusing)",
     rooted.rows[0].state === 'verified' && rooted.rows[0].prefix === '0999881');

  const beforeA = await marked('node');
  const a2 = await refused(
    `INSERT INTO node (key_type, state, source) VALUES ('pgln','verified',$1)`, [MARK]);
  ok('A2 verified WITHOUT a prefix rejected by a CHECK (23514)', a2?.code === '23514');
  ok("A2 the constraint is node_gate_prefix", a2?.constraint === 'node_gate_prefix');
  ok('A2 ZERO rows written', (await marked('node')) === beforeA);

  // What the check actually enforces is narrower than its name: it binds the
  // VERIFIED state only. Candidates are first-class and carry no prefix.
  const cand = await client.query(
    `INSERT INTO node (key_type, state, source) VALUES ('giai','candidate',$1)
     RETURNING id, state, prefix`, [MARK]);
  ok("A3 candidate WITHOUT a prefix inserts — the gate binds 'verified' only",
     cand.rows[0].state === 'candidate' && cand.rows[0].prefix === null);
  const exc = await client.query(
    `INSERT INTO node (key_type, state, source, exception_reason)
     VALUES ('giai','exception',$1,'no GS1 record') RETURNING id, state, prefix`, [MARK]);
  ok('A4 exception WITHOUT a prefix inserts — likewise',
     exc.rows[0].state === 'exception' && exc.rows[0].prefix === null);

  // KNOWN GAP, asserted nowhere on purpose: node_gate_prefix tests IS NOT NULL,
  // so prefix = '' would satisfy it. party.prefix has a digits-only CHECK
  // (party_prefix_digits_only, migration 002); node.prefix has no equivalent yet.
  // Reported, not encoded — asserting the gap here would read as endorsing it,
  // and would fight the fix when the backstop arrives.

  // ── Part B: node_event_one_subject ────────────────────────────────────────
  console.log('[node_event] provenance threads to exactly one subject');
  const other = await client.query(
    `INSERT INTO node (key_type, state, source) VALUES ('giai','candidate',$1) RETURNING id`, [MARK]);
  // node-pg returns bigint as a STRING; keep both sides of every id comparison
  // as whatever the driver handed back rather than coercing to Number.
  const NODE_ID = cand.rows[0].id;
  const assoc = await client.query(
    `INSERT INTO association (subject_node_id, object_node_id, rel, source)
     VALUES ($1,$2,'part_of',$3) RETURNING id`, [NODE_ID, other.rows[0].id, MARK]);
  const ASSOC_ID = assoc.rows[0].id;

  const onNode = await client.query(
    `INSERT INTO node_event (node_id, event_type, source) VALUES ($1,'node_minted',$2)
     RETURNING id, node_id, association_id`, [NODE_ID, MARK]);
  ok('B1 node-only event inserts',
     onNode.rows[0].node_id === NODE_ID && onNode.rows[0].association_id === null);
  const onAssoc = await client.query(
    `INSERT INTO node_event (association_id, event_type, source) VALUES ($1,'associated',$2)
     RETURNING id, node_id, association_id`, [ASSOC_ID, MARK]);
  ok('B2 association-only event inserts',
     onAssoc.rows[0].association_id === ASSOC_ID && onAssoc.rows[0].node_id === null);

  const beforeB = await marked('node_event');
  const b3 = await refused(
    `INSERT INTO node_event (event_type, source) VALUES ('node_minted',$1)`, [MARK]);
  ok('B3 NEITHER subject rejected by a CHECK (23514)', b3?.code === '23514');
  ok('B3 the constraint is node_event_one_subject', b3?.constraint === 'node_event_one_subject');
  ok('B3 ZERO rows written', (await marked('node_event')) === beforeB);

  const b4 = await refused(
    `INSERT INTO node_event (node_id, association_id, event_type, source)
     VALUES ($1,$2,'associated',$3)`, [NODE_ID, ASSOC_ID, MARK]);
  ok('B4 BOTH subjects rejected by a CHECK (23514) — it is an XOR, not "at least one"',
     b4?.code === '23514');
  ok('B4 the constraint is node_event_one_subject', b4?.constraint === 'node_event_one_subject');
  ok('B4 ZERO rows written', (await marked('node_event')) === beforeB);

  ok('exactly the two valid events survive the four attempts', (await marked('node_event')) === 2);

  await client.query('ROLLBACK');   // nothing from this test persists, even in scratch.
  console.log('\n(transaction rolled back — no rows persisted)');
} finally {
  await client.query('ROLLBACK').catch(() => {});   // in case a real error left a tx open
  // Belt and braces: if the transaction above died mid-flight, sweep by marker.
  // node_event/association cascade from node, so deleting the nodes is enough.
  await client.query(`DELETE FROM node_event WHERE source = $1`, [MARK]).catch(() => {});
  await client.query(`DELETE FROM association WHERE source = $1`, [MARK]).catch(() => {});
  await client.query(`DELETE FROM node WHERE source = $1`, [MARK]).catch(() => {});
  client.release();
  await pool.end();
}
console.log(failures ? `\n${failures} FAILED` : '\nnode_spine_guards: ALL PASS');
process.exit(failures ? 1 : 0);
