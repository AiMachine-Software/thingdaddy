#!/usr/bin/env bash
# Bring the ThingDaddy demo stack up on a server (Ubuntu + Docker + nginx).
#   first time:  git clone -b production https://github.com/AiMachine-Software/thingdaddy.git ~/thingdaddy
#   every time:  bash ~/thingdaddy/deploy/server/up.sh
# Pulls the production branch, rebuilds the image, restarts the containers, then checks /health and /stats.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
git pull --ff-only origin production
docker compose -f deploy/docker-compose.yml up -d --build
echo "waiting for the API ..."
for i in $(seq 1 30); do
  if curl -fs http://127.0.0.1:8789/health >/dev/null 2>&1; then break; fi
  sleep 2
done
echo "health: $(curl -fs http://127.0.0.1:8789/health || echo 'NOT UP')"
echo "stats:  $(curl -fs http://127.0.0.1:8789/stats || echo 'NOT UP')"
echo "web:    $(curl -fs -o /dev/null -w '%{http_code}' http://127.0.0.1:8789/)"
