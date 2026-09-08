#!/usr/bin/env bash
# Installs a launchd agent that runs the full pipeline (A then B) daily.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.thingdaddy.loops.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"

sed -e "s|{{ROOT}}|$ROOT|g" -e "s|{{PYTHON}}|$PYTHON|g" \
    "$ROOT/launchd/com.thingdaddy.loops.plist" > "$PLIST"

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Loaded $PLIST"
echo "Runs daily at 02:30. Logs: $ROOT/logs/  |  manual kick: launchctl start com.thingdaddy.loops"
