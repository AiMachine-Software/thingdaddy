// THE API LAYER - the population API, same origin in production.
// A THINGSITE IS KEYED BY PREFIX, NOT COMPANY. A company holding three
// licences has three ThingSites; which they claim is theirs to decide.
// Every panel is labelled LIVE or FIXTURE. The fixture never masquerades.
import { useSyncExternalStore } from 'react';
import { BASE } from '../registry/api.js';

export const API = BASE; // '' = same origin

// Raw response log, shown by the "show raw responses" toggle in the API bar.
let RAW = [];
const listeners = new Set();
function log(path, status, ms, body) {
  RAW = [
    `GET ${path}   → ${status}  ${ms}ms\n` + JSON.stringify(body, null, 1).split('\n').slice(0, 26).join('\n'),
    ...RAW,
  ].slice(0, 12);
  listeners.forEach((fn) => fn());
}
export function useRawLog() {
  return useSyncExternalStore(
    (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    () => RAW,
  );
}

export async function call(path) {
  const t0 = performance.now();
  try {
    const r = await fetch(API + path, { headers: { Accept: 'application/json' } });
    const j = await r.json();
    log(path, r.status, Math.round(performance.now() - t0), j);
    return { ok: r.ok, status: r.status, body: j };
  } catch (e) {
    log(path, 'ERR', Math.round(performance.now() - t0), String(e));
    return { ok: false, status: 0, body: { error: String(e) } };
  }
}

// health - say plainly whether we are on the database or on fixtures.
// Resolves to { live:true, db, stats } or { live:false }.
export async function health() {
  const h = await call('/health');
  if (!(h.ok && h.body && h.body.ok)) return { live: false };
  const st = await call('/stats');
  const stats = st.ok && st.body && typeof st.body.total === 'number' ? st.body : null;
  return { live: true, db: h.body.db || '?', stats };
}

// /search returns party rows. Each party may hold prefixes; each prefix is its
// own ThingSite. null = API down; [] = API up, genuinely not found.
export async function search(q) {
  const r = await call('/search?q=' + encodeURIComponent(q));
  if (!r.ok || !r.body || !Array.isArray(r.body.rows)) return null;
  return r.body.rows;
}

// party.prefix may be null in production while the prefix still sits in
// staging - that is the promote gap, and it must show as an honest unrooted
// party rather than as nothing.
export async function recordByPrefix(prefix) {
  const r = await call('/record/prefix/' + encodeURIComponent(prefix));
  return r.ok && r.body && !r.body.error ? r.body : null;
}
export async function completeness(partyId) {
  const r = await call('/party/' + partyId + '/completeness');
  return r.ok ? r.body : null;
}
export async function nodeForParty(partyId) {
  const r = await call('/node/by-legacy/party/' + partyId);
  return r.ok && r.body && !r.body.error ? r.body : null;
}
export async function associations(nodeId) {
  const r = await call('/node/' + nodeId + '/associations');
  return r.ok ? r.body : null;
}
