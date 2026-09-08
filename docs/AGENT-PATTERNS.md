# ThingDaddy Agent Patterns — Compound Stack, Mapped to the Fleet

The one idea worth keeping from the Fable 5 write-up, stripped of the marketing:
**self-improvement is a property of the system around the model, not the model.** The
compounding stack — objective stop-conditions, persistent state, an *independent*
grader, vision-check, rule distillation — is ordinary good engineering that runs on
Sonnet and Haiku at a fraction of top-tier cost. You do not need a $10/$50 orchestrator
to capture most of the value, and for the harvest fleet you almost never do.

This doc maps each layer to our fleet, answers the model-pairing question, and specs the
independent-verifier retrofit — starting with today's build: the harvest agents.

---

## 1. Model pairing is a first-class feature — route by complexity, not by default

In Claude Code, every subagent is a markdown file in `.claude/agents/` (project) or
`~/.claude/agents/` (user) with YAML frontmatter:

```yaml
---
name: agent-name
description: when the lead should delegate to this agent
tools: Read, Grep, Bash        # omit to inherit; restrict to lock an agent down
model: haiku                   # haiku | sonnet | opus  (or a pinned id, e.g. claude-haiku-4-5)
isolation: worktree            # optional: fresh checkout so parallel agents can't collide
---
System prompt goes here.
```

The `model:` line is the whole game for cost. Our tiering for the fleet:

| Role | Model | Why |
|------|-------|-----|
| **Orchestrator** (loop controller, planner, gate-applier) | **Sonnet 4.6** | Coordinates and decides. Opus only for a genuinely hard bounded subtask; Fable/top-tier basically never for harvest. |
| **Harvester workers** (scan / clean / normalize GUDID, NDC, OFF, GLEIF) | **Haiku 4.5** | High-volume, structured extraction. The bulk of the tokens. Cheap by design. |
| **Verifier / grader** (verified-or-exception check, prefix-length resolution) | **Haiku 4.5** | Anthropic's own recommendation for graders. Bump to Sonnet if you want extra safety on the mint gate. |

**The cheaper move underneath the model tiering:** don't run an LLM over 70–80k records
when Python already does the mechanical harvest (the SQLite checkpoint loop, union-find,
API pulls). Reserve LLM calls for *judgment* — disambiguation, candidate-vs-verified
decisions, exception classification. Most of the record volume never needs a token. That
keeps the whole fleet economical regardless of which model each agent runs.

> Billing reminder (from the API-key setup): with `ANTHROPIC_API_KEY` set, all of this
> is metered pay-as-you-go, not covered by a Max subscription. Haiku harvest is cents,
> but keep a spend limit on the key.

---

## 2. The four layers, mapped to what we already have

Read bottom-up — that's the order leverage compounds.

**Layer 1 · Primitives.** Fable 5 / Opus / sub-agents / worktrees. *We're here today* —
raw Claude Code plus our Python loops. Fine as a floor; no compounding yet.

**Layer 2 · Orchestration.** Objective stop-conditions and self-correcting loops
(`/goal`, Outcomes). *Gap.* Our harvest loops stop at "handled enough," not at a graded
"done." Adding a stop-condition checked by an independent grader is the first upgrade.

**Layer 3 · Memory.** State files that resume instead of restart. **We're strong here.**
IP-LOG.md is the record; SESSION-HANDOFF.md is the resume pointer; **verified-or-exception
IS the state-3 "verified facts vs. open guesses" distinction** the write-up says most
models never reach. The 5-stage memory progression (Fail → Investigate → Verify →
Distill → Consult) is our "no faking ever" written as an engineering loop. The culture
is already in place; what's missing is the automation that writes to it every run.

**Layer 4 · Self-improvement.** Independent grader, vision-check, rule distillation.
**We just built our first one** — the register lint agent is exactly a verifier
sub-agent: reads the artifact against a rubric, no skin in the maker's game, reports
rather than self-blesses. Section 3 generalizes that across the loops.

---

## 3. The independent-verifier retrofit (maker ≠ grader)

The single highest-leverage pattern in the write-up, and the one that maps cleanest onto
verified-or-exception: **the agent that produces a record is never the agent that
confirms it.** A maker that grades itself prefers conclusions consistent with what it
already wrote; a separate grader sees only the artifact and the rubric.

Our rubric is already written — it's the mint gate: *a record is VERIFIED only if its
GS1 company prefix length is resolved against an authoritative source (GEPIR / GCP Length
Table / Verified by GS1); otherwise it is CANDIDATE (provisional); a guessed prefix is
REJECTED.* That's a gradable rubric a cheap independent verifier can enforce.

Retrofit, loop by loop:

- **GTIN harvest loop.** Maker (Haiku) scans GUDID/NDC/OFF and emits candidate records.
  Verifier (Haiku, read-only) resolves prefix length and stamps VERIFIED / CANDIDATE /
  REJECTED before anything is written to the populated store. No minting on a guess —
  enforced structurally, not by trusting the harvester.
- **Civilization-build (Loop A/B).** Maker derives candidate prefixes (GLEIF → GUDID →
  Verified by GS1) and relationship edges (EDGAR Exhibit 21, USASpending, SAM.gov).
  Verifier confirms the cross-MO union-find didn't merge two distinct entities and that
  each edge cites its source. Illustrative-until-verified stays illustrative until the
  grader passes it.
- **apply → prospect.** Maker scores the application and drafts the GS1 prospect record.
  Verifier checks the prospect's prefix/identity claim before it enters outreach —
  candidate-flagged until corroborated, human-gated for send.

Enforcement, not just advice: a **SubagentStop hook** can hard-block the lead from
folding a maker's result back in until the verifier returns `VERDICT: pass`. That's the
gate expressed as code.

---

## 4. Two more layers worth adding after the verifier

- **Vision-verify** → the React/TSX platform. A grader screenshots the webview and
  checks it against the GoDaddy teal/black/white design tokens and the previous
  screenshot. Catches brand/UI drift a text-only check misses.
- **Worktrees** → now that there are two engineers plus fan-out agents, `isolation:
  worktree` on the harvesters stops two agents editing the same file. Non-optional the
  moment loops run in parallel.

---

## 5. Today's build — harvest agents on the Mac mini

Goal for the session: API key set, three agents installed, a **sample harvest** run on a
small N, verifier confirmed catching guesses. Three drop-in agent files ship alongside
this doc.

**Install:**

```bash
mkdir -p ~/thingdaddy/.claude/agents
cp td-harvest-orchestrator.md td-harvester.md td-prefix-verifier.md \
   ~/thingdaddy/.claude/agents/
cd ~/thingdaddy
/agents            # inside claude: confirm all three show under Project scope
```

**Sample run (start tiny):**

```bash
claude "Using the td-harvest-orchestrator agent, harvest 200 records from GUDID only.
Delegate extraction to td-harvester and gate every record through td-prefix-verifier.
Write VERIFIED rows to the store; leave CANDIDATE rows provisional; log REJECTED guesses.
Do not mint on an unresolved prefix. Report counts by verdict."
```

**What to check on the sample:**
1. Verdict split looks sane (a real GUDID pull yields mostly CANDIDATE until GEPIR
   resolves length — that's correct, not a bug).
2. The verifier actually rejects a deliberately bad prefix. Slip one in and confirm it
   comes back REJECTED, not VERIFIED. That's the maker≠grader test.
3. Cost. 200 records through Haiku workers + Haiku grader is cents. Note the number so
   you can extrapolate before scaling to the 70–80k held prefixes.

**Then scale**, not before: bump N, add NDC and Open Food Facts sources, turn on
`isolation: worktree` when you parallelize harvesters.

**Mythos boundary — mostly clear for harvest.** Sonnet/Haiku/Opus carry no Mythos
classifier layer, so there's no silent Fable-5 fallback in the harvest fleet. Keep the
classifier consideration for *later* — only if you put Fable 5 in an orchestrator role
over the bio/chem-adjacent work (Diazyme, OpenADMET) or the security-adjacent GA/CMMC
line. Harvest on the cheap tier doesn't hit it.

---

## 6. Caveat, in your own epistemic spirit

The source is a third-party explainer citing Anthropic's docs, not the primary source.
The architecture advice is sound regardless, but the specific figures and dates
(Parameter Golf "~6×," Continual Learning Bench "73% vs 17%," the April/May feature
dates) should be confirmed against Anthropic's actual documentation before any cost or
architecture commitment rests on them. Verified beats right.
