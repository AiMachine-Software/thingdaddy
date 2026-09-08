#!/usr/bin/env bash
# rerender_thingsites.sh — re-render EVERY ThingSite from its cached harvest data.
# Picks up the new pillar drill-down + the verified-root badge. No network, no
# re-harvest — reads the sitemap CSVs already on disk. Run from the population/ dir:
#     cd ~/thingdaddy/population && bash rerender_thingsites.sh
set -u
cd "$(dirname "$0")"
RENDER="${RENDER:-sitemap/render_harvest_site.py}"
SITES="${SITES:-sites}"

# optional brand accents (domain -> "ACCENT DEEP"); anything else derives from the name
accent_for_domain() {
  case "$1" in
    thermofisher.com) echo "E1251B 6e0f08" ;;
    tecan.com)        echo "1F6FEB 12335e" ;;
    *)                echo "" ;;
  esac
}

n=0; verified=0
for d in "$SITES"/*/; do
  slug=$(basename "$d")
  struct="${d}sitemap_structure.csv"
  [ -f "$struct" ] || continue          # only real harvests
  pal="${d}content_palette.json"
  name="$slug"; domain=""
  if [ -f "$pal" ]; then
    name=$(python3 -c "import json;print(json.load(open('$pal')).get('company') or '$slug')" 2>/dev/null || echo "$slug")
    domain=$(python3 -c "import json;print(json.load(open('$pal')).get('domain') or '')" 2>/dev/null || echo "")
  fi
  docs="${d}sitemap_documents.csv"; [ -f "$docs" ] || docs=""
  out="${d}${slug}_ThingSite.html"

  args=(--name "$name" --domain "$domain" --structure "$struct" --out "$out")
  [ -n "$docs" ] && args+=(--documents "$docs")
  acc=$(accent_for_domain "$domain")
  if [ -n "$acc" ]; then read -r a1 a2 <<< "$acc"; args+=(--accent "$a1" --deep "$a2"); fi

  root=$(python3 "$RENDER" "${args[@]}" 2>&1 | grep -E '^   root' | sed 's/^   root *: *//')
  n=$((n+1))
  case "$root" in *VERIFIED*) verified=$((verified+1));; esac
  printf '[%2d] %-32s %s\n' "$n" "$name" "$root"
done

echo "------------------------------------------------------------"
# refresh the gallery from the (now updated) palettes — no network
[ -f render_fleet.py ] && python3 render_fleet.py --sites "$SITES" 2>/dev/null || true
echo "re-rendered $n ThingSites · $verified with a VERIFIED root · the rest candidate (honest)"
echo "gallery:  open sites/fleet_index.html"
echo "hero   :  open sites/thermo-fisher-scientific/thermo-fisher-scientific_ThingSite.html"
