import React from 'react';
import StateChip from './StateChip.jsx';

// One party in the result list. Identity-first: legal name, then the GS1 prefix
// (the root) in monospace. Prefix-less rows say so plainly (candidate reality).
export default function ResultRow({ row, onOpen }) {
  return (
    <button className="row" onClick={() => onOpen(row)}>
      <div>
        <div className="name">{row.legal_name}</div>
        <div className="prefix">
          {row.prefix ? `prefix ${row.prefix}` : <span className="null">no prefix yet</span>}
        </div>
        <div className="meta">
          {row.mo && <span>MO <b>{row.mo}</b></span>}
          {row.gln && <span>GLN <b>{row.gln}</b></span>}
          <span>source <b>{row.source}</b></span>
        </div>
      </div>
      <div className="right">
        <StateChip state={row.state} />
      </div>
    </button>
  );
}
