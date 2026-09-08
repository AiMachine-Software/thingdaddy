// THE ADAPTER - API shape -> the record shape every screen reads.
// Defensive by construction: an absent field becomes a SLOT, never a guess,
// and never an empty string.

export function shapeParty(p, extras = {}) {
  const prefix = p.prefix || null;
  const root = {
    prefix,
    gcp_length: prefix ? prefix.length : null,
    licence_type: p.licence_type || null,
    gln: p.gln || null,
    mo: p.mo || null,
    state: p.state || 'candidate',
    registered_to: p.legal_name || null,
    doors: p.url ? [{ url: p.url, country: p.country || '' }] : [],
    provenance: {
      authority: p.mo || 'not read',
      via: p.licence_type_source || p.source || 'not read',
      read_at: (p.verified_at || p.last_updated || '').slice(0, 10),
    },
  };
  return {
    '@type': 'td:ThingSite',
    label: p.legal_name,
    party_id: p.id,
    id: null,
    mint: false,
    state: prefix ? (p.state || 'candidate') : 'exception',
    exception_reason: prefix ? null : 'no-prefix-in-production',
    roots: prefix ? [root] : [],
    unrooted_root: root, // kept so the card can still show what IS known
    provenance: root.provenance,
    graph: extras.graph || null,
    pillars: extras.pillars || emptyPillars(),
    live: true,
  };
}

export function emptyPillars() {
  const slot = (t) => ({ count: 0, grades: {}, rows: [], slot: t });
  return {
    P1_identity: slot('nothing promoted to production yet'),
    P2_drivers: slot('harvest pending'),
    P3_protocols: slot('harvest pending'),
    P4_cloud: slot('your console'),
    P5_graph: slot('edges appear as pillars are confirmed'),
  };
}

// completeness -> pillar counts, whatever shape it returns
export function shapePillars(c) {
  if (!c || typeof c !== 'object') return emptyPillars();
  const P = emptyPillars();
  const put = (k, n, label) => {
    if (typeof n === 'number' && n > 0) {
      P[k] = { count: n, grades: { c: n }, rows: [{ label, key_type: null, urn: null, grade: 'c',
        source: { url: 'population API · /completeness' } }] };
    }
  };
  const g = (k) => c[k] ?? (c.counts && c.counts[k]) ?? null;
  put('P1_identity', g('assets') ?? g('identities') ?? g('nodes'), 'identities held in production');
  put('P2_drivers', g('drivers') ?? g('docs'), 'documents and drivers held');
  put('P3_protocols', g('methods') ?? g('protocols'), 'methods held');
  put('P4_cloud', g('carriers'), 'carrier bindings held');
  put('P5_graph', g('edges') ?? g('associations'), 'edges held');
  return P;
}

// associations -> a graph slice the same renderer can draw
export function shapeGraph(label, assoc) {
  const list = Array.isArray(assoc) ? assoc : assoc && Array.isArray(assoc.rows) ? assoc.rows : null;
  if (!list || !list.length) return null;
  const nodes = [{ id: 'self', label, k: 'pgln', g: 'c', x: 480, y: 70 }];
  const edges = [];
  list.slice(0, 10).forEach((a, i) => {
    const id = 'n' + i, cols = 5, col = i % cols, row = Math.floor(i / cols);
    nodes.push({ id, label: (a.label || a.object_label || a.rel || 'node ' + i).slice(0, 26),
      k: a.key_type || 'gtin', g: a.state === 'verified' ? 'v' : 'c', x: 120 + col * 190, y: 200 + row * 110 });
    edges.push(['self', id]);
  });
  return { nodes, edges };
}

export function host(u) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return u; }
}

export function breakdown(g) {
  return Object.entries(g || {}).map(([k, n]) => n + k).join(' ') || '—';
}
