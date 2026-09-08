import React from 'react';
import { stateStyle } from '../theme.js';

// The state pill — the same green/amber/red language everywhere it appears.
export default function StateChip({ state }) {
  const s = stateStyle(state);
  return (
    <span className="state" style={{ color: s.fg, background: s.bg }}>
      <span className="sdot" style={{ background: s.dot }} />
      {s.label}
    </span>
  );
}
