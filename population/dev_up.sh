#!/bin/bash
# Bring the integrated stack up: population API (8787) + 5-pillar UI (Vite 5173).
# Reads api/.env (INGEST_TOKEN, PG*) and ui/.env (VITE_*). Backgrounds both,
# tails logs, and prints a health check. Postgres must already be running.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG=/tmp/td; mkdir -p "$LOG"

echo "▸ Postgres check…"
if command -v pg_isready >/dev/null 2>&1; then pg_isready || echo "  (pg_isready says not ready — start Postgres.app / brew services start postgresql)"; fi

echo "▸ starting population API on :8787"
( cd "$HERE/api" && npm start >"$LOG/api.log" 2>&1 & echo $! >"$LOG/api.pid" )
sleep 4
echo "▸ starting UI (Vite) on :5173"
( cd "$HERE/ui" && npm run dev >"$LOG/ui.log" 2>&1 & echo $! >"$LOG/ui.pid" )
sleep 5

echo; echo "===== API health ====="
curl -s http://127.0.0.1:8787/health || echo "(no response)"; echo
echo "===== API stats ====="
curl -s http://127.0.0.1:8787/stats || echo "(no response)"; echo
echo; echo "===== API log tail ====="; tail -6 "$LOG/api.log"
echo; echo "===== UI log tail ====="; tail -10 "$LOG/ui.log"
echo; echo "▸ open  http://localhost:5173"
