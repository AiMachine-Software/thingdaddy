#!/usr/bin/env bash
# ThingDaddy Loops — one-shot Mac mini setup.
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 not found (install via 'brew install python')"; exit 1; }
echo "==> Python: $(python3 --version)"

echo "==> Creating venv + installing requirements"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

echo "==> Running offline self-test (no network)"
python3 tests/selftest.py

cat <<NEXT

==> Setup complete.

Next steps:
  1. Edit config.yaml:
       - net.user_agent  : put your real contact email (SEC EDGAR requires it)
       - sam_gov.api_key : optional free key from sam.gov (leave blank to skip SAM edges)
       - offline: false  : already set for live pulls
  2. First live run (this can take a while on the initial GLEIF load):
       make run-all
  3. Schedule always-on daily runs:
       make install-launchd
Outputs land in ./out (profiles, cross-MO links, needs-prefix queue, graph_*).
NEXT
