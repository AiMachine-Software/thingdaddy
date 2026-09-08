// health - say plainly whether we are on the database or on fixtures.
import React, { useState } from 'react';
import { API, useRawLog } from './api.js';

export default function ApiBar({ status }) {
  const [raw, setRaw] = useState(false);
  const log = useRawLog();
  const st = status.stats;
  return (
    <>
      <div className="apibar">
        <span className={'dot' + (status.state === 'live' ? ' is-ok' : status.state === 'down' ? ' is-bad' : '')} />
        <span>
          {status.state === 'checking' && 'checking the API…'}
          {status.state === 'live' && (
            <>
              <b>LIVE</b> — {API || 'same origin'} · db {status.db}
              {st && (
                <> &nbsp;·&nbsp; {st.total.toLocaleString()} records (
                  {Object.entries(st.by_state || {}).map(([k, v]) => v.toLocaleString() + ' ' + k).join(' · ')})</>
              )}
            </>
          )}
          {status.state === 'down' && (
            <><b>NO API</b> — falling back to fixtures. Start it with <code>npm run dev:api</code> from the repo root, then reload.</>
          )}
        </span>
        <span className="sp" />
        <label className="rawtog"><input type="checkbox" checked={raw} onChange={(e) => setRaw(e.target.checked)} /> show raw responses</label>
      </div>
      {raw && <pre className="rawpanel">{log.join('\n\n──────────\n\n')}</pre>}
    </>
  );
}
