#!/usr/bin/env bash
# run-ip-lint.sh — run the IP lint agent over the register and commit its findings.
# Called manually, or weekly by com.thingdaddy.iplint.plist (launchd).
#
# COST: this uses `claude -p` (headless), which bills API tokens if ANTHROPIC_API_KEY
# is set. One read-mostly pass over the register is cheap, but it IS metered. If you're
# on a Max plan and want it free, run the lint interactively (`claude`, logged in)
# instead of via this script. Keep a spend limit on the key either way.

set -euo pipefail

REPO="${REPO:-$HOME/thingdaddy}"
cd "$REPO"

# launchd does NOT source ~/.zshrc, so an API key set there is invisible to a scheduled
# run. If you schedule this, put the key in the plist's EnvironmentVariables (see the
# .plist file) or uncomment and hardcode a source line here.
# export ANTHROPIC_API_KEY="sk-ant-api03-..."

PROMPT='Run the IP lint agent per docs/ip/IP-LINT-AGENT.md. Walk docs/ip/IP-LOG.md end
to end and run checks C1 through C8. Append one dated findings block to
docs/ip/LINT-EXCEPTIONS.md using the schema in that spec (ID, severity, check, families,
evidence with line refs, recommended action, STATUS: OPEN). Do NOT edit IP-LOG.md, do
NOT renumber, do NOT fabricate to fill a gap, do NOT send anything to counsel. Report only.'

echo "==> Running IP lint at $(date)"
claude -p "$PROMPT"

# Commit only the exceptions file — the record itself is never touched by lint.
if ! git diff --quiet -- docs/ip/LINT-EXCEPTIONS.md; then
  git add docs/ip/LINT-EXCEPTIONS.md
  git commit -q -m "IP lint $(date +%F)"
  echo "==> Findings committed."
else
  echo "==> No new findings (clean run)."
fi
