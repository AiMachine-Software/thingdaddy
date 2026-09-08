import React from 'react';

// The legacy single-file HTML demos live in public/demo/ and are served as plain
// files next to the app. They open in the same tab; the browser back button
// returns here.
const BASE = import.meta.env.BASE_URL; // "/" or "/thingdaddy/"

const STATIC = [
  ['screens.html', 'Screens S1 – S6', 'Deployable demo. Each panel is labelled LIVE or FIXTURE; without an API every panel is FIXTURE.'],
  ['console.html', 'Console', 'Deployable demo, console view. FIXTURE data when no API is reachable.'],
  ['td_screens_live.html', 'Screens S1 – S6 (fill variant)', 'Earlier version of the demo screens.'],
  ['td_console.html', 'Console (fill variant)', 'Earlier version of the console.'],
  ['td_configurator.html', 'Configurator', 'Self-contained page, no backend needed.'],
  ['GA_ThingSite.html', 'General Atomics · ThingSite', 'Generated ThingSite page for one company, fully static.'],
];

const NEEDS_API = [
  ['td_home.html', 'Home', 'Calls /api/companies_full. Shows "engine unreachable" without the API.'],
  ['td_thingsite.html', 'ThingSite', 'Calls the population API for prefix lookup and search.'],
  ['td_demo.html', 'Demo', 'Hard-wired to http://127.0.0.1:8793, local machine only.'],
];

function List({ items }) {
  return (
    <ul>
      {items.map(([file, title, note]) => (
        <li key={file}>
          <a href={`${BASE}demo/${file}`}>{title}</a>
          <small>{note}</small>
        </li>
      ))}
    </ul>
  );
}

export default function DemoIndex() {
  return (
    <main className="demo-index">
      <h1>Demo pages</h1>
      <p className="lead">The earlier single-file HTML demos, kept as they were.</p>
      <h2>Runs here (static)</h2>
      <List items={STATIC} />
      <h2>Needs the population API (data will not load without it)</h2>
      <List items={NEEDS_API} />
      <h2>Run everything with the API</h2>
      <ul>
        <li>
          Docker Desktop, then from the repo root:
          <small><code>docker compose -f deploy/docker-compose.yml up -d --build</code> and open <code>http://localhost:8789/</code>. See deploy/README.md.</small>
        </li>
      </ul>
    </main>
  );
}
