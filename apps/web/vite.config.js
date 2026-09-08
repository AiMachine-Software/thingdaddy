import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { copyFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

// One Vite app for the whole site. Output goes to <repo>/dist.
//
//   VITE_BASE      sub-path the site is served from. "" (default) for the root of a
//                  host or a custom domain, "/thingdaddy" for GitHub Pages.
//   VITE_API_BASE  origin of the population API used by the registry UI. Unset =
//                  same origin in production (the Docker image serves both), and
//                  http://localhost:8787 in `vite` dev.
const BASE = (process.env.VITE_BASE || '').replace(/\/+$/, '');
const OUT = resolve(__dirname, '../../dist');

// Static hosts (GitHub Pages) have no server-side routing. Serving index.html as
// 404.html lets a deep link such as /registry boot the app, which then routes.
function spaFallback() {
  return {
    name: 'spa-404-fallback',
    closeBundle() {
      const index = resolve(OUT, 'index.html');
      if (existsSync(index)) copyFileSync(index, resolve(OUT, '404.html'));
    },
  };
}

export default defineConfig({
  base: `${BASE}/`,
  plugins: [react(), spaFallback()],
  build: {
    outDir: OUT,
    emptyOutDir: true,
    // The platform is one 37K-line file by design (see src/platform/CLAUDE.md);
    // it cannot be split without editing it, so raise the warning threshold.
    chunkSizeWarningLimit: 2500,
  },
  server: { port: 5173 },
});
