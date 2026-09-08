// ============================================================================
// db.js — the single Postgres connection point for the Population API.
//
// Isolation: this module owns ALL database access for the API. It connects only
// to the thingdaddy_population DB (via env). It imports nothing from platform/
// or agents/. Everything above it (server.js) speaks HTTP; everything below is
// SQL. There is no third path to the data.
// ============================================================================
import pg from 'pg';
import dotenv from 'dotenv';

dotenv.config();

// node-pg reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD from the environment
// automatically; passing an empty object lets those defaults flow through. We
// keep a small pool — this is a local single-user service, not a fleet.
// ============================================================================
// TEST DATABASE GUARD — fail closed before the pool is constructed.
//
// api/test/gate_authority.mjs runs `DELETE FROM party WHERE prefix='0817089'`
// (Diazyme), and .env points PGDATABASE at thingdaddy_population. Every FK
// into party CASCADEs. A test that is safe only because someone remembered an
// environment variable is one keystroke from destructive, so the refusal is
// here rather than in each test file: an import cannot be forgotten and the
// pool cannot be opened around it.
//
// Override with TD_ALLOW_TEST_DB=1 only if you know exactly why.
// ============================================================================
{
  const entry = process.argv[1] || '';
  const inTest =
    /(^|[\\/])test[\\/]/.test(entry) ||
    process.env.NODE_TEST_CONTEXT !== undefined ||
    process.argv.includes('--test');
  const db = process.env.PGDATABASE || '';

  if (inTest && !db.endsWith('_test') && process.env.TD_ALLOW_TEST_DB !== '1') {
    console.error(`
  REFUSED: a test tried to open ${db ? `"${db}"` : 'an unnamed database'}.

  Tests write and delete. They run only against a database whose name ends
  "_test". This one does not, so nothing was opened.

      PGDATABASE=thingdaddy_population_test node --test test/*.mjs

  If that database does not exist yet:

      createdb thingdaddy_population_test

  An unset PGDATABASE is refused too: libpq would resolve it to your
  username, and a database this process cannot name is one it must not
  write to.
`);
    process.exit(1);
  }
}

export const pool = new pg.Pool({
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

// Postgres error code for a CHECK-constraint violation. This is how the gate
// (party_gate_prefix_required) tells us a verified row lacked a prefix — we
// defer to the DB rather than re-implementing the rule in JS.
export const PG_CHECK_VIOLATION = '23514';

// Postgres error code for a UNIQUE-constraint violation. The claim path relies
// on the DB to reject a re-used prefix (ux_party_prefix) or a double re-root
// (ux_party_origin_party) — we map it to a 409 conflict rather than re-checking.
export const PG_UNIQUE_VIOLATION = '23505';

// Thin query helper so routes read cleanly: `const { rows } = await q(sql, args)`.
export function q(text, params) {
  return pool.query(text, params);
}

// Run a set of statements in one transaction. `fn` receives a dedicated client;
// it is COMMITted on success and ROLLBACKed on any throw (so a failed write
// never leaves a half-applied party + no event, or vice versa).
export async function tx(fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// Liveness probe for GET /health.
export async function ping() {
  const { rows } = await pool.query('SELECT 1 AS ok');
  return rows[0]?.ok === 1;
}
