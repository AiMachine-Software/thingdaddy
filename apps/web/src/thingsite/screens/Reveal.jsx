// S2 · THE REVEAL - live first, fixture only as a labelled fallback.
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import * as api from '../api.js';
import { RECORDS } from '../data.js';
import { shapeParty } from '../shape.js';
import { useThingSite } from '../store.jsx';

export function Badge({ live }) {
  return <span className={'srcbadge ' + (live ? 'live' : 'fix')}>{live ? 'LIVE' : 'FIXTURE'}</span>;
}

export function Card({ cls, name, badge, urn, note, actions }) {
  return (
    <div className={'rcard ' + (cls || '')}>
      <div style={{ minWidth: 225 }}>
        <div className="nm">{name} {badge && <span className={'badge b-' + badge[0]}>{badge[1]}</span>}</div>
        {urn && <div style={{ marginTop: 6 }}><span className="urn">{urn}</span></div>}
      </div>
      <div className="sp" />
      {(actions || []).map((a, i) => (
        a.to
          ? <Link key={i} className={'btn ' + a.c} to={a.to}>{a.t}</Link>
          : <button key={i} type="button" className={'btn ' + a.c} onClick={a.fn}>{a.t}</button>
      ))}
      {note && <div className="note">{note}</div>}
    </div>
  );
}

const Sep = () => <> &nbsp;·&nbsp; </>;
function joinNotes(parts) {
  const list = parts.filter(Boolean);
  return list.map((p, i) => <React.Fragment key={i}>{i > 0 && <Sep />}{p}</React.Fragment>);
}
const NotRead = () => <span style={{ color: 'var(--td-candidate)' }}>licence type not read — candidate, never root</span>;

export default function Reveal() {
  const [params] = useSearchParams();
  const q = (params.get('q') || '').trim();
  const { putLive, setLastQuery, setCurrentKey } = useThingSite();
  const navigate = useNavigate();
  const [res, setRes] = useState({ mode: 'idle' });

  useEffect(() => {
    setLastQuery(q);
    if (!q) { setRes({ mode: 'idle' }); return undefined; }
    let alive = true;
    setRes({ mode: 'loading' });
    api.search(q).then((rows) => {
      if (!alive) return;
      if (rows === null) { setRes({ mode: 'fixture' }); return; }         // API down -> the fixture
      if (!rows.length) { setRes({ mode: 'none' }); return; }             // API up, genuinely not found
      const parties = rows.slice(0, 8).map((p) => shapeParty(p));         // duplicates visible, never merged silently
      parties.forEach((p) => {
        if (p.roots.length) p.roots.forEach((r) => putLive('p:' + r.prefix, p));
        else putLive('y:' + p.party_id, p);
      });
      setRes({ mode: 'live', parties });
    });
    return () => { alive = false; };
  }, [q, putLive, setLastQuery]);

  return (
    <section>
      <div className="crumb" onClick={() => navigate('/thingsite')}>&larr; start again</div>
      {res.mode === 'loading' && <div className="stateline"><span style={{ opacity: 0.6 }}>searching…</span></div>}
      {res.mode === 'live' && <LiveResult q={q} parties={res.parties} />}
      {res.mode === 'none' && (
        <>
          <div className="stateline">Nothing in the register under that name. <Badge live /> <b>That is not the same as not looked at.</b></div>
          <Card cls="u" name={q} badge={['slot', 'not in the register']}
            note="Searched and not found. Tell us and it enters the queue with your name against it."
            actions={[{ t: 'Pre-build mine', c: 'claim' }]} />
        </>
      )}
      {res.mode === 'fixture' && <FixtureResult raw={q} onKey={setCurrentKey} />}
    </section>
  );
}

/* ---- LIVE PATH: one card PER PREFIX - a ThingSite is keyed by prefix, not by company ---- */
function LiveResult({ q, parties }) {
  const rooted = parties.filter((p) => p.roots.length);
  const unrooted = parties.filter((p) => !p.roots.length);
  return (
    <>
      <div className="stateline">
        You have a website. <b>This is what the register actually holds</b> for {q}. <Badge live />
        {parties.length > 1 && <> &nbsp;<b>{parties.length} party rows</b> — duplicates are shown, never merged silently.</>}
      </div>
      {rooted.map((p) => p.roots.map((root) => {
        const key = 'p:' + root.prefix;
        return (
          <Card key={key} cls={root.state === 'verified' ? '' : 'c'} name={p.label}
            badge={[root.state === 'verified' ? 'v' : 'c', root.state]} urn={'prefix ' + root.prefix}
            note={joinNotes(['party ' + p.party_id,
              root.licence_type ? 'licence type: ' + root.licence_type : <NotRead />,
              root.gln ? 'GLN ' + root.gln : null, root.mo || null,
              root.doors.length ? root.doors[0].url : 'no door on file',
              'via ' + root.provenance.via])}
            actions={[{ t: 'View ThingSite', c: 'view', to: '/thingsite/site/' + key },
              { t: 'Claim this licence', c: 'claim', to: '/thingsite/claim/' + key },
              { t: 'This one is not us', c: 'ghost' }]} />
        );
      }))}
      {/* an unrooted party is NOT nothing. Show it, say why, and name what is missing. */}
      {unrooted.map((p) => {
        const key = 'y:' + p.party_id;
        return (
          <Card key={key} cls="e" name={p.label} badge={['e', 'no prefix in production']}
            note={<>party {p.party_id} <Sep /> state {p.state} <Sep /> source {p.provenance.via}<br />
              This company is in the register with <b>no prefix attached in production</b>. A prefix may exist in
              staging and not yet be promoted — that is a gap in our machine, not a statement about your company.</>}
            actions={[{ t: 'Open what is held', c: 'view', to: '/thingsite/site/' + key }]} />
        );
      })}
    </>
  );
}

/* ---- the fixture path, unchanged, but always badged FIXTURE ---- */
function FixtureResult({ raw, onKey }) {
  const q = raw.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
  const key = q && (Object.keys(RECORDS).find((d) => RECORDS[d].label && RECORDS[d].label.toLowerCase().includes(q))
    || Object.keys(RECORDS).find((d) => d.startsWith(q.split('.')[0])));
  const rec = key ? RECORDS[key] : null;
  useEffect(() => { if (key) onKey(key); }, [key, onKey]);

  if (!rec) return (
    <>
      <div className="stateline">We have not built this one yet. <Badge /> <b>That is not the same as not finding it.</b></div>
      <Card cls="u" name={raw} badge={['slot', 'not yet built']}
        note="No one has looked. Ask and it enters the queue with your name against it."
        actions={[{ t: 'Pre-build mine', c: 'claim' }]} />
    </>
  );
  if (rec.demo) return (
    <>
      <div className="stateline"><b>This is the walkthrough, not a real company.</b> <Badge /> ACME runs on the reserved
        demonstration prefix <b>9520001</b> — a range the standard reserves for demonstration, which no real company
        holds. Every identifier is graded <b>built</b>.</div>
      <Card name="ACME Corp" badge={['b', 'built']} urn="prefix 9520001"
        note="A range the standard reserves for demonstration. No real company holds it, so nothing here can collide with a real estate."
        actions={[{ t: 'Walk through the ThingSite', c: 'view', to: '/thingsite/site/acme.example' }]} />
    </>
  );
  if (rec.state === 'exception') {
    const lead = rec.related_rooted;
    return (
      <>
        <div className="stateline">No licence on record for this company. <Badge /> <b>Nothing is issued here.</b></div>
        <Card cls="e" name={rec.label} badge={['e', 'exception']}
          note={<>Read at {rec.provenance.read_at} via {rec.provenance.via}.
            {lead && <><br /><b>{lead.label}</b> (prefix {lead.prefix}) does hold one — a {lead.relation}. That is a lead, not a root.</>}</>}
          actions={[{ t: 'Get a prefix', c: 'claim' }]} />
      </>
    );
  }
  const multi = rec.roots.length > 1;
  return (
    <>
      <div className="stateline">You have a website. <b>We already built your ThingSite</b> <Badge /> — from your own public record, candidate until you confirm it.</div>
      {rec.roots.map((root) => (
        <Card key={root.prefix} cls={root.state === 'verified' ? '' : 'c'} name={rec.label}
          badge={[root.state === 'verified' ? 'v' : 'c', root.state]} urn={'prefix ' + root.prefix}
          note={joinNotes([root.registered_to || null,
            root.licence_type ? 'licence type: ' + root.licence_type : <NotRead />,
            root.gln ? 'GLN ' + root.gln : null,
            root.doors.length ? root.doors.map((d) => d.url).join(' · ') : 'no door on file',
            'via ' + root.provenance.via])}
          actions={multi
            ? [{ t: 'View ThingSite', c: 'view', to: '/thingsite/site/' + key },
              { t: 'Claim this licence', c: 'claim', to: '/thingsite/claim/' + key },
              { t: 'This one is not us', c: 'ghost' }]
            : [{ t: 'View ThingSite', c: 'view', to: '/thingsite/site/' + key },
              { t: 'Claim this ThingSite', c: 'claim', to: '/thingsite/claim/' + key }]} />
      ))}
    </>
  );
}
