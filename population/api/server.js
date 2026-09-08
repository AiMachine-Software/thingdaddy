// ============================================================================
// server.js — ThingDaddy Population Database REST API (Step 3).
//
// Isolated data tier over the thingdaddy_population Postgres DB. It does NOT
// import from or touch platform/. The platform's only cross-boundary read is
// GET /verified.
//
// The four laws are enforced here as they are in the schema:
//   - Prefix is root: /gate requires a prefix; the DB CHECK has final say.
//   - Verified-or-exception: /ingest can only ever land candidate|exception.
//   - Nothing mints on a guess: promotion happens solely through /gate.
//   - Provenance spine: every write also appends an append-only party_event.
//
// Writers: POST /ingest, POST /gate/:id, POST /claim/:id  (nothing else writes).
// Readers : GET /search, /record/:id, /record/prefix/:prefix, /verified, /stats.
// ============================================================================
import express from 'express';
import { pathToFileURL, fileURLToPath } from 'url';
import { execFile } from 'node:child_process';
import { timingSafeEqual } from 'node:crypto';
import path from 'node:path';
import { readFileSync, existsSync } from 'node:fs';
import { q, tx, ping, PG_CHECK_VIOLATION, PG_UNIQUE_VIOLATION } from './db.js';

export const app = express();
app.use(express.json({ limit: '4mb' }));

// CORS — the Population UI is a separate app on a different origin (e.g.
// http://localhost:5173) and calls this API from the browser. Without these
// headers the browser blocks the cross-origin fetch ("failed to fetch"). Origin
// is configurable via CORS_ORIGIN (default '*' for local dev). Simple GETs don't
// preflight; we still answer OPTIONS so browser POSTs (/ingest, /gate) work too.
const CORS_ORIGIN = process.env.CORS_ORIGIN || '*';
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', CORS_ORIGIN);
  res.header('Vary', 'Origin');
  res.header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

const PORT = process.env.PORT || 8787;
// Loopback only. The API is a local data tier fronted by the platform + loaders on
// the same host; it must NOT bind 0.0.0.0. Overridable via HOST for a deliberate
// deployment behind its own network controls — never widen it casually.
const HOST = process.env.HOST || '127.0.0.1';
const MAX_PAGE = 20; // hard ceiling on any page — never return more than 20 rows.

// Closed vocab, mirrored from the schema's CHECK constraints.
const STATES = new Set(['candidate', 'verified', 'exception']);

// --- small helpers ----------------------------------------------------------

// Clamp a requested page size into [1, MAX_PAGE]; default to MAX_PAGE.
function pageLimit(raw) {
  const n = Number.parseInt(raw, 10);
  if (Number.isNaN(n) || n < 1) return MAX_PAGE;
  return Math.min(n, MAX_PAGE);
}

// Keyset cursor is simply the last id seen (ascending, stable). Parse defensively.
function parseCursor(raw) {
  if (raw === undefined || raw === null || raw === '') return null;
  const n = Number.parseInt(raw, 10);
  return Number.isNaN(n) || n < 0 ? null : n;
}

// Wrap an async route so any throw becomes a clean 500 instead of a hang.
function h(fn) {
  return (req, res) => fn(req, res).catch((err) => {
    console.error(`[${req.method} ${req.path}]`, err);
    res.status(500).json({ error: 'internal error', detail: err.message });
  });
}

// --- write auth (shared-secret gate on the mutating endpoints) ---------------
// /ingest and /gate mutate the registry, so they require a shared secret in the
// `Authorization: Bearer <token>` header, matched against INGEST_TOKEN. FAILS
// CLOSED: if INGEST_TOKEN is unset on the server, writes are DISABLED (503), not
// open — an unconfigured server can never be tricked into accepting a write.
// Read at call time so ops/tests can set it per process without a code change.
//
// This is INTERIM protection: it authenticates the CALLER. It does NOT make
// req.body.vbg server-verified — a caller with the token can still assert vbg.
// Real authority is the tracked follow-up (server-side VbG/GEPIR). See the PR
// "Trust model" section.
function safeEqual(a, b) {
  const ba = Buffer.from(String(a));
  const bb = Buffer.from(String(b));
  return ba.length === bb.length && timingSafeEqual(ba, bb);
}
function requireWriteToken(req, res, next) {
  const expected = process.env.INGEST_TOKEN;
  if (!expected) {
    return res.status(503).json({
      error: 'write_auth_unconfigured',
      detail: 'INGEST_TOKEN is not set on the server; write endpoints are disabled until it is',
    });
  }
  // Auth scheme is case-insensitive (RFC 7235); tolerate extra whitespace.
  const m = /^Bearer\s+(\S+)$/i.exec((req.headers['authorization'] || '').trim());
  const presented = m ? m[1] : null;
  if (!presented || !safeEqual(presented, expected)) {
    return res.status(401).json({
      error: 'unauthorized',
      detail: 'missing or invalid write token (send Authorization: Bearer <INGEST_TOKEN>)',
    });
  }
  next();
}

// --- authority ownership pre-check (the verified-or-exception seam) ----------
// FAILS CLOSED. Live GEPIR / Verified-by-GS1 is not wired yet, so this gate
// confirms NOTHING: it can only ever return { confirmed:false }, so a claim can
// never verify on thin evidence and never defaults to verified. Every
// unconfirmed claim lands as a NAMED exception. Replacing this body with a real
// GEPIR + LEI ownership check is the ONLY way to make confirmed:true reachable —
// the { confirmed, reason } contract stays the same.
function authorityCheck(/* { prefix, party, authority } */) {
  // TODO(authority): confirm (a) `prefix` is a REAL GS1 company prefix
  // (GEPIR / Verified-by-GS1) AND (b) it BELONGS TO this claimant (LEI / GLEIF
  // cross-reference). Until that is wired, nothing is confirmed.
  return {
    confirmed: false,
    reason: 'authority pending: GEPIR / Verified-by-GS1 not wired — claim held as exception',
  };
}

// --- GS1 prefix authority + length resolution (the /gate seam) ---------------
// The SAME deterministic gate the agent fleet uses (common/verify.py) — reached
// over a stdin/stdout shim (verify_cli.py) so this is the single source of truth,
// not a reimplementation that could drift. FAILS CLOSED.
//
// NOTE FOR REVIEW: this reaches OUT of population/ into agents/…/common. That
// couples the data tier to the agent fleet (see population/CLAUDE.md "self-
// contained"). VERIFY_PY_DIR makes the path overridable so we can instead vendor
// a copy under population/ if the reviewer prefers strict isolation. Flagged, not
// silently chosen.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_VERIFY_PY_DIR = path.resolve(__dirname, '../../agents/thingdaddy_loops/common');
const VERIFY_PY_CLI = 'verify_cli.py';

// A real GS1 company prefix is digits only (mirrors the DB CHECK
// party_prefix_digits_only). A '0DEMO…' placeholder has letters, so this rejects
// it before we ever spend a verifier call. Exported for unit testing.
export function isPlainDigits(prefix) {
  return typeof prefix === 'string' && /^[0-9]+$/.test(prefix);
}

// resolvePrefixAuthority — consult common/verify.py for (a) is this a real,
// authority-confirmed GS1 prefix and (b) its licensed LENGTH. FAILS CLOSED:
// confirmed:true is reachable ONLY when verify.py returns status 'verified' with
// a resolved integer length (Verified by GS1 confirmed prefix + licensee + len).
// Every other outcome — a 'candidate'/'exception' verdict, unparseable output, a
// missing interpreter, a timeout — resolves to { confirmed:false }. `unreachable`
// distinguishes "the verifier could not answer" (an upstream 502) from "the
// verifier answered no" (a business 422); either way, nothing is promoted.
export function resolvePrefixAuthority({ prefix, derived_source, vbg_confirm }) {
  // Config read at call time so a caller (ops override, or a test exercising the
  // unreachable path) can repoint the verifier per call, not just at boot.
  const python = process.env.PYTHON || 'python3';
  const verifyDir = process.env.VERIFY_PY_DIR || DEFAULT_VERIFY_PY_DIR;
  // Guard against a malformed VERIFY_TIMEOUT_MS (NaN would disable the timeout).
  const rawTimeout = Number(process.env.VERIFY_TIMEOUT_MS);
  const timeout = Number.isFinite(rawTimeout) && rawTimeout > 0 ? rawTimeout : 4000;
  return new Promise((resolve) => {
    const child = execFile(
      python, [VERIFY_PY_CLI],
      { cwd: verifyDir, timeout },
      (err, stdout) => {
        if (err) {
          return resolve({ confirmed: false, unreachable: true,
            reason: `verifier unavailable: ${err.code || err.message}` });
        }
        let v;
        try { v = JSON.parse(stdout); }
        catch {
          return resolve({ confirmed: false, unreachable: true,
            reason: 'verifier returned unparseable output' });
        }
        const confirmed = v.status === 'verified' && Number.isInteger(v.length);
        resolve({
          confirmed,
          status: v.status,
          length: Number.isInteger(v.length) ? v.length : null,
          citation: v.citation || null,
          reason: confirmed ? null
            : `prefix ${prefix} not authority-confirmed (verify.py status=${v.status})`,
        });
      });
    // A verifier that dies before draining stdin makes this write emit EPIPE. Fail
    // CLOSED at the pipe error too: resolve as unreachable — NEVER confirmed — the
    // same shape as the execFile error path. resolve() is idempotent, so whichever
    // fires first (this handler or the callback) wins and the other is a no-op; a
    // stdin error can never leave the promise hanging or promote a row.
    child.stdin.on('error', (e) => resolve({
      confirmed: false, unreachable: true,
      reason: `verifier stdin error: ${e.code || e.message}`,
    }));
    child.stdin.end(JSON.stringify({
      derived_source: derived_source || null,
      vbg_confirm: vbg_confirm || null,
    }));
  });
}

// The party columns the API returns (search_tsv is internal — never exposed).
const PARTY_COLS = `
  id, prefix, gln, legal_name, city, country, mo, lei, duns,
  state, source, exception_reason, verified_at, first_seen, last_updated
`;

// --- GET /health -------------------------------------------------------------
app.get('/health', h(async (_req, res) => {
  const ok = await ping();
  // Report the ACTUAL connected database, not a hardcoded label — the connection
  // is whatever PGDATABASE resolves to, so ask Postgres directly. Leave db null if
  // the lookup fails (ok already reflects reachability).
  let db = null;
  try {
    const { rows } = await q('SELECT current_database() AS db');
    db = rows[0]?.db ?? null;
  } catch (_e) { /* db stays null */ }
  res.json({ ok, service: 'population-api', db });
}));

// --- GET /search -------------------------------------------------------------
// Paginated (keyset on id ASC, max 20). Filters: q (trigram name), state, mo,
// source. Trigram uses the pg_trgm `%` operator so ix_party_legal_name_trgm can
// serve it. Keyset is on id so pagination stays stable across the filtered set.
app.get('/search', h(async (req, res) => {
  const { q: term, state, mo, source } = req.query;
  const limit = pageLimit(req.query.limit);
  const cursor = parseCursor(req.query.cursor);

  if (state !== undefined && !STATES.has(state)) {
    return res.status(400).json({ error: `invalid state '${state}' (candidate|verified|exception)` });
  }

  const where = [];
  const args = [];
  const add = (clause, val) => { args.push(val); where.push(clause.replace('?', `$${args.length}`)); };

  // One search box, three identity handles: name, prefix, GLN. Case-insensitive
  // substring match. legal_name ILIKE is trigram-accelerated (ix_party_legal_name_trgm);
  // prefix/gln are indexed (ux_party_prefix, ix_party_gln). So "0702054" finds a
  // party by prefix, a GLN finds by gln, and text finds by name — all through q.
  // LIKE metachars in the user term are escaped so they match literally.
  if (term) {
    const like = `%${String(term).replace(/[\\%_]/g, '\\$&')}%`;
    args.push(like, like, like);
    const n = args.length;
    where.push(`(legal_name ILIKE $${n - 2} OR prefix ILIKE $${n - 1} OR gln ILIKE $${n})`);
  }
  if (state) add('state = ?', state);
  if (mo) add('mo = ?', mo);
  if (source) add('source = ?', source);
  if (cursor !== null) add('id > ?', cursor);         // keyset

  const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';
  args.push(limit + 1); // fetch one extra to detect has_more without a count.

  const sql = `
    SELECT ${PARTY_COLS}
    FROM party
    ${whereSql}
    ORDER BY id ASC
    LIMIT $${args.length}
  `;
  const { rows } = await q(sql, args);

  const has_more = rows.length > limit;
  const page = has_more ? rows.slice(0, limit) : rows;
  const next_cursor = has_more ? page[page.length - 1].id : null;

  res.json({ rows: page, count: page.length, has_more, next_cursor });
}));

// --- GET /verified -----------------------------------------------------------
// Verified-only feed — the SOLE cross-boundary read the platform consumes.
// Same keyset pagination as /search. Optional mo/source filters.
app.get('/verified', h(async (req, res) => {
  const { mo, source } = req.query;
  const limit = pageLimit(req.query.limit);
  const cursor = parseCursor(req.query.cursor);

  const where = [`state = 'verified'`];
  const args = [];
  const add = (clause, val) => { args.push(val); where.push(clause.replace('?', `$${args.length}`)); };

  if (mo) add('mo = ?', mo);
  if (source) add('source = ?', source);
  if (cursor !== null) add('id > ?', cursor);

  args.push(limit + 1);
  const sql = `
    SELECT ${PARTY_COLS}
    FROM party
    WHERE ${where.join(' AND ')}
    ORDER BY id ASC
    LIMIT $${args.length}
  `;
  const { rows } = await q(sql, args);

  const has_more = rows.length > limit;
  const page = has_more ? rows.slice(0, limit) : rows;
  const next_cursor = has_more ? page[page.length - 1].id : null;

  res.json({ rows: page, count: page.length, has_more, next_cursor });
}));

// --- GET /stats --------------------------------------------------------------
// Counts by state, mo, source, plus a grand total. Cheap aggregate reads.
app.get('/stats', h(async (_req, res) => {
  const [byState, byMo, bySource, total] = await Promise.all([
    q(`SELECT state, count(*)::int AS n FROM party GROUP BY state ORDER BY state`),
    q(`SELECT coalesce(mo, '(none)') AS mo, count(*)::int AS n FROM party GROUP BY mo ORDER BY n DESC, mo`),
    q(`SELECT source, count(*)::int AS n FROM party GROUP BY source ORDER BY n DESC, source`),
    q(`SELECT count(*)::int AS n FROM party`),
  ]);

  const fold = (rows, key) => Object.fromEntries(rows.map((r) => [r[key], r.n]));
  res.json({
    total: total.rows[0].n,
    by_state: fold(byState.rows, 'state'),
    by_mo: fold(byMo.rows, 'mo'),
    by_source: fold(bySource.rows, 'source'),
  });
}));

// --- record assembly (shared by both /record routes) -------------------------
// Returns the party plus its subject-side edges and full event history, or null.
async function loadRecord(party) {
  if (!party) return null;
  const [edges, events] = await Promise.all([
    q(`SELECT id, subject_party_id, rel, object_label, object_prefix, object_party_id,
              state, source, inferred, doc, asserter, valid_from, valid_to, first_seen, last_updated
         FROM edge WHERE subject_party_id = $1 ORDER BY id ASC`, [party.id]),
    q(`SELECT id, event_type, from_state, to_state, detail, source, actor, at
         FROM party_event WHERE party_id = $1 ORDER BY at ASC, id ASC`, [party.id]),
  ]);
  return { party, edges: edges.rows, events: events.rows };
}

// --- GET /record/:id ---------------------------------------------------------
app.get('/record/:id(\\d+)', h(async (req, res) => {
  const { rows } = await q(`SELECT ${PARTY_COLS} FROM party WHERE id = $1`, [req.params.id]);
  const record = await loadRecord(rows[0]);
  if (!record) return res.status(404).json({ error: `no party with id ${req.params.id}` });
  res.json(record);
}));

// --- GET /record/prefix/:prefix ----------------------------------------------
// Prefix is unique among non-null rows (ux_party_prefix), so this resolves to
// at most one party.
app.get('/record/prefix/:prefix', h(async (req, res) => {
  const { rows } = await q(`SELECT ${PARTY_COLS} FROM party WHERE prefix = $1`, [req.params.prefix]);
  const record = await loadRecord(rows[0]);
  if (!record) return res.status(404).json({ error: `no party with prefix ${req.params.prefix}` });
  res.json(record);
}));

// --- POST /party/:id/edge ----------------------------------------------------
// Assert a typed edge on a party — a role stamp, or co-reference via rel='same_as'.
// registrar-does-not-adjudicate: the edge ALWAYS lands `candidate` (an assertion,
// never a verified fact; sameAs is never auto-merged). Stamped with asserter +
// validity window (migration 004). Upserts on the existing assertion unique key
// (ux_edge_assertion: subject_party_id, rel, object_label, source) so re-asserting
// is idempotent. Appends an 'updated' party_event for the provenance spine.
//
// Body: { rel, object_label, object_prefix?, object_party_id?, source?, doc?,
//         asserter?, valid_from?, valid_to?, inferred? }
app.post('/party/:id(\\d+)/edge', requireWriteToken, h(async (req, res) => {
  const id = req.params.id;
  const b = req.body || {};
  if (!b.rel || typeof b.rel !== 'string' || !b.object_label || typeof b.object_label !== 'string') {
    return res.status(400).json({ error: 'rel and object_label are required (non-empty strings)' });
  }
  try {
    const edge = await tx(async (client) => {
      const subj = await client.query(`SELECT id FROM party WHERE id = $1`, [id]);
      if (subj.rows.length === 0) {
        throw Object.assign(new Error(`no party with id ${id}`), { httpStatus: 404 });
      }
      // ALWAYS candidate — the registrar asserts, it does not adjudicate.
      const up = await client.query(
        `INSERT INTO edge (subject_party_id, rel, object_label, object_prefix, object_party_id,
                           state, source, inferred, doc, asserter, valid_from, valid_to)
         VALUES ($1,$2,$3,$4,$5,'candidate',$6,$7,$8,$9,$10,$11)
         ON CONFLICT (subject_party_id, rel, object_label, source) DO UPDATE SET
           object_prefix   = COALESCE(EXCLUDED.object_prefix, edge.object_prefix),
           object_party_id = COALESCE(EXCLUDED.object_party_id, edge.object_party_id),
           inferred        = EXCLUDED.inferred,
           doc             = COALESCE(EXCLUDED.doc, edge.doc),
           asserter        = COALESCE(EXCLUDED.asserter, edge.asserter),
           valid_from      = EXCLUDED.valid_from,
           valid_to        = EXCLUDED.valid_to,
           last_updated    = now()
         RETURNING id, subject_party_id, rel, object_label, object_prefix, object_party_id,
                   state, source, inferred, doc, asserter, valid_from, valid_to, first_seen, last_updated`,
        [id, b.rel, b.object_label, b.object_prefix || null, b.object_party_id || null,
         b.source || 'manual', b.inferred === true, b.doc || null,
         b.asserter || 'manual', b.valid_from || null, b.valid_to || null]);
      const row = up.rows[0];
      // Provenance: the subject party's relationship graph changed.
      await client.query(
        `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
         VALUES ($1,'updated',NULL,NULL,$2,$3,$4)`,
        [id, JSON.stringify({ via: 'POST /party/:id/edge', edge_id: row.id, rel: b.rel,
                              object_label: b.object_label, edge_state: 'candidate' }),
         b.source || 'manual', b.asserter || 'manual']);
      return row;
    });
    res.status(201).json({ ok: true, edge });
  } catch (err) {
    if (err.httpStatus === 404) return res.status(404).json({ error: err.message });
    if (err.code === PG_UNIQUE_VIOLATION) {
      return res.status(409).json({ error: 'conflict', detail: 'edge already asserted', constraint: err.constraint || null });
    }
    throw err;
  }
}));

// --- GET /party/:id/completeness ---------------------------------------------
// Computed-only completeness report — NO mutation, NO fabrication. State-aware: a
// row is `complete` only when `verified` AND carrying the base required fields.
// Missing fields are listed, never invented. `classification` is a Cycle 1 stub
// (the 'classify' screen's hook; real Person/Place/Thing -> schema.org -> GS1-key
// classification is a later cycle, never faked here).
const COMPLETENESS_REQUIRED = ['legal_name', 'prefix', 'gln', 'mo'];
app.get('/party/:id(\\d+)/completeness', h(async (req, res) => {
  const { rows } = await q(`SELECT ${PARTY_COLS} FROM party WHERE id = $1`, [req.params.id]);
  if (rows.length === 0) return res.status(404).json({ error: `no party with id ${req.params.id}` });
  const p = rows[0];
  const has = (f) => p[f] != null && p[f] !== '';
  const present = COMPLETENESS_REQUIRED.filter(has);
  const missing = COMPLETENESS_REQUIRED.filter((f) => !has(f));
  const complete = p.state === 'verified' && missing.length === 0;
  res.json({
    id: p.id,
    state: p.state,
    complete,
    required: COMPLETENESS_REQUIRED,
    present,
    missing,
    classification: { status: 'stub', note: 'classification pending (Cycle 1 stub)', key: null },
  });
}));

// --- POST /ingest ------------------------------------------------------------
// Batch upsert. ALWAYS lands as candidate (or exception when exception_reason is
// present) — NEVER verified, regardless of what the payload says. Upsert key is
// prefix when present (ux_party_prefix); otherwise a plain insert. Each row also
// appends a party_event so the provenance spine records the staging/update.
//
// Body: { rows: [ { legal_name, prefix?, gln?, city?, country?, mo?, lei?, duns?,
//                   source, exception_reason? }, ... ] }   (source defaults to
// the batch-level `source`, else 'ingest').
app.post('/ingest', requireWriteToken, h(async (req, res) => {
  const batch = Array.isArray(req.body) ? req.body : req.body?.rows;
  if (!Array.isArray(batch) || batch.length === 0) {
    return res.status(400).json({ error: 'body must be a non-empty array, or { rows: [...] }' });
  }
  if (batch.length > 1000) {
    return res.status(400).json({ error: `batch too large (${batch.length} > 1000)` });
  }
  const batchSource = (!Array.isArray(req.body) && req.body?.source) || 'ingest';

  const results = await tx(async (client) => {
    const out = [];
    for (let i = 0; i < batch.length; i++) {
      const r = batch[i] || {};
      if (!r.legal_name || typeof r.legal_name !== 'string') {
        throw Object.assign(new Error(`row ${i}: legal_name is required`), { httpStatus: 400 });
      }
      const source = r.source || batchSource;
      // Verified-or-exception, enforced at the door: ingest can never mint verified.
      const state = r.exception_reason ? 'exception' : 'candidate';
      const exceptionReason = r.exception_reason || null;

      // Upsert on prefix only when a prefix is actually present. The partial
      // unique index ux_party_prefix makes ON CONFLICT (prefix) valid here.
      let row, action;
      if (r.prefix) {
        const up = await client.query(
          `INSERT INTO party (prefix, gln, legal_name, city, country, mo, lei, duns,
                              state, source, exception_reason)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
           ON CONFLICT (prefix) WHERE prefix IS NOT NULL
           DO UPDATE SET
             gln              = COALESCE(EXCLUDED.gln, party.gln),
             legal_name       = EXCLUDED.legal_name,
             city             = COALESCE(EXCLUDED.city, party.city),
             country          = COALESCE(EXCLUDED.country, party.country),
             mo               = COALESCE(EXCLUDED.mo, party.mo),
             lei              = COALESCE(EXCLUDED.lei, party.lei),
             duns             = COALESCE(EXCLUDED.duns, party.duns),
             -- NEVER downgrade an already-verified row back to candidate on re-ingest.
             state            = CASE WHEN party.state = 'verified' THEN party.state ELSE EXCLUDED.state END,
             source           = EXCLUDED.source,
             exception_reason = EXCLUDED.exception_reason
           RETURNING id, state, (xmax <> 0) AS updated`,
          [r.prefix, r.gln || null, r.legal_name, r.city || null, r.country || null,
           r.mo || null, r.lei || null, r.duns || null, state, source, exceptionReason],
        );
        row = up.rows[0];
        action = row.updated ? 'updated' : 'inserted';
      } else {
        const ins = await client.query(
          `INSERT INTO party (gln, legal_name, city, country, mo, lei, duns,
                              state, source, exception_reason)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
           RETURNING id, state`,
          [r.gln || null, r.legal_name, r.city || null, r.country || null,
           r.mo || null, r.lei || null, r.duns || null, state, source, exceptionReason],
        );
        row = ins.rows[0];
        action = 'inserted';
      }

      // Provenance spine: one append-only event per ingested row.
      const eventType = action === 'updated'
        ? 'updated'
        : (state === 'exception' ? 'exception' : 'candidate_staged');
      await client.query(
        `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
         VALUES ($1,$2,$3,$4,$5,$6,$7)`,
        [row.id, eventType, null, row.state,
         JSON.stringify({ action, via: 'POST /ingest', index: i }), source, 'ingest'],
      );

      out.push({ index: i, id: row.id, action, state: row.state });
    }
    return out;
  }).catch((err) => {
    if (err.httpStatus) throw err; // surfaced below as a clean 400.
    throw err;
  });

  const summary = results.reduce((a, r) => { a[r.action] = (a[r.action] || 0) + 1; return a; }, {});
  res.status(201).json({ ingested: results.length, summary, results });
}));

// promoteGate — the DB half of POST /gate: flip a locked row to verified with a
// confirmed prefix, stamp verified_at, and append the 'verified' provenance event
// (carrying the resolved prefix LENGTH + authority citation). Assumes authority
// has ALREADY been resolved by the caller (resolvePrefixAuthority().confirmed ===
// true). Like promoteClaim it NEVER consults the verifier, so the promote branch
// is unit-testable in-process without spawning python. The DB CHECK
// (party_gate_prefix_required) stays the final backstop. Runs on the caller's tx
// `client`. Exported for direct testing.
export async function promoteGate(client, before, { prefix, gln, mo, lei, actor, length, citation }) {
  const upd = await client.query(
    `UPDATE party
        SET state       = 'verified',
            prefix      = COALESCE($2, prefix),
            gln         = COALESCE($3, gln),
            mo          = COALESCE($4, mo),
            lei         = COALESCE($5, lei),
            verified_at = now()
      WHERE id = $1
    RETURNING ${PARTY_COLS}`,
    [before.id, prefix || null, gln || null, mo || null, lei || null],
  );
  const after = upd.rows[0];

  await client.query(
    `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
     VALUES ($1,'verified',$2,'verified',$3,'gate',$4)`,
    [before.id, before.state,
     JSON.stringify({ via: 'POST /gate', prefix: after.prefix,
                      prefix_length: length ?? null, authority: citation || null }),
     actor || 'manual'],
  );
  return after;
}

// --- POST /gate/:id ----------------------------------------------------------
// The SOLE promotion path: candidate -> verified. Now FAILS CLOSED on authority,
// mirroring POST /claim: we do NOT flip a row on a bare prefix string. Order:
//   0. format pre-check   non-digits / DEMO / empty -> 422 invalid_prefix
//   1. authority + length via common/verify.py (FAILS CLOSED)
//        verifier could not answer  -> 502 verifier_unavailable  (nothing promoted)
//        answered "not verified"    -> 422 prefix_unconfirmed     (nothing promoted)
//   2. confirmed -> load+lock the row, promoteGate() (verified + length in event)
// The DB CHECK (party_gate_prefix_required) remains the final backstop.
//
// Body: { prefix, actor?, gln?, mo?, lei?, source?, vbg?:{licensee,length,country} }
// `vbg` is the Verified-by-GS1 confirmation payload; without it verify.py cannot
// return 'verified', so promotion is refused. An agent PROPOSES a prefix; only an
// authority-confirmed one REGISTERS.
app.post('/gate/:id(\\d+)', requireWriteToken, h(async (req, res) => {
  const id = req.params.id;
  const prefix = req.body?.prefix;
  const actor = req.body?.actor || 'manual';

  // 0. format pre-check — a DEMO placeholder or empty prefix cannot be promoted.
  if (!isPlainDigits(prefix)) {
    return res.status(422).json({
      error: 'invalid_prefix',
      detail: 'gate requires a real GS1 company prefix (digits only); a DEMO placeholder cannot be promoted',
    });
  }

  // 1. authority + length resolution — FAILS CLOSED (see resolvePrefixAuthority).
  const auth = await resolvePrefixAuthority({
    prefix,
    derived_source: req.body?.source || 'manual',
    vbg_confirm: req.body?.vbg || null,
  });
  if (auth.unreachable) {
    return res.status(502).json({
      error: 'verifier_unavailable',
      detail: auth.reason,
      hint: 'the GS1 prefix verifier (common/verify.py) returned no verdict; nothing was promoted',
    });
  }
  if (auth.confirmed !== true) {
    return res.status(422).json({
      error: 'prefix_unconfirmed',
      detail: auth.reason,
      status: auth.status,
      hint: 'promotion requires an authority-confirmed prefix (Verified by GS1: licensee + length). Supply a "vbg" payload.',
    });
  }

  // 2. confirmed → flip under a row lock. DB CHECK remains the final backstop.
  try {
    const result = await tx(async (client) => {
      const cur = await client.query(`SELECT id, state, prefix FROM party WHERE id = $1 FOR UPDATE`, [id]);
      if (cur.rows.length === 0) {
        throw Object.assign(new Error(`no party with id ${id}`), { httpStatus: 404 });
      }
      return await promoteGate(client, cur.rows[0], {
        prefix, gln: req.body?.gln, mo: req.body?.mo, lei: req.body?.lei,
        actor, length: auth.length, citation: auth.citation,
      });
    });

    res.json({ ok: true, promoted: true, party: result, prefix_length: auth.length });
  } catch (err) {
    if (err.code === PG_CHECK_VIOLATION) {
      return res.status(422).json({
        error: 'gate rejected: a verified party must root in a GS1 prefix',
        constraint: err.constraint || 'party_gate_prefix_required',
        hint: 'supply a non-empty "prefix" in the request body',
      });
    }
    if (err.httpStatus === 404) return res.status(404).json({ error: err.message });
    throw err;
  }
}));

// promoteClaim — steps 4+5 of the claim path (anchor-conflict → atomic in-place
// re-root → immutable party_origin snapshot → prefix_claimed + origin_linked
// events). Extracted so the promote branch is unit-testable by calling it
// directly on a scratch-DB client. It assumes authority has ALREADY been
// confirmed by the caller: the live route reaches it ONLY after
// authorityCheck(...).confirmed === true, and authorityCheck stays fail-closed
// globally. This function never consults authorityCheck, so testing it in-process
// opens no gate. Runs on the caller's tx `client`; throws the same
// httpStatus / PG errors the route maps. Returns { kind:'claimed', party, origin }.
export async function promoteClaim(client, before, { prefix, gln, mo, demo_urn, authority, actor }) {
  const id = before.id;

  // 4. anchor-conflict — never silently overwrite an existing identity anchor.
  if (before.prefix && before.prefix !== prefix) {
    throw Object.assign(
      new Error(`party ${id} is already anchored to prefix ${before.prefix}; claim requested ${prefix}`),
      { httpStatus: 409, code409: 'anchor_conflict' });
  }

  // 5. atomic promote (in-place re-root).
  const upd = await client.query(
    `UPDATE party
        SET prefix      = $2,
            state       = 'verified',
            is_demo     = false,
            gln         = COALESCE($3, gln),
            mo          = COALESCE($4, mo),
            verified_at = now()
      WHERE id = $1 AND state = 'candidate'
    RETURNING ${PARTY_COLS}`,
    [id, prefix, gln || null, mo || null]);
  if (upd.rows.length === 0) {
    // lost the race — the row was resolved between the caller's lock and this update.
    throw Object.assign(new Error(`party ${id} was resolved concurrently`),
      { httpStatus: 409, code409: 'already_resolved' });
  }
  const after = upd.rows[0];

  // freeze the pre-claim identity into the append-only origin ledger.
  const originUrn = before.demo_urn || demo_urn || null;
  const originIns = await client.query(
    `INSERT INTO party_origin (party_id, origin_urn, origin_prefix, claimed_prefix, authority, actor)
     VALUES ($1,$2,$3,$4,$5,$6)
     RETURNING id, claimed_prefix, origin_urn, origin_prefix`,
    [id, originUrn, before.prefix || null, prefix, JSON.stringify(authority || {}), actor]);
  const origin = originIns.rows[0];

  // prefix_claimed — the state change; origin_linked — the provenance link.
  await client.query(
    `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
     VALUES ($1,'prefix_claimed',$2,'verified',$3,'claim',$4)`,
    [id, before.state,
     JSON.stringify({ via: 'POST /claim', claimed_prefix: prefix, origin_urn: originUrn,
                      origin_prefix: before.prefix || null, authority: authority || {} }), actor]);
  await client.query(
    `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
     VALUES ($1,'origin_linked','verified','verified',$2,'claim',$3)`,
    [id, JSON.stringify({ via: 'POST /claim', party_origin_id: origin.id, origin_urn: originUrn,
                          origin_prefix: before.prefix || null }), actor]);

  return { kind: 'claimed', party: after, origin };
}

// --- POST /claim/:id ---------------------------------------------------------
// The self-service re-root: a company claims a candidate / DEMO-staged party by
// rooting it onto its verified GS1 prefix (Model A — in place, id stays stable
// so edges + events follow). Distinct from /gate (the agent/authority promotion
// path): /claim additionally records WHO claimed and writes the immutable
// party_origin snapshot (Caterpillar->Butterfly / TD-M-50).
//
// Resolution order (all in one tx, row locked FOR UPDATE):
//   0. DEMO/format pre-check   bad/absent prefix -> 422 invalid_prefix
//   1. load + lock             missing           -> 404
//   2. state gate              not 'candidate'   -> 409 already_resolved
//   3. authority pre-check     unconfirmed       -> land state='exception' (202, claimed:false)
//   4. anchor-conflict         existing != claim -> 409 anchor_conflict
//   5. promote + party_origin + prefix_claimed + origin_linked -> 200 claimed:true
//
// The authority step FAILS CLOSED (authorityCheck): a claim can never verify on
// thin evidence and never defaults to verified — unconfirmed ownership is a
// named exception, always.
//
// Body: { prefix, actor?, authority?:{gepir?,lei?,doc?}, gln?, mo?, demo_urn? }
app.post('/claim/:id(\\d+)', requireWriteToken, h(async (req, res) => {
  const id = req.params.id;
  const prefix = req.body?.prefix;
  const actor = req.body?.actor || 'claimant';
  const authority = req.body?.authority || {};

  // 0. DEMO / format pre-check — digits-only, no length band (mirrors the DB
  // CHECK party_prefix_digits_only). A '0DEMO...' string has letters, so it is
  // rejected here with a friendly 422 before the DB backstop ever fires.
  if (!prefix || typeof prefix !== 'string' || !/^[0-9]+$/.test(prefix)) {
    return res.status(422).json({
      error: 'invalid_prefix',
      detail: 'claim requires a real GS1 company prefix (digits only); a DEMO placeholder cannot be claimed onto',
    });
  }

  try {
    const outcome = await tx(async (client) => {
      // 1. load + lock the target row.
      const cur = await client.query(
        `SELECT id, state, prefix, is_demo, demo_urn FROM party WHERE id = $1 FOR UPDATE`, [id]);
      if (cur.rows.length === 0) {
        throw Object.assign(new Error(`no party with id ${id}`), { httpStatus: 404 });
      }
      const before = cur.rows[0];

      // 2. state gate — a claim acts only on a candidate.
      if (before.state !== 'candidate') {
        throw Object.assign(
          new Error(`party ${id} is '${before.state}', not claimable (a claim acts only on a candidate)`),
          { httpStatus: 409, code409: 'already_resolved' });
      }

      // 3. authority ownership pre-check — FAILS CLOSED. Anything but a strict
      // `confirmed === true` lands a NAMED exception: no prefix is written (so
      // the row cannot verify) and no party_origin is written (no re-root).
      const auth = authorityCheck({ prefix, party: before, authority });
      if (auth.confirmed !== true) {
        const exc = await client.query(
          `UPDATE party
              SET state = 'exception', exception_reason = $2
            WHERE id = $1 AND state = 'candidate'
          RETURNING ${PARTY_COLS}`,
          [id, auth.reason]);
        await client.query(
          `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
           VALUES ($1,'claim_held',$2,'exception',$3,'claim',$4)`,
          [id, before.state,
           JSON.stringify({ via: 'POST /claim', reason: auth.reason, requested_prefix: prefix }), actor]);
        return { kind: 'held', reason: auth.reason, party: exc.rows[0] };
      }

      // 4 + 5. authority confirmed → anchor-conflict check, atomic in-place
      // re-root, immutable origin snapshot, and the two provenance events.
      // Extracted into promoteClaim() so this branch is unit-testable directly
      // WITHOUT ever opening the real authorityCheck (which stays fail-closed).
      return await promoteClaim(client, before, {
        prefix, gln: req.body?.gln, mo: req.body?.mo, demo_urn: req.body?.demo_urn, authority, actor,
      });
    });

    if (outcome.kind === 'held') {
      return res.status(202).json({
        ok: true, claimed: false, state: 'exception',
        exception_reason: outcome.reason, party: outcome.party,
      });
    }
    return res.status(200).json({ ok: true, claimed: true, party: outcome.party, origin: outcome.origin });
  } catch (err) {
    if (err.code === PG_CHECK_VIOLATION) {
      return res.status(422).json({
        error: 'claim rejected by a database constraint',
        constraint: err.constraint || null,
        hint: 'a verified claim must root in a real GS1 prefix; a DEMO placeholder cannot be claimed',
      });
    }
    if (err.code === PG_UNIQUE_VIOLATION) {
      const c = err.constraint || '';
      const detail = c.includes('party_origin')
        ? 'party already re-rooted (one origin per party)'
        : 'prefix already claimed by another party';
      return res.status(409).json({ error: 'conflict', detail, constraint: c || null });
    }
    if (err.httpStatus) {
      const label = err.code409 || (err.httpStatus === 404 ? 'not_found' : 'conflict');
      return res.status(err.httpStatus).json({ error: label, detail: err.message });
    }
    throw err; // unknown -> h() returns a clean 500.
  }
}));

// --- GIAI mint shim (the asset seam) -----------------------------------------
// Mirrors resolvePrefixAuthority: reach the reference engine's mint() over a
// stdin/stdout shim (mint_cli.py) instead of hand-building a GIAI. FAILS CLOSED —
// any non-ok / unreachable result mints NOTHING. MAP NOTE: mint_cli shims to the
// reference stand-in engine; Pom's authoritative engine replaces it, same contract.
const MINT_PY_CLI = 'mint_cli.py';
function mintGiai({ prefix, component, carriers, source }) {
  const python = process.env.PYTHON || 'python3';
  const dir = process.env.MINT_PY_DIR || process.env.VERIFY_PY_DIR || DEFAULT_VERIFY_PY_DIR;
  const rawTimeout = Number(process.env.MINT_TIMEOUT_MS);
  const timeout = Number.isFinite(rawTimeout) && rawTimeout > 0 ? rawTimeout : 4000;
  return new Promise((resolve) => {
    const child = execFile(python, [MINT_PY_CLI], { cwd: dir, timeout }, (err, stdout) => {
      if (err) return resolve({ ok: false, unreachable: true, error: `mint shim unavailable: ${err.code || err.message}` });
      let v;
      try { v = JSON.parse(stdout); } catch { return resolve({ ok: false, unreachable: true, error: 'mint shim returned unparseable output' }); }
      resolve(v);
    });
    child.stdin.on('error', (e) => resolve({ ok: false, unreachable: true, error: `mint shim stdin error: ${e.code || e.message}` }));
    child.stdin.end(JSON.stringify({ key: 'giai', prefix, component, carriers: carriers || null, source: source || 'SYNTHETIC' }));
  });
}

// --- POST /party/:id/asset ---------------------------------------------------
// Mint a GIAI asset instance rooted in the party's prefix. The ENGINE mints (R9
// numeric, P32 no-alpha, carrier gate) — this route never hand-builds a URN. An
// asset ALWAYS lands `candidate`. Prefix-is-root: a party with no prefix cannot
// root an asset (422). origin_asset_id is the immutable Caterpillar->Butterfly link.
// Body: { component, label?, carriers?, source?, origin_asset_id?, actor? }
app.post('/party/:id(\\d+)/asset', requireWriteToken, h(async (req, res) => {
  const id = req.params.id;
  const { component, label, carriers, source, origin_asset_id } = req.body || {};
  if (!component || !/^[0-9]+$/.test(String(component))) {
    return res.status(422).json({ error: 'invalid_component', detail: 'asset component must be engine-mintable digits (R9); no hand-built or alpha values' });
  }
  const pr = await q('SELECT id, prefix FROM party WHERE id = $1', [id]);
  if (pr.rows.length === 0) return res.status(404).json({ error: `no party with id ${id}` });
  const prefix = pr.rows[0].prefix;
  if (!prefix) {
    return res.status(422).json({ error: 'no_root_prefix', detail: 'prefix-is-root: this party has no prefix yet, so it cannot root an asset. Claim/verify a prefix first.' });
  }
  const m = await mintGiai({ prefix, component: String(component), carriers, source });
  if (!m.ok) {
    const st = m.unreachable ? 502 : 422;
    return res.status(st).json({ error: m.unreachable ? 'mint_unavailable' : 'mint_refused', detail: m.error, kind: m.kind || null });
  }
  try {
    const asset = await tx(async (client) => {
      const ins = await client.query(
        `INSERT INTO asset (party_id, prefix, giai_component, urn, label, origin_asset_id, state, source)
         VALUES ($1,$2,$3,$4,$5,$6,'candidate',$7)
         RETURNING id, party_id, prefix, giai_component, urn, label, origin_asset_id, state, source, first_seen`,
        [id, prefix, String(component), m.urn, label || null, origin_asset_id || null, source || 'manual']);
      const a = ins.rows[0];
      await client.query(
        `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
         VALUES ($1,'asset_minted',null,'candidate',$2,'asset',$3)`,
        [id, JSON.stringify({ via: 'POST /party/:id/asset', asset_id: a.id, urn: a.urn }), req.body?.actor || 'manual']);
      return a;
    });
    res.status(201).json({ ok: true, asset });
  } catch (err) {
    if (err.code === PG_UNIQUE_VIOLATION) return res.status(409).json({ error: 'conflict', detail: 'that GIAI URN already exists (one identity, once)' });
    throw err;
  }
}));


// --- Carrier gate (admissibility, not encoding) ------------------------------
// A carrier is a GATED PROFILE: the engine confirms this asset's URN is admissible
// on a given carrier (RAIN-96 packs the variable part as a number -> numeric only).
// The reference engine returns only the URN; it does NOT emit the encoded
// RAIN-96/GS1-128/DL value. So we store the PROFILE (candidate, value NULL) and
// leave the encoding as the seam Pom's authoritative engine fills. We NEVER
// hand-build a carrier value. Admissibility is re-affirmed through the ONE door
// (mint_cli) -- same engine, same contract.
const CARRIER_TYPES = ['RAIN-96', 'GS1-128', 'DL'];

// --- POST /asset/:id/carrier -------------------------------------------------
// Declare a carrier profile on a minted asset. The ENGINE gates admissibility;
// this route never fabricates an encoded value. The profile ALWAYS lands
// `candidate` with value NULL -- only a real engine-emitted encoding promotes it
// (DB gate: carrier_gate_value_required). Body: { carrier_type, source?, actor? }
app.post('/asset/:id(\\d+)/carrier', requireWriteToken, h(async (req, res) => {
  const id = req.params.id;
  const { carrier_type, source } = req.body || {};
  if (!CARRIER_TYPES.includes(carrier_type)) {
    return res.status(422).json({ error: 'invalid_carrier_type', detail: `carrier_type must be one of ${CARRIER_TYPES.join(', ')}` });
  }
  const ar = await q('SELECT id, party_id, prefix, giai_component, urn FROM asset WHERE id = $1', [id]);
  if (ar.rows.length === 0) return res.status(404).json({ error: `no asset with id ${id}` });
  const asset = ar.rows[0];
  // Gate through the engine (the one door): re-affirm the URN is admissible on
  // this carrier. Deterministic -- returns the SAME urn or a carrier refusal.
  const g = await mintGiai({ prefix: asset.prefix, component: asset.giai_component, carriers: [carrier_type], source });
  if (!g.ok) {
    const st = g.unreachable ? 502 : 422;
    return res.status(st).json({ error: g.unreachable ? 'gate_unavailable' : 'carrier_refused', detail: g.error, kind: g.kind || null });
  }
  if (g.urn !== asset.urn) {
    // engine disagreed with the stored URN -- never paper over it.
    return res.status(500).json({ error: 'gate_inconsistent', detail: 'engine returned a different URN than the asset holds' });
  }
  try {
    const carrier = await tx(async (client) => {
      const ins = await client.query(
        `INSERT INTO carrier (asset_id, carrier_type, value, state, source)
         VALUES ($1,$2,null,'candidate',$3)
         RETURNING id, asset_id, carrier_type, value, state, source, first_seen`,
        [id, carrier_type, source || 'manual']);
      const c = ins.rows[0];
      await client.query(
        `INSERT INTO party_event (party_id, event_type, from_state, to_state, detail, source, actor)
         VALUES ($1,'carrier_declared',null,'candidate',$2,'carrier',$3)`,
        [asset.party_id, JSON.stringify({ via: 'POST /asset/:id/carrier', asset_id: id, carrier_id: c.id, carrier_type, urn: asset.urn }), req.body?.actor || 'manual']);
      return c;
    });
    res.status(201).json({ ok: true, carrier });
  } catch (err) {
    if (err.code === PG_UNIQUE_VIOLATION) return res.status(409).json({ error: 'conflict', detail: 'that carrier profile already exists for this asset (one profile per carrier)' });
    throw err;
  }
}));

// --- GET /party/:id/epcis ----------------------------------------------------
// EPCIS-shaped READ PROJECTION of the provenance ledger. NOT a stored or authored
// EPCIS document -- it projects the party's URN-bearing thing-events
// (asset_minted, carrier_declared) into EPCIS 2.0 ObjectEvent shape. Registry
// lifecycle events without an EPC (candidate_staged, verified, prefix_claimed on
// the party itself) are not projected -- EPCIS describes THINGS, not legal parties.
// Edge -> AggregationEvent projection is the next slice.
const EPCIS_MAP = {
  asset_minted:     { action: 'ADD', bizStep: 'urn:epcglobal:cbv:bizstep:commissioning' },
  carrier_declared: { action: 'ADD', bizStep: 'urn:thingdaddy:bizstep:encoding' }, // non-CBV: TD namespace, honest
};
function toEpcisEvent(pe) {
  const urn = pe.detail && pe.detail.urn;
  if (!urn) return null;                        // no EPC -> not an EPCIS thing-event
  const m = EPCIS_MAP[pe.event_type] || { action: 'OBSERVE', bizStep: null };
  return {
    eventType: 'ObjectEvent',
    eventTime: pe.at,
    action: m.action,
    epcList: [urn],
    bizStep: m.bizStep,
    disposition: null,
    readPoint: null,
    recordTime: pe.at,
    'thingdaddy:source': pe.source,
    'thingdaddy:recordedBy': pe.actor,
    'thingdaddy:registryEventType': pe.event_type,
  };
}
app.get('/party/:id(\\d+)/epcis', h(async (req, res) => {
  const id = req.params.id;
  const pr = await q('SELECT id FROM party WHERE id = $1', [id]);
  if (pr.rows.length === 0) return res.status(404).json({ error: `no party with id ${id}` });
  const evs = await q(
    `SELECT event_type, detail, source, actor, at FROM party_event WHERE party_id = $1 ORDER BY at ASC, id ASC`, [id]);
  const eventList = [];
  let omitted = 0;
  for (const pe of evs.rows) {
    const e = toEpcisEvent(pe);
    if (e) eventList.push(e); else omitted++;
  }
  res.json({
    isA: 'EPCISDocument',
    schemaVersion: '2.0',
    projection: true,   // NOT a stored/conformant EPCIS document -- a read projection.
    note: 'EPCIS-shaped projection of the provenance ledger. Registry lifecycle events without an EPC are not projected.',
    epcisBody: { eventList },
    registryEventsOmitted: omitted,
  });
}));


// --- GET /party/:id/assets ---------------------------------------------------
// Read a party's minted assets (GIAI instances). Read-only, no gate concerns —
// the write path (POST /party/:id/asset) is where the engine + prefix-is-root
// rules live. Returns [] for a party with no assets (honest empty, never faked).
app.get('/party/:id(\\d+)/assets', h(async (req, res) => {
  const id = req.params.id;
  const pr = await q('SELECT id FROM party WHERE id = $1', [id]);
  if (pr.rows.length === 0) return res.status(404).json({ error: `no party with id ${id}` });
  const r = await q(
    `SELECT id, party_id, prefix, giai_component, urn, label, origin_asset_id, state, source, first_seen
       FROM asset WHERE party_id = $1 ORDER BY first_seen ASC, id ASC`, [id]);
  res.json({ assets: r.rows });
}));

// --- GET /asset/:id/carriers -------------------------------------------------
// Read an asset's carrier profiles. `value` is NULL for a declared-but-unencoded
// profile (the encoding is Pom's engine seam) — the UI renders that as "encoding
// pending", never a fabricated carrier value.
app.get('/asset/:id(\\d+)/carriers', h(async (req, res) => {
  const id = req.params.id;
  const ar = await q('SELECT id FROM asset WHERE id = $1', [id]);
  if (ar.rows.length === 0) return res.status(404).json({ error: `no asset with id ${id}` });
  const r = await q(
    `SELECT id, asset_id, carrier_type, value, state, source, first_seen
       FROM carrier WHERE asset_id = $1 ORDER BY carrier_type ASC, id ASC`, [id]);
  res.json({ carriers: r.rows });
}));

// --- Cycle 3 spine reads (node + association) --------------------------------
// Read the unified graph spine ALONGSIDE the legacy tables (pre-cutover). Additive,
// read-only — no write path rewires yet. The spine is populated by migration 011.

// GET /node/:id — a single spine node (any key_type).
app.get('/node/:id(\\d+)', h(async (req, res) => {
  const r = await q('SELECT * FROM node WHERE id = $1', [req.params.id]);
  if (r.rows.length === 0) return res.status(404).json({ error: `no node with id ${req.params.id}` });
  res.json({ node: r.rows[0] });
}));

// GET /node/:id/associations — the node's one-hop neighborhood (both directions),
// bounded. Each row carries the neighbor's urn/label/legal_name/key_type for rendering.
app.get('/node/:id(\\d+)/associations', h(async (req, res) => {
  const id = req.params.id;
  const nr = await q('SELECT id FROM node WHERE id = $1', [id]);
  if (nr.rows.length === 0) return res.status(404).json({ error: `no node with id ${id}` });
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 500) : 100;
  const r = await q(
    `SELECT a.id, a.rel, a.attributes, a.state, a.inferred, a.source,
            CASE WHEN a.subject_node_id = $1 THEN 'out' ELSE 'in' END AS direction,
            a.subject_node_id, a.object_node_id,
            sn.urn AS subject_urn, sn.label AS subject_label, sn.legal_name AS subject_legal_name, sn.key_type AS subject_key_type,
            onode.urn AS object_urn, onode.label AS object_label, onode.legal_name AS object_legal_name, onode.key_type AS object_key_type
       FROM association a
       JOIN node sn    ON sn.id = a.subject_node_id
       JOIN node onode ON onode.id = a.object_node_id
      WHERE a.subject_node_id = $1 OR a.object_node_id = $1
      ORDER BY a.id
      LIMIT $2`, [id, limit]);
  res.json({ node_id: Number(id), associations: r.rows, bounded_at: limit });
}));


// GET /node/by-legacy/party/:partyId — resolve a party's spine node via its
// legacy ref. The UI bridge: the workspace holds a party id; the spine is keyed
// by node id. 404 when the spine hasn't been backfilled for this party (honest —
// the UI shows "not on the spine yet", never fakes a node).
app.get('/node/by-legacy/party/:partyId(\\d+)', h(async (req, res) => {
  const pid = req.params.partyId;
  const r = await q(`SELECT * FROM node WHERE key_type = 'pgln' AND legacy->>'party_id' = $1`, [pid]);
  if (r.rows.length === 0) return res.status(404).json({ error: `no spine node backfilled for party ${pid}` });
  res.json({ node: r.rows[0] });
}));

// ============================================================================
// TIER 1 READ-ONLY ENDPOINTS
//
// Four GETs that give the Tier 1 screens real answers instead of mockups.
// Nothing here writes. Nothing here mints.
//
// THE CONTAINMENT RULE: a GS1 prefix that is a strict leading substring of
// another prefix is arithmetically impossible — licences do not nest. Every
// hit is a bad cut, a mis-filing, a subsidiary filing inside the parent's
// licence, or misuse. All four look identical. WE REPORT THE CONTAINMENT;
// THE LICENSEE REPORTS THE CAUSE.
// ============================================================================

// GET /containment/:prefix — both directions for one prefix.
//   inside : prefixes that START WITH this one — allocated in its namespace
//   outside: prefixes this one starts with — this row may sit inside another
app.get('/containment/:prefix(\\d+)', h(async (req, res) => {
  const p = req.params.prefix;

  const inside = await q(
    `SELECT id, prefix, gln, legal_name, state, source, mo, first_seen
       FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1
      ORDER BY length(prefix), prefix
      LIMIT 200`, [p]);

  // Bounded by construction: at most 8 probes against ux_party_prefix.
  const outside = await q(
    `SELECT pp.id, pp.prefix, pp.gln, pp.legal_name, pp.state, pp.source, pp.mo
       FROM generate_series(4, greatest(length($1) - 1, 4)) n
       JOIN party pp ON pp.prefix = left($1, n) AND pp.prefix <> $1
      ORDER BY length(pp.prefix)`, [p]);

  const self = await q(
    `SELECT id, prefix, gln, legal_name, state, source, mo FROM party WHERE prefix = $1`, [p]);

  res.json({
    prefix: p,
    holders: self.rows,                    // may be 0, 1 or more
    inside: inside.rows,
    outside: outside.rows,
    finding: (inside.rows.length || outside.rows.length) ? 'containment' : 'none',
    note: 'A containment is a FACT, not a verdict. A bad cut, a mis-filing, a '
        + 'subsidiary filing inside the parent licence, and misuse all look '
        + 'identical here. Only the licensee knows which.',
  });
}));

// GET /containment — the estate-wide sweep. Paged; never returns everything.
app.get('/containment', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 500) : 100;
  const rawOffset = Number(req.query.offset);
  const offset = Number.isFinite(rawOffset) && rawOffset > 0 ? rawOffset : 0;

  const { rows } = await q(
    `SELECT a.id   AS child_id,   a.prefix AS child,  a.legal_name AS child_name,
            a.source AS child_source, a.state AS child_state, a.gln AS child_gln,
            b.id   AS parent_id,  b.prefix AS parent, b.legal_name AS parent_name,
            b.source AS parent_source, b.state AS parent_state
       FROM party a
       JOIN LATERAL (
            SELECT p.id, p.prefix, p.legal_name, p.source, p.state
              FROM generate_series(4, greatest(length(a.prefix) - 1, 4)) n
              JOIN party p ON p.prefix = left(a.prefix, n) AND p.prefix <> a.prefix
             ORDER BY length(p.prefix)
             LIMIT 1
       ) b ON true
      WHERE a.prefix IS NOT NULL
      ORDER BY b.prefix, a.prefix
      LIMIT $1 OFFSET $2`, [limit, offset]);

  res.json({
    rows, count: rows.length, limit, offset,
    has_more: rows.length === limit,
    note: 'Containment is arithmetic over digits — no name matching, no '
        + 'judgement. The register reports it; the licensee explains it.',
  });
}));

// GET /exceptions — what we looked at and could not resolve, named.
// A declared gap is stronger than a blank. This is a trust exhibit.
app.get('/exceptions', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 500) : 100;
  const rawOffset = Number(req.query.offset);
  const offset = Number.isFinite(rawOffset) && rawOffset > 0 ? rawOffset : 0;
  const reason = typeof req.query.reason === 'string' && req.query.reason ? req.query.reason : null;

  const byReason = await q(
    `SELECT coalesce(exception_reason, '<<unnamed>>') AS reason, count(*)::int AS n
       FROM party
      WHERE state = 'exception'
      GROUP BY 1 ORDER BY n DESC`);

  const rows = reason
    ? await q(`SELECT id, prefix, gln, legal_name, state, source, mo, exception_reason, last_updated
                 FROM party WHERE state = 'exception' AND exception_reason = $1
                ORDER BY id LIMIT $2 OFFSET $3`, [reason, limit, offset])
    : await q(`SELECT id, prefix, gln, legal_name, state, source, mo, exception_reason, last_updated
                 FROM party WHERE state = 'exception'
                ORDER BY id LIMIT $1 OFFSET $2`, [limit, offset]);

  const total = byReason.rows.reduce((a, r) => a + r.n, 0);

  res.json({
    total,
    by_reason: byReason.rows,
    rows: rows.rows,
    count: rows.rows.length,
    limit, offset,
    has_more: rows.rows.length === limit,
    note: 'An exception is a thing we looked at and could not resolve, named. '
        + 'It is not a failure to hide — it is the reason the other grades mean '
        + 'anything.',
  });
}));

// GET /estate — party rows sharing a name fold.
//
// production's party.prefix is SCALAR under a unique index, so a company with
// four licences appears as FOUR ROWS. Grouping them is a CANDIDATE ASSERTION
// on name-fold evidence, never a claim that they are the same legal entity.
// The registrar does not adjudicate co-reference.
app.get('/estate', h(async (req, res) => {
  const fold = typeof req.query.fold === 'string' && req.query.fold ? req.query.fold : null;
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 200) : 50;

  if (fold) {
    const { rows } = await q(
      `SELECT id, prefix, gln, legal_name, state, source, mo, exception_reason
         FROM party WHERE name_fold = $1 ORDER BY (prefix IS NULL), prefix`, [fold]);
    return res.json({
      fold, rows, count: rows.length,
      rooted: rows.filter((r) => r.prefix).length,
      unrooted: rows.filter((r) => !r.prefix).length,
      grade: 'candidate',
      note: 'These rows share a name fold. That is EVIDENCE of one enterprise, '
          + 'not a ruling that they are one. Grade: candidate. The owner confirms.',
    });
  }

  const { rows } = await q(
    `SELECT name_fold,
            min(legal_name)                                  AS example_name,
            count(*)::int                                    AS rows,
            count(prefix)::int                               AS rooted,
            count(*) FILTER (WHERE prefix IS NULL)::int      AS unrooted,
            count(DISTINCT mo)::int                          AS mos
       FROM party
      WHERE name_fold IS NOT NULL
      GROUP BY name_fold
     HAVING count(prefix) > 1
      ORDER BY count(prefix) DESC, name_fold
      LIMIT $1`, [limit]);

  res.json({
    rows, count: rows.length, limit, grade: 'candidate',
    note: 'Multi-licence estates, grouped on name fold. Candidate evidence, '
        + 'never an assertion. A name fold is the least reliable operation in '
        + 'the system and is recorded here as such.',
  });
}));

// GET /claims/grades — the pillar x grade matrix. Feeds "the register at a
// glance". NULL is its own bucket and is never collapsed into a grade.
app.get('/claims/grades', h(async (_req, res) => {
  const { rows } = await q(
    `SELECT pillar, coalesce(grade, '<<NULL>>') AS grade, count(*)::int AS n
       FROM content_claim GROUP BY 1, 2 ORDER BY 1, 2`);

  const matrix = {};
  let total = 0, ungraded = 0;
  for (const r of rows) {
    matrix[r.pillar] = matrix[r.pillar] || {};
    matrix[r.pillar][r.grade] = r.n;
    total += r.n;
    if (r.grade === '<<NULL>>') ungraded += r.n;
  }

  res.json({
    total, ungraded, matrix,
    grades: ['v', 'c', 'e', 'b', 'slot'],
    note: ungraded > 0
      ? `${ungraded} claim(s) carry NO GRADE. content_claim_grade_valid is a `
        + 'CHECK, and a CHECK PASSES ON NULL — so the constraint reads as '
        + 'enforced and is not. Reported, not hidden.'
      : 'Every claim carries a grade.',
  });
}));

// ============================================================================
// CLAIM READ ENDPOINTS
//
// content_claim over HTTP, so the five pillars render what the register holds
// instead of five empty slots. Both routes are GET; nothing writes.
//
// tx is where the source lives and it travels WHOLE. A claim without its tx is
// a number with no provenance. The screen may shorten it; the API does not.
// ============================================================================

async function claimsForParty(partyId, limit) {
  const { rows } = await q(
    `SELECT id, pillar, section, display_order, nm, identifier, grade, tx, doc_key,
            first_seen, last_updated
       FROM content_claim
      WHERE party_id = $1
      ORDER BY pillar, display_order, id
      LIMIT $2`, [partyId, limit]);

  // Grouped by pillar for rendering; NULL grade is its own bucket and is never
  // folded into a grade. content_claim_grade_valid is a CHECK, and a CHECK
  // PASSES ON NULL — so an ungraded row is a real state that must be visible.
  const pillars = {};
  const counts  = {};
  let ungraded = 0;
  for (const r of rows) {
    (pillars[r.pillar] = pillars[r.pillar] || []).push(r);
    const g = r.grade == null ? '<<NULL>>' : r.grade;
    counts[r.pillar] = counts[r.pillar] || {};
    counts[r.pillar][g] = (counts[r.pillar][g] || 0) + 1;
    if (r.grade == null) ungraded++;
  }
  return { rows, pillars, counts, ungraded, total: rows.length };
}

// GET /party/:id/claims
app.get('/party/:id(\\d+)/claims', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 2000) : 500;

  const p = await q(`SELECT ${PARTY_COLS} FROM party WHERE id = $1`, [req.params.id]);
  if (p.rows.length === 0)
    return res.status(404).json({ error: `no party with id ${req.params.id}` });

  const c = await claimsForParty(req.params.id, limit);
  res.json({
    party: p.rows[0],
    ...c,
    limit,
    truncated: c.total === limit,
    note: c.total === 0
      ? 'This party holds no content claims. That is an empty register for this '
        + 'row, not a rendering failure — and an empty pillar is a declared gap.'
      : 'Every claim carries its grade and its tx. tx is where the source lives.',
  });
}));

// GET /prefix/:prefix/claims — the prefix is the key; a screen should not need
// to know a party id to read the record.
app.get('/prefix/:prefix(\\d+)/claims', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 2000) : 500;

  const p = await q(`SELECT ${PARTY_COLS} FROM party WHERE prefix = $1`, [req.params.prefix]);
  if (p.rows.length === 0)
    return res.status(404).json({ error: `no party with prefix ${req.params.prefix}` });

  // ux_party_prefix makes this one row today. Under the 4 September ruling a
  // prefix may carry MANY claims from many sources, so the shape stays plural.
  const out = [];
  for (const row of p.rows) out.push({ party: row, ...(await claimsForParty(row.id, limit)) });

  res.json({
    prefix: req.params.prefix,
    holders: out.length,
    records: out,
    limit,
    note: 'One prefix, one ThingSite. Where more than one row holds a prefix, all '
        + 'are returned — duplicates are shown, never merged silently.',
  });
}));

// ============================================================================
// AGENT-FIRST RECORD
//
// Ratified 2026-07-12: ask what the graph's consumer -- the agent -- needs.
// A bare number is only a CANDIDATE for context. This endpoint makes the
// context travel.
//
// THE PREFIX IS THE SUBJECT. Everything else is a dated, sourced, graded
// claim about it. The screen renders from this; this never renders for the
// screen.
// ============================================================================

// The five grades. party.state uses a three-value vocabulary; content_claim
// uses the five. ONE vocabulary reaches an agent.
const AG_GRADE = { verified: 'v', candidate: 'c', exception: 'e',
                   v: 'v', c: 'c', e: 'e', b: 'b', slot: 'slot' };
const agGrade = (s) => AG_GRADE[s] || 'slot';

// A display string carrying several values is SPLIT, and the split is
// declared. " · " is our own rendering join -- undoing it is a repair of our
// defect, not an interpretation of the source.
const AG_JOIN = /\s+·\s+/;
function agSplit(identifier) {
  if (identifier == null) return { values: [], split: false };
  const s = String(identifier);
  if (!AG_JOIN.test(s)) return { values: [s], split: false };
  return { values: s.split(AG_JOIN).map((x) => x.trim()).filter(Boolean), split: true };
}

// Provenance as STRUCTURE. What can be lifted from a column is lifted; what
// only exists in the prose stays in `rendered`. NOTHING IS PARSED OUT OF THE
// PROSE BY GUESSWORK -- a regex over a sentence is exactly the kind of
// derivation that invents a well-formed value.
function agProv(row, extra) {
  const p = {
    source: row.source || null,
    source_kind:
      row.source === 'GUDID' ? 'regulator-filing'
      : row.source === 'GDSN' ? 'pooled-feed'
      : row.source === 'EUDAMED' ? 'regulator-filing'
      : row.source === 'seed' ? 'seeded'
      : (row.source || '').startsWith('gepir') ? 'retired-registry'
      : 'unclassified',
    first_seen: row.first_seen || null,
    last_updated: row.last_updated || null,
    verified_at: row.verified_at || null,
    rendered: row.tx || null,
    rendered_is_prose: !!row.tx,
  };
  if (p.source_kind === 'retired-registry')
    p.note = 'GEPIR was retired 31 December 2023. This row is almost certainly '
           + 'a correct hand-read recorded under a name that no longer exists. '
           + 'Reported, not silently renamed.';
  if (p.source_kind === 'pooled-feed')
    p.note = 'A pooled feed is not a filing. Ruled 3 September 2026.';
  if (p.source_kind === 'seeded')
    p.note = 'A row whose source is "seed" was not attested by any authority.';
  return Object.assign(p, extra || {});
}

const agValue = (value, grade, prov) => ({ value, grade: agGrade(grade), provenance: prov });

// ── the authority register ──────────────────────────────────────────────────
// population/standards/authority_reads.json is a HUMAN'S READ OF THE AUTHORITY'S
// OWN DISPLAY, screen filed. It is read AT REQUEST TIME, never cached: the
// register can change between two requests and the API must never serve a
// reading the file has since withdrawn.
//
// Why this exists — the 5 September 2026 supersession. 0817089 had sat in
// verified_prefixes.json since 20 July labelled GEPIR-verified. GEPIR was
// retired 31 December 2023, so no authority could have been consulted: 0817089
// was a plausible parse of GLN 0817089020009, never a licence key. On 5 Sep KJ
// read Verified by GS1 (gs1.org) and filed IMG_6519.PNG: the licence is
// 081708902. The old value is NOT deleted — a published book cites it 41 times
// and 252 nodes root on it — but the API must say, on every record it serves
// for it, that the authority holds something else. A prefix the DB still
// roots nodes on is not thereby a prefix GS1 ever delegated.
const AUTHORITY_REGISTER = path.resolve(__dirname, '../standards/authority_reads.json');
function readAuthorityRegister() {
  try {
    const j = JSON.parse(readFileSync(AUTHORITY_REGISTER, 'utf8'));
    return { reads: j.reads || [], superseded: j.superseded || [], error: null };
  } catch (err) {
    // A register that cannot be read is a DECLARED GAP, not a silent "nothing
    // superseded". The caller reports it.
    return { reads: [], superseded: [], error: String(err.message || err).slice(0, 240) };
  }
}
// What the authority register says about one prefix. Exact string match on the
// value — nothing is parsed, derived or prefix-matched here.
function authorityFor(pfx) {
  const reg = readAuthorityRegister();
  const sup = reg.superseded.find((x) => String(x.value) === String(pfx)) || null;
  const read = reg.reads.find((x) => String(x.licence_key) === String(pfx)
                                    && x.grade === 'confirmed') || null;
  const out = { error: reg.error, supersession: null, authority_confirmed: null };
  if (sup) {
    // The capture belongs to the read that superseded it, when one is filed.
    const by = sup.superseded_by
      ? reg.reads.find((x) => String(x.licence_key) === String(sup.superseded_by)) : null;
    out.supersession = { superseded_by: sup.superseded_by || null, on: sup.on || null,
                         why: sup.why || null, capture: (by && by.capture) || null };
  }
  if (read) out.authority_confirmed = { read_at: read.read_at || null, capture: read.capture || null };
  return out;
}
// The two optional top-level blocks, spread into a response. Absent keys stay
// absent — a record with neither block carries neither.
function authorityBlocks(a) {
  const b = {};
  if (a.supersession) b.supersession = a.supersession;
  if (a.authority_confirmed) b.authority_confirmed = a.authority_confirmed;
  return b;
}
const authorityGap = (a) => a.error
  ? [{ field: 'authority_register', why: 'population/standards/authority_reads.json could not be read',
       detail: a.error,
       consequence: 'supersession and authority_confirmed are NOT reported. Their absence '
                  + 'here is a failure to read, NOT a statement that the authority agrees.' }]
  : [];

// GET /agent/prefix/:prefix
app.get('/agent/prefix/:prefix(\\d+)', h(async (req, res) => {
  const pfx = req.params.prefix;
  const authority = authorityFor(pfx);

  const holders = await q(`SELECT ${PARTY_COLS} FROM party WHERE prefix = $1`, [pfx]);
  if (holders.rows.length === 0) {
    // An honest not-found is a real answer, and it says what WOULD resolve it.
    // The authority may still have spoken about a prefix the register holds no
    // party for (081708902 on 5 Sep): that is reported here too.
    return res.status(404).json({
      subject: { prefix: pfx, resolves: false },
      grade: 'e',
      reason: 'no-holder-on-record',
      statement: 'The register holds no party rooted on this prefix. NEVER FABRICATED.',
      ...authorityBlocks(authority),
      gaps: authorityGap(authority),
      ask: { containment: `/agent/prefix/${pfx}/containment` },
    });
  }
  const gaps = authorityGap(authority);

  // ── the subject ─────────────────────────────────────────────────────────
  const subject = {
    prefix: pfx,
    length: pfx.length,
    length_method: 'arithmetic — char_length of the prefix, not a lookup',
    holders_on_record: holders.rows.length,
    holders_note: holders.rows.length > 1
      ? 'MORE THAN ONE ROW HOLDS THIS PREFIX. Both are returned. Duplicates are '
        + 'shown, never merged silently, and the registrar does not adjudicate '
        + 'which is right.'
      : null,
  };

  // ── claims, one value per field, grade on the value ─────────────────────
  const claims = { legal_name: [], gln: [], mo: [], duns: [], lei: [],
                   city: [], country: [], licence_type: [] };

  for (const r of holders.rows) {
    const prov = agProv(r, { party_id: String(r.id) });
    const g = agGrade(r.state);
    const put = (k, v) => { if (v != null && v !== '') claims[k].push(agValue(v, g, prov)); };
    put('legal_name', r.legal_name);
    put('gln', r.gln);
    put('mo', r.mo);
    put('duns', r.duns);
    put('lei', r.lei);
    put('city', r.city);
    put('country', r.country);
    put('licence_type', r.licence_type);

    if (r.exception_reason)
      gaps.push({ field: 'state', why: r.exception_reason, party_id: String(r.id),
                  blocks: ['verified'] });
    if (!r.licence_type)
      gaps.push({ field: 'licence_type', why: 'not read', party_id: String(r.id),
                  blocks: ['verified'],
                  rule: 'licence_type absent => candidate, never root (4 Sep 2026)' });
    if (!r.mo)
      gaps.push({ field: 'mo', why: 'not read', party_id: String(r.id),
                  rule: 'mo is RECORDED from an authority or NULL. Deriving it from '
                      + 'the prefix digits is mo-band, forbidden since 18 Jul 2026.' });
  }

  // ── what is rooted here, one value per row, splits declared ─────────────
  const ids = holders.rows.map((r) => r.id);
  const cl = await q(
    `SELECT pillar, section, nm, identifier, grade, tx, doc_key, party_id
       FROM content_claim WHERE party_id = ANY($1::bigint[])
      ORDER BY pillar, display_order, id LIMIT 800`, [ids]);

  const attached = [];
  let splitCount = 0;
  for (const c of cl.rows) {
    const s = agSplit(c.identifier);
    if (s.split) splitCount++;
    for (const v of (s.values.length ? s.values : [null])) {
      attached.push({
        pillar: c.pillar, section: c.section, name: c.nm,
        value: v,
        grade: agGrade(c.grade),
        grade_is_null: c.grade == null,
        split_from_display: s.split,
        provenance: { rendered: c.tx || null, rendered_is_prose: !!c.tx,
                      doc_key: c.doc_key || null, party_id: String(c.party_id) },
      });
    }
    if (c.grade == null)
      gaps.push({ field: 'grade', why: 'this claim carries NO grade',
                  detail: 'content_claim_grade_valid is a CHECK, and a CHECK PASSES '
                        + 'ON NULL. The constraint reads as enforced and is not.',
                  claim: c.nm });
  }

  // ── findings in this namespace ──────────────────────────────────────────
  const inside = await q(
    `SELECT id, prefix, gln, legal_name, state, source FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1 ORDER BY length(prefix) LIMIT 50`, [pfx]);

  // ── the actor layer, which is entirely absent and says so ───────────────
  const actors = {
    grade: 'slot',
    gsrn: null, srin: null,
    statement: 'NO ACTOR IDENTITY IS HELD FOR THIS NAMESPACE. An enforced limit '
             + 'stops an unsafe VALUE; it cannot stop an unauthorised ACTOR. '
             + 'Without a GSRN there is no answer to "who performed this action", '
             + 'and without an SRIN no answer to "which revision of it".',
  };

  res.json({
    record: 'thingdaddy.agent.v1',
    generated_at: new Date().toISOString(),
    shaped_for: 'a consumer that has never seen the page',

    // present only when the authority register says so — see authorityFor()
    ...authorityBlocks(authority),

    subject,
    claims,
    attached,
    keys_attached: attached.length,
    display_strings_split: splitCount,
    split_note: splitCount
      ? 'Some identifiers were stored as a single display string joining several '
        + 'values with " · ". They are split here and the split is flagged. THIS IS '
        + 'A REPAIR OF OUR OWN DEFECT: a value that can only be read by eye is not '
        + 'in context.'
      : null,

    findings: {
      containment: inside.rows.map((r) => ({
        prefix: r.prefix, holder: r.legal_name, gln: r.gln,
        source: r.source, grade: agGrade(r.state),
        relation: 'issued-inside',
        statement: 'This key sits inside the subject prefix. GS1 licences do not '
                 + 'nest, so only the licensee allocates there. A FACT, NOT A '
                 + 'VERDICT -- a bad cut, a mis-filing, a subsidiary, and misuse '
                 + 'all look identical here, and only the licensee knows which.',
      })),
    },

    capability: { grade: 'slot',
      statement: 'No capability surface is served from this API. SiLA Features and '
               + 'envelope bounds exist as files, not as records.' },
    actors,

    gaps,
    gap_policy: 'A DECLARED GAP IS STRONGER THAN A BLANK. Absence of evidence is a '
              + 'candidate, never an exception, never a guess. null is a refused key.',

    grades: { v: 'verified — an authority attested it',
              c: 'candidate — found, nothing has attested it',
              e: 'exception — looked at, could not resolve, named',
              b: 'built', slot: 'a declared gap' },
    grade_note: 'There is no grade for "we guessed", because nothing is guessed.',

    ask: {
      containment: `/agent/prefix/${pfx}/containment`,
      claims_full: holders.rows[0] ? `/prefix/${pfx}/claims` : null,
      human_page: `/record/prefix/${pfx}`,
      what_else: `/agent/prefix/${pfx}/ask`,
    },
  });
}));

// GET /agent/prefix/:prefix/ask — what can be asked, and what cannot.
// An agent should not have to discover our limits by hitting them.
app.get('/agent/prefix/:prefix(\\d+)/ask', h(async (req, res) => {
  const pfx = req.params.prefix;
  res.json({
    subject: { prefix: pfx },
    answerable: [
      { question: 'who holds this prefix, and on what evidence',
        at: `/agent/prefix/${pfx}`, grade_ceiling: 'v' },
      { question: 'what keys are rooted here',
        at: `/prefix/${pfx}/claims`, grade_ceiling: 'v' },
      { question: 'is anything filed inside this licence',
        at: `/containment/${pfx}`, grade_ceiling: 'v' },
      { question: 'how complete is this record',
        at: '/party/:id/completeness', grade_ceiling: 'v' },
    ],
    not_answerable: [
      { question: 'what may this instrument do',
        why: 'capability surfaces are files, not records. Not served.' },
      { question: 'what materials may it contact, and at what pH',
        why: 'ENVELOPE BOUNDS HAVE NOT BEEN HARVESTED. A user-guide bounds pass '
           + 'is owed. This is the axis a composition check cannot fire on today.' },
      { question: 'who may act on this, and in what role',
        why: 'no GSRN and no SRIN are held. There is no actor layer.' },
      { question: 'what is this thing worth, or should I buy it',
        why: 'not a question a registrar answers. We register and resolve.' },
    ],
    never_answerable: [
      { question: 'mint me an identifier',
        why: 'THE CUSTOMER MINTS. Nothing is ever minted by ThingDaddy.' },
      { question: 'which of two conflicting claims is correct',
        why: 'the registrar does not adjudicate. Both publish, dated and sourced, '
           + 'and the licensee answers.' },
    ],
  });
}));

// GET /agent/prefix/:prefix/containment — the finding, agent-shaped.
app.get('/agent/prefix/:prefix(\\d+)/containment', h(async (req, res) => {
  const pfx = req.params.prefix;
  const inside = await q(
    `SELECT id, prefix, gln, legal_name, state, source, first_seen FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1 ORDER BY length(prefix) LIMIT 200`, [pfx]);
  const outside = await q(
    `SELECT pp.id, pp.prefix, pp.legal_name, pp.state, pp.source FROM
       generate_series(4, greatest(length($1) - 1, 4)) n
       JOIN party pp ON pp.prefix = left($1, n) AND pp.prefix <> $1
      ORDER BY length(pp.prefix)`, [pfx]);
  res.json({
    subject: { prefix: pfx },
    method: 'string containment over digits. No name matching. No judgement.',
    inside: inside.rows.map((r) => ({ prefix: r.prefix, holder: r.legal_name,
      gln: r.gln, source: r.source, grade: agGrade(r.state), first_seen: r.first_seen })),
    outside: outside.rows.map((r) => ({ prefix: r.prefix, holder: r.legal_name,
      source: r.source, grade: agGrade(r.state) })),
    finding: (inside.rows.length || outside.rows.length) ? 'containment' : 'none',
    verdict: null,
    verdict_policy: 'THE REGISTER REPORTS THE CONTAINMENT AND NEVER THE CAUSE. '
                  + 'A bad cut by the registrar, a mis-filing, a subsidiary or channel '
                  + 'filing inside the parent licence, and genuine misuse are '
                  + 'indistinguishable here. Route the question to the licensee.',
  });
}));

// ============================================================================
// AGENT ECOSYSTEM — who this prefix connects to.
//
// A single registered company is a page. A registered ECOSYSTEM is a graph
// that resolves. Every edge here is GRADED and carries its asserter, because
// a candidate edge read as a contract is the failure this whole register
// exists to prevent.
// ============================================================================

app.get('/agent/prefix/:prefix(\\d+)/ecosystem', h(async (req, res) => {
  const pfx = req.params.prefix;
  const authority = authorityFor(pfx);
  const gaps = authorityGap(authority);

  const me = await q(`SELECT id, legal_name, name_fold FROM party WHERE prefix = $1`, [pfx]);
  if (me.rows.length === 0)
    return res.status(404).json({ subject:{prefix:pfx, resolves:false},
      reason:'no-holder-on-record', ...authorityBlocks(authority), gaps });

  const ids = me.rows.map(r => r.id);
  const folds = me.rows.map(r => r.name_fold).filter(Boolean);

  // ── siblings: other rows sharing the name fold ──────────────────────────
  // A NAME FOLD IS EVIDENCE, NOT IDENTITY. It is the least reliable operation
  // in the system and is recorded here as a candidate assertion, never as a
  // ruling that these rows are one legal entity.
  let siblings = [];
  if (folds.length) {
    const s = await q(
      `SELECT id, prefix, gln, legal_name, state, source, mo
         FROM party WHERE name_fold = ANY($1::text[]) AND id <> ALL($2::bigint[])
        ORDER BY (prefix IS NULL), prefix LIMIT 100`, [folds, ids]);
    siblings = s.rows.map(r => ({
      prefix: r.prefix, holder: r.legal_name, gln: r.gln, mo: r.mo, source: r.source,
      grade: 'c',
      relation: 'same-name-fold',
      evidence: `the legal name normalises to the same fold as ${me.rows[0].legal_name}`,
      asserter: 'name-fold, computed',
      note: 'CANDIDATE. Shared naming is evidence of one enterprise, never a ruling '
          + 'that they are one. Only the licensee can confirm it, and the registrar '
          + 'does not adjudicate co-reference.',
    }));
  }

  // ── asserted edges ──────────────────────────────────────────────────────
  // The edge table's shape has not been read by this patch's author. If the
  // query fails, that is REPORTED, not swallowed and not 500'd.
  let edges = [];
  try {
    const e = await q(
      `SELECT e.*, sp.legal_name AS subject_name, sp.prefix AS subject_prefix,
              op.legal_name AS object_name,  op.prefix  AS object_prefix
         FROM edge e
         LEFT JOIN party sp ON sp.id = e.subject_party_id
         LEFT JOIN party op ON op.id = e.object_party_id
        WHERE e.subject_party_id = ANY($1::bigint[])
           OR e.object_party_id  = ANY($1::bigint[])
        LIMIT 200`, [ids]);
    edges = e.rows.map(r => {
      const out = ids.map(String).includes(String(r.subject_party_id));
      return {
        direction: out ? 'out' : 'in',
        relation: r.rel || r.relation || r.edge_type || null,
        counterparty: out ? r.object_name : r.subject_name,
        counterparty_prefix: out ? r.object_prefix : r.subject_prefix,
        grade: r.state === 'verified' ? 'v' : r.state === 'exception' ? 'e' : 'c',
        source: r.source || null,
        is_demo_linkage: /demo/i.test(String(r.source || '')),
        asserter: r.asserter || r.actor || null,
        note: /demo/i.test(String(r.source || ''))
          ? 'A DEMONSTRATION LINKAGE. Not a sourced commercial relationship. '
            + 'Shown as what it is.'
          : null,
      };
    });
  } catch (err) {
    gaps.push({ field: 'edges', why: 'the edge table could not be read with the '
              + 'expected column names', detail: String(err.message || err).slice(0, 240),
              consequence: 'asserted relationships are NOT shown. Their absence here is a '
                         + 'failure to read, NOT a statement that none exist.' });
  }

  // ── the containment finding belongs to the neighbourhood too ────────────
  const inside = await q(
    `SELECT prefix, legal_name, gln, source, state FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1 ORDER BY length(prefix) LIMIT 50`, [pfx]);

  // A superseded subject has no licence to be inside of. The DB still roots
  // rows under 0817089 (the 5 Sep supersession), and LIKE '0817089%' would
  // happily return them — but containment is a statement about a GS1 licence,
  // and the authority holds a different one. Computed, then WITHHELD, and the
  // gap says so.
  const sup = authority.supersession;
  const insideRows = sup ? [] : inside.rows;
  if (sup)
    gaps.push({ field: 'inside_this_licence',
      why: `the subject prefix is superseded by ${sup.superseded_by || 'nothing'} per `
         + `Verified by GS1 ${sup.on}; containment computed against it is not meaningful `
         + 'and has been withheld.',
      withheld: inside.rows.length });

  if (!siblings.length && !edges.length && !inside.rows.length)
    gaps.push({ field: 'ecosystem', why: 'no neighbour of any kind is held for this prefix',
      consequence: 'This is an honest empty neighbourhood, not a rendering failure. '
                 + 'A company with no edges in the register has not been harvested for '
                 + 'them — it does not mean it has none.' });

  res.json({
    record: 'thingdaddy.agent.ecosystem.v1',
    subject: { prefix: pfx, holder: me.rows[0].legal_name },
    ...authorityBlocks(authority),
    siblings,
    edges,
    inside_this_licence: insideRows.map(r => ({
      prefix: r.prefix, holder: r.legal_name, gln: r.gln, source: r.source,
      grade: r.state === 'verified' ? 'v' : 'c', relation: 'issued-inside' })),
    counts: { siblings: siblings.length, edges: edges.length,
              inside: insideRows.length },
    gaps,
    policy: 'EVERY EDGE CARRIES ITS GRADE AND ITS ASSERTER. A candidate edge read as a '
          + 'contract is the failure this register exists to prevent. The fastest route '
          + 'from candidate to verified on a commercial edge is to ask the counterparty — '
          + 'nobody else can attest to it, and they answer in one sentence.',
  });
}));

// Serve the demo page from the same origin as the API when PUBLIC_DIR is set, so the
// browser needs no hardcoded API host and no CORS. Unset = unchanged behaviour.
const PUBLIC_DIR = process.env.PUBLIC_DIR || '';
if (PUBLIC_DIR && existsSync(PUBLIC_DIR)) app.use(express.static(PUBLIC_DIR));

// --- 404 fallthrough ---------------------------------------------------------
app.use((req, res) => res.status(404).json({ error: `no route ${req.method} ${req.path}` }));

// Start the server only when run directly (`node server.js`). When this module
// is imported (e.g. by a promote-branch test importing promoteClaim), it does
// NOT listen — so tests exercise the extracted logic without booting the API.
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  app.listen(PORT, HOST, async () => {
    // Report the REAL connected database (same source of truth as GET /health) —
    // never a hardcoded guess. db.js passes no explicit `database`, so an unset
    // PGDATABASE resolves via libpq (username), not 'thingdaddy_population'; only
    // current_database() is reliable. Falls back to 'unknown' if the lookup fails.
    let db = 'unknown';
    try {
      const { rows } = await q('SELECT current_database() AS db');
      db = rows[0]?.db ?? db;
    } catch { /* leave 'unknown' */ }
    console.log(`▸ population-api listening on http://${HOST}:${PORT}  (db: ${db})`);
  });
}
