#!/usr/bin/env bash
# =============================================================================
# demo_down.sh — stop the demo API started by demo_up.sh.
#
#     ./population/seed/demo_down.sh
#
# Stops the process and nothing else. The database is left in place: rebuilding
# it is cheap, and dropping something on the way out is how work disappears.
#
#     dropdb thingdaddy_population      # if you want it gone
# =============================================================================
set -euo pipefail

PIDFILE="/tmp/td_demo_api.pid"
PORT=8787

echo

if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    sleep 0.5
    kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
    echo "  stopped pid $PID"
  else
    echo "  pid $PID from $PIDFILE is not running"
  fi
  rm -f "$PIDFILE"
else
  echo "  no $PIDFILE — demo_up.sh may not have started it"
fi

# Say plainly whether the port is now free. "I sent a signal" is not the same
# as "it stopped", and only one of those is worth reporting.
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo
  echo "  NOTE: something is STILL listening on $PORT:"
  lsof -nP -iTCP:$PORT -sTCP:LISTEN | tail -n +2 | sed 's/^/    /'
  echo
  echo "  demo_up.sh will refuse to start until that is gone."
else
  echo "  port $PORT is free"
fi

echo "  database left in place. dropdb thingdaddy_population to remove it."
echo
