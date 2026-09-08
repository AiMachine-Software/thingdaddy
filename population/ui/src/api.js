// The ONLY bridge between the UI and the population API. Every network call goes
// through here. Reads: /search, /record, /stats, /verified. Writes (token-gated):
// /ingest (land a candidate) and /claim (self-service re-root through the gate).
// Nothing here mints a URN or promotes to verified on its own — the API + DB gate
// decide. Imports nothing from platform/.

const BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8787').replace(/\/$/, '');

// INTERIM dev caller-token. server.js authenticates the caller with a shared
// secret (Authorization: Bearer <INGEST_TOKEN>); it does NOT make the caller an
// authority. For a local single-host demo we carry it here; real deployments move
// writes server-side. If unset, the UI disables write actions instead of failing.
const WRITE_TOKEN = import.meta.env.VITE_INGEST_TOKEN || '';
export const WRITES_ENABLED = !!WRITE_TOKEN;

async function get(path) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { headers: { accept: 'application/json' } });
  } catch (err) {
    throw new Error(`Cannot reach the population API at ${BASE}. Is it running? (${err.message})`);
  }
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).error || ''; } catch { /* non-JSON body */ }
    // Carry the status code on the error, exactly as post() does. Callers that
    // need to tell a legitimate "there is nothing here" (404) from a real
    // failure must branch on this — never on the text of the message.
    const e = new Error(`API ${res.status}${detail ? `: ${detail}` : ''}`);
    e.status = res.status; throw e;
  }
  return res.json();
}

async function post(path, body) {
  if (!WRITE_TOKEN) {
    const e = new Error('Writes are disabled in this build. Set VITE_INGEST_TOKEN (the dev caller token) and restart the UI.');
    e.disabled = true; throw e;
  }
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
        authorization: `Bearer ${WRITE_TOKEN}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new Error(`Cannot reach the population API at ${BASE}. Is it running? (${err.message})`);
  }
  let data = {};
  try { data = await res.json(); } catch { /* empty/non-JSON body */ }
  if (!res.ok) {
    const e = new Error(data.detail || data.error || `API ${res.status}`);
    e.status = res.status; e.body = data; throw e;
  }
  return data;
}

const qs = (params) => {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') u.set(k, v);
  }
  const s = u.toString();
  return s ? `?${s}` : '';
};

// ── reads ──────────────────────────────────────────────────────────────────
export function search({ q, state, cursor, limit = 20 } = {}) {
  return get(`/search${qs({ q, state, cursor, limit })}`);
}
export function record(id) { return get(`/record/${encodeURIComponent(id)}`); }
export function recordByPrefix(prefix) { return get(`/record/prefix/${encodeURIComponent(prefix)}`); }

// Cycle 3 spine reads (read the unified node+association spine, pre-cutover).
export function nodeByParty(partyId) { return get(`/node/by-legacy/party/${encodeURIComponent(partyId)}`); }
export function nodeAssociations(nodeId) { return get(`/node/${encodeURIComponent(nodeId)}/associations`); }

export function stats() { return get('/stats'); }
export function verified({ cursor, limit = 20 } = {}) {
  return get(`/verified${qs({ cursor, limit })}`);
}
// Completeness gate — computed-only, state-aware. Reports what's present/missing;
// never fabricates. { state, complete, required, present, missing, classification }.
export function completeness(id) { return get(`/party/${encodeURIComponent(id)}/completeness`); }

// Cycle 2 reads — a party's minted assets, and an asset's carrier profiles.
// A carrier's `value` is NULL when the profile is declared but not yet encoded
// (the encoding is the engine's job); the UI renders that as "encoding pending".
export function assets(partyId) { return get(`/party/${encodeURIComponent(partyId)}/assets`); }
export function carriers(assetId) { return get(`/asset/${encodeURIComponent(assetId)}/carriers`); }
export function epcis(partyId) { return get(`/party/${encodeURIComponent(partyId)}/epcis`); }

// ── writes (token-gated; fail-closed on the server) ─────────────────────────
// Land a new party. ALWAYS lands candidate|exception — never verified.
export function ingest(rows, source = 'manual') {
  return post('/ingest', { source, rows: Array.isArray(rows) ? rows : [rows] });
}
// Self-service re-root (Model A, in place). Authority FAILS CLOSED on the server:
// an unconfirmed claim comes back { claimed:false, state:'exception' } with a
// named reason — the gate holding, honestly surfaced. Never fabricated here.
export function claim(id, { prefix, actor, authority, gln, mo, demo_urn } = {}) {
  return post(`/claim/${encodeURIComponent(id)}`, { prefix, actor, authority, gln, mo, demo_urn });
}
// Assert a typed edge — a role stamp, or co-reference via rel='same_as'. ALWAYS
// lands candidate on the server (registrar-does-not-adjudicate; sameAs is never
// auto-merged). Stamped with the asserter; upsert-idempotent server-side.
export function stampEdge(id, { rel, object_label, object_prefix, asserter, valid_from, valid_to, doc, source } = {}) {
  return post(`/party/${encodeURIComponent(id)}/edge`, {
    rel, object_label, object_prefix, asserter, valid_from, valid_to, doc, source,
  });
}

export { BASE };
