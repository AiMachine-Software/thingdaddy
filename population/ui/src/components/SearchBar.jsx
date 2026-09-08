import React from 'react';

// One box for name / prefix / GLN. Controlled input; parent debounces the query.
export default function SearchBar({ value, onChange }) {
  return (
    <div className="searchbar">
      <span className="icon">⌕</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search by legal name, GS1 prefix, or GLN…"
        spellCheck={false}
        autoFocus
      />
      {value && (
        <button className="clear" onClick={() => onChange('')} title="Clear" aria-label="Clear search">×</button>
      )}
    </div>
  );
}
