# Mint Gate — Deterministic Enforcement of Verified-or-Exception

A system prompt is a request; a hook is a guarantee. The agent files tell the harvester
and verifier what to do. This hook makes the mint gate *impossible to skip* — no row
reaches the populated store unless the independent verifier stamped it VERIFIED. It's the
same principle as the register lint gate, pushed down to the exact action that must not
happen on a guess: the write.

**Package (four files):**

| File | Role | Lives at |
|------|------|----------|
| `mint-gate.py` | **the hard gate** (PreToolUse) | `.claude/hooks/` |
| `harvest-completion-gate.py` | completion safety net (SubagentStop) | `.claude/hooks/` |
| `settings.hooks.json` | registers both hooks | merge into `.claude/settings.json` |
| `MINT-GATE-HOOK.md` | this doc | `docs/` |

---

## 1. Why PreToolUse, not SubagentStop

You asked for the SubagentStop hook. Here's the honest correction, because it changes
whether the gate actually holds: the thing you want to block is the **write to the
populated store**, and a write is a *tool call*. A hook is a guarantee only when it sits
on the exact action it's guarding.

- **PreToolUse** fires *before* a tool runs and can cancel it (`exit 2`). This is where
  the write gets blocked. It's the guarantee.
- **SubagentStop** fires when the harvester *finishes*. Useful as a completion check, but
  it can't block a write — the write already happened. Worse, SubagentStop hooks in
  settings.json have a documented history of firing unreliably for delegated dispatches
  (anthropics/claude-code #27755). Leaning on it as the gate would be a false sense of
  safety.

So: `mint-gate.py` on PreToolUse is the lock. `harvest-completion-gate.py` on
SubagentStop is a secondary net that catches candidates left without a verdict. Two
layers, and the guarantee doesn't depend on the flaky one.

---

## 2. The file contract

The hooks read three plain-JSONL files under `<repo>/state/` — the same staging your
Python harvest loop already writes. No database parsing, so the gate stays simple and
deterministic.

```
state/candidates.jsonl     harvester output      {"id": ...}
state/verdicts.jsonl       verifier output       {"id": ..., "verdict": "verified|candidate|rejected", "reason": ...}
state/promote-batch.jsonl  rows about to be written to the populated store   {"id": ...}
```

Flow: harvester writes `candidates.jsonl` → verifier writes `verdicts.jsonl` →
orchestrator stages the rows it intends to promote into `promote-batch.jsonl`, then runs
the promote command. The gate intercepts that command.

---

## 3. What the gate does

`mint-gate.py` fires on every Bash call, but exits immediately (allow) unless the command
is a promotion to the populated store — detected by the markers at the top of the script
(`promote.py`, `populated.db`, `INSERT INTO populated`; edit to match your loop). When it
*is* a promotion:

- Every staged row has a `verified` verdict → **allow** (exit 0).
- Any staged row is CANDIDATE, REJECTED, or has no verdict → **block** (exit 2), with the
  offending ids sent back to Claude as the reason.
- No staged batch exists but a promote command is running → **block**. The gate **fails
  closed**: if it can't prove verification, it refuses. That's verified-or-exception
  applied to the gate itself.

`harvest-completion-gate.py` fires when `td-harvester` stops. If any candidate has no
verdict yet, it blocks the stop so those rows get routed through the verifier instead of
being silently dropped.

---

## 4. Install

```bash
mkdir -p ~/thingdaddy/.claude/hooks ~/thingdaddy/state
cp mint-gate.py harvest-completion-gate.py ~/thingdaddy/.claude/hooks/
```

Merge `settings.hooks.json` into `~/thingdaddy/.claude/settings.json` (create the file
with that content if it doesn't exist; if it does, add the two entries under an existing
`"hooks"` object rather than overwriting). Commit `settings.json` so the whole team
shares the gate.

> **Reliability upgrade for the completion net:** because settings.json SubagentStop can
> be flaky, the more dependable place for the completion check is the harvester's **own
> frontmatter** — add a `Stop` hook there and Claude Code converts it to SubagentStop
> automatically, which fires more reliably than the settings.json route. Keep the
> PreToolUse gate in settings.json regardless; that's the one that has to hold.

---

## 5. Test it (extends the sample-run test)

The bad-prefix test from the harvest build now has teeth. Slip a guessed prefix into the
batch and confirm the verifier marks it REJECTED — then confirm the gate **blocks the
promotion**:

```bash
cd ~/thingdaddy
# stage a batch where one row is a known guess
printf '%s\n' '{"id":"A1"}' '{"id":"A2"}' '{"id":"A3"}' > state/promote-batch.jsonl
printf '%s\n' '{"id":"A1","verdict":"verified"}' \
              '{"id":"A2","verdict":"verified"}' \
              '{"id":"A3","verdict":"rejected","reason":"guessed prefix"}' > state/verdicts.jsonl

# simulate the PreToolUse event for a promote command
echo '{"tool_name":"Bash","tool_input":{"command":"python3 promote.py"}}' \
  | CLAUDE_PROJECT_DIR="$PWD" python3 .claude/hooks/mint-gate.py; echo "exit=$?"
```

Expect `exit=2` and a stderr line naming `A3`. Flip A3 to `verified` and it returns
`exit=0`. If the block fires on the guess and only the guess, the gate is live and you can
let the harvest loop run unattended — a guessed prefix can no longer reach the register,
even if every prompt-level instruction failed.

---

## 6. Two footguns

- **Exit 1 blocks nothing.** Only `exit 2` blocks; `exit 1` is a plain error the model
  shrugs off. The scripts never exit 1 — keep it that way if you edit them.
- **Match the promote markers to reality.** If your real promotion command doesn't
  contain any of the default markers, the gate will wave it through. Set
  `PROMOTE_MARKERS` in `mint-gate.py` to whatever your loop actually runs, and test that
  a real promote command trips the gate before trusting it.
