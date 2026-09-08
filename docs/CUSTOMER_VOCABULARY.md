# ThingDaddy — Customer Labels (working notes)

NOT a taxonomy, NOT a locked system, NOT a release gate. Just the specific customer-facing
labels we've decided so far. The GS1 key stays underneath (shown where useful, and to agents).
More labels get decided as they come up. GS1 builds standards; we build the solution, so the
UI speaks plainly.

## Decided so far
| GS1 key (underneath) | UI label |
|---|---|
| GLN  | Location  (Global Location Number) |
| PGLN | Organization  (Enterprise for a multi-site / multi-country org) |
| GSRN | Person or Agent  (organic or digital) |

## Standing rule
- Don't show "party" on the UI — not a customer word.
- Don't lead with a bare GS1 acronym as a label; show the key where it's useful / to agents.
- Use a plain human word. Decide labels per key as they come up — don't coin a new word when a real one exists.

Note on GSRN: organic vs digital is a flag, not a type — the system is intelligence-agnostic; the
flag gates ratification only. See candidate_ip_intelligence_agnostic_actor.md.
