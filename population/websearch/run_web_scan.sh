#!/usr/bin/env bash
# run_web_scan.sh — load web-discovered GTINs (spine_gtin_web.csv) into <db>.node, GUARDED.
# Scratch-first by design, same discipline as run_gdsn_100.sh. Discovery itself is done by
# websearch_gtin.py (no DB access); THIS is the only step that writes the DB.
set -euo pipefail
cd "$(dirname "$0")"

POP_DB="${POP_DB:-thingdaddy_population_test}"
CSV="spine_gtin_web.csv"

# --- Guard 1: scratch/test DB only (unless ALLOW_PROD=1 is set on purpose) ---
case "$POP_DB" in
  *_test|*_scratch|*_dev) : ;;
  *)
    if [ "${ALLOW_PROD:-0}" != "1" ]; then
      echo "REFUSING: POP_DB='$POP_DB' is not *_test/_scratch/_dev."
      echo "  Web GTINs rehearse on scratch first. To load production deliberately:"
      echo "    ALLOW_PROD=1 POP_DB=$POP_DB ./run_web_scan.sh   (and only after the spine cutover gate)"
      exit 1
    fi
    echo "!! ALLOW_PROD=1 — loading web GTINs into PRODUCTION '$POP_DB'. This is a deliberate act." ;;
esac

# --- Guard 2: the node table must exist (the spine cutover gate) ---
HAS_NODE=$(psql -d "$POP_DB" -tAc "SELECT to_regclass('public.node') IS NOT NULL;" 2>/dev/null || echo f)
if [ "$HAS_NODE" != "t" ]; then
  echo "REFUSING: '$POP_DB' has no 'node' table. Apply the spine (010/011, merge #8/#9) first."
  exit 1
fi

# --- Guard 3: the CSV exists and is non-empty ---
if [ ! -s "$CSV" ]; then
  echo "No '$CSV' (or empty). Run discovery first, e.g.:"
  echo "  python3 websearch_gtin.py --source openfoodfacts --query 'coffee' --limit 200 --outdir ."
  exit 1
fi

ROWS=$(wc -l < "$CSV" | tr -d ' ')
echo ">> target DB : $POP_DB"
echo ">> loading   : $ROWS web GTIN rows (source=WEB) into ${POP_DB}.node"
echo ">> sample:"; head -3 "$CSV"
printf ">> proceed? [y/N] "; read -r ok
[ "$ok" = "y" ] || { echo "aborted (nothing written)."; exit 0; }

psql -v ON_ERROR_STOP=1 -d "$POP_DB" -f load_web_spine.sql
echo ">> done. (prefix NULL on every web row; MO set; state=candidate; source=WEB)"
