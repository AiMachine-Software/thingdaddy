// S5 · THE BOOK - structure RATIFIED 2026-08-06.
// doctrine (F0-F11) + one full-depth chapter PER OPERATING SEGMENT + the walk.
// Diazyme = 1 segment = 1 chapter = ~80-100pp / 534 paras.
// Honeywell = 5 segments = 5 chapters = 118pp / 794 paras.
// Extent comes from real segment breadth, never from padding.
import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { BACK, BOOKS, FRONT } from '../data.js';
import { breakdown } from '../shape.js';
import { Missing, useRecord } from './Site.jsx';

export default function Book() {
  const { key } = useParams();
  const navigate = useNavigate();
  const { loading, rec } = useRecord(key);
  const [open, setOpen] = useState('segment0');
  const back = () => navigate('/thingsite/site/' + key);

  if (loading) return <section><div className="crumb" onClick={back}>&larr; back to the ThingSite</div><div className="stateline"><span style={{ opacity: 0.6 }}>loading…</span></div></section>;
  if (!rec) return <section><div className="crumb" onClick={back}>&larr; back to the ThingSite</div><Missing /></section>;

  const meta = BOOKS[key] || { segments: ['One segment'] };
  const segs = meta.segments.map((s, i) => ({ k: 'segment' + i, n: 'Chapter ' + (i + 1), t: s }));
  const all = [...FRONT, ...segs, ...BACK];

  return (
    <section>
      <div className="crumb" onClick={back}>&larr; back to the ThingSite</div>
      <div className="book">
        <div className="ch">A THINGBOOK</div>
        <h2 className="sh" style={{ marginBottom: 14 }}>{rec.label} — your physical estate, told in identity</h2>
        <div className="bookwrap">
          <div className="toc">
            <h4>{rec.label}</h4>
            <div className="tot">{meta.pages ? <><b>{meta.pages} pages</b> · {meta.paras} paragraphs · </> : null}{segs.length} operating segment{segs.length > 1 ? 's' : ''}</div>
            {all.map((c) => (
              <a key={c.k} className={c.k === open ? 'on' : ''} onClick={() => setOpen(c.k)}>
                <span>{c.t}</span><span className="pp">{c.n}</span>
              </a>
            ))}
            <div className="fm"><b>One full-depth chapter per operating segment.</b> Diazyme has one, so its book is one
              chapter plus the shared doctrine and walk. An enterprise with five segments gets five chapters at the same
              depth — <b>extent comes from real segment breadth, never from padding.</b></div>
          </div>
          <div className="chap"><Chapter rec={rec} k={open} meta={meta} /></div>
        </div>
      </div>
    </section>
  );
}

const Head = ({ n, t }) => <><div className="ch">{n}</div><h3 style={{ marginTop: 2 }}>{t}</h3></>;
const H4 = ({ children }) => <h4 style={{ fontSize: 15, margin: '16px 0 6px' }}>{children}</h4>;

function Chapter({ rec, k, meta }) {
  const p = rec.pillars, reg = rec.regulatory;

  if (k === 'cover') return (
    <>
      <Head n="COVER" t="The root" />
      <p>You have a website: one address, one page, for people to read. This is your <b>ThingSite</b>: one address for every physical thing you make, for a machine to resolve. Same idea, different internet.</p>
      <p>{rec.label} resolves to {rec.roots.length > 1
        ? <><b>{rec.roots.length} company prefixes</b></>
        : rec.roots.length === 1 ? <>one company prefix, <b>{rec.roots[0].prefix}</b></> : <b>no company prefix in production yet</b>}
        , and from that root the entire physical estate descends. Nine key types, one grammar, and a single prefix beneath them all.</p>
      <p>You have a website: one address, one page, for people to read. This is your <b>ThingSite</b>: one address for every physical thing you make, for a machine to resolve. Same idea, different internet.</p>
      <p className="close">Every fact in this book resolves to a provenanced source or is named plainly as a candidate. Where the record is certain it is marked verified and cited; where it is not, it is left honest. That discipline is not a limitation — it is the entire point.</p>
    </>
  );

  if (k === 'doctrine') return (
    <>
      <Head n="F0 – F11" t="The doctrine — one identity, seven layers" />
      <p>The shared opening of every book, identical across companies. One identity carried through seven layers: the thing, the document that governs it, the driver that operates it, the workflow that runs it, the place it stands, the agent that acts, and the record that it ran.</p>
      <p><b>A consumable is a class; an instrument is an individual.</b> A barcode tells you what something is. An identity tells you which one it is, where it stands, and what it is allowed to do.</p>
    </>
  );

  if (k === 'map') return (
    <>
      <Head n="MAP" t="The enterprise map" />
      <p>{rec.label} operates <b>{meta.segments.length} segment{meta.segments.length > 1 ? 's' : ''}</b>. Each gets one full-depth chapter, and the number of chapters is the number of segments — not a target length.</p>
      <ul className="rows">{meta.segments.map((s) => <li key={s}>{s}</li>)}</ul>
    </>
  );

  if (k.startsWith('segment')) {
    const i = +k.slice(7), name = meta.segments[i];
    return (
      <>
        <Head n={'CHAPTER ' + (i + 1)} t={name} />
        {/* the per-segment standard: lit nine-key board · estate opening · ranked gap · close */}
        <H4>The nine-key board</H4>
        <p>Every slot carries a value and an honest state. {p.P1_identity.count} identifiers on the board, {breakdown(p.P1_identity.grades)}. Nothing is left blank and nothing is filled with a guess — a slot declared honestly is stronger than a wrong row rendered as held.</p>
        <H4>The estate</H4>
        <p>At the surface sit <b>{p.P1_identity.count}</b> device identifiers — real, authority-attested records. They do not float free: they thread into assay families, where a reagent, its calibrator and its control compose a single working method. Beneath the consumables stand the things that actually do the work: {p.P2_drivers.count} drivers, {breakdown(p.P2_drivers.grades)}, and {p.P3_protocols.count} methods, {breakdown(p.P3_protocols.grades)}, each resolving as a governed document with its driver and its protocol.</p>
        {reg && (
          <>
            <H4>The regulatory load</H4>
            <p>{reg.clearances} clearances carrying {reg.codes} distinct product codes, each with a genuine number and date from the regulator’s own record, running {reg.first} to {reg.latest}. Write the rulebook once for a product code and every instance of that assay is governed by it. That timeline is the part no competitor can reconstruct after the fact — <b>you cannot backfill twenty-two years of a record you did not keep.</b></p>
          </>
        )}
        <H4>The ranked honest gap</H4>
        <p className="close">Ranked by mass, regulatory load and custody churn. {p.P4_cloud.slot ? p.P4_cloud.slot + ' is declared, not filled. ' : ''}The gaps are named here rather than hidden, because the ranked gap is what tells you where the next work is — and a book that shows none is a book that was not read.</p>
      </>
    );
  }

  if (k === 'register') return (
    <>
      <Head n="REGISTER" t="The consolidated register" />
      <p>Every identifier printed in this book, in one table, with its state and its source. {p.P5_graph.count} edges across the estate. Candidate keys are tagged as minted candidates on the prefix; a facility location, a trade item or a lot is <b>never fabricated</b> — it is left pending, with the authority named, because pending is not the same as absent.</p>
    </>
  );

  if (k === 'walk') return (
    <>
      <Head n="T7" t="The screen-by-screen walk" />
      <p>The shared walk, fixed and identical across every volume: search, reveal, the ThingSite, a row opened to its citation, the claim. It is the same in every book because it is the same product in every book.</p>
      <p className="close">Open item on the record: the walk still carries framing from the volume it was first shot on. In another company’s book that reads as a seam, and it is either neutralised or re-shot.</p>
    </>
  );

  return (
    <>
      <Head n="CLOSE" t="The three stacks, and an honest close" />
      <p>Three stacks meet on one identity: the things, the rules that govern them, and the systems that run them. The graph is what those become when they merge on a shared identity — not built over them, but what they turn into.</p>
      <div className="close">
        <p>Not everything here is verified, and this book says so plainly. The identities are candidates until you confirm them — because in the end the only authority on whether this is your estate is you.</p>
        <p>Anyone can generate a confident page about your company. No one else can hand you a resolvable, cited, checkable map of your physical world and invite you to correct it.</p>
      </div>
    </>
  );
}
