#!/usr/bin/env bash
# =============================================================================
# demo_up.sh — bring up the ThingDaddy screens demo, from nothing, in one go.
#
#     cd ~/thingdaddy && ./population/seed/demo_up.sh
#
# Fetches what it needs, builds a local database from the seed, starts the API
# on 8787, VERIFIES THE API BUILD IS CURRENT, and opens the screens.
#
# WHY THE ROUTE CHECK EXISTS
#   On 5 September the Mac mini served this demo all afternoon with a banner
#   reading "LIVE · 102,472 records" while three endpoints returned
#   {"error":"no route ..."}. The port answered. /health answered. The record
#   count was real. And the pillars rendered empty because the routes the
#   screens call did not exist in the running build — a bun process from
#   22 August, two weeks behind server.js on disk.
#
#   A port that answers is not a build that serves. This script asks every
#   route the screens actually call and refuses to say READY if any of them
#   comes back "no route".
#
# WHY THE CLOSING NOTES ARE COMPUTED, NOT WRITTEN
#   The first version of this script printed "you will see 4 records" and
#   "the pillars show slot" no matter what database it found — and printed
#   exactly that over a 102,472-row production database. Notes that do not
#   read the thing they describe are a guess wearing a fact's clothes.
#   Everything from §5 down is read from the database actually attached.
#
#   Stop with:  ./population/seed/demo_down.sh
# =============================================================================
set -euo pipefail

DB="${TD_DEMO_DB:-thingdaddy_population}"
PORT=8787            # NOT configurable: td_screens_live.html hardcodes
                     # const API = 'http://127.0.0.1:8787' at line 649.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API="$ROOT/apps/api"
SEED="$ROOT/population/seed"
SCREENS="$ROOT/apps/web/public/demo/td_screens_live.html"
LOG="/tmp/td_demo_api.log"
PIDFILE="/tmp/td_demo_api.pid"

SEED_BRANCH="origin/seed/dev-seed"
SCREENS_BRANCH="origin/screens/td-screens-live-original"

say()  { printf '  %s\n' "$*"; }
step() { printf '\n%s\n' "$*"; }
die()  { printf '\n  REFUSED: %s\n\n' "$*" >&2; exit 1; }

echo
echo "demo_up   ThingDaddy screens against a local API"
echo "  repo: $ROOT"
echo "  db:   $DB"
echo "  port: $PORT"

# ── 0 · preflight ────────────────────────────────────────────────────────────
step "PREFLIGHT"
for c in git psql createdb node npm curl; do
  command -v "$c" >/dev/null || die "$c is not on PATH"
done
say "git psql createdb node npm curl"

if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  die "something is already listening on $PORT.

           The screens hardcode 127.0.0.1:$PORT — the port is not
           configurable, so this cannot be worked around by moving.
           Find it with:   lsof -nP -iTCP:$PORT -sTCP:LISTEN
           Then stop it, or run ./population/seed/demo_down.sh"
fi
say "port $PORT is free"

# ── 1 · the files ────────────────────────────────────────────────────────────
# The seed and the screens are on branches until their PRs merge. Take them
# from the branch WITHOUT switching: a checkout moves the whole tree and makes
# other files vanish underneath you — which happened four times on 5 September.
step "FILES"
cd "$ROOT"
git fetch origin --quiet 2>/dev/null || say "could not fetch — using what is local"

if [ ! -f "$SEED/01_schema.sql" ]; then
  git rev-parse --verify --quiet "$SEED_BRANCH" >/dev/null \
    || die "no seed on disk and $SEED_BRANCH not found. Fetch it, or merge PR #20."
  mkdir -p "$SEED"
  for f in 01_schema.sql 02_party.csv 03_content_claim.csv 04_party_event.csv 05_load.sql MANIFEST.txt README.md seed_up.sh; do
    git show "$SEED_BRANCH:population/seed/$f" > "$SEED/$f"
  done
  chmod +x "$SEED/seed_up.sh"
  say "seed taken from $SEED_BRANCH"
else
  say "seed already present"
fi

if [ ! -f "$SCREENS" ]; then
  git rev-parse --verify --quiet "$SCREENS_BRANCH" >/dev/null \
    || die "no screens on disk and $SCREENS_BRANCH not found. Fetch it, or merge PR #18."
  mkdir -p "$(dirname "$SCREENS")"
  git show "$SCREENS_BRANCH:apps/web/public/demo/td_screens_live.html" > "$SCREENS"
  say "screens taken from $SCREENS_BRANCH"
else
  say "screens already present"
fi

[ -f "$API/server.js" ] || die "$API/server.js not found. Is this the platform repo?"
say "api present"

# ── 2 · the database ─────────────────────────────────────────────────────────
step "DATABASE"
if psql -qAt -d "$DB" -c 'select 1' >/dev/null 2>&1; then
  N=$(psql -qAt -d "$DB" -c "select count(*) from party;" 2>/dev/null || echo "?")
  say "$DB already exists, holding $N party row(s) — left alone"
  say "to rebuild from the seed:  dropdb $DB && ./population/seed/demo_up.sh"
else
  createdb "$DB"
  say "created $DB"
  ( cd "$SEED" && PGDATABASE="$DB" ./seed_up.sh >/tmp/td_seed_load.log 2>&1 ) \
    || die "the seed failed to load. See /tmp/td_seed_load.log"
  say "seed loaded and verified against MANIFEST"
fi

# ── 3 · the API ──────────────────────────────────────────────────────────────
step "API"
cd "$API"
[ -d node_modules ] || { say "npm install…"; npm install --silent; }

PGDATABASE="$DB" PORT=$PORT node server.js >"$LOG" 2>&1 &
API_PID=$!
echo "$API_PID" > "$PIDFILE"

for i in $(seq 1 20); do
  sleep 0.5
  curl -sf "127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  kill -0 "$API_PID" 2>/dev/null || { cat "$LOG"; die "the API exited on startup. Log above."; }
  [ "$i" = "20" ] && { cat "$LOG"; die "the API never answered /health. Log above."; }
done

HEALTH=$(curl -s "127.0.0.1:$PORT/health")
say "pid $API_PID · $HEALTH"

case "$HEALTH" in
  *"$DB"*) say "confirmed reading $DB" ;;
  *) kill "$API_PID" 2>/dev/null
     die "the API is not reading $DB. It reported: $HEALTH
           An API pointed at the wrong database renders wrong numbers under
           a banner that says LIVE." ;;
esac

# ── 4 · THE ROUTE CHECK — a port that answers is not a build that serves ─────
# Every route the screens call, asked for real. A missing endpoint returns a
# body containing "no route"; an honest empty answer does not. Both are 404,
# and that difference is the whole check.
step "ROUTES  (the build check — see the header of this script)"
PID_ONE=$(psql -qAt -d "$DB" -c "select id from party where prefix is not null order by (state='verified') desc, id limit 1;")
PFX_ONE=$(psql -qAt -d "$DB" -c "select prefix from party where prefix is not null order by (state='verified') desc, id limit 1;")

[ -n "$PID_ONE" ] || { kill "$API_PID" 2>/dev/null; die "$DB holds no rooted party. Nothing to demo."; }

missing=0
check_route() {
  local label="$1" path="$2" body
  body=$(curl -s "127.0.0.1:$PORT$path" || echo '')
  if printf '%s' "$body" | grep -q '"error": *"no route'; then
    printf '  MISSING  %-34s %s\n' "$label" "$path"
    missing=1
  else
    printf '  present  %-34s %s\n' "$label" "$path"
  fi
}

check_route "health"            "/health"
check_route "stats"             "/stats"
check_route "search"            "/search?q=a"
check_route "record by prefix"  "/record/prefix/$PFX_ONE"
check_route "completeness"      "/party/$PID_ONE/completeness"
check_route "spine node"        "/node/by-legacy/party/$PID_ONE"

if [ "$missing" = "1" ]; then
  kill "$API_PID" 2>/dev/null
  die "the running API does not serve every route the screens call.

           This is a STALE BUILD, not missing data. The screens will render
           empty pillars while the banner says LIVE — which is exactly what
           happened on the Mac mini on 5 September, for two weeks.

           git pull, then run this script again."
fi
say "every route the screens call is served by this build"

# ── 4b · THE SCREENS CHECK — every page the demo opens must be on disk ───────
# Same shape as ROUTES: one line per screen, present or MISSING, and any
# MISSING refuses READY. A screen that is not on disk is a 404 in the browser
# under a banner that says LIVE, and td_home.html spent two weeks untracked.
step "SCREENS  (the pages the demo opens)"
screens_missing=0
check_screen() {
  local label="$1" path="apps/web/public/demo/$1.html"
  if [ -f "$ROOT/$path" ]; then
    printf '  present  %-34s %s\n' "$label" "$path"
  else
    printf '  MISSING  %-34s %s\n' "$label" "$path"
    screens_missing=1
  fi
}

for scr in td_demo td_thingsite td_console td_configurator td_screens_live td_home; do
  check_screen "$scr"
done

if [ "$screens_missing" = "1" ]; then
  kill "$API_PID" 2>/dev/null
  die "not every screen the demo opens is on disk under apps/web/public/demo/.

           A page that is not there renders as a 404 while the API says
           healthy. Restore the MISSING file(s) from git, then run this
           script again."
fi
say "every screen the demo opens is on disk"

# ── 5 · what is actually here — READ, never assumed ──────────────────────────
step "WHAT THIS DATABASE ACTUALLY HOLDS"
N_PARTY=$(psql -qAt -d "$DB" -c "select count(*) from party;")
N_ROOTED=$(psql -qAt -d "$DB" -c "select count(*) from party where prefix is not null;")
N_VERIFIED=$(psql -qAt -d "$DB" -c "select count(*) from party where state='verified';")
N_CLAIMS=$(psql -qAt -d "$DB" -c "select count(*) from content_claim;")
N_NODES=$(psql -qAt -d "$DB" -c "select count(*) from node n where n.key_type='pgln' and exists (select 1 from party p where p.id = (n.legacy->>'party_id')::bigint);" 2>/dev/null || echo 0)
PREFIXES=$(psql -qAt -d "$DB" -c "select prefix from party where prefix is not null order by (state='verified') desc, id limit 4;" | tr '\n' ' ')

printf '  %-18s %s\n' "party rows"     "$N_PARTY"
printf '  %-18s %s\n' "rooted"         "$N_ROOTED"
printf '  %-18s %s\n' "verified"       "$N_VERIFIED"
printf '  %-18s %s\n' "content claims" "$N_CLAIMS"
printf '  %-18s %s\n' "spine nodes"    "$N_NODES"

step "READY"
command -v open >/dev/null && open "$SCREENS" || say "open: $SCREENS"

echo
echo "  TRY THESE PREFIXES:  $PREFIXES"
echo
echo "  The LIVE banner will read $N_PARTY records. That is this database,"
echo "  and it is correct."
echo

if [ "$N_NODES" = "0" ]; then
  cat <<'EOF'
  THE GRAPH AND ASSOCIATION SCREENS WILL BE EMPTY — BY DESIGN.
    No spine node is backfilled for any party here, so
    /node/by-legacy/party/:id returns 404 saying "no spine node backfilled".
    That is the HONEST 404, not the stale-build one: the route exists and
    there is genuinely nothing to return. The UI says "not on the spine yet"
    and never fakes a node.

EOF
fi

if [ "$N_PARTY" -le 10 ]; then
  cat <<'EOF'
  THIS IS THE SEED, NOT PRODUCTION.
    Four companies, 187 claims. /stats returns 4 and that is correct — it
    counts the whole database. Searching a company name may return TWO rows,
    one rooted and one not: duplicates are shown, never merged silently.

    A dated snapshot of real production rows. Not fabricated, not
    authoritative, not a source of truth, not test data. Regenerate, never
    edit. See MANIFEST.txt for when it was taken.

EOF
else
  cat <<'EOF'
  THIS IS A FULL DATABASE, NOT THE SEED.
    The pillars should carry real content. A pillar reading "slot" is a
    DECLARED GAP in the data, not a failure of the screens — and a declared
    gap is stronger than a blank.

EOF
fi

cat <<EOF
  ALSO TRUE, AND NOT A BUG
    The counter and "Over 11,000,000 identities" on S1 are HARDCODED
    strings, not queries. Flagged in PR #17, unruled.

    Typing ACME hits the fixture at line 285, not the API. The file is a
    hybrid: some screens call the API, some still read const RECORDS.
    Pointing the rest at the API is open work.

    Searching a PREFIX may return MORE rows than expected — a longer prefix
    containing the one you typed is a containment finding, not a duplicate.
    It may also DROP a matching row that has no prefix at all. Both known,
    both on the tape for 5 September.

  Nothing here writes anywhere. Nothing flows back to the record.

STOP IT
  ./population/seed/demo_down.sh      or:  kill $API_PID
  API log: $LOG

EOF
