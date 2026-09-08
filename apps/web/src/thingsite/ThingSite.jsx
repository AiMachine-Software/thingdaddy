// The ThingSite flow (S1 - S6) as real routes:
//   /thingsite                 S1 home - search + the rotating hero
//   /thingsite/reveal?q=       S2 the reveal
//   /thingsite/site/:key       S3/S4 the ThingSite (?depth=1 opens every citation)
//   /thingsite/book/:key       S5 the Book
//   /thingsite/claim/:key      S6 the claim
// key = a fixture domain (acme.example, diazyme.com, ...) or a live record
// (p:<prefix>, y:<party_id>) found by search.
import React from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import ApiBar from './ApiBar.jsx';
import { NAV } from './data.js';
import Book from './screens/Book.jsx';
import Claim from './screens/Claim.jsx';
import Home from './screens/Home.jsx';
import Reveal from './screens/Reveal.jsx';
import Site from './screens/Site.jsx';
import { ThingSiteProvider, useThingSite } from './store.jsx';
import './thingsite.css';

export default function ThingSite() {
  return (
    <ThingSiteProvider>
      <Shell />
    </ThingSiteProvider>
  );
}

function Shell() {
  const { status, claimed } = useThingSite();
  return (
    <div className="ts">
      <ApiBar status={status} />
      <div className="wrap">
        <Rail claimed={claimed} />
        <div className="main"><div className="inner">
          <Routes>
            <Route index element={<Home />} />
            <Route path="reveal" element={<Reveal />} />
            <Route path="site/:key" element={<Site />} />
            <Route path="book/:key" element={<Book />} />
            <Route path="claim/:key" element={<Claim />} />
            <Route path="*" element={<Navigate to="/thingsite" replace />} />
          </Routes>
        </div></div>
      </div>
    </div>
  );
}

// The rail. Home, Identify and ThingSite are built; the rest are the next
// tranche (S7 owner console, WHOIS, Get a Prefix, Pricing, Samples) and say so
// in place instead of an alert.
function Rail({ claimed }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { currentKey, lastQuery, notice, setNotice } = useThingSite();
  const active = pathname.includes('/reveal') ? 'reveal'
    : /\/(site|book|claim)\//.test(pathname) ? 'site' : 'home';

  function go(id) {
    setNotice('');
    if (id === 'home') return navigate('/thingsite');
    if (id === 'reveal') return navigate('/thingsite/reveal' + (lastQuery ? '?q=' + encodeURIComponent(lastQuery) : ''));
    if (id === 'site') return navigate(currentKey ? '/thingsite/site/' + currentKey : '/thingsite');
    return setNotice(id + ' — not built. S7 owner console, WHOIS, Get a Prefix, Pricing and Samples are the next tranche.');
  }

  return (
    <aside className="rail">
      {NAV.map(([id, en, th]) => (
        <a key={id} className={active === id ? 'on' : ''} onClick={() => go(id)}>
          <div className="en">{en}</div><div className="th">{th}</div>
        </a>
      ))}
      {notice && <div className="railnote">{notice}</div>}
      <div className="railfoot">claimed <b>{claimed}</b></div>
    </aside>
  );
}
