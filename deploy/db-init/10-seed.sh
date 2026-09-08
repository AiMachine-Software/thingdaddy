#!/usr/bin/env bash
# =============================================================================
# 10-seed.sh — runs ONCE, on the first boot of an empty postgres volume.
#
# The official postgres entrypoint executes every file in
# /docker-entrypoint-initdb.d after it has created $POSTGRES_DB. We do NOT
# mount population/seed/ there directly, because the entrypoint would also
# execute demo_up.sh, demo_down.sh and make_seed.sh. Instead the seed is
# mounted read-only at /seed and this one script drives it.
#
# It delegates to the seed's own seed_up.sh so the load and the MANIFEST row
# count verification are KJ's, not a reimplementation. 05_load.sql uses psql
# \copy with RELATIVE csv paths, which is why seed_up.sh cd's to its own
# directory first — that is also why this must run from /seed.
# =============================================================================
set -euo pipefail

export PGDATABASE="${POSTGRES_DB:-thingdaddy_population}"
export PGUSER="${POSTGRES_USER:-postgres}"

echo "10-seed: loading the dev seed into ${PGDATABASE} as ${PGUSER}"

cd /seed
bash ./seed_up.sh

echo "10-seed: done."
