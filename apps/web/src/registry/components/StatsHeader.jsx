import React, { useEffect, useState } from 'react';
import { stats as fetchStats } from '../api.js';
import { STATE, COLOR } from '../theme.js';

const fmt = (n) => (n ?? 0).toLocaleString('en-US');

// Live counts across the whole 4M population. Refreshes on mount and every 20s,
// and whenever `refreshKey` changes (e.g. after a search that might have shifted
// counts). Reads GET /stats only.
export default function StatsHeader({ refreshKey, onError }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => fetchStats()
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) onError?.(e.message); });
    load();
    const t = setInterval(load, 20_000);
    return () => { alive = false; clearInterval(t); };
  }, [refreshKey]);

  const s = data?.by_state || {};
  const tiles = [
    { key: 'total', label: 'Total records', n: data?.total, swatch: COLOR.brand },
    { key: 'verified', label: STATE.verified.label, n: s.verified, swatch: STATE.verified.dot },
    { key: 'candidate', label: STATE.candidate.label, n: s.candidate, swatch: STATE.candidate.dot },
    { key: 'exception', label: STATE.exception.label, n: s.exception, swatch: STATE.exception.dot },
  ];

  return (
    <div className="stats">
      {tiles.map((t) => (
        <div key={t.key} className={`tile ${t.key === 'total' ? 'total' : ''}`}>
          {t.key !== 'total' && <span className="swatch" style={{ background: t.swatch }} />}
          <div className="n">{data ? fmt(t.n) : '—'}</div>
          <div className="k">{t.label}</div>
        </div>
      ))}
    </div>
  );
}
