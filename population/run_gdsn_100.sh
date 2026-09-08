#!/bin/bash
# ThingDaddy — bounded GDSN REHEARSAL (Scenario A: scratch only).
# Ingest N GDSN candidates into a SCRATCH db, then project onto the spine.
# Safe-by-refusal: will NOT write to production. Backfill guarded on spine existence.
# Usage:  POP_DB=thingdaddy_population_test  ./run_gdsn_100.sh [limit]
set -uo pipefail
cd "$(dirname "$0")"

LIMIT="${1:-100}"
POP_DB="${POP_DB:-thingdaddy_population_test}"       # scratch default — never prod
POP_API="${POP_API:-http://127.0.0.1:8787}"
export POP_DB POP_API

echo "== ThingDaddy · GDSN rehearsal =="
echo "   limit : $LIMIT"
echo "   DB    : $POP_DB"
echo "   API   : $POP_API"

# Guard 1 — DB name must look like scratch, never production
case "$POP_DB" in
  *test*|*scratch*|*dev*) : ;;
  *) echo "!! REFUSING: POP_DB='$POP_DB' is not a scratch db (needs test/scratch/dev). This rehearsal must not touch production."; exit 1 ;;
esac

# Guard 2 — API up
curl -s "$POP_API/health" >/dev/null 2>&1 || { echo "!! API not up at $POP_API — start it against $POP_DB (dev_up.sh, repointed to scratch) first."; exit 1; }

# Guard 3 — REFUSE a production-bound API (the ingest goes through the API, not POP_DB)
STATS="$(curl -s "$POP_API/stats" 2>/dev/null)"
echo "   /stats: $STATS"
TOTAL="$(printf '%s' "$STATS" | grep -oE '[0-9]+' | sort -rn | head -1)"
if [ "${TOTAL:-0}" -gt 1000 ]; then
  echo "!! REFUSING: the API at $POP_API reports ~$TOTAL registrants — that is the LOADED/PRODUCTION registry, not a fresh scratch."
  echo "   Start the API bound to $POP_DB (scratch) before ingesting."
  exit 1
fi

# Guard 4 — spine must exist on target, else the backfill (step 4) would crash
HAS_NODE="$(psql -d "$POP_DB" -tAc "SELECT to_regclass('public.node') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')"
echo "   spine on $POP_DB (node table present): ${HAS_NODE:-unknown}"

# token
export INGEST_TOKEN="$(grep -E '^INGEST_TOKEN=' api/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)"
[ -n "${INGEST_TOKEN:-}" ] || { echo "!! INGEST_TOKEN not found in api/.env"; exit 1; }

echo; echo "-- 1) DRY RUN (read only) --"
python3 loaders/load_population.py --source gdsn --limit "$LIMIT" --dry-run --no-dedup

echo
read -p ">> Ingest $LIMIT GDSN candidates into $POP_DB via $POP_API ? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || { echo "aborted (nothing written)."; exit 0; }

echo "-- 2) INGEST (candidates only, prefix=NULL) --"
python3 loaders/load_population.py --source gdsn --limit "$LIMIT"

echo "-- 3) stats --"; curl -s "$POP_API/stats"; echo

if [ "$HAS_NODE" = "t" ]; then
  echo "-- 4) project onto the spine (migration 011) --"
  psql -v ON_ERROR_STOP=1 -d "$POP_DB" -f db/migrations/011_backfill_spine.sql
else
  echo "-- 4) SKIPPED: no spine (node table) on $POP_DB — apply 010/011 (merge #8/#9) first, then backfill."
fi
echo "== done =="
