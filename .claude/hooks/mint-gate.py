#!/usr/bin/env python3
"""
mint-gate.py  — PreToolUse hook (matcher: Bash)

The hard gate. Fires before every Bash tool call. If the command is a promotion to the
populated store, it blocks unless EVERY row in the staged batch carries a VERIFIED
verdict from td-prefix-verifier. Anything else — CANDIDATE, REJECTED, or missing — is
blocked. Fails CLOSED: if it can't prove verification, it does not let the write through.
That is verified-or-exception applied to the gate itself.

Contract (files under <repo>/state/):
  candidates.jsonl    harvester output      {"id": ..., ...}
  verdicts.jsonl      verifier output       {"id": ..., "verdict": "verified|candidate|rejected", "reason": ...}
  promote-batch.jsonl rows about to be written to the populated store  {"id": ..., ...}

Exit codes:  0 = allow   2 = hard block (reason on stderr, shown to Claude)
Never exit 1 — that is an error, not a block.
"""
import json, os, sys

# --- what counts as a promotion to the populated store (edit to match your loop) ---
PROMOTE_MARKERS = ("promote.py", "populated.db", "INSERT INTO populated")

def repo_root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

def load_ids(path, want_verdict=False):
    """Return set of ids, or dict id->verdict when want_verdict."""
    out = {} if want_verdict else set()
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = row.get("id")
            if rid is None:
                continue
            if want_verdict:
                out[rid] = (row.get("verdict") or "").lower()
            else:
                out.add(rid)
    return out

def block(msg):
    sys.stderr.write("MINT GATE — promotion blocked.\n" + msg +
                     "\nverified-or-exception: nothing mints on an unverified row.\n")
    sys.exit(2)

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # no parseable event: don't interfere

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (data.get("tool_input") or {}).get("command", "")
    if not any(m in cmd for m in PROMOTE_MARKERS):
        sys.exit(0)  # not a promotion — not our concern

    # It IS a promotion. From here we fail closed.
    state = os.path.join(repo_root(), "state")
    batch = load_ids(os.path.join(state, "promote-batch.jsonl"))
    verdicts = load_ids(os.path.join(state, "verdicts.jsonl"), want_verdict=True)

    if not batch:
        block("No staged promote-batch.jsonl found, but a promotion command is running. "
              "Refusing to promote an unverifiable write.")

    bad = [rid for rid in batch if verdicts.get(rid) != "verified"]
    if bad:
        preview = ", ".join(str(r) for r in bad[:10])
        more = "" if len(bad) <= 10 else f" (+{len(bad) - 10} more)"
        block(f"{len(bad)} of {len(batch)} staged rows lack a VERIFIED verdict: "
              f"{preview}{more}. Route them through td-prefix-verifier first.")

    sys.exit(0)  # every staged row is verified — allow the write

if __name__ == "__main__":
    main()
