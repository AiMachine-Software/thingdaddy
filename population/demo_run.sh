#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# demo_run.sh — ThingDaddy LIVE BUILD button (for the Andy call)
#
# Builds three ThingSites from ALREADY-EXTRACTED data (staged CSVs) so the
# audience watches the pipeline run — no harvest, no network, no waiting.
# The slow part (harvest/extract) was done earlier; this re-renders live.
#
# Run from the repo:   cd ~/thingdaddy/population && bash demo_run.sh
# ─────────────────────────────────────────────────────────────────────────────
set -u
cd "$(dirname "$0")"

# Three pre-extracted companies (name | domain | slug). All have full staged CSVs.
FLEET=(
  "Thermo Fisher Scientific|thermofisher.com|thermo-fisher-scientific"
  "Tecan|tecan.com|tecan"
  "Sartorius|sartorius.com|sartorius"
)
PACE="${PACE:-0.5}"   # seconds between stages, for live pacing; PACE=0 for instant

line(){ printf '─%.0s' {1..70}; echo; }
banner(){ echo; line; echo "  $1"; line; }

banner "THINGDADDY · LIVE BUILD — 3 ThingSites from extracted data"
echo "  Source: harvested palettes already on disk. Building live, no network."
echo "  Queue:"
for row in "${FLEET[@]}"; do IFS='|' read -r name domain slug <<< "$row"; echo "    • $name  ($domain)"; done
sleep "$PACE"

for row in "${FLEET[@]}"; do
  IFS='|' read -r name domain slug <<< "$row"
  banner "▶ BUILDING  $name"
  dir="sites/$slug"
  # remove only the rendered artifacts so the render stage visibly re-runs
  rm -f "$dir/${slug}_ThingSite.html" "$dir/${slug}_P5_Graph.html"
  sleep "$PACE"
  python3 website_agent.py --domain "$domain" --name "$name" --fast
  echo "  ✓ built → $dir/${slug}_ThingSite.html"
  sleep "$PACE"
done

banner "▶ UPDATING THE STORE (catalog + management UI)"
python3 thingsite_store.py 2>/dev/null || python3 thingsite_store.py
sleep "$PACE"

banner "✓ DONE — opening the results"
OPENER="$(command -v open || command -v xdg-open || true)"
if [ -n "$OPENER" ]; then
  for row in "${FLEET[@]}"; do
    IFS='|' read -r name domain slug <<< "$row"
    [ -f "sites/$slug/${slug}_ThingSite.html" ] && "$OPENER" "sites/$slug/${slug}_ThingSite.html"
  done
  [ -f sites/fleet_index.html ]       && "$OPENER" sites/fleet_index.html
  [ -f sites/thingsite_store.html ]   && "$OPENER" sites/thingsite_store.html
  # Thermo is the hero — also open its mined graph + binding sets if present
  [ -f sites/thermo-fisher-scientific/thermo-fisher-scientific_Mined_Graph.html ] && \
    "$OPENER" sites/thermo-fisher-scientific/thermo-fisher-scientific_Mined_Graph.html
else
  echo "  (no opener found — open sites/*/*_ThingSite.html and thingsite_store.html manually)"
fi
echo
echo "  Talking point: harvest was done earlier; what you just watched is the"
echo "  render from extracted candidate data — same pipeline that roots to a WHO"
echo "  when run with --root against the population DB."
