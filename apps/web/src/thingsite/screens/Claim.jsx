// S6 · CLAIM - the email domain IS the verification.
import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { FREE_MAIL } from '../data.js';
import { host } from '../shape.js';
import { useThingSite } from '../store.jsx';
import { Missing, useRecord } from './Site.jsx';

export default function Claim() {
  const { key } = useParams();
  const navigate = useNavigate();
  const { addClaim } = useThingSite();
  const { loading, rec } = useRecord(key);
  const [name, setName] = useState('');
  const [mail, setMail] = useState('');
  const [li, setLi] = useState('');
  const [verdict, setVerdict] = useState(null);
  const back = () => navigate('/thingsite/site/' + key);

  if (loading) return <section><div className="crumb" onClick={back}>&larr; back to the ThingSite</div><div className="stateline"><span style={{ opacity: 0.6 }}>loading…</span></div></section>;
  if (!rec) return <section><div className="crumb" onClick={back}>&larr; back to the ThingSite</div><Missing /></section>;

  const held = rec.roots.flatMap((r) => r.doors).map((d) => host(d.url));

  function verify(e) {
    e.preventDefault();
    const m = mail.trim().toLowerCase();
    const domain = m.split('@')[1];
    const refuse = (c, msg) => setVerdict({ refuse: c, msg });
    if (!domain) return refuse('malformed-address', 'That is not an address we can read.');
    if (FREE_MAIL.has(domain)) return refuse('free-mail-address', 'Use an address at your company domain. The domain is the verification — a free-mail address proves nothing.');
    if (!held.length) return refuse('no-door-held', 'We hold no web door for this company yet, so there is nothing to match against. Tell us the domain and it becomes the door.');
    if (!held.includes(domain)) return refuse('domain-not-held', 'We hold ' + held.join(', ') + ' for this company. If ' + domain + ' is right, tell us and we will verify it — we will not assume it.');
    addClaim();
    setVerdict({ ok: true, mail: m, token: 'td_tok_' + rec.roots[0].prefix + '_' + Math.random().toString(36).slice(2, 10) });
  }

  return (
    <section>
      <div className="crumb" onClick={back}>&larr; back to the ThingSite</div>
      <form className="form" onSubmit={verify}>
        <h2 className="sh" style={{ fontSize: 22 }}>Claim {rec.label}</h2>
        <p style={{ color: 'var(--mut)', fontSize: 14, margin: '0 0 6px' }}>Your company email is the verification — it must match a door we already hold. That is the whole check.</p>
        <label htmlFor="cname">Your name</label>
        <input id="cname" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" />
        <label htmlFor="cmail">Company email</label>
        <input id="cmail" type="email" value={mail} onChange={(e) => setMail(e.target.value)} placeholder={'you@' + (held[0] || 'yourcompany.com')} />
        <div className="hint">We hold {held.length ? held.join(', ') : 'no door for this company yet'}. The domain must match — that is the check.</div>
        <label htmlFor="cli">LinkedIn <span style={{ fontWeight: 400, color: 'var(--mut)' }}>— optional</span></label>
        <input id="cli" type="text" value={li} onChange={(e) => setLi(e.target.value)} placeholder="linkedin.com/in/…" />
        <div className="hint">So we know who to come back to. Nothing is looked up without your say-so.</div>
        <div style={{ marginTop: 20 }}><button type="submit" className="btn claim">Verify and issue my token</button></div>
        {verdict && verdict.refuse && <div className="refuse"><b>Refused — {verdict.refuse}</b><br />{verdict.msg}</div>}
        {verdict && verdict.ok && (
          <div className="ok"><b>Verified.</b> {verdict.mail} matches the door we already held. Your token is issued, your ThingSite is skinned to your own colours, and the demo runs on <b>your</b> prefix.
            <div className="tok">{verdict.token}</div>
            <div className="note" style={{ marginTop: 10 }}>Your ThingSite is published <b>as we found it</b> — nothing corrected, nothing assumed. What is wrong is yours to correct.</div>
            <div className="note" style={{ marginTop: 8 }}>Nothing was minted. You mint; we register and resolve.</div>
          </div>
        )}
      </form>
    </section>
  );
}
