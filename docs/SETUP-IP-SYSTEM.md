# ThingDaddy IP System — Complete Setup Runbook

From a bare Mac mini to a live, git-tracked IP register with a weekly lint agent.
Do the steps in order. Everything here respects your rules: the record is append-only,
TD numbers are provisional until your gate, gaps are named exceptions (never
back-filled), and nothing renumbers silently.

**Package (five files):**

| File | Role | Lives at (on the Mac) |
|------|------|-----------------------|
| `SETUP-IP-SYSTEM.md` | this runbook | `docs/ip/` (reference) |
| `IP-LINT-AGENT.md` | the agent spec (checks, guardrails, output schema) | `docs/ip/` |
| `bootstrap-ip-repo.sh` | one-time repo setup | `scripts/` |
| `run-ip-lint.sh` | the lint runner (manual or scheduled) | `scripts/` |
| `com.thingdaddy.iplint.plist` | weekly scheduler | `~/Library/LaunchAgents/` |

---

## Prerequisites

1. **Claude Code is working on the Mac mini.** (From the API-key setup: either logged
   in on your subscription via `/login`, or `ANTHROPIC_API_KEY` set — see the cost note
   in Step 4 before you decide which.)
2. **`IP-LOG.md` is on disk.** This is the register file generated in the counsel-memo
   session. Have it in `~/Downloads`. If you don't have it, ask Claude to regenerate it
   before starting — the bootstrap will refuse to create a placeholder (verified-or-
   exception).

---

## Step 1 — Place the files

```bash
mkdir -p ~/thingdaddy/scripts ~/thingdaddy/docs/ip
# from wherever you downloaded the package:
cp IP-LINT-AGENT.md SETUP-IP-SYSTEM.md ~/thingdaddy/docs/ip/
cp bootstrap-ip-repo.sh run-ip-lint.sh   ~/thingdaddy/scripts/
chmod +x ~/thingdaddy/scripts/*.sh
```

## Step 2 — Bootstrap the register

```bash
~/thingdaddy/scripts/bootstrap-ip-repo.sh
```

This creates the directory structure, moves `IP-LOG.md` into `docs/ip/` as the canonical
record, appends the IP governance block to `CLAUDE.md` (without clobbering anything
already there), points `SESSION-HANDOFF.md` at the register, and makes the first git
commit. It is safe to re-run.

**Verify:**

```bash
cd ~/thingdaddy
ls docs/ip/                       # IP-LOG.md, LINT-EXCEPTIONS.md, IP-LINT-AGENT.md, snapshots/
grep -A2 "IP register laws" CLAUDE.md
git log --oneline -1              # "Bootstrap IP register + lint governance"
```

## Step 3 — First lint run (interactive)

Run it by hand the first time so you can watch it work and confirm it only touches the
exceptions file:

```bash
cd ~/thingdaddy
claude "Run the IP lint agent per docs/ip/IP-LINT-AGENT.md. Walk docs/ip/IP-LOG.md, run
checks C1-C8, append a dated findings block to docs/ip/LINT-EXCEPTIONS.md. Do not edit
IP-LOG.md, do not renumber, do not fabricate. Report only."
```

**Expect** three known items to surface as OPEN exceptions: the TD-M-53/54/55 collision
(RED), the ungated 48–57 provisional range (AMBER), and the IP-C-11…39 gap (LILAC).
Confirm `IP-LOG.md` is unchanged:

```bash
git status                        # only LINT-EXCEPTIONS.md should be modified
```

## Step 4 — Gate the backlog (your call, not the agent's)

Work `docs/ip/LINT-EXCEPTIONS.md` top-down. **LX-001 (the 53/54/55 collision) is the
priority — nothing goes to counsel until it's decided.** When you resolve an item, you
(or an ingest append) update `IP-LOG.md`, then flip the exception line to
`STATUS: RESOLVED <date> — <what changed>`. The exceptions log stays append-only so
every gate decision is on the record.

> **Numbering discipline:** the lint agent only ever *recommends* a renumber. The move
> happens when you gate it. The agent's own slot, **TD-C-56**, is likewise provisional
> until you confirm it.

## Step 5 — Schedule the weekly run (optional)

```bash
# edit the plist first: replace REPLACE_ME with your macOS username
cp com.thingdaddy.iplint.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.thingdaddy.iplint.plist
# to remove later:  launchctl unload ~/Library/LaunchAgents/com.thingdaddy.iplint.plist
```

Default schedule: Mondays 06:00. Output goes to `docs/ip/lint.log`.

> **Cost + a real gotcha.** The scheduled runner uses headless `claude -p`, which bills
> **API tokens** if `ANTHROPIC_API_KEY` is set — a weekly read-mostly pass is only cents,
> but it is metered, not covered by a Max subscription. Also, **launchd does not read
> `~/.zshrc`**, so a key set there is invisible to the scheduled job; put the key in the
> plist's `EnvironmentVariables` if you want the unattended run to work. If you'd rather
> keep it free, skip Step 5 and just run Step 3's interactive command once a week while
> logged in. Keep a spend limit on the key regardless.

---

## The loop, once it's running

- **Ingest** — Claude appends new candidates to `IP-LOG.md` per the CLAUDE.md rule, as
  you invent.
- **Query** — ask anything; Claude answers from the register in your own numbering.
- **Lint** — weekly (or on demand), the agent walks the register and hands you a gated
  worklist of collisions, ungated provisionals, stale claims, orphans, and gaps —
  without changing a thing until you say so.

That's the three-command system, on plain markdown, git-tracked, no vector DB — with a
patent-grade gate bolted on where a free-form wiki would just auto-edit.
