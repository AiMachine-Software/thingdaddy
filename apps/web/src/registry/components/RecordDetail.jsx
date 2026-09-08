import React, { useEffect, useState } from 'react';
import { record as fetchRecord } from '../api.js';
import StateChip from './StateChip.jsx';

const dt = (s) => (s ? new Date(s).toLocaleString('en-US') : '—');

// Right-side drawer. On open, GET /record/:id → party + edges + event history.
// `seed` is the list row we already have, shown instantly while the full record
// (with edges + events) loads.
export default function RecordDetail({ seed, onClose }) {
  const [rec, setRec] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    setRec(null); setErr(null);
    fetchRecord(seed.id)
      .then((d) => { if (alive) setRec(d); })
      .catch((e) => { if (alive) setErr(e.message); });
    return () => { alive = false; };
  }, [seed.id]);

  const p = rec?.party || seed;
  const edges = rec?.edges || [];
  const events = rec?.events || [];

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Record detail">
        <header>
          <div>
            <h2>{p.legal_name}</h2>
            <div className="bigprefix">
              {p.prefix ? `GS1 prefix ${p.prefix}` : <span className="null">no prefix — candidate</span>}
            </div>
            <div style={{ marginTop: 8 }}><StateChip state={p.state} /></div>
          </div>
          <button className="x" onClick={onClose} aria-label="Close">×</button>
        </header>

        <div className="scroll">
          {err && <div className="banner">{err}</div>}

          <div className="section">
            <h3>Identity</h3>
            <dl className="kv">
              <dt>Legal name</dt><dd>{p.legal_name}</dd>
              <dt>Prefix</dt><dd className="mono">{p.prefix || '—'}</dd>
              <dt>GLN</dt><dd className="mono">{p.gln || '—'}</dd>
              <dt>LEI</dt><dd className="mono">{p.lei || '—'}</dd>
              <dt>MO band</dt><dd>{p.mo || '—'}</dd>
              <dt>Locality</dt><dd>{[p.city, p.country].filter(Boolean).join(', ') || '—'}</dd>
              <dt>Source</dt><dd>{p.source}</dd>
              {p.exception_reason && (<><dt>Exception</dt><dd>{p.exception_reason}</dd></>)}
              <dt>Verified at</dt><dd>{dt(p.verified_at)}</dd>
              <dt>First seen</dt><dd>{dt(p.first_seen)}</dd>
            </dl>
          </div>

          <div className="section">
            <h3>Edges {edges.length ? `· ${edges.length}` : ''}</h3>
            {!rec && !err && <div className="empty">Loading…</div>}
            {rec && edges.length === 0 && <div className="empty">No relationships recorded.</div>}
            {edges.map((e) => (
              <div className="card" key={e.id}>
                <div className="top">
                  <span className="rel">{e.rel}</span>
                  <StateChip state={e.state} />
                </div>
                <div className="obj" style={{ marginTop: 4 }}>→ {e.object_label}</div>
                {e.object_prefix && <div className="objp">prefix {e.object_prefix}</div>}
                <div className="sub">
                  source {e.source}{e.inferred ? ' · inferred' : ''}{e.doc ? ` · ${e.doc}` : ''}
                </div>
              </div>
            ))}
          </div>

          <div className="section">
            <h3>Event history {events.length ? `· ${events.length}` : ''}</h3>
            {!rec && !err && <div className="empty">Loading…</div>}
            {rec && events.length === 0 && <div className="empty">No events recorded.</div>}
            {events.length > 0 && (
              <div className="timeline">
                {events.map((ev) => (
                  <div className="ev" key={ev.id}>
                    <div className="et">{ev.event_type}</div>
                    <div className="em">
                      {[ev.from_state, ev.to_state].filter(Boolean).join(' → ') || ''}
                      {ev.actor ? ` · ${ev.actor}` : ''} · {dt(ev.at)}
                    </div>
                    {ev.detail && Object.keys(ev.detail).length > 0 && (
                      <div className="ed">{JSON.stringify(ev.detail)}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
