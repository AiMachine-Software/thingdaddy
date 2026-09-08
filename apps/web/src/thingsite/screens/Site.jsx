// S3 / S4 · THINGSITE - their slice of the graph, then the pillars.
// depth=1 opens every row and its citation.
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { GRADE_LABEL, PILLARS } from '../data.js';
import { SliceGraph } from '../graph.jsx';
import { breakdown } from '../shape.js';
import { useThingSite } from '../store.jsx';

// Loads a record by key (fixture or live). Shared with Book and Claim.
export function useRecord(key) {
  const { loadRecord, setCurrentKey } = useThingSite();
  const [state, setState] = useState({ loading: true, rec: null });
  useEffect(() => {
    let alive = true;
    setState({ loading: true, rec: null });
    loadRecord(key).then((rec) => { if (alive) { setState({ loading: false, rec }); if (rec) setCurrentKey(key); } });
    return () => { alive = false; };
  }, [key, loadRecord, setCurrentKey]);
  return state;
}

export function Missing() {
  return (
    <div className="stateline">This record is not in memory (an unrooted party is only reachable from a search).{' '}
      <Link to="/thingsite">Start again</Link>.</div>
  );
}

export default function Site() {
  const { key } = useParams();
  const [params] = useSearchParams();
  const depth = params.get('depth') === '1';
  const { lastQuery } = useThingSite();
  const navigate = useNavigate();
  const { loading, rec } = useRecord(key);

  const back = () => navigate(lastQuery ? '/thingsite/reveal?q=' + encodeURIComponent(lastQuery) : '/thingsite');
  if (loading) return <section><div className="crumb" onClick={back}>&larr; back</div><div className="stateline"><span style={{ opacity: 0.6 }}>loading…</span></div></section>;
  if (!rec) return <section><div className="crumb" onClick={back}>&larr; back</div><Missing /></section>;

  return (
    <section>
      <div className="crumb" onClick={back}>&larr; back</div>
      <h2 className="sh">{rec.label}</h2>
      <div className="facts">
        {rec.roots.map((r) => (
          <React.Fragment key={r.prefix}>
            <span className="urn">{r.prefix}</span> <span className={'badge b-' + (r.state === 'verified' ? 'v' : 'c')}>{r.state}</span> &nbsp;
          </React.Fragment>
        ))}
        {rec.owned_by && <> &nbsp;·&nbsp; owned by {rec.owned_by}</>}
        &nbsp;·&nbsp; built from your own public record. <b style={{ color: 'var(--ink)' }}>Every line says where it came from.</b>
      </div>
      <p className="lead2">Your website is where people read about you. <b>Your ThingSite is where machines resolve your things.</b></p>
      {rec.graph && <SliceGraph graph={rec.graph} />}
      <div style={{ marginTop: 16 }}>
        {PILLARS.map(([k, label], i) => <Pillar key={k} p={rec.pillars && rec.pillars[k]} label={label} n={i + 1} depth={depth} recKey={key} />)}
      </div>
      <div style={{ marginTop: 16, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Link className="btn claim" to={'/thingsite/claim/' + key}>Claim this site</Link>
        <Link className="btn view" to={'/thingsite/book/' + key}>Read the Book</Link>
        <Link className="btn" to={'/thingsite/site/' + key + (depth ? '' : '?depth=1')}>{depth ? 'Collapse' : 'Open every row and its citation'}</Link>
      </div>
    </section>
  );
}

function Pillar({ p, label, n, depth, recKey }) {
  if (!p || p.count === 0) { // CONTAINER BEFORE CONTENT
    return (
      <div className="pillar">
        <div className="ph"><span className="n">{n}</span><h3>{label}</h3><span className="badge b-slot">slot</span></div>
        <div className="slotrow">{(p && p.slot) || 'nothing held yet — a declared gap, not a blank'}</div>
      </div>
    );
  }
  const shown = depth ? p.rows : p.rows.slice(0, 3);
  const hidden = p.rows.length - shown.length;
  return (
    <div className="pillar">
      <div className="ph"><span className="n">{n}</span><h3>{label}</h3><span className="cnt">{p.count} · {breakdown(p.grades)}</span></div>
      <ul className="rows">{shown.map((r, i) => <Row key={i} r={r} depth={depth} />)}</ul>
      {hidden > 0 && <Link className="more-rows" to={'/thingsite/site/' + recKey + '?depth=1'}>{hidden} more, with citations →</Link>}
      {p.slot && <div className="slotrow">{p.slot}</div>}
    </div>
  );
}

function Row({ r, depth }) {
  const src = r.source;
  const pg = src && src.page_printed ? ' p.' + src.page_printed + ' (pdf ' + src.page_pdf + ')' : '';
  return (
    <li>
      {r.label} <span className={'badge b-' + r.grade}>{GRADE_LABEL[r.grade]}</span>{' '}
      {r.urn ? <span className="urn">{r.urn}</span> : r.key_type ? <span className="urn" style={{ opacity: 0.55 }}>{r.key_type} — not minted</span> : null}{' '}
      {depth && src && <span className="cite">{src.url}{pg}{src.sha256 ? ' · ' + src.sha256.slice(0, 12) : ''}</span>}
      {r.reason && <div className="note">{r.reason}</div>}
      {r.slot && <div className="note">{r.slot}</div>}
    </li>
  );
}
