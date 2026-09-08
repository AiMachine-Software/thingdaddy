#!/usr/bin/env bash
# Rebuild the static site and copy it to the nginx web root that serves /thingdaddy/.
#   WEB_ROOT=/var/www/html/thingdaddy bash ~/thingdaddy/deploy/server/static-up.sh
# Pulls production, builds with VITE_BASE=/thingdaddy (same-origin API), rsyncs dist/ into WEB_ROOT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WEB_ROOT="${WEB_ROOT:?set WEB_ROOT to the directory nginx serves as /thingdaddy/}"
cd "$ROOT"
git pull --ff-only origin production
npm ci --silent
VITE_BASE=/thingdaddy VITE_API_BASE= npm run build
sudo mkdir -p "$WEB_ROOT"
sudo rsync -a --delete dist/ "$WEB_ROOT"/
echo "web:   $(curl -fs -o /dev/null -w '%{http_code}' http://127.0.0.1/thingdaddy/)"
echo "api:   $(curl -fs http://127.0.0.1/health || echo 'NOT PROXIED — include deploy/server/thingdaddy-api-proxy.conf in nginx')"
