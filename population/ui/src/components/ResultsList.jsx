import React from 'react';
import ResultRow from './ResultRow.jsx';

// The paginated result set. Renders whatever rows the parent has accumulated
// across keyset pages and exposes "Load more" while has_more is true. Never
// holds more than the user has explicitly paged to — never the whole table.
export default function ResultsList({ rows, hasMore, loading, onOpen, onLoadMore }) {
  if (!loading && rows.length === 0) {
    return <div className="status">No records match. Try a different name, prefix, or GLN.</div>;
  }
  return (
    <>
      <div className="results">
        {rows.map((row) => (
          <ResultRow key={row.id} row={row} onOpen={onOpen} />
        ))}
      </div>
      {loading && <div className="status">Searching…</div>}
      {!loading && hasMore && (
        <button className="loadmore" onClick={onLoadMore}>Load more</button>
      )}
      {!loading && !hasMore && rows.length > 0 && (
        <div className="status">End of results · {rows.length.toLocaleString('en-US')} shown</div>
      )}
    </>
  );
}
