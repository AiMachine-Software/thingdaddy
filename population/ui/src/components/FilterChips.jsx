import React from 'react';
import { STATE } from '../theme.js';

const ORDER = ['verified', 'candidate', 'exception'];

// Single-select state filter. Clicking the active chip clears it (back to "all").
// Green / amber / red, matched to the state color language.
export default function FilterChips({ value, onChange }) {
  return (
    <div className="chips">
      <span className="lbl">Filter:</span>
      <button
        className={`chip ${!value ? 'active' : ''}`}
        style={!value ? { color: '#374151' } : undefined}
        onClick={() => onChange(null)}
      >
        All
      </button>
      {ORDER.map((k) => {
        const s = STATE[k];
        const active = value === k;
        return (
          <button
            key={k}
            className={`chip ${active ? 'active' : ''}`}
            style={active ? { color: s.fg, background: s.bg } : undefined}
            onClick={() => onChange(active ? null : k)}
          >
            <span className="cdot" style={{ background: s.dot }} />
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
