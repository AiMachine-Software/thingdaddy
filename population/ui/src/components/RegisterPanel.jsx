import React, { useState } from 'react';
import { ingest as apiIngest, WRITES_ENABLED } from '../api.js';

// "Land → Register": add a party to the population registry. ALWAYS lands as a
// candidate (the server forces it) — registration is the start of the journey,
// not a verification. A prefix here is a claim to be checked later, never a mint.
export default function RegisterPanel({ onClose, onRegistered }) {
  const [f, setF] = useState({ legal_name: '', prefix: '', gln: '', mo: '', city: '', country: '' });
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState(null);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  const submit = async () => {
    setBusy(true); setOutcome(null);
    const row = {};
    for (const [k, v] of Object.entries(f)) if (v.trim()) row[k] = v.trim();
    try {
      const r = await apiIngest([row], 'manual');
      const res = r.results?.[0];
      setOutcome({ kind: 'ok', title: `Landed as ${res?.state || 'candidate'}`, body: `Party #${res?.id} is in the registry. It stays a candidate until an authority confirms its prefix — nothing verifies on a guess.` });
      setTimeout(() => onRegistered && onRegistered(res?.id), 1100);
    } catch (e) {
      if (e.disabled) setOutcome({ kind: 'err', title: 'Writes disabled in this build', body: e.message });
      else setOutcome({ kind: 'err', title: `Rejected (${e.status || 'error'})`, body: e.message });
    } finally { setBusy(false); }
  };

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header><h3>Register an identity</h3><button className="x" onClick={onClose}>×</button></header>
        <div className="body">
          <div className="form" style={{ border: 0, padding: 0 }}>
            <div className="field"><label>Legal name *</label>
              <input style={{ fontFamily: 'inherit' }} value={f.legal_name} onChange={set('legal_name')} placeholder="Acme Instruments, Inc." /></div>
            <div className="field"><label>GS1 prefix (candidate — checked later)</label>
              <input value={f.prefix} onChange={set('prefix')} placeholder="0801234 (optional)" /></div>
            <div className="field"><label>GLN</label>
              <input value={f.gln} onChange={set('gln')} placeholder="optional" /></div>
            <div className="field"><label>MO band</label>
              <input style={{ fontFamily: 'inherit' }} value={f.mo} onChange={set('mo')} placeholder="e.g. GS1 US (optional)" /></div>
            <div className="actions">
              <button className="btn primary" disabled={busy || !f.legal_name.trim()} onClick={submit}>{busy ? 'Landing…' : 'Register (lands candidate)'}</button>
              <button className="btn ghost" onClick={onClose} disabled={busy}>Cancel</button>
            </div>
            <p className="hint">Registration never verifies. The row lands as a <b>candidate</b>; verification happens only through the claim/gate path with a real GS1 authority. {!WRITES_ENABLED && <span style={{ color: '#991B1B' }}>This build has no write token set (VITE_INGEST_TOKEN), so writes are blocked client-side.</span>}</p>
            {outcome && <div className={`outcome ${outcome.kind}`}><div className="oh">{outcome.title}</div>{outcome.body}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
