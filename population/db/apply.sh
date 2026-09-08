#!/usr/bin/env bash
# ============================================================================
# apply.sh — idempotent: create the population DB (if absent) + apply schema.
#
#   ./apply.sh                 # uses db "thingdaddy_population"
#   DB=other ./apply.sh        # override the target db name
#
# Requires psql/createdb on PATH (Postgres.app or Homebrew postgresql@16).
# Safe to run repeatedly — schema.sql is idempotent.
# ============================================================================
set -euo pipefail

DB="${DB:-thingdaddy_population}"
DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not found on PATH. Install Postgres first (see population/CLAUDE.md)." >&2
  exit 1
fi

# create-db, idempotently (does nothing if it already exists).
if psql -lqt | cut -d '|' -f1 | tr -d ' ' | grep -qx "$DB"; then
  echo "▸ database '$DB' already exists — skipping create"
else
  createdb "$DB"
  echo "▸ created database '$DB'"
fi

# apply schema; stop on the first error so a bad migration never half-applies.
psql -v ON_ERROR_STOP=1 -d "$DB" -f "$DIR/schema.sql"
echo "▸ schema applied to '$DB'"
