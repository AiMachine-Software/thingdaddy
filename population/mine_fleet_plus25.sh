#!/usr/bin/env bash
# mine_fleet_plus25.sh — add 25 NEW deep-dive ThingSites to the fleet (fleet 25 -> 50).
# DEEP = full pipeline per company: sitemap harvest -> page read -> doc-mine -> root (registry+GLEIF).
# Uses --max-sitemaps 6 so sitemap-index sites harvest for real (not the 1-sitemap default).
#
# NEEDS network. Run in your REAL Terminal (not the Cowork bridge):
#     cd ~/thingdaddy/population && bash mine_fleet_plus25.sh
# Long-running. Runs MAXJ companies at a time (default 4). Set MAXJ=1 for a calm serial log.
# Everything stays candidate; GLEIF fills real LEIs; prefixes stay candidate until verified.
set -u
cd "$(dirname "$0")"
MAXJ="${MAXJ:-4}"

# 25 real analytical / life-science / process-instrument companies NOT already in the fleet.
COMPANIES=(
  "perkinelmer.com|PerkinElmer"                 "sigmaaldrich.com|MilliporeSigma"
  "biomerieux.com|bioMerieux"                   "anton-paar.com|Anton Paar"
  "malvernpanalytical.com|Malvern Panalytical"  "jeol.com|JEOL"
  "leica-microsystems.com|Leica Microsystems"   "horiba.com|HORIBA"
  "oxinst.com|Oxford Instruments"               "sciex.com|SCIEX"
  "phenomenex.com|Phenomenex"                   "restek.com|Restek"
  "integra-biosciences.com|INTEGRA Biosciences" "avantorsciences.com|Avantor"
  "bio-techne.com|Bio-Techne"                   "neb.com|New England Biolabs"
  "takarabio.com|Takara Bio"                    "lonza.com|Lonza"
  "criver.com|Charles River"                    "lgcgroup.com|LGC"
  "hamamatsu.com|Hamamatsu"                     "evidentscientific.com|Evident"
  "endress.com|Endress+Hauser"                  "yokogawa.com|Yokogawa"
  "ika.com|IKA"
)

n=0
for entry in "${COMPANIES[@]}"; do
  domain="${entry%%|*}"; name="${entry##*|}"
  ( echo ">> mining  $name  ($domain)"
    python3 website_agent.py --domain "$domain" --name "$name" \
        --max-sitemaps 6 --limit 800 --pages-limit 60 --mine --root --gleif --force \
        >"sites/_log_${domain}.txt" 2>&1
    echo "<< done   $name" ) &
  n=$((n+1))
  while [ "$(jobs -r | wc -l)" -ge "$MAXJ" ]; do sleep 1; done
done
wait
echo "=============================================================="
echo ">> mined $n new companies. Re-render the fleet gallery:"
echo "     python3 render_fleet.py && open sites/fleet_index.html"
echo ">> (Cloud & Edge layer renders once render_p4_cloud_edge.py lands — I'm building it now.)"
