# ThingDaddy IP Lint Agent — Spec & Runbook

**Purpose.** Complete the three-command loop over your IP register. You already have
*ingest* (the continuous IP-scan rule) and *query* (Claude Code answering from
`IP-LOG.md`). This is the missing third leg: a scheduled **lint** pass that walks the
whole register, flags collisions / stale claims / orphans / gaps, and writes its
findings to a dated exceptions block **for your gate** — never editing or renumbering
anything on its own.

**The one law.** The lint agent is *read-mostly*. It reports; it does not decide.
Nothing in `IP-LOG.md` changes, no TD-M number moves, and nothing reaches counsel
without KJ's explicit gate.

> Status note: this assumes the Mac mini repo does not yet exist. Section 0 builds it
> from zero. Sections 1–6 are the agent itself.

---

## 0. Prerequisites & repo bootstrap (do this first)

**Assumes:** Claude Code is running on the Mac mini, and you have `IP-LOG.md` (the file
generated in the counsel-memo session) on disk.

### 0.1 Create the structure

```bash
mkdir -p ~/thingdaddy/docs/ip
cd ~/thingdaddy
git init
# drop the generated file in:
mv ~/Downloads/IP-LOG.md docs/ip/IP-LOG.md
```

Target layout:

```
~/thingdaddy/
├── CLAUDE.md                 # standing instructions (read every session)
├── SESSION-HANDOFF.md        # session pointer / state
└── docs/ip/
    ├── IP-LOG.md             # canonical, append-only register  (the record)
    ├── LINT-EXCEPTIONS.md    # lint findings, dated, append-only (agent writes here)
    └── snapshots/            # generated .docx/.xlsx go here (not the record)
```

### 0.2 Add the governing rules to `CLAUDE.md`

Append this block verbatim:

```markdown
## IP register laws
- `docs/ip/IP-LOG.md` is the canonical, append-only source of truth for all IP.
  The .docx/.xlsx in docs/ip/snapshots/ are generated views, never the record.
- On any new invention: append to IP-LOG.md — one-line claim, novelty vs. the
  existing register, TD-M mapping. Continuous scan; surface candidates proactively.
- New TD-M / IP-C numbers are PROVISIONAL until KJ's gate. Never renumber silently.
- Verified-or-exception: never fabricate to fill a gap. A gap is a named exception.
- "Legacy IDs," never "old IDs," in all output.

## IP lint agent
- Weekly (or on demand), walk IP-LOG.md end to end and run the checks in
  docs/ip/IP-LINT-AGENT.md §2.
- Write findings ONLY to docs/ip/LINT-EXCEPTIONS.md as a dated, append-only block.
- Never edit IP-LOG.md, never renumber, never promote a candidate, never send to
  counsel. Findings are OPEN until KJ resolves them.
```

### 0.3 Point the session pointer at it

In `SESSION-HANDOFF.md`, ensure every session opens by reading the register and the
open exceptions:

```markdown
## Read first
1. docs/ip/IP-LOG.md            (current register state)
2. docs/ip/LINT-EXCEPTIONS.md   (open items awaiting KJ gate)
```

### 0.4 Commit the baseline

```bash
git add -A && git commit -m "Bootstrap IP register + lint governance"
```

From here the register is live: git tracks every append, and the lint agent has a
vault to walk.

---

## 1. What the agent is

- **Identity.** A maintenance Digital FTE in the **TD-C** namespace (company-operations
  fleet). Suggested slot: **TD-C-56 (provisional)** — the next clean number above the
  current roster top (TD-C-10 … TD-C-55), so no gap is opened. GSRN-passported through
  the F0 control plane like the rest of the fleet. Provisional until your gate; do not
  treat as assigned until then.
- **Posture.** Read-mostly. Read scope: all of `docs/ip/`. Write scope: **only**
  `docs/ip/LINT-EXCEPTIONS.md`.
- **Cadence.** Weekly by default; also runnable on demand before any counsel snapshot.

---

## 2. What it checks

Each check maps to a real failure mode already present in the register.

| # | Check | What it catches | Live example |
|---|-------|-----------------|--------------|
| C1 | **Numbering collision** | One TD-M / IP-C number assigned to two distinct invention sets | TD-M-53/54/55 (ERP/SAP federation vs. Agent Service-Relation Identity) |
| C2 | **Ungated provisional** | Provisional numbers that never passed KJ's gate | the 48–57 provisional range |
| C3 | **Sequence gap** | Missing IDs in a run — flagged as a *named exception*, never back-filled | IP-C-11…39 ("may exist," not "absent") |
| C4 | **Stale / superseded claim** | A family marked superseded but still cross-referenced as active; contradictory status flags | — |
| C5 | **Orphan** | A TD-M family with no originating IP-C entry, or an IP-C entry never promoted to TD-M | — |
| C6 | **Cross-ref integrity** | Linked pairs that disagree | IP-C-40 ↔ TD-M-53 linkage consistency |
| C7 | **Keystone integrity** | Keystone families present, correctly flagged, not drifted | TD-M-50, TD-M-57 |
| C8 | **Verified-or-exception audit** | Any blank field that should be a named exception rather than empty | — |

---

## 3. What it must NOT do

- **Never renumber.** Collisions are reported with a *recommended* resolution; the move
  waits for your gate.
- **Never edit `IP-LOG.md`.** It is append-only and only *you* (or an ingest append)
  writes to it. Lint writes elsewhere.
- **Never fabricate.** A gap is logged as a named exception (verified-or-exception),
  never filled with a guess.
- **Never promote or file.** It does not change a candidate's status to filed/drafted.
- **Never route to counsel.** Snapshots for counsel are a separate, human-initiated step.

---

## 4. Output — the exceptions block

The agent appends one dated block per run to `docs/ip/LINT-EXCEPTIONS.md`. Every finding
carries a stable ID, a severity flag matching your snapshot color scheme, and status
`OPEN` until you resolve it.

**Severity flags:** `RED` collision · `AMBER` provisional/ungated · `LILAC` gap ·
`GREY` stale/orphan · `GOLD` keystone-integrity.

**Schema per finding:** `[ID] SEVERITY | check | families | evidence (line refs) |
recommended action | STATUS`

**Example first-run output:**

```markdown
## Lint run 2026-07-12  (agent: TD-C-56, provisional)

[LX-001] RED  · C1 collision
  families: TD-M-53, TD-M-54, TD-M-55
  evidence: IP-LOG.md L412–430 (ERP/SAP federation) vs L611–628 (Agent
            Service-Relation Identity, also carried as IP-C-40)
  recommended: keep 53/54/55 on one set; renumber the other into next free block.
  STATUS: OPEN — awaiting KJ gate

[LX-002] AMBER · C2 ungated provisional
  families: TD-M-48 … TD-M-57
  evidence: no gate marker on IP-LOG.md entries in this range
  recommended: KJ gate pass to confirm or renumber before next counsel snapshot.
  STATUS: OPEN — awaiting KJ gate

[LX-003] LILAC · C3 sequence gap
  range: IP-C-11 … IP-C-39
  evidence: IP-C log jumps 10 → 40
  recommended: confirm whether these exist (transcript recovery) or mark as a
               permanent named exception. Do NOT back-fill.
  STATUS: OPEN — awaiting KJ decision

[LX-004] GREY · C6 cross-ref integrity
  pair: IP-C-40 ↔ TD-M-53
  evidence: IP-C-40 points to TD-M-53, but TD-M-53 is also the ERP/SAP family
  recommended: resolves automatically once LX-001 is gated; re-check after.
  STATUS: OPEN — blocked on LX-001
```

When you resolve an item, you (or an ingest append) update `IP-LOG.md` and flip the
line to `STATUS: RESOLVED 2026-07-xx — <what changed>`. The exceptions file stays
append-only so there's an audit trail of every gate decision.

---

## 5. How to run it

**On demand (recommended to start):** from the repo root,

```bash
claude "Run the IP lint agent per docs/ip/IP-LINT-AGENT.md. Walk docs/ip/IP-LOG.md,
run checks C1–C8, and append a dated findings block to docs/ip/LINT-EXCEPTIONS.md.
Do not edit IP-LOG.md, do not renumber, do not fabricate. Report only."
```

**Weekly, unattended:** a `launchd` job (macOS's cron) running headless:

```bash
cd ~/thingdaddy && claude -p "Run the IP lint agent per docs/ip/IP-LINT-AGENT.md..." \
  && git add docs/ip/LINT-EXCEPTIONS.md \
  && git commit -m "Weekly IP lint $(date +%F)"
```

> **Cost note (ties to the API-key setup):** headless `claude -p` runs bill against API
> tokens, not your subscription. A weekly lint over the whole register is cheap — one
> read-mostly pass — but it *is* metered if `ANTHROPIC_API_KEY` is set. If you're on a
> Max plan and want it free, run it interactively (`claude`, logged in) rather than
> headless, or accept the few cents/week and keep a spend limit on the key.

---

## 6. First run — what to expect

The first lint will surface your existing backlog as OPEN exceptions: the 53/54/55
collision (RED), the ungated 48–57 provisional range (AMBER), and the IP-C-11…39 gap
(LILAC). That's the point — it converts the drift you already know about into a gated
worklist, and from then on catches new drift the moment it appears, while you sleep.

**Highest-priority gate before any counsel snapshot:** LX-001, the 53/54/55 collision.
Nothing downstream is clean until that one is decided.
