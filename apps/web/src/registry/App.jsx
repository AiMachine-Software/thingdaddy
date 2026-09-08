import React, { useCallback, useEffect, useRef, useState } from 'react';
import { search as apiSearch, BASE, WRITES_ENABLED } from './api.js';
import StatsHeader from './components/StatsHeader.jsx';
import SearchBar from './components/SearchBar.jsx';
import FilterChips from './components/FilterChips.jsx';
import ResultsList from './components/ResultsList.jsx';
import Workspace from './components/Workspace.jsx';
import RegisterPanel from './components/RegisterPanel.jsx';

// One integrated flow over the real population registry:
//   land → find your company → claim → manage (the 5-pillar workspace)
// Reads come from GET /search + /record; writes (register, claim) route through
// the token-gated, fail-closed API. The UI never mints or fabricates a value.
export default function App() {
  const [query, setQuery] = useState('');
  const [term, setTerm] = useState('');
  const [stateFilter, setStateFilter] = useState(null);
  const [rows, setRows] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [subject, setSubject] = useState(null);   // the party being managed (workspace)
  const [registering, setRegistering] = useState(false);
  const reqToken = useRef(0);

  useEffect(() => { const t = setTimeout(() => setTerm(query.trim()), 300); return () => clearTimeout(t); }, [query]);

  const runSearch = useCallback(async () => {
    const token = ++reqToken.current;
    setLoading(true); setError(null);
    try {
      const data = await apiSearch({ q: term, state: stateFilter, cursor: null });
      if (token !== reqToken.current) return;
      setRows(data.rows); setCursor(data.next_cursor); setHasMore(data.has_more);
    } catch (e) {
      if (token !== reqToken.current) return;
      setError(e.message); setRows([]); setHasMore(false);
    } finally { if (token === reqToken.current) setLoading(false); }
  }, [term, stateFilter]);

  useEffect(() => { runSearch(); }, [runSearch]);

  const loadMore = useCallback(async () => {
    if (!hasMore || loading) return;
    const token = ++reqToken.current; setLoading(true);
    try {
      const data = await apiSearch({ q: term, state: stateFilter, cursor });
      if (token !== reqToken.current) return;
      setRows((prev) => [...prev, ...data.rows]); setCursor(data.next_cursor); setHasMore(data.has_more);
    } catch (e) { if (token === reqToken.current) setError(e.message); }
    finally { if (token === reqToken.current) setLoading(false); }
  }, [hasMore, loading, term, stateFilter, cursor]);

  const stage = subject ? (subject.state === 'verified' ? 'manage' : 'claim') : 'find';
  const steps = [
    { id: 'land', label: 'Land' },
    { id: 'find', label: 'Find your company' },
    { id: 'claim', label: 'Claim' },
    { id: 'manage', label: 'Manage' },
  ];
  const order = ['land', 'find', 'claim', 'manage'];
  const curIdx = order.indexOf(stage === 'find' ? 'find' : stage);

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <div className="masthead">
            <span className="dot" />
            <h1>ThingDaddy — Registrar</h1>
            <span className="tag">one In-Context Identity spine · prefix-rooted</span>
          </div>
          <div className="subtle">Live over the population registry · API {BASE}{WRITES_ENABLED ? '' : ' · read-only build'}</div>
        </div>
        {!subject && <button className="btn primary" onClick={() => setRegistering(true)}>+ Register an identity</button>}
      </div>

      <div className="flow">
        {steps.map((s, i) => (
          <React.Fragment key={s.id}>
            <span className={`step${order.indexOf(s.id) < curIdx ? ' done' : ''}${order.indexOf(s.id) === curIdx ? ' on' : ''}`}>
              <span className="b">{order.indexOf(s.id) < curIdx ? '✓' : i + 1}</span>{s.label}
            </span>
            {i < steps.length - 1 && <span className="arw">→</span>}
          </React.Fragment>
        ))}
      </div>

      {error && !subject && <div className="banner">{error}</div>}

      {subject ? (
        <Workspace
          seed={subject}
          onBack={() => { setSubject(null); runSearch(); }}
          onChanged={runSearch}
        />
      ) : (
        <>
          <StatsHeader refreshKey={term + '|' + (stateFilter || '')} onError={setError} />
          <div className="controls">
            <SearchBar value={query} onChange={setQuery} />
            <FilterChips value={stateFilter} onChange={setStateFilter} />
          </div>
          <ResultsList rows={rows} hasMore={hasMore} loading={loading} onOpen={setSubject} onLoadMore={loadMore} />
        </>
      )}

      {registering && (
        <RegisterPanel
          onClose={() => setRegistering(false)}
          onRegistered={() => { setRegistering(false); setQuery(''); setTerm(''); runSearch(); }}
        />
      )}
    </div>
  );
}
