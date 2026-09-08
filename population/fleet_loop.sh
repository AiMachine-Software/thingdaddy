#!/usr/bin/env bash
# fleet_loop.sh — the loop agent. Continuously builds NEW deep-dive ThingSites
# (harvest -> page-read -> doc-mine -> root) + the Cloud & Edge (P4) layer, from
# fleet_queue.txt. Skips already-populated sites; marks hard-blocked ones (.blocked)
# so it converges instead of hammering. Add domains to fleet_queue.txt anytime — the
# loop picks them up next pass.
#
# NEEDS network. Run in your REAL Terminal:
#     cd ~/thingdaddy/population && bash fleet_loop.sh
# Background it:  nohup bash fleet_loop.sh >/dev/null 2>&1 &   (watch: tail -f sites/_loop.log)
# Tunables:  MAXJ=4 (concurrency)  SLEEP=60 (pause between passes)  RETRY_BLOCKED=1 (re-try blocked)
set -u; cd "$(dirname "$0")"
MAXJ="${MAXJ:-4}"; SLEEP="${SLEEP:-60}"; RETRY="${RETRY_BLOCKED:-0}"; LOG=sites/_loop.log
slug(){ python3 -c "import re,sys;print(re.sub(r'[^a-z0-9]+','-',sys.argv[1].lower()).strip('-'))" "$1"; }
echo ">> fleet_loop START $(date)  MAXJ=$MAXJ SLEEP=$SLEEP" | tee -a "$LOG"
pass=0
while true; do
  pass=$((pass+1)); built=0
  while IFS='|' read -r domain name; do
    [ -z "${domain// }" ] && continue
    [ -z "${name// }" ] && name="$domain"
    s=$(slug "$name"); d="sites/$s"
    f="$d/sitemap_structure.csv"; n=0; [ -f "$f" ] && n=$(tail -n +2 "$f" 2>/dev/null | wc -l | tr -d ' ')
    [ "$n" -gt 0 ] && continue                             # already populated
    [ "$RETRY" != "1" ] && [ -f "$d/.blocked" ] && continue  # known-blocked, don't hammer
    ( echo ">> [$pass] build $name ($domain)" | tee -a "$LOG"
      python3 website_agent.py --domain "$domain" --name "$name" \
        --max-sitemaps 6 --limit 800 --pages-limit 60 --mine --root --gleif --force \
        >"sites/_loop_${domain}.txt" 2>&1
      nn=0; [ -f "$f" ] && nn=$(tail -n +2 "$f" 2>/dev/null | wc -l | tr -d ' ')
      if [ "$nn" -gt 0 ]; then python3 render_p4_cloud_edge.py --site "$d" >/dev/null 2>&1;
        echo "<< [$pass] OK   $name  ($nn urls)" | tee -a "$LOG"
      else mkdir -p "$d"; : > "$d/.blocked"; echo "<< [$pass] BLOCKED $name (0 urls -> .blocked)" | tee -a "$LOG"; fi ) &
    built=$((built+1))
    while [ "$(jobs -r | wc -l)" -ge "$MAXJ" ]; do sleep 1; done
  done < fleet_queue.txt
  wait
  python3 render_fleet.py >/dev/null 2>&1
  pop=$(for dd in sites/*/; do ff="${dd}sitemap_structure.csv"; [ -f "$ff" ] && [ "$(tail -n +2 "$ff" 2>/dev/null|wc -l|tr -d ' ')" -gt 0 ] && echo x; done | wc -l | tr -d ' ')
  echo ">> [$pass] PASS DONE · built $built · fleet populated: $pop · $(date)" | tee -a "$LOG"
  if [ "$built" -eq 0 ]; then echo ">> idle — queue drained/blocked. Add domains to fleet_queue.txt (or RETRY_BLOCKED=1 after the harvester patch). Sleeping ${SLEEP}s." | tee -a "$LOG"; fi
  sleep "$SLEEP"
done
