# CLAUDE.md — deploying ThingDaddy on the team server

Read this when you are a Claude Code session **on the server** (Ubuntu, nginx, Docker) and the
task is to bring up, update, verify, or roll back the ThingDaddy demo. The root `CLAUDE.md`
is KJ's engineering contract for the product and still applies; this file only covers deploy.

## What runs where

| Piece | Where | Port |
|---|---|---|
| Postgres (seeded from `population/seed/` on first boot) | container `thingdaddy-web-demo-db-1` | 127.0.0.1:5434 |
| API + built web app, one origin (`apps/api` serving `dist/`) | container `thingdaddy-web-demo-app-1` | 127.0.0.1:8789 |
| Public https | nginx site `thingdaddy` → 127.0.0.1:8789 | https://td-demo.49.0.64.117.nip.io |
| Source of truth | branch `production` of `AiMachine-Software/thingdaddy` | checkout at `~/thingdaddy` |

Other things on this machine that you must **never** stop, rebuild, or re-port: the field-mark
web (nginx site + `next start`), its Postgres, and anything on 8787 / 8788 / 5432 / 5433.
This stack only uses 8789 and 5434, both loopback.

## Two layouts — check which one this server uses first

- **Layout A (own hostname)**: nginx site `thingdaddy` → container 8789 serves API + web at
  `https://td-demo.49.0.64.117.nip.io/`. Commands below.
- **Layout B (what Ant set up on 8 Sep)**: static `dist/` under the default server at
  `http://49.0.64.117/thingdaddy/`, API container on 8789 reached through
  `snippets/thingdaddy-api-proxy.conf` (root-relative paths /health /stats /record …).
  Update = `WEB_ROOT=<dir> bash deploy/server/static-up.sh` after `docker compose up -d --build`.
  Verify: `curl http://127.0.0.1/health` must return JSON, not the SPA HTML.
  Find `<dir>` with: `grep -rn "thingdaddy" /etc/nginx/sites-enabled/`.

## Commands (copy exactly) — Layout A

First deploy:
```bash
git clone -b production https://github.com/AiMachine-Software/thingdaddy.git ~/thingdaddy
bash ~/thingdaddy/deploy/server/up.sh
sudo cp ~/thingdaddy/deploy/server/thingdaddy.nginx.conf /etc/nginx/sites-available/thingdaddy
sudo ln -sf /etc/nginx/sites-available/thingdaddy /etc/nginx/sites-enabled/thingdaddy
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d td-demo.49.0.64.117.nip.io
```

Update to the latest `production`:
```bash
bash ~/thingdaddy/deploy/server/up.sh
```
`up.sh` = `git pull --ff-only` → `docker compose up -d --build` → prints `/health`, `/stats`, web status.
It is safe to run repeatedly. It never touches the database volume.

Verify (all three must pass before you say "deployed"):
```bash
curl -fs http://127.0.0.1:8789/health
curl -fs http://127.0.0.1:8789/stats
curl -fs -o /dev/null -w '%{http_code}\n' https://td-demo.49.0.64.117.nip.io/     # 200
```
Then open the site: the top bar must be green `LIVE` with a record count. Red `NO API`
means the app container is not up — `docker compose -f ~/thingdaddy/deploy/docker-compose.yml logs app --tail 50`.

Roll back (the previous image is still on disk):
```bash
cd ~/thingdaddy && git log --oneline -5           # pick the last good production commit
git checkout <sha> -- . && docker compose -f deploy/docker-compose.yml up -d --build
git checkout production -- .                      # working tree back to the branch tip when done
```
Do not `git reset --hard` and do not force-push. If a rollback is needed for real, tell Ant
and revert on `production` with `git revert` so the history keeps it.

## Database rules

- `docker compose ... down` keeps the data (volume `pgdata`). `down -v` erases it and the seed
  reloads on next boot — only with Ant's explicit go.
- The seed is a dated snapshot (4 parties, 187 claims). The full registry dump (81,928 rows)
  lives with KJ; if it arrives, restore it into the container's Postgres on 5434 instead of the
  seed, and record what you did in `docs/`.
- Writes to the API are disabled (503) unless `INGEST_TOKEN` is set in `~/thingdaddy/deploy/.env`.
  Leave it unset for a public demo. Never commit `.env`.

## Don'ts

- Never edit files under `~/thingdaddy` by hand on the server — changes go through `production`
  on GitHub, then `up.sh`. A hand edit will be overwritten by the next pull and is invisible to the team.
- Never change the nginx sites of other apps, and never change ports in `deploy/docker-compose.yml`
  on the server; propose it in a PR instead.
- Never run `population/seed/demo_down.sh` or `make_seed.sh` here — they are for local dev.
- Say exactly what you verified (paste the three curl outputs). "Should be up" is not a status.

## If Ant asks "is it up?"

Run the three verify commands and answer with their output plus `docker compose ps`.
