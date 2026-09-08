#!/usr/bin/env bash
# =============================================================================
# seed_up.sh — load the dev seed into a local database.
#
#   createdb thingdaddy_population
#   ./seed_up.sh
#
# A DATED SNAPSHOT OF REAL PRODUCTION ROWS, FOR LOCAL DEVELOPMENT.
# Not fabricated · not authoritative · not a source of truth · not test data.
# See MANIFEST.txt for when it was taken. REGENERATE, NEVER EDIT.
# =============================================================================
set -euo pipefail

DB="${PGDATABASE:-thingdaddy_population}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

say() { printf '  %s\n' "$*"; }
die() { printf '\n  REFUSED: %s\n\n' "$*" >&2; exit 1; }

echo
echo "seed_up  ->  $DB"
echo

# ── preflight: refuse before writing, not halfway through ────────────────────
for f in 01_schema.sql 02_party.csv 03_content_claim.csv 04_party_event.csv 05_load.sql MANIFEST.txt; do
  [ -f "$f" ] || die "$f is missing. The seed is incomplete — get a full copy."
done

command -v psql >/dev/null || die "psql not on PATH"
psql -qAt -d "$DB" -c 'select 1' >/dev/null 2>&1 \
  || die "cannot connect to $DB. Run:  createdb $DB"

# Refuse to load over an existing seed. Loading twice would collide on
# ux_party_prefix and leave the database half-written.
EXISTING=$(psql -qAt -d "$DB" -c \
  "select count(*) from information_schema.tables
    where table_schema='public' and table_name='party';")
if [ "$EXISTING" != "0" ]; then
  N=$(psql -qAt -d "$DB" -c 'select count(*) from party;')
  die "$DB already has a party table holding $N row(s).
           This script does not load over an existing database.
           To start clean:  dropdb $DB && createdb $DB && ./seed_up.sh"
fi

echo "PREFLIGHT"
say "all six files present"
say "$DB reachable and empty"
echo
sed -n '1,12p' MANIFEST.txt | sed 's/^/  /'
echo

# ── load ─────────────────────────────────────────────────────────────────────
echo "SCHEMA"
psql -q -v ON_ERROR_STOP=1 -d "$DB" -f 01_schema.sql
say "12 tables, constraints, indexes, triggers"

echo
echo "DATA"
psql -q -v ON_ERROR_STOP=1 -d "$DB" -f 05_load.sql
say "loaded"

# ── verify against the MANIFEST, not against the load's own report ───────────
# The load reporting success is not evidence the rows are there. Count them.
echo
echo "VERIFY"
fail=0
check() {
  local table="$1" want
  want=$(awk -v t="$table" '$1==t {print $2}' MANIFEST.txt)
  local got
  got=$(psql -qAt -d "$DB" -c "select count(*) from $table;")
  if [ "$got" = "$want" ]; then
    printf '  PASS  %-16s %s\n' "$table" "$got"
  else
    printf '  FAIL  %-16s got %s, MANIFEST says %s\n' "$table" "$got" "$want"
    fail=1
  fi
}
check party
check content_claim
check party_event

[ "$fail" = "0" ] || die "the loaded database does not match the MANIFEST.
           Do NOT use it. A partial load renders an empty screen and
           looks like a bug in the screens.
           dropdb $DB && createdb $DB && ./seed_up.sh"

# ── what to expect, so an empty screen is information and not a bug report ───
cat <<'EOF'

READY.

  cd ../api && npm install && npm start
  open ../fill/td_screens_live.html

WHAT WORKS
  /health · /stats · /search?q= · /verified
  /record/prefix/081627002 · /record/prefix/081577302
  /record/prefix/081693402 · /record/prefix/0817089
  /party/:id/completeness

WHAT IS EMPTY, BY DESIGN, NOT A BUG
  /node/by-legacy/party/:id   404 — no spine node is backfilled for these
                              parties in production either. The UI shows
                              "not on the spine yet" and never fakes a node.
  /party/:id/assets           []
  /party/:id/epcis            []

ALSO CORRECT, ALSO NOT A BUG
  /stats returns 4. It counts the whole database.
  S1 shows "Over 11,000,000 identities" — a hardcoded string, not from
    /stats. Flagged in #17 finding 3, marked TODO, unruled.
  const RECORDS survives at line 285 of td_screens_live.html. The file is
    a hybrid: some screens call the API, some still read the fixture.

  Nothing here flows back to the record. Regenerate, never edit.

EOF
