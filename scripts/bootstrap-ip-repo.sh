#!/usr/bin/env bash
# bootstrap-ip-repo.sh — one-time setup of the ThingDaddy IP register + lint governance.
# Safe to re-run: it never overwrites IP-LOG.md or clobbers an existing CLAUDE.md.
# Follows the rules: append-only record, provisional numbers, verified-or-exception,
# never renumber silently.

set -euo pipefail

REPO="${1:-$HOME/thingdaddy}"          # pass a path to override, else ~/thingdaddy
IP_DIR="$REPO/docs/ip"
LOG="$IP_DIR/IP-LOG.md"
EXC="$IP_DIR/LINT-EXCEPTIONS.md"
CLAUDE="$REPO/CLAUDE.md"
HANDOFF="$REPO/SESSION-HANDOFF.md"
SENTINEL="## IP register laws"          # marker so we never double-append

echo "==> Repo root: $REPO"
mkdir -p "$IP_DIR/snapshots"

# --- IP-LOG.md : the canonical record. Never overwrite. ---
if [[ -f "$LOG" ]]; then
  echo "==> IP-LOG.md already present — leaving untouched (append-only record)."
else
  # Look for the generated file in common drop spots.
  FOUND=""
  for c in "$HOME/Downloads/IP-LOG.md" "$REPO/IP-LOG.md" "./IP-LOG.md"; do
    [[ -f "$c" ]] && FOUND="$c" && break
  done
  if [[ -n "$FOUND" ]]; then
    mv "$FOUND" "$LOG"
    echo "==> Moved $FOUND -> $LOG"
  else
    echo "!!! IP-LOG.md not found in ~/Downloads or repo root."
    echo "    Drop the generated IP-LOG.md into ~/Downloads and re-run, OR ask Claude"
    echo "    to regenerate it first. NOT creating a placeholder (verified-or-exception)."
    exit 1
  fi
fi

# --- LINT-EXCEPTIONS.md : where the lint agent writes. Create empty if absent. ---
if [[ ! -f "$EXC" ]]; then
  cat > "$EXC" <<'EOF'
# IP Lint — Exceptions Log

Append-only. Each lint run adds a dated block. Findings are OPEN until KJ resolves them.
The lint agent writes here and ONLY here — it never edits IP-LOG.md and never renumbers.
EOF
  echo "==> Created $EXC"
fi

# --- CLAUDE.md : append governance block only if not already there. ---
if [[ -f "$CLAUDE" ]] && grep -qF "$SENTINEL" "$CLAUDE"; then
  echo "==> CLAUDE.md already carries IP register laws — not re-appending."
else
  [[ -f "$CLAUDE" ]] || : > "$CLAUDE"
  cat >> "$CLAUDE" <<'EOF'

## IP register laws
- `docs/ip/IP-LOG.md` is the canonical, append-only source of truth for all IP.
  The .docx/.xlsx in docs/ip/snapshots/ are generated views, never the record.
- On any new invention: append to IP-LOG.md — one-line claim, novelty vs. the
  existing register, TD-M mapping. Continuous scan; surface candidates proactively.
- New TD-M / IP-C numbers are PROVISIONAL until KJ's gate. Never renumber silently.
- Verified-or-exception: never fabricate to fill a gap. A gap is a named exception.
- "Legacy IDs," never "old IDs," in all output.

## IP lint agent (TD-C-56, provisional)
- Weekly or on demand, walk IP-LOG.md end to end and run checks C1–C8 in
  docs/ip/IP-LINT-AGENT.md.
- Write findings ONLY to docs/ip/LINT-EXCEPTIONS.md as a dated, append-only block.
- Never edit IP-LOG.md, never renumber, never promote a candidate, never send to
  counsel. Findings are OPEN until KJ resolves them.
EOF
  echo "==> Appended IP governance to CLAUDE.md"
fi

# --- SESSION-HANDOFF.md : ensure it points readers at the register + exceptions. ---
if [[ -f "$HANDOFF" ]] && grep -qF "docs/ip/IP-LOG.md" "$HANDOFF"; then
  echo "==> SESSION-HANDOFF.md already points at the register."
else
  cat >> "$HANDOFF" <<'EOF'

## Read first (IP)
1. docs/ip/IP-LOG.md            (current register state)
2. docs/ip/LINT-EXCEPTIONS.md   (open items awaiting KJ gate)
EOF
  echo "==> Updated SESSION-HANDOFF.md"
fi

# --- git ---
cd "$REPO"
[[ -d .git ]] || git init -q
git add -A
git commit -q -m "Bootstrap IP register + lint governance" || echo "==> Nothing new to commit."
echo "==> Done. Register is live at $LOG"
