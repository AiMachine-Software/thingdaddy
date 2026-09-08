# ThingDaddy — Session Handoff (API + Agents)

Everything built this session, arranged in the repo layout it belongs in. Unzip this at
`~/thingdaddy` and the files are already in the right place. Then run the steps below in
order.

## What's here

```
thingdaddy/
├── docs/
│   ├── ClaudeCode_MacMini_Setup_and_Cost.docx   API key setup + cost guide
│   ├── SETUP-IP-SYSTEM.md                        runbook: bare Mac -> live IP register + weekly lint
│   ├── AGENT-PATTERNS.md                         compound-stack patterns mapped to the fleet + model pairing
│   ├── MINT-GATE-HOOK.md                         how the deterministic mint gate works
│   └── ip/
│       └── IP-LINT-AGENT.md                      the lint agent spec (checks, guardrails, output)
├── scripts/
│   ├── bootstrap-ip-repo.sh                      one-time repo setup (git init, CLAUDE.md rules, first commit)
│   └── run-ip-lint.sh                            the weekly lint runner
├── .claude/
│   ├── settings.json                             registers the two hooks
│   ├── agents/
│   │   ├── td-harvest-orchestrator.md            Sonnet: plans loop, applies mint gate
│   │   ├── td-harvester.md                       Haiku: high-volume extraction, candidate-only
│   │   └── td-prefix-verifier.md                 Haiku: read-only grader (the mint gate rubric)
│   └── hooks/
│       ├── mint-gate.py                          PreToolUse: hard-blocks unverified promotions
│       └── harvest-completion-gate.py            SubagentStop: completion safety net
└── launchd/
    └── com.thingdaddy.iplint.plist              weekly lint scheduler (copy to ~/Library/LaunchAgents/)
```

## Prerequisites (not in this zip — verified-or-exception)

- **Claude Code working** on the Mac mini. Decide subscription vs. API key first — see
  `docs/ClaudeCode_MacMini_Setup_and_Cost.docx`. If you set `ANTHROPIC_API_KEY`, all
  agent runs are metered; keep a spend limit on the key.
- **`IP-LOG.md`** — the register file generated Saturday (the counsel-memo session). It
  is NOT in this zip because it wasn't created this session; drop it into `~/Downloads`
  and the bootstrap moves it into `docs/ip/`. If you don't have it, ask me to regenerate
  it before running step 2.

## Run order

1. **Place the files.**
   ```bash
   cd ~ && unzip thingdaddy_handoff.zip        # creates ~/thingdaddy/...
   cd ~/thingdaddy && chmod +x scripts/*.sh
   ```

2. **Bootstrap the register.**
   ```bash
   ./scripts/bootstrap-ip-repo.sh
   ```
   Creates the structure, moves `IP-LOG.md` in from Downloads, appends the IP governance
   block to `CLAUDE.md` (without clobbering your existing one), points SESSION-HANDOFF.md
   at the register, and makes the first commit.

3. **Wire the remote and push** — this is the step that resolves the team's "not pushed"
   message. Nothing is on the shared repo until you do this once:
   ```bash
   git remote add origin <your-repo-url>       # e.g. git@github.com:org/thingdaddy.git
   git push -u origin main
   ```

4. **Confirm the harvest agents.** They're already in `.claude/agents/`.
   ```bash
   claude
   /agents        # confirm td-harvest-orchestrator, td-harvester, td-prefix-verifier show under Project
   ```

5. **Arm the mint gate.** The hooks are already registered in `.claude/settings.json`.
   Before trusting the gate, open `.claude/hooks/mint-gate.py` and set `PROMOTE_MARKERS`
   to whatever your real promotion command actually contains. Then test it (see
   `docs/MINT-GATE-HOOK.md` §5) — slip a guessed prefix in and confirm the promotion is
   BLOCKED, not written.

6. **Sample harvest run.** Start tiny (200 records, GUDID only) per `docs/AGENT-PATTERNS.md`
   §5. Check the verdict split, confirm the verifier rejects a bad prefix, note the cost.

7. **Optional — weekly lint scheduler.** Edit `launchd/com.thingdaddy.iplint.plist`
   (replace `REPLACE_ME` with your macOS username), then:
   ```bash
   cp launchd/com.thingdaddy.iplint.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.thingdaddy.iplint.plist
   ```
   Note: the scheduled run uses headless `claude -p`, which is metered even on Max, and
   launchd doesn't read `~/.zshrc` — put the key in the plist if you schedule it.

## One honest caveat

I can't push to the Mac or your GitHub from the app — this is still download-and-drop.
Once step 3 is done, the shared repo is live and the team can pull.
