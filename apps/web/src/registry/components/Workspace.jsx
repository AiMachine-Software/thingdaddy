import React, { useCallback, useEffect, useState } from 'react';
import {
  record as fetchRecord, claim as apiClaim, completeness as fetchCompleteness, stampEdge,
  assets as fetchAssets, carriers as fetchCarriers, epcis as fetchEpcis,
  nodeByParty, nodeAssociations, WRITES_ENABLED,
} from '../api.js';
import { PILLARS, ID_TYPES, LIVE_PILLARS, ROLE_RELS, isRoleRel, roleLabel } from '../workspace.js';
import StateChip from './StateChip.jsx';

const dt = (s) => (s ? new Date(s).toLocaleString('en-US') : '—');

// The "Manage" surface. A party found in the registry opens here: its In-Context
// identity spine (real), its graph edges (real), its provenance ledger (real),
// and the claim action (self-service re-root — fail-closed on the server, so an
// unconfirmed claim comes back as a NAMED exception, never a fabricated verify).
export default function Workspace({ seed, onBack, onChanged }) {
  const [rec, setRec] = useState(null);
  const [err, setErr] = useState(null);
  const [active, setActive] = useState('ids');
  const [claiming, setClaiming] = useState(false);

  const load = useCallback(() => {
    setErr(null);
    fetchRecord(seed.id).then(setRec).catch((e) => setErr(e.message));
  }, [seed.id]);

  useEffect(() => { setRec(null); load(); }, [load]);

  const p = rec?.party || seed;
  const edges = rec?.edges || [];
  const events = rec?.events || [];

  const NAV = [...PILLARS, { id: 'provenance', n: '·', label: 'Provenance', sub: 'Append-only event ledger', color: '#6B7280' }];

  return (
    <div>
      <button className="backlink" onClick={onBack}>← Back to find</button>

      <div className="ws-head">
        <div>
          <h2>{p.legal_name}</h2>
          <div className="bigprefix">
            {p.prefix ? `GS1 prefix ${p.prefix}` : <span className="null">no prefix — candidate</span>}
            {p.gln ? `  ·  GLN ${p.gln}` : ''}
          </div>
          <div style={{ marginTop: 8 }}><StateChip state={p.state} /></div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {p.state === 'candidate' && (
            <button className="btn primary" onClick={() => { setActive('ids'); setClaiming(true); }}>
              Claim this company
            </button>
          )}
        </div>
      </div>

      {err && <div className="banner">{err}</div>}

      <div className="ws">
        <nav className="snav">
          {NAV.map((pl) => (
            <button
              key={pl.id}
              className={`lk${active === pl.id ? ' on' : ''}`}
              style={active === pl.id ? { borderLeftColor: pl.color } : undefined}
              onClick={() => setActive(pl.id)}
            >
              <span className="num" style={{ background: pl.color }}>{pl.n}</span>
              <span>
                <span className="lab">{pl.label}</span>
                <span className="sb">{pl.sub}</span>
              </span>
            </button>
          ))}
        </nav>

        <section className="panel">
          {active === 'ids' && (
            <IdsPillar p={p} edges={edges} claiming={claiming} setClaiming={setClaiming} onChanged={() => { load(); onChanged && onChanged(); }} />
          )}
          {active === 'graph' && <GraphPillar edges={edges} loaded={!!rec} partyId={p.id} />}
          {['drivers', 'workflows', 'cloud'].includes(active) && (
            <HoldPillar pillar={PILLARS.find((x) => x.id === active)} party={p} />
          )}
          {active === 'provenance' && <Provenance events={events} loaded={!!rec} />}
        </section>
      </div>
    </div>
  );
}

// Pillar 1 — In-Context IDs: the real identity spine + claim action + Cycle 1
// depth (completeness gate, role stamps, co-reference). All live over the API.
function IdsPillar({ p, edges, claiming, setClaiming, onChanged }) {
  const rooted = !!p.prefix;
  return (
    <div>
      <div className="pillhead">
        <span className="dot" style={{ background: ID_TYPES.GIAI }} />
        <h3>In-Context IDs</h3>
        <span className="live">Live · registry</span>
      </div>
      <p className="pillsub">The unique, in-context, prefix-rooted identity — read straight from the population registry. No value shown here is fabricated.</p>

      <div className="spine">
        <Row k="Legal name" v={p.legal_name} plain />
        <Row k="Prefix (root)" v={p.prefix || 'none yet'} nullish={!rooted} badge={rooted ? 'ROOT' : null} />
        <Row k="GLN" v={p.gln || '—'} nullish={!p.gln} />
        <Row k="MO band" v={p.mo || '—'} nullish={!p.mo} plain />
        <Row k="LEI" v={p.lei || '—'} nullish={!p.lei} />
        <Row k="Source" v={p.source} plain />
        {p.exception_reason && <Row k="Exception" v={p.exception_reason} plain />}
      </div>

      <div className="idlegend">
        {Object.entries(ID_TYPES).map(([t, c]) => (
          <span className="idchip" key={t}><span className="sw" style={{ background: c }} />{t}</span>
        ))}
      </div>
      <p className="hint" style={{ marginTop: 10 }}>
        Concrete asset IDs (GIAI, CPID, GDTI…) are minted by the engine <b>after</b> a company claims its prefix — never typed by hand, never here. This pillar shows the registry root they descend from.
      </p>

      {claiming && p.state === 'candidate' && (
        <ClaimForm party={p} onDone={() => { setClaiming(false); onChanged(); }} onCancel={() => setClaiming(false)} />
      )}
      {p.state === 'verified' && (
        <div className="outcome ok"><div className="oh">Verified — rooted in prefix {p.prefix}</div>
          This identity roots in an authority-confirmed GS1 company prefix. Everything below it inherits that root.</div>
      )}
      {p.state === 'exception' && !claiming && (
        <div className="outcome held"><div className="oh">Held as a named exception</div>
          {p.exception_reason || 'Ownership not authority-confirmed.'} The registry never guesses — it holds until an authority speaks.</div>
      )}

      <CompletenessCard id={p.id} refreshKey={`${p.state}|${p.last_updated}`} />
      <RolesSection party={p} edges={edges} onChanged={onChanged} />
      <CoReferenceSection party={p} edges={edges} onChanged={onChanged} />
      <AssetsPanel partyId={p.id} rooted={rooted} />
      <CarrierProfile />
      <ClassifySection />
    </div>
  );
}

// Assets (GIAI) minted under this party's prefix, each with its carrier profiles.
// Reads GET /party/:id/assets, then GET /asset/:id/carriers per asset. Assets
// descend from a prefix root, so nothing shows until the party is rooted. Honest
// empty state; never invents a URN or a carrier value.
function AssetsPanel({ partyId, rooted }) {
  const [assets, setAssets] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (!rooted) { setAssets([]); return undefined; }
    let alive = true;
    setAssets(null); setErr(null);
    fetchAssets(partyId)
      .then((d) => { if (alive) setAssets(d.assets || []); })
      .catch((e) => { if (alive) setErr(e.message); });
    return () => { alive = false; };
  }, [partyId, rooted]);

  if (!rooted) return null; // assets descend from a prefix root — none to show until claimed
  return (
    <div style={{ marginTop: 20 }}>
      <div className="pillhead" style={{ marginBottom: 6 }}>
        <span className="dot" style={{ background: ID_TYPES.GIAI }} />
        <h3 style={{ fontSize: 15 }}>Assets (GIAI)</h3>
        <span className="live">Live · registry</span>
      </div>
      <p className="pillsub">Serialized instances minted by the engine under this prefix — the URN is exactly what the engine returned, never typed here. Carriers hang off each asset as gated profiles; the encoding is the engine's to fill, never fabricated.</p>
      {err && <div className="empty">{err}</div>}
      {!assets && !err && <div className="empty">Loading…</div>}
      {assets && assets.length === 0 && (
        <div className="holdcard"><div className="ht">No assets minted yet</div>
          <div className="hb">This identity is rooted, but no GIAI instances have been minted under it. Assets appear here once the engine mints them — never invented to fill the view.</div></div>
      )}
      {assets && assets.map((a) => (
        <div className="card" key={a.id}>
          <div className="top"><span className="objp" style={{ fontSize: 12 }}>{a.urn}</span><StateChip state={a.state} /></div>
          {a.label && <div className="sub" style={{ marginTop: 3 }}>{a.label}</div>}
          <CarrierList assetId={a.id} />
        </div>
      ))}
    </div>
  );
}

// One asset's carrier profiles. value NULL => declared but not yet encoded (the
// engine's job); shown as "encoding pending", never a fabricated value.
function CarrierList({ assetId }) {
  const [carriers, setCarriers] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let alive = true;
    fetchCarriers(assetId)
      .then((d) => { if (alive) setCarriers(d.carriers || []); })
      .catch((e) => { if (alive) setErr(e.message); });
    return () => { alive = false; };
  }, [assetId]);
  if (err) return <div className="empty">carriers: {err}</div>;
  if (!carriers) return <div className="empty">Loading carriers…</div>;
  if (carriers.length === 0) return <div className="empty">No carrier profiles declared.</div>;
  return (
    <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
      {carriers.map((c) => (
        <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 12 }}>{c.carrier_type}</span>
          <span className="sub" style={{ marginTop: 0, textAlign: 'right' }}>
            {c.value
              ? <span className="objp">{c.value}</span>
              : <span style={{ fontStyle: 'italic' }}>encoding pending the engine</span>}
          </span>
        </div>
      ))}
    </div>
  );
}

// Completeness gate — computed-only, state-aware. Honest "what's missing", never faked.
function CompletenessCard({ id, refreshKey }) {
  const [c, setC] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setC(null); setErr(null);
    fetchCompleteness(id).then(setC).catch((e) => setErr(e.message));
  }, [id, refreshKey]);
  return (
    <div className="section">
      <div className="sechead"><h4>Completeness</h4><span className="sechint">computed · never fabricated</span></div>
      {err && <div className="banner">{err}</div>}
      {!c && !err && <div className="empty">Checking…</div>}
      {c && (
        <div className={`completecard ${c.complete ? 'ok' : 'gap'}`}>
          <div className="ctop">
            <span className={`cbadge ${c.complete ? 'ok' : 'gap'}`}>{c.complete ? 'Complete' : 'Incomplete'}</span>
            <span className="cstate">state: {c.state}</span>
          </div>
          {c.complete
            ? <div className="cbody">All base fields present and verified — this registration is complete.</div>
            : <div className="cbody">
                Missing: {c.missing.map((m) => <span className="miss" key={m}>{m}</span>)}
                <div className="chint">Nothing is invented to fill these — the registry reports the gap honestly until real data or an authority fills it.</div>
              </div>}
        </div>
      )}
    </div>
  );
}

// Role stamps — typed edges on this location/party. Curated GS1 roles; each stamp
// lands `candidate` (registrar-does-not-adjudicate) and carries its asserter.
function RolesSection({ party, edges, onChanged }) {
  const roles = (edges || []).filter((e) => isRoleRel(e.rel));
  const [open, setOpen] = useState(false);
  return (
    <div className="section">
      <div className="sechead"><h4>Roles</h4>
        <span className="sechint">typed edges on this location · asserted, not adjudicated</span></div>
      {roles.length === 0 && <div className="empty">No roles stamped yet.</div>}
      {roles.map((e) => (
        <div className="card" key={e.id}>
          <div className="top"><span className="rel">{roleLabel(e.rel)}</span><StateChip state={e.state} /></div>
          <div className="obj" style={{ marginTop: 4 }}>→ {e.object_label}</div>
          <div className="sub">asserted by {e.asserter || '—'}{e.valid_from ? ` · from ${dt(e.valid_from)}` : ''}{e.doc ? ` · ${e.doc}` : ''}</div>
        </div>
      ))}
      {WRITES_ENABLED
        ? (open
            ? <StampForm party={party} rels={ROLE_RELS} defaultRel="located_at" kind="role"
                onDone={() => { setOpen(false); onChanged && onChanged(); }} onCancel={() => setOpen(false)} />
            : <button className="btn ghost" style={{ marginTop: 10 }} onClick={() => setOpen(true)}>+ Stamp a role</button>)
        : <p className="hint">Stamping roles needs a write token (VITE_INGEST_TOKEN) — disabled in this build.</p>}
    </div>
  );
}

// Co-reference (same-as) — an assertion that two records are the same entity.
// UNADJUDICATED: candidate only; the registrar never merges on an assertion.
function CoReferenceSection({ party, edges, onChanged }) {
  const sames = (edges || []).filter((e) => e.rel === 'same_as');
  const [open, setOpen] = useState(false);
  return (
    <div className="section">
      <div className="sechead"><h4>Co-reference (same-as)</h4>
        <span className="sechint">unadjudicated · the registrar does not merge</span></div>
      {sames.length === 0 && <div className="empty">No co-reference assertions.</div>}
      {sames.map((e) => (
        <div className="card" key={e.id}>
          <div className="top"><span className="rel">same as</span><StateChip state={e.state} /></div>
          <div className="obj" style={{ marginTop: 4 }}>≡ {e.object_label}</div>
          <div className="sub">asserted by {e.asserter || '—'} · held candidate — never auto-merged</div>
        </div>
      ))}
      {WRITES_ENABLED
        ? (open
            ? <StampForm party={party} rels={[{ rel: 'same_as', label: 'Same as' }]} defaultRel="same_as" kind="sameas"
                onDone={() => { setOpen(false); onChanged && onChanged(); }} onCancel={() => setOpen(false)} />
            : <button className="btn ghost" style={{ marginTop: 10 }} onClick={() => setOpen(true)}>+ Assert co-reference</button>)
        : <p className="hint">Asserting co-reference needs a write token — disabled in this build.</p>}
    </div>
  );
}

// Shared stamp form for a role edge or a same-as assertion. Lands candidate.
function StampForm({ party, rels, defaultRel, kind, onDone, onCancel }) {
  const [rel, setRel] = useState(defaultRel);
  const [obj, setObj] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await stampEdge(party.id, { rel, object_label: obj.trim(), asserter: 'ui-registrar', source: 'manual' });
      onDone();
    } catch (e) { setErr(e.disabled ? e.message : (e.message || 'stamp failed')); }
    finally { setBusy(false); }
  };
  return (
    <div className="form" style={{ marginTop: 12 }}>
      {rels.length > 1 && (
        <div className="field">
          <label>Role</label>
          <select value={rel} onChange={(e) => setRel(e.target.value)}>
            {rels.map((r) => <option key={r.rel} value={r.rel}>{r.label}</option>)}
          </select>
        </div>
      )}
      <div className="field">
        <label>{kind === 'sameas' ? 'Other record (name / label)' : 'Location or organization (name / label)'}</label>
        <input value={obj} onChange={(e) => setObj(e.target.value)} placeholder="e.g. Plant 5, Phoenix" />
      </div>
      <div className="actions">
        <button className="btn primary" disabled={busy || !obj.trim()} onClick={submit}>{busy ? 'Stamping…' : 'Stamp'}</button>
        <button className="btn ghost" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
      <p className="hint">Lands as a <b>candidate</b> assertion, stamped with who asserted it — the registrar records the claim, it does not adjudicate it.</p>
      {err && <div className="outcome err"><div className="oh">Not stamped</div>{err}</div>}
    </div>
  );
}

function ClaimForm({ party, onDone, onCancel }) {
  const [prefix, setPrefix] = useState('');
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState(null);

  const submit = async () => {
    setBusy(true); setOutcome(null);
    try {
      const r = await apiClaim(party.id, { prefix: prefix.trim(), actor: 'ui-claimant' });
      if (r.claimed) setOutcome({ kind: 'ok', title: 'Claimed — verified', body: `Re-rooted onto prefix ${r.party?.prefix}. Origin preserved in the append-only ledger.` });
      else setOutcome({ kind: 'held', title: 'Claim received — held as a named exception', body: r.exception_reason || 'Authority pending: GEPIR / Verified-by-GS1 not wired — nothing verified on thin evidence.' });
      setTimeout(onDone, 1400);
    } catch (e) {
      if (e.disabled) setOutcome({ kind: 'err', title: 'Writes disabled in this build', body: e.message });
      else setOutcome({ kind: 'err', title: `Rejected (${e.status || 'error'})`, body: e.message });
    } finally { setBusy(false); }
  };

  return (
    <div className="form" style={{ marginTop: 16 }}>
      <div className="field">
        <label>Your verified GS1 company prefix</label>
        <input value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="e.g. 0702054 (digits only)" />
      </div>
      <div className="actions">
        <button className="btn primary" disabled={busy || !prefix.trim()} onClick={submit}>{busy ? 'Submitting…' : 'Submit claim'}</button>
        <button className="btn ghost" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
      <p className="hint">Self-service claim routes through the gate. Authority (GEPIR / Verified-by-GS1) is <b>not yet wired</b>, so the server <b>fails closed</b>: your claim is recorded as a named exception, not a fabricated verification. That hold is the product working as designed.</p>
      {!WRITES_ENABLED && <p className="hint" style={{ color: '#991B1B' }}>Note: this UI build has no write token — the claim will be blocked client-side until VITE_INGEST_TOKEN is set.</p>}
      {outcome && (
        <div className={`outcome ${outcome.kind}`}><div className="oh">{outcome.title}</div>{outcome.body}</div>
      )}
    </div>
  );
}

// Pillar 5 — AI Graph: the party's real edges.
function GraphPillar({ edges, loaded, partyId }) {
  return (
    <div>
      <div className="pillhead">
        <span className="dot" style={{ background: '#7C3AED' }} />
        <h3>AI Graph</h3>
        <span className="live">Live · registry</span>
      </div>
      <p className="pillsub">Typed relationships this identity asserts — each edge carries its own state and provenance. Nothing is forced to "verified" it didn't earn.</p>
      {!loaded && <div className="empty">Loading…</div>}
      {loaded && edges.length === 0 && (
        <div className="holdcard"><div className="ht">No edges recorded yet</div>
          <div className="hb">This identity has no relationships in the registry. Edges are asserted by loaders and agents (candidate) and promoted on evidence — never invented to fill the view.</div></div>
      )}
      {edges.map((e) => (
        <div className="card" key={e.id}>
          <div className="top"><span className="rel">{e.rel}</span><StateChip state={e.state} /></div>
          <div className="obj" style={{ marginTop: 4 }}>→ {e.object_label}</div>
          {e.object_prefix && <div className="objp">prefix {e.object_prefix}</div>}
          <div className="sub">source {e.source}{e.inferred ? ' · inferred' : ''}{e.doc ? ` · ${e.doc}` : ''}</div>
        </div>
      ))}

      <EpcisStream partyId={partyId} />
      <SpineView partyId={partyId} />
    </div>
  );
}

// SpineView — the party's neighborhood read from the unified node+association
// spine (backfilled), shown BESIDE the legacy edges so the two are distinct.
// Read-only. 404 = not yet backfilled onto the spine → said honestly, never faked.
function SpineView({ partyId }) {
  const [st, setSt] = useState({ status: 'loading' });   // loading | absent | ready | error
  const [assoc, setAssoc] = useState(null);
  useEffect(() => {
    let alive = true;
    setSt({ status: 'loading' }); setAssoc(null);
    nodeByParty(partyId)
      .then((d) => {
        if (!alive) return undefined;
        setSt({ status: 'ready', node: d.node });
        return nodeAssociations(d.node.id).then((a) => { if (alive) setAssoc(a.associations || []); });
      })
      .catch((e) => {
        if (!alive) return;
        // 404 is the registry's legitimate "this party is not on the spine yet";
        // anything else is a failure. Branch on the STATUS CODE, never on the
        // error text — an error whose detail merely contains "404" is not a
        // negative answer, and reporting it as one would hide an outage.
        if (e.status === 404) setSt({ status: 'absent' });
        else setSt({ status: 'error', message: e.message });
      });
    return () => { alive = false; };
  }, [partyId]);

  return (
    <div style={{ marginTop: 24, borderTop: '1px dashed var(--border)', paddingTop: 16 }}>
      <div className="pillhead" style={{ marginBottom: 6 }}>
        <span className="dot" style={{ background: '#111827' }} />
        <h3 style={{ fontSize: 15 }}>Unified spine <span style={{ fontWeight: 400, color: 'var(--muted)' }}>· read-only</span></h3>
        <span className="live">Live · node graph</span>
      </div>
      <p className="pillsub">The same relationships read from the unified node + association spine (backfilled from the legacy graph). Shown beside the legacy edges above — this is the graph the registry is migrating onto.</p>
      {st.status === 'loading' && <div className="empty">Loading…</div>}
      {st.status === 'absent' && (
        <div className="holdcard"><div className="ht">Not on the spine yet</div>
          <div className="hb">This identity hasn't been backfilled into the node spine. It still reads from the legacy tables above — shown honestly, never faked.</div></div>
      )}
      {st.status === 'error' && <div className="empty">spine: {st.message}</div>}
      {st.status === 'ready' && (
        <>
          <div className="sub" style={{ marginBottom: 8 }}>node #{st.node.id} · {st.node.key_type}{st.node.urn ? ` · ${st.node.urn}` : ''}</div>
          {!assoc && <div className="empty">Loading associations…</div>}
          {assoc && assoc.length === 0 && <div className="empty">No associations on the spine.</div>}
          {assoc && assoc.map((a) => (
            <div className="card" key={a.id}>
              <div className="top">
                <span className="rel">{a.direction === 'out' ? '→' : '←'} {a.rel}</span>
                <StateChip state={a.state} />
              </div>
              <div className="obj" style={{ marginTop: 4 }}>
                {a.direction === 'out'
                  ? (a.object_legal_name || a.object_label || a.object_urn || `node #${a.object_node_id}`)
                  : (a.subject_legal_name || a.subject_label || a.subject_urn || `node #${a.subject_node_id}`)}
              </div>
              <div className="sub">source {a.source}{a.inferred ? ' · inferred' : ''}</div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

// Turn an EPCIS bizStep URI into a short human label:
//   urn:epcglobal:cbv:bizstep:commissioning -> "commissioning"
//   urn:thingdaddy:bizstep:encoding          -> "encoding"
const shortBizStep = (b) => (b ? b.split(':').pop() : '—');

// EPCIS event stream — a READ PROJECTION of this party's provenance ledger into
// EPCIS 2.0 ObjectEvent shape (GET /party/:id/epcis). NOT a stored/conformant
// EPCIS document; thing-events only (asset mint, carrier encoding). Registry
// lifecycle events without an EPC are not projected — surfaced as a count, honest.
function EpcisStream({ partyId }) {
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let alive = true;
    setDoc(null); setErr(null);
    fetchEpcis(partyId)
      .then((d) => { if (alive) setDoc(d); })
      .catch((e) => { if (alive) setErr(e.message); });
    return () => { alive = false; };
  }, [partyId]);

  const events = doc?.epcisBody?.eventList || [];
  const omitted = doc?.registryEventsOmitted || 0;

  return (
    <div style={{ marginTop: 24 }}>
      <div className="pillhead" style={{ marginBottom: 6 }}>
        <span className="dot" style={{ background: '#7C3AED' }} />
        <h3 style={{ fontSize: 15 }}>EPCIS event stream</h3>
        <span className="live">Live · projection</span>
      </div>
      <p className="pillsub">A read projection of the provenance ledger into EPCIS 2.0 ObjectEvent shape — <b>not</b> a stored or conformant EPCIS document. Thing-events only (asset commissioning, carrier encoding); registry-lifecycle events without an EPC are not projected.</p>
      {err && <div className="empty">{err}</div>}
      {!doc && !err && <div className="empty">Loading…</div>}
      {doc && events.length === 0 && (
        <div className="holdcard"><div className="ht">No EPCIS events yet</div>
          <div className="hb">This identity has no URN-bearing events yet. Mint an asset and its commissioning event appears here.{omitted ? ` (${omitted} registry event${omitted === 1 ? '' : 's'} not projected — no EPC.)` : ''}</div></div>
      )}
      {events.length > 0 && (
        <>
          <div className="timeline">
            {events.map((ev, i) => (
              <div className="ev" key={i}>
                <div className="et">{ev.eventType} · {ev.action} · {shortBizStep(ev.bizStep)}</div>
                <div className="em">
                  {dt(ev.eventTime)}
                  {ev['thingdaddy:registryEventType'] ? ` · ${ev['thingdaddy:registryEventType']}` : ''}
                  {ev['thingdaddy:source'] ? ` · ${ev['thingdaddy:source']}` : ''}
                </div>
                <div className="ed">{(ev.epcList || []).join(', ')}</div>
              </div>
            ))}
          </div>
          {omitted > 0 && (
            <p className="hint" style={{ marginTop: 10 }}>{omitted} registry event{omitted === 1 ? '' : 's'} not shown — lifecycle events without an EPC aren't EPCIS thing-events.</p>
          )}
        </>
      )}
    </div>
  );
}

// Pillars 2/3/4 — honest: the registry does not hold drivers/workflows/cloud
// bindings; those bind in the engine after a claim. We say so rather than fake it.
function HoldPillar({ pillar, party }) {
  return (
    <div>
      <div className="pillhead">
        <span className="dot" style={{ background: pillar.color }} />
        <h3>{pillar.label}</h3>
      </div>
      <p className="pillsub">{pillar.sub}</p>
      <div className="holdcard">
        <div className="ht">Binds after the claim</div>
        <div className="hb">
          {pillar.label} are not records in the population registry — they attach to this identity in the engine once {party.legal_name} claims its prefix and its assets are minted. Showing an empty, honest panel here instead of fabricated bindings is the verified-or-exception law applied to the UI.
        </div>
      </div>
    </div>
  );
}

function Provenance({ events, loaded }) {
  return (
    <div>
      <div className="pillhead"><span className="dot" style={{ background: '#6B7280' }} /><h3>Provenance</h3><span className="live">Live · registry</span></div>
      <p className="pillsub">The append-only event ledger — every state change, claim, and exception, written once and never overwritten.</p>
      {!loaded && <div className="empty">Loading…</div>}
      {loaded && events.length === 0 && <div className="empty">No events recorded.</div>}
      {events.length > 0 && (
        <div className="timeline">
          {events.map((ev) => (
            <div className="ev" key={ev.id}>
              <div className="et">{ev.event_type}</div>
              <div className="em">{[ev.from_state, ev.to_state].filter(Boolean).join(' → ')}{ev.actor ? ` · ${ev.actor}` : ''} · {dt(ev.at)}</div>
              {ev.detail && Object.keys(ev.detail).length > 0 && <div className="ed">{JSON.stringify(ev.detail)}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ k, v, nullish, plain, badge }) {
  return (
    <div className="rowk">
      <span className="k">{k}</span>
      <span className={`v${plain ? ' plain' : ''}${nullish ? ' null' : ''}`} style={plain && !nullish ? { fontFamily: 'inherit' } : undefined}>{v}</span>
      {badge ? <span className="rootbadge">{badge}</span> : <span />}
    </div>
  );
}


// SUPERSEDED (Cycle 2): these rows are a hardcoded pre-Cycle-2 illustration, not
// data — the live asset+carrier reads now render in <AssetsPanel> above.
//
// Carrier profile — READ-ONLY illustration. One EPC identity can ride many
// carriers; they bind to a minted asset (its own key), not this record, so this
// shows the carrier PROFILE grounded in real DZ-Lite hardware. Asset+carrier tier
// is Cycle 2; nothing here is written.
const CARRIER_PROFILE = [
  { type: 'RAIN RFID (UHF)',   documented: true,  note: 'DZ-Lite 3000 Plus — RFID reagent tag' },
  { type: '1D / 2D barcode',   documented: true,  note: 'DZ-Lite 3000 Plus — barcode sample reader' },
  { type: 'NFC / HF',          documented: false, note: 'profile — supported by the EPC identity' },
  { type: 'GS1 Digital Link',  documented: false, note: 'profile — web-resolvable carrier' },
  { type: 'Human-readable',    documented: false, note: 'profile — printed element string' },
];
function CarrierProfile() {
  return (
    <div className="section">
      <div className="sechead"><h4>Carrier profile</h4><span className="sechint">one identity, many carriers · illustration</span></div>
      <p className="hint" style={{ marginTop: 0 }}>
        One EPC identity can ride many data carriers at once. Carriers bind to a minted <b>asset</b> (its own key), not to this record — so this is the <b>profile</b> (the carrier types available), illustrated with real DZ-Lite hardware. The asset + carrier binding lands in Cycle 2; nothing here is written.
      </p>
      <div className="carriers">
        {CARRIER_PROFILE.map((c) => (
          <div className={`carrier ${c.documented ? 'doc' : 'prof'}`} key={c.type}>
            <span className="ctag">{c.documented ? 'documented' : 'profile'}</span>
            <span className="cname">{c.type}</span>
            <span className="cnote">{c.note}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Classify — SHELL. Classification will drive the completeness required-docs gate
// in Cycle 3 (hazmat -> SDS, device -> GUDID). Here it previews the concept and
// feeds the completeness classification stub — no required-docs engine, no write.
const CLASS_OPTIONS = [
  { key: 'medical_device', label: 'Medical device',         implies: 'GUDID / UDI documents (Cycle 3)' },
  { key: 'chemical',       label: 'Chemical / hazmat',      implies: 'Safety Data Sheet (Cycle 3)' },
  { key: 'instrument',     label: 'Instrument / equipment', implies: 'manual + calibration (Cycle 3)' },
  { key: 'reagent',        label: 'Reagent / consumable',   implies: 'lot + control docs (Cycle 3)' },
  { key: 'general',        label: 'General trade item',     implies: 'none required' },
];
function ClassifySection() {
  const [sel, setSel] = useState(null);
  const chosen = CLASS_OPTIONS.find((o) => o.key === sel);
  return (
    <div className="section">
      <div className="sechead"><h4>Classify</h4><span className="sechint">shell · drives required docs in Cycle 3</span></div>
      <p className="hint" style={{ marginTop: 0 }}>
        Classification decides what an identity <b>must</b> carry to be complete — a hazmat item needs an SDS, a device needs GUDID. This picker previews that; the required-docs gate itself is a later cycle. Nothing is written.
      </p>
      <div className="chips">
        {CLASS_OPTIONS.map((o) => (
          <button key={o.key} className={`chip${sel === o.key ? ' active' : ''}`} onClick={() => setSel(sel === o.key ? null : o.key)}>{o.label}</button>
        ))}
      </div>
      {chosen && (
        <div className="hint" style={{ marginTop: 10 }}>
          <b>{chosen.label}</b> → implies: {chosen.implies}.
          <div className="mut" style={{ marginTop: 4 }}>Feeds the completeness classification stub. No required-docs enforced yet (Cycle 3).</div>
        </div>
      )}
    </div>
  );
}
