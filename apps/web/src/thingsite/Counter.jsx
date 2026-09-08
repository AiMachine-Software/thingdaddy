// THE COUNTER - composed from the sources, never asserted. The total is
// arithmetic: change a source and the total follows.
// TODO(KJ): both fixture figures are the recorded ones. Re-run the DB1 count
// and replace them - the estate line elsewhere reads 9.88M, which does not
// reconcile with the sum below. Whichever survives the query wins.
//
// THE HARVEST, REPLAYED. It does not tick up on a timer - it lands in bursts,
// the way a source actually arrives: a file loads and thousands appear at
// once, then a pause, then more. FDA lands first, then China stacks on top,
// and it STOPS at the current total. Nothing is being added while you watch.
//
// If the API answered, every figure comes from /stats - a number anyone can
// check with one curl - instead of the harvest constants.
import React, { useEffect, useState } from 'react';
import { SOURCES } from './data.js';

export default function Counter({ status }) {
  const [shown, setShown] = useState(0);
  const [entities, setEntities] = useState(0);

  const live = status.state === 'live' && status.stats && typeof status.stats.total === 'number';
  const sources = live
    ? [{ name: 'production records', devices: status.stats.total, prefixes: (status.stats.by_state || {}).verified || 0 }]
    : SOURCES;
  const TOTAL = sources.reduce((a, s) => a + s.devices, 0);
  const ENTITIES = sources.reduce((a, s) => a + s.prefixes, 0);

  useEffect(() => {
    if (status.state === 'checking') return undefined; // wait for the API verdict
    const timers = [];
    const later = (fn, ms) => timers.push(setTimeout(fn, ms));
    let acc = 0, done = 0;
    function source(i) {
      if (i >= sources.length) { setShown(TOTAL); setEntities(ENTITIES); return; } // all in - settle on the exact figures
      const src = sources[i], target = done + src.devices;
      const STEPS = 64, step = src.devices / STEPS;
      let t = 0;
      (function burst() {
        t += 1;
        // uneven file sizes; never 0, or a small live total would sit at 0 for the full run
        const batch = Math.max(1, Math.floor(step * (0.55 + Math.random() * 0.95)));
        acc = Math.min(target, acc + batch);
        setShown(acc);
        setEntities(TOTAL ? Math.floor(ENTITIES * (acc / TOTAL)) : 0);
        if (acc < target && t < STEPS * 2) later(burst, 150 + Math.random() * 420); // the pause between files
        else { acc = target; done = target; setShown(acc); later(() => source(i + 1), 1400); } // the next source opens
      })();
    }
    later(() => source(0), 900);
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.state]);

  return (
    <div className="counter">
      <span className="odo">{shown.toLocaleString()}</span>
      <span style={{ marginLeft: 8 }}>identities &nbsp;·&nbsp;
        <span>{entities.toLocaleString()}</span> <span>{live ? 'verified' : 'entities registered'}</span>
        &nbsp;·&nbsp; <span className="yours">is your company one of them?</span></span>
    </div>
  );
}
