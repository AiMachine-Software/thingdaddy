# ThingDaddy

The GoDaddy of the physical world — GS1 EPC URN identity registry, agent fleet,
and Physical-AI graph. See CLAUDE.md for the engineering laws.

## Web (production build)

Live site: https://aimachine-software.github.io/thingdaddy/ — built from the
`production` branch by `.github/workflows/deploy.yml` on every push.

| Path            | What                                            | Source            |
|-----------------|-------------------------------------------------|-------------------|
| `/`             | V4 platform (React, single-file)                | `platform/`       |
| `/population/`  | Population registry UI (React, needs the API)   | `population/ui/`  |
| `/demo/`        | Legacy single-file HTML demos + hub             | `web/public/`, `population/fill/` |

```bash
npm install                          # one install for all three workspaces
npm run build                        # -> dist/  (root of a host / custom domain)
VITE_BASE=/thingdaddy npm run build  # -> dist/  (GitHub Pages sub-path)
npm run preview                      # build, then serve dist on http://localhost:4173

npm run dev:platform                 # platform dev server
npm run dev:population               # population UI dev server (:5173)
npm run dev:api                      # population API (:8787, needs Postgres)
```

GitHub Pages serves static files only, so the population API is not there.
Point the UI at a hosted API by setting the repository variable `API_BASE`
(Settings → Secrets and variables → Actions → Variables) and re-running the
workflow. To run API + pages together on one machine use the Docker stack in
`web/` (`docker compose -f web/docker-compose.yml up -d --build`).

## Quickstart
```bash
# platform
cd platform && npm install && npm run dev

# agents (offline)
python3 agents/thingdaddy_agent_fleet.py --status
python3 agents/thingdaddy_agent_fleet_loopB.py

# agents (live — needs open network)
python3 agents/thingdaddy_agent_fleet_loopB.py --live
SAM_API_KEY=xxxxx python3 agents/thingdaddy_agent_fleet_loopB.py --live
```

## Working with Claude Code
Run `claude` in this directory. It reads CLAUDE.md (and platform/CLAUDE.md,
agents/CLAUDE.md) automatically. Ask it to make changes; it edits in place,
runs parse-check.sh / the agent tests, and commits.
