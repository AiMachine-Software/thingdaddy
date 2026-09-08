# ThingDaddy

The GoDaddy of the physical world — GS1 EPC URN identity registry, agent fleet,
and Physical-AI graph. See CLAUDE.md for the engineering laws.

## Layout

```
apps/web/        the web app — React + Vite, one router, one nav
  src/platform/    the V4 platform (single 37K-line file, see its CLAUDE.md)   route /
  src/thingsite/   the ThingSite flow S1-S6: search, reveal, site, book, claim  route /thingsite
  src/registry/    the population registry UI (talks to the API)              route /registry
  public/demo/     the legacy single-file HTML demos, served as plain files    route /demo
apps/api/        the population API — Express over Postgres (+ acceptance tests)
population/      data tier: schema, seed, loaders, fleet tooling (Python + SQL)
agents/          the population fleet
deploy/          Docker: one image = API + built web app, with a seeded Postgres
docs/            mission, charter, blueprints, roadmap, setup playbook
```

## Web app

Live site: https://aimachine-software.github.io/thingdaddy/ — built from the
`production` branch by `.github/workflows/deploy.yml` on every push.

```bash
npm install                          # one install for apps/web + apps/api
npm run dev                          # web app on http://localhost:5173
npm run dev:api                      # population API on :8787 (needs Postgres, see apps/api/README.md)

npm run build                        # static site -> dist/   (root of a host / custom domain)
VITE_BASE=/thingdaddy npm run build  # static site -> dist/   (GitHub Pages sub-path)
npm run preview                      # serve the last build locally
npm run parse-check                  # Babel parse of the platform file; must print PARSE OK
```

Environment (build time, all optional; see `apps/web/.env.example`):

| Variable          | Meaning |
|-------------------|---------|
| `VITE_BASE`       | sub-path the site is served from (`/thingdaddy` on Pages) |
| `VITE_API_BASE`   | origin of the population API for `/registry`. Unset = same origin in production, `http://localhost:8787` in dev |
| `VITE_INGEST_TOKEN` | dev caller token for registry writes; unset = read-only |

GitHub Pages serves static files only, so there is no API there: `/registry`
and the API-backed demo pages report the API as unreachable. To connect a hosted
API set the repository variable `API_BASE` (Settings → Secrets and variables →
Actions → Variables) and re-run the workflow.

## API + web app together (Docker)

```bash
docker compose -f deploy/docker-compose.yml up -d --build
open http://localhost:8789/
```

One image builds `apps/web`, then serves it and `apps/api` from the same origin,
next to a Postgres seeded from `population/seed`. See deploy/README.md.

## Agents

```bash
python3 agents/thingdaddy_agent_fleet.py --status          # offline
python3 agents/thingdaddy_agent_fleet_loopB.py             # offline
python3 agents/thingdaddy_agent_fleet_loopB.py --live      # needs open network
SAM_API_KEY=xxxxx python3 agents/thingdaddy_agent_fleet_loopB.py --live
```

## Working with Claude Code
Run `claude` in this directory. It reads CLAUDE.md (and apps/web/src/platform/CLAUDE.md,
agents/CLAUDE.md, population/CLAUDE.md) automatically. Ask it to make changes; it edits
in place, runs `npm run parse-check` / the agent tests, and commits.
