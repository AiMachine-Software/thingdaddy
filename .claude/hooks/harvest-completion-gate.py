#!/usr/bin/env python3
"""
harvest-completion-gate.py  — SubagentStop hook (matcher: td-harvester)

The completion complement to the mint gate. Fires when td-harvester finishes. If any
candidate it produced this run has no verifier verdict yet, it blocks the stop so those
rows can't be silently dropped — they get routed through td-prefix-verifier before the
run is allowed to end.

This is a SAFETY NET, not the guarantee. The guarantee is mint-gate.py at PreToolUse.
SubagentStop hooks in settings.json have a history of firing unreliably for delegated
dispatches; if you want this check to be reliable, register it in the harvester's OWN
frontmatter as a Stop hook (Claude Code converts an in-agent Stop hook to SubagentStop),
which fires more dependably than the settings.json route.

Exit codes:  0 = allow stop   2 = block stop (reason on stderr, sent back to the agent)
"""
import json, os, sys

def repo_root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

def load_ids(path, want_verdict=False):
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

def main():
    try:
        json.load(sys.stdin)  # consume event; we don't need its fields here
    except Exception:
        sys.exit(0)

    state = os.path.join(repo_root(), "state")
    candidates = load_ids(os.path.join(state, "candidates.jsonl"))
    verdicts = load_ids(os.path.join(state, "verdicts.jsonl"), want_verdict=True)

    unverdicted = [rid for rid in candidates if rid not in verdicts]
    if unverdicted:
        preview = ", ".join(str(r) for r in unverdicted[:10])
        more = "" if len(unverdicted) <= 10 else f" (+{len(unverdicted) - 10} more)"
        sys.stderr.write(
            f"HARVEST GATE — {len(unverdicted)} candidate rows have no verifier verdict "
            f"yet: {preview}{more}. Send them through td-prefix-verifier before finishing; "
            f"do not drop them. verified-or-exception.\n")
        sys.exit(2)

    sys.exit(0)

if __name__ == "__main__":
    main()
