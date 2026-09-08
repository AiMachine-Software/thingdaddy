# Pre-Release Conformance Check — "check us before we release"

Run at the Prove+Land gate of every cycle, before a PR merges. Best-effort — catch what we can;
a caught issue is a candidate/exception to fix or name, never shipped silently. Grows into a lint
script / CI job / watcher over time (P32 scanner, mint-gate hook, IP-lint agent).

## AUTO — mechanical (grep / scan / test; automate first)
- [ ] Tests green (engine, actors, population API suites — SCRATCH DB, not production).
- [ ] Parse-check passes (UI + server).
- [ ] No fabricated identity: no verified row without a real prefix; no DEMO promoted; no hand-built URN outside the engine.
- [ ] P32 — no alpha in any minted URN / graph node.
- [ ] No banned UI words: grep UI for "party", and bare GS1 acronyms (GIAI/GRAI/GSRN/PGLN) used as a primary label.
- [ ] No secrets committed (.env, tokens).

## HUMAN — judgment, the SME check
- [ ] Vocabulary (nudge, not a hard gate): plain human labels; no "party" and no bare GS1 acronym as a primary label (see CUSTOMER_VOCABULARY.md).
- [ ] Laws hold: prefix-is-root . verified-or-exception . one-identity-many-carriers . registrar-does-not-adjudicate . only-the-answerable-ratifies.
- [ ] Correct level: nothing modeled at the wrong tier (carriers on assets not parties; role stamps as edges; drivers/workflows not party rows).
- [ ] Honest empties: no real data -> the UI says so, never faked.
- [ ] Provenance: every state change leaves an event.
- [ ] Build 44: guidance only — never wired, copied, or shipped.

## The rule
Corrections are the product. A failed check is surfaced, not swept. Ship honestly or don't ship.
