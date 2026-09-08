# Architecture — one page

## What talks to what

```
   browser  http://localhost:8789
      │
      │  ALL of it — pages AND API — over ONE origin.
      │  That is the whole point: no CORS, no hardcoded API host,
      │  so the same build works on localhost or behind any domain.
      ▼
┌─────────────────────────────────────────────────────────┐
│  container: app        (image built from deploy/Dockerfile) │
│  node:22-alpine · listens 0.0.0.0:8787 · published :8789 │
│                                                          │
│   apps/api/server.js  — Express, 26 routes         │
│      ├── GET /health /stats /search /verified            │
│      ├── GET /record/:id · /record/prefix/:prefix         │
│      ├── GET /party/:id/... · /prefix/:prefix/claims      │
│      │                                                    │
│      ├── express.static('/app/public')   ← ADDED, opt-in │
│      │      /            → public/index.html (the React app; /registry, /demo route client-side)             │
│      │      /demo/*.html  → the legacy pages          │
│      │                                                    │
│      └── 404 fallthrough  {"error":"no route ..."}       │
│                                                          │
│   apps/api/db.js — single pg Pool, the ONLY path   │
│                          to the database                 │
└───────────────────────────┬─────────────────────────────┘
                            │ PGHOST=db  PGPORT=5432
                            │ (compose network, not the host)
                            ▼
┌─────────────────────────────────────────────────────────┐
│  container: db         postgres:16 · published :5434     │
│  database thingdaddy_population                          │
│                                                          │
│  volume  pgdata:/var/lib/postgresql/data   ← data lives  │
│  mount   ../population/seed → /seed  (read-only)         │
│  init    deploy/db-init/10-seed.sh → docker-entrypoint-     │
│                                    initdb.d, FIRST BOOT  │
└─────────────────────────────────────────────────────────┘
```

## Ports

| Port | Who | Note |
|---|---|---|
| **8789** | this demo, page + API | host → app:8787. Bound to `127.0.0.1` only |
| **5434** | this demo, Postgres | host → db:5432. Convenience for `psql`; the app does not use it |
| 8787 | *not us* | KJ's bare `node server.js` demo. Left alone |
| 8788 | *not us* | `thingdaddy-staging-api-1`. Left alone |
| 5432 | *not us* | `taxmap-survey-db-1`, another client. Left alone |
| 5433 | *not us* | `td-demo-pg`. Left alone |

Both of ours are published on `127.0.0.1` so nothing is exposed off the machine.

## Where the data comes from

`population/seed/` — a dated snapshot (2026-09-05) of real rows from
`thingdaddy_population` on the Mac mini. Four parties, 187 content claims, four
party events. Real GS1 prefixes with real GUDID provenance; **not** fabricated,
**not** authoritative, **not** a source of truth.

On the first boot of an empty `pgdata` volume, the Postgres entrypoint runs
`db-init/10-seed.sh`, which `cd`s to `/seed` and executes the seed's own
`seed_up.sh`. That script loads `01_schema.sql`, then `05_load.sql`, then counts
the loaded rows against `MANIFEST.txt` and fails loudly on a mismatch — so a
half-loaded database stops the container instead of rendering an empty screen
that looks like a front-end bug.

Two details that decided the design:

- **`05_load.sql` uses psql `\copy` with relative CSV paths.** `\copy` is
  client-side and resolves against psql's working directory, which is why the
  seed must be driven from inside `/seed` rather than pointed at from elsewhere.
- **`population/seed/` is NOT mounted into `/docker-entrypoint-initdb.d`.** The
  entrypoint executes every `.sh` and `.sql` it finds there, alphabetically —
  which would also run `demo_down.sh`, `demo_up.sh` and `make_seed.sh`. Mounting
  the seed read-only at `/seed` and putting a single script in `initdb.d` keeps
  exactly one thing executable.

Init scripts run **only** when the volume is empty. `docker compose down` keeps
the volume, so a restart reuses the loaded data. `down -v` drops it and the seed
reloads on the next `up`.

## The static-serving change

`server.js` gained five lines: an `import fs from 'node:fs'` beside the other
`node:` imports, and this block placed immediately before the 404 fallthrough —
after every real route, so it can never shadow one:

```js
const PUBLIC_DIR = process.env.PUBLIC_DIR || '';
if (PUBLIC_DIR && fs.existsSync(PUBLIC_DIR)) app.use(express.static(PUBLIC_DIR));
```

`PUBLIC_DIR` is set only in `web/docker-compose.yml`. Unset — which is every
existing way of running this API — the block does nothing and `GET /` returns
the original `{"error":"no route GET /"}`.

## Known cosmetic artifact

The S1 page prints the API base into its own status banner:

```js
txt.innerHTML='<b>LIVE</b> — '+API+' · db '+esc(h.body.db||'?');
```

With `API = ''` the banner reads `LIVE — · db thingdaddy_population · 4 records
(1 candidate · 3 verified)` — an empty gap where the host used to be. The counts
are real and prove the page reached the API. Fixing the gap would mean editing a
second line, which was deliberately out of scope.
