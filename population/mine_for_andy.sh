#!/usr/bin/env bash
# mine_for_andy.sh — live demo: mine 5 logistics / freight / cold-chain companies
# with OUR agent and add them to the fleet. Proves "one engine, every industry":
# the same pipeline that mapped lab instruments (GTIN-heavy) will map freight
# forwarders (GLN-location-heavy + GDTI-document-heavy) — different shape, one engine.
#
# NEEDS network (fetches each company's real sitemap + pages). Run in your REAL
# Terminal, not the Cowork bridge:
#     cd ~/thingdaddy/population && bash mine_for_andy.sh
#
# Everything stays CANDIDATE — no prefix is invented. GLEIF fills real LEIs; the GS1
# prefix stays candidate until the answerable party ratifies. That is the discipline.
set -u
cd "$(dirname "$0")"

# domain|Name  — swap any line to change the demo set
COMPANIES=(
  "kerrylogistics.com|Kerry Logistics"       # Asia / Thailand freight — Andy's backyard
  "kuehne-nagel.com|Kuehne + Nagel"          # global freight forwarder
  "dbschenker.com|DB Schenker"               # global logistics
  "dsv.com|DSV"                              # global transport & logistics
  "lineagelogistics.com|Lineage Logistics"   # cold-chain — ties to the pilot in the brief
)

for entry in "${COMPANIES[@]}"; do
  domain="${entry%%|*}"; name="${entry##*|}"
  echo "=============================================================="
  echo ">> mining  $name  ($domain)"
  python3 website_agent.py --domain "$domain" --name "$name" \
      --max-sitemaps 6 --limit 800 --pages-limit 60 --mine --root --gleif --force
done

echo "=============================================================="
echo ">> re-rendering the fleet gallery with the new sites..."
python3 render_fleet.py
echo ">> done. open the gallery to watch it grow:"
echo "     open sites/fleet_index.html"
