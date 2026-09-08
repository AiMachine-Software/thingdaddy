import React from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import ThingDaddyPlatform from './platform/ThingDaddy_V4_Unified.jsx';
import Registry from './registry/App.jsx';
import './registry/styles.css';
import DemoIndex from './pages/DemoIndex.jsx';

// The three surfaces of the site behind one nav:
//   /          the V4 platform (single-file React app, untouched)
//   /registry  the population registry UI (reads/writes the population API)
//   /demo      index of the legacy single-file HTML demos in public/demo/
const LINKS = [
  { to: '/', label: 'Platform', end: true },
  { to: '/registry', label: 'Registry' },
  { to: '/demo', label: 'Demo pages' },
];

export default function App() {
  return (
    <>
      <nav className="shell-nav" aria-label="Site">
        <span className="shell-brand">ThingDaddy</span>
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}
            className={({ isActive }) => 'shell-link' + (isActive ? ' is-active' : '')}>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <Routes>
        <Route path="/" element={<ThingDaddyPlatform />} />
        <Route path="/registry" element={<div className="registry"><Registry /></div>} />
        <Route path="/demo" element={<DemoIndex />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
