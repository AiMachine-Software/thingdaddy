#!/usr/bin/env bash
# reharvest_empty.sh — fix empty-pillar ThingSites by re-harvesting them DEEP.
# Finds every fleet site whose sitemap_structure.csv has 0 url rows and re-runs the
# agent with --max-sitemaps 6 (the original fleet was built on the old 1-sitemap
# default). Whatever is STILL empty afterward is the headless-render bucket.
#
# NEEDS network. Run in your REAL Terminal:  cd ~/thingdaddy/population && bash reharvest_empty.sh
set -u
cd "$(dirname "$0")"
MAXJ="${MAXJ:-3}"
empties=(); fixed=(); still=()

for d in sites/*/; do
  slug=$(basename "$d")
  [ "$slug" = "_control" ] && continue
  f="${d}sitemap_structure.csv"
  n=0; [ -f "$f" ] && n=$(tail -n +2 "$f" 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] && continue                      # already populated
  pal="${d}content_palette.json"
  [ -f "$pal" ] || { echo "[skip] $slug (no palette)"; continue; }
  domain=$(python3 -c "import json;print(json.load(open('$pal')).get('domain') or '')" 2>/dev/null)
  name=$(python3 -c "import json;print(json.load(open('$pal')).get('company') or '$slug')" 2>/dev/null)
  [ -n "$domain" ] || { echo "[skip] $slug (no domain in palette)"; continue; }
  empties+=("$slug|$domain|$name")
done

echo ">> ${#empties[@]} empty sites to re-harvest deep:"; printf '   %s\n' "${empties[@]%%|*}"
echo "=============================================================="
for e in "${empties[@]}"; do
  IFS='|' read -r slug domain name <<< "$e"
  ( echo ">> re-harvest  $name  ($domain)"
    python3 website_agent.py --domain "$domain" --name "$name" \
        --max-sitemaps 6 --limit 800 --pages-limit 60 --mine --root --gleif --force \
        >"sites/_relog_${domain}.txt" 2>&1 ) &
  while [ "$(jobs -r | wc -l)" -ge "$MAXJ" ]; do sleep 1; done
done
wait

echo "=============================================================="
echo ">> results (url count after re-harvest):"
for e in "${empties[@]}"; do
  IFS='|' read -r slug domain name <<< "$e"
  f="sites/${slug}/sitemap_structure.csv"
  n=0; [ -f "$f" ] && n=$(tail -n +2 "$f" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -gt 0 ]; then fixed+=("$slug($n)"); else still+=("$slug"); fi
done
echo ">> FIXED (now populated): ${fixed[*]:-none}"
echo ">> STILL EMPTY (headless-render bucket): ${still[*]:-none}"
echo ">> re-render the fleet:  python3 render_fleet.py && open sites/fleet_index.html"
