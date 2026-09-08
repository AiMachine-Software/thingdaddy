// Shared state of the ThingSite flow: API status, the live records found by
// search (keyed p:<prefix> or y:<party_id>), the last query, the claim count.
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import * as api from './api.js';
import { RECORDS } from './data.js';
import { shapeGraph, shapeParty, shapePillars } from './shape.js';

const Ctx = createContext(null);

export function ThingSiteProvider({ children }) {
  const [status, setStatus] = useState({ state: 'checking' });
  const live = useRef({});                 // key -> shaped record (+ _loaded once pillars/graph fetched)
  const [lastQuery, setLastQuery] = useState('');
  const [currentKey, setCurrentKey] = useState(null);
  const [claimed, setClaimed] = useState(0);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let alive = true;
    api.health().then((h) => {
      if (!alive) return;
      setStatus(h.live ? { state: 'live', db: h.db, stats: h.stats } : { state: 'down' });
    });
    return () => { alive = false; };
  }, []);

  const putLive = useCallback((key, rec) => { live.current[key] = rec; }, []);

  // A record by key: a fixture from RECORDS, or a live one. A live prefix key
  // that is not in memory (deep link, reload) is rebuilt from /record/prefix;
  // an unrooted party key (y:) cannot be, and resolves to null.
  const loadRecord = useCallback(async (key) => {
    if (RECORDS[key]) return RECORDS[key];
    let rec = live.current[key];
    if (!rec && key.startsWith('p:')) {
      // /record/prefix answers { party, edges, events }; /search answers bare party rows.
      const r = await api.recordByPrefix(key.slice(2));
      const p = r && (r.party || r);
      if (p && p.legal_name) { rec = shapeParty(p); live.current[key] = rec; }
    }
    if (!rec) return null;
    if (!rec._loaded) {
      const node = await api.nodeForParty(rec.party_id);
      const [comp, assoc] = await Promise.all([
        api.completeness(rec.party_id),
        node && node.id ? api.associations(node.id) : Promise.resolve(null),
      ]);
      rec.pillars = shapePillars(comp);
      rec.graph = shapeGraph(rec.label, assoc);
      rec._loaded = true;
    }
    return rec;
  }, []);

  const value = useMemo(() => ({
    status, putLive, loadRecord,
    lastQuery, setLastQuery, currentKey, setCurrentKey,
    claimed, addClaim: () => setClaimed((n) => n + 1),
    notice, setNotice,
  }), [status, putLive, loadRecord, lastQuery, currentKey, claimed, notice]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useThingSite() {
  return useContext(Ctx);
}
