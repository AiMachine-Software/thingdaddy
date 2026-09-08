#!/usr/bin/env node
// Assemble the production static site into <repo>/dist.
//
//   VITE_BASE=/thingdaddy npm run build     # GitHub Pages under a sub-path
//   npm run build                           # custom domain / root of a host
//   npm run preview                         # build, then serve dist on :4173
//
// Layout of dist/ (all paths relative to VITE_BASE):
//   /                 platform/            the V4 React platform
//   /population/      population/ui        React registry UI over the population API
//   /demo/            web/public + population/fill + GA_ThingSite.html  (legacy pages)
//   /demo/index.html  web/site/demo-index.html                          (hub for them)
//   /standards/       authority_reads.json (td_thingsite.html reads ../standards/)
//
// Environment passed through to the React builds:
//   VITE_BASE       sub-path the site is served from ("" or "/thingdaddy"). No trailing slash.
//   VITE_API_BASE   origin of the population API for population/ui. Unset = the UI
//                   reports "cannot reach the population API" instead of guessing.

import { execFileSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const BASE = (process.env.VITE_BASE || '').replace(/\/+$/, '');
const preview = process.argv.includes('--preview');

function log(msg) { console.log(`[build-site] ${msg}`); }

function vite(workspace, base, outDir) {
  log(`vite build ${workspace} -> ${outDir} (base ${base})`);
  execFileSync('npx', ['vite', 'build', '--base', base, '--outDir', outDir, '--emptyOutDir'], {
    cwd: join(ROOT, workspace),
    stdio: 'inherit',
    env: { ...process.env, VITE_BASE: BASE },
  });
}

function copyHtml(srcDir, destDir) {
  mkdirSync(destDir, { recursive: true });
  for (const f of readdirSync(srcDir)) {
    if (f.endsWith('.html')) cpSync(join(srcDir, f), join(destDir, f));
  }
}

// 1. clean
rmSync(DIST, { recursive: true, force: true });
mkdirSync(DIST, { recursive: true });

// 2. React apps
vite('platform', `${BASE}/`, join(DIST));
vite('population/ui', `${BASE}/population/`, join(DIST, 'population'));

// 3. legacy static pages
const DEMO = join(DIST, 'demo');
copyHtml(join(ROOT, 'web', 'public'), DEMO);
// web/public/index.html would collide with the hub below; it is the S1-S6 screens page.
cpSync(join(DEMO, 'index.html'), join(DEMO, 'screens.html'));
copyHtml(join(ROOT, 'population', 'fill'), DEMO);
cpSync(join(ROOT, 'GA_ThingSite.html'), join(DEMO, 'GA_ThingSite.html'));
cpSync(join(ROOT, 'web', 'site', 'demo-index.html'), join(DEMO, 'index.html'));
mkdirSync(join(DIST, 'standards'), { recursive: true });
cpSync(join(ROOT, 'population', 'standards', 'authority_reads.json'), join(DIST, 'standards', 'authority_reads.json'));

// 4. Pages housekeeping: no Jekyll pass, so nothing gets dropped or rewritten.
writeFileSync(join(DIST, '.nojekyll'), '');

log(`done -> ${DIST}`);

// 5. optional local preview that mounts dist at VITE_BASE, like the real host does
if (preview) {
  const port = Number(process.env.PORT || 4173);
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
  createServer((req, res) => {
    let path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (BASE && !path.startsWith(BASE + '/') && path !== BASE) { res.writeHead(404); return res.end('outside base'); }
    path = path.slice(BASE.length) || '/';
    if (path.endsWith('/')) path += 'index.html';
    const file = join(DIST, path);
    if (!existsSync(file)) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
    res.end(readFileSync(file));
  }).listen(port, () => log(`preview http://localhost:${port}${BASE}/`));
}
