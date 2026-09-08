# ThingDaddy

The GoDaddy of the physical world — GS1 EPC URN identity registry, agent fleet,
and Physical-AI graph. See CLAUDE.md for the engineering laws.

## Quickstart
```bash
# platform
cd platform && npm install && npm run dev

# agents (offline)
python3 agents/thingdaddy_agent_fleet.py --status
python3 agents/thingdaddy_agent_fleet_loopB.py

# agents (live — needs open network)
python3 agents/thingdaddy_agent_fleet_loopB.py --live
SAM_API_KEY=xxxxx python3 agents/thingdaddy_agent_fleet_loopB.py --live
```

## Working with Claude Code
Run `claude` in this directory. It reads CLAUDE.md (and platform/CLAUDE.md,
agents/CLAUDE.md) automatically. Ask it to make changes; it edits in place,
runs parse-check.sh / the agent tests, and commits.
