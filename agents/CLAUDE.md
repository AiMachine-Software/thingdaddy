# ThingDaddy Agents — area CLAUDE.md (agents/)

Rules specific to the Python agent fleet. Read the root `CLAUDE.md` first for the
four laws, the registration spine, and the verified prefixes.

---

## Files

- `thingdaddy_agent_fleet.py` — base fleet. Orchestrator (TD-A-00) drives
  population (F1) → verify (F2) → register (F3). `--status` prints the 33-agent
  roster; a CSV arg runs against real rows; default runs the built-in seed.
- `thingdaddy_agent_fleet_loopB.py` — F4 relationship/graph (Loop B) + F5/F6
  driver/binding. Imports the base fleet's primitives. Flags: `--live`,
  `--edges-only`, `--drivers-only`. Exports `loopB_seed_associations.json` in the
  platform's Semantic-Graph shape.
- `td_live_connectors.py` — real SEC EDGAR / USASpending / SAM.gov connectors.
- `entity_resolution_agent.py` — generic namesake resolver. Configure an
  `EntityProfile` (or load JSON); Samsung is the built-in worked example.

## The invariants (enforced in code, never relaxed)

1. **Every agent carries a GSRN passport** (`agent_gsrn`, issued by TD-A-01).
2. **Verified-or-exception.** A candidate is VERIFIED against an authority or
   held as an EXCEPTION. Nothing mints on a guess.
3. **The gate.** `register_agent()` is the Python analogue of the platform's
   `addParty()`. It returns `None` unless the candidate is VERIFIED with a
   confirmed prefix. Population/relationship/demo agents PROPOSE; they never mint
   around the gate.
4. **Edges too.** In Loop B, an edge is VERIFIED only if BOTH endpoints are
   registered parties AND it has a documentary source. No source → exception.
   Inferred edges are always candidate and flagged `inferred=True`.
5. **No-Assumption Guard (TD-A-24)** blocks any bind whose owner prefix isn't a
   registered party — never assume a parent-brand prefix.

## Live connectors — access reality

- **SEC EDGAR** — free, keyless. Requires a descriptive `User-Agent` header (SEC
  policy) — it's set in `UA`. Pulls the latest 10-K's EX-21 for subsidiaries.
- **USASpending** — free, keyless. POST JSON to `/api/v2/search/spending_by_award/`.
- **SAM.gov** — free but NEEDS an API key (register at sam.gov). Set `SAM_API_KEY`
  in `.env`. Without it, the SAM connector SKIPS rather than fabricates.
- On any live failure, Loop B falls back to the offline seed and marks the run
  `seed`. The first real run may need a small tweak to the EX-21 regex or the
  USASpending field names if a response shape has drifted — inspect the raw
  response and tighten the parser; do not paper over it with fake data.

## Running

```bash
python3 thingdaddy_agent_fleet.py --status          # 33-agent roster
python3 thingdaddy_agent_fleet.py                   # base loop (seed)
python3 thingdaddy_agent_fleet_loopB.py             # Loop B + driver/binding (seed)
python3 thingdaddy_agent_fleet_loopB.py --live      # live EDGAR + USASpending
SAM_API_KEY=xxx python3 thingdaddy_agent_fleet_loopB.py --live   # + SAM
```

## When you change an agent

- Keep the full 33-agent `FLEET` roster in sync with the platform's
  `agent_registry` module (ids, families, statuses).
- After edits, run `--status` and a full loop; confirm the gate still holds back
  unverified rows (e.g. Samsung seed → 1 registered, 7 held).
- Ledgers (`agent_fleet_*_ledger.json`) are git-ignored; commit code, not runs.
