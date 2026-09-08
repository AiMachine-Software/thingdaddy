#!/usr/bin/env bash
# fleet_mine.sh — DEEPEN the fleet. Runs the full pipeline (page-read + doc-mine + root)
# on every harvested site so the shallow 23 get as deep as Thermo:
#   stage 2  page-read   — real GTINs (incl. SPA structured-data recovery) + doc links + edges
#   stage M  doc-mine    — settings/identifiers/attribution mined from inside the PDFs
#   stage 5  root        — GTINs cross-referenced to a WHO (registry + GLEIF)
#
# NEEDS network (fetches pages + PDFs) and the population DB (rooting). Run in your REAL
# Terminal, not the Cowork bridge:   cd ~/thingdaddy/population && bash fleet_mine.sh
#
# Long-running and yield VARIES: some vendors bot-block their PDF hosts (expect 403s on a
# few, same as Thermo's tools. subdomain). Cached sitemaps are reused — no re-harvest.
set -u
cd "$(dirname "$0")"
SKIP="${SKIP:-thermo-fisher-scientific}"     # already deep; space-separate to skip more
MINE_LIMIT="${MINE_LIMIT:-40}"               # max PDFs mined per site
ONLY="${ONLY:-}"                             # optional: run one slug only, e.g. ONLY=tecan

start=""; done_n=0
for d in sites/*/; do
  slug=$(basename "$d")
  [ -f "${d}sitemap_structure.csv" ] || continue
  [ -n "$ONLY" ] && [ "$slug" != "$ONLY" ] && continue
  case " $SKIP " in *" $slug "*) echo "[skip] $slug (already deep)"; continue;; esac
  pal="${d}content_palette.json"
  name="$slug"; domain=""
  if [ -f "$pal" ]; then
    name=$(python3 -c "import json;print(json.load(open('$pal')).get('company') or '$slug')" 2>/dev/null || echo "$slug")
    domain=$(python3 -c "import json;print(json.load(open('$pal')).get('domain') or '')" 2>/dev/null || echo "")
  fi
  [ -n "$domain" ] || { echo "[skip] $slug (no domain in palette)"; continue; }
  echo "=============================================================="
  echo ">> deepening  $name  ($domain)"
  python3 website_agent.py --domain "$domain" --name "$name" \
      --mine --root --gleif --mine-limit "$MINE_LIMIT"
  done_n=$((done_n+1))
done
echo "=============================================================="
echo ">> fleet mine complete — deepened $done_n site(s)."
echo ">> now re-render so the ThingSites show the new depth (mined graph, binding sets, roots):"
echo "     bash rerender_thingsites.sh"
echo "     open sites/fleet_index.html"
