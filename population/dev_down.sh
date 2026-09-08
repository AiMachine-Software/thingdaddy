#!/bin/bash
LOG=/tmp/td
for p in api ui; do
  if [ -f "$LOG/$p.pid" ]; then kill "$(cat "$LOG/$p.pid")" 2>/dev/null && echo "stopped $p"; rm -f "$LOG/$p.pid"; fi
done
# belt and suspenders: free the ports
for port in 8787 5173; do lsof -ti tcp:$port 2>/dev/null | xargs -r kill 2>/dev/null; done
echo "ports 8787 + 5173 free"
