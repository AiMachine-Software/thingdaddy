# Contributing to thingdaddy-platform

Short and practical. **Read [`CLAUDE.md`](./CLAUDE.md) first — it is the contract and
the single source of truth for how ThingDaddy is built.** This file is the day-to-day
workflow; where the two differ, CLAUDE.md wins.

## 1. Workflow (enforced on `main`)

`main` is protected: **no direct pushes, no force-push, no deletion, and review is
required for everyone — admins included.** So:

1. **Branch off `main`.**
2. Push your branch and **open a Pull Request.**
3. Get **1 approving review.**
4. **Merge.** New commits dismiss stale approvals, so re-request review after you push
   changes to an approved PR.

One concern per PR. Never commit to `main` directly — the server will reject it.

## 2. Branch naming

- `feature/<desc>` — a new capability (e.g. `feature/gate-prefix-authority-guard`)
- `fix/<desc>` — a bug or correctness fix (e.g. `fix/health-db-label`)

Keep `<desc>` short and kebab-case.

## 3. The canon you must not violate

These are enforced by construction (DB constraints, tests), not by diligence. Do not
weaken them. The full text is **[`CLAUDE.md`](./CLAUDE.md) §1 — that is the source of
truth**; this is a pointer, not a replacement.

- **Prefix is root.** Every identity roots in a GS1 company prefix — the prefix IS the
  namespace. No prefix, no namespace, no identity. The DB CHECK
  `party_gate_prefix_required` enforces it (a row cannot be `verified` without a prefix).
  Never bypass it.
- **Verified-or-exception — nothing mints on a guess.** Every identity value is
  GEPIR/GDSN/GUDID-verified or written as an explicit **named exception**. Candidates are
  first-class state: a candidate stays `candidate` until an authority resolves it. Agents
  **propose**; only verified rows **register**. Promotion happens **solely** through the
  gate (`POST /gate`), never around it.
- **Never fabricate** a prefix, GLN, LEI, edge, or status. Unresolvable → candidate or
  named exception.
- **Writing:** say **"legacy IDs,"** never "old IDs." Use exact EPC URN syntax. Call a
  GLN/prefix "verified through GEPIR/GS1" only when it actually is. (CLAUDE.md §9.)

If a change would bend one of these, **stop and raise it in the PR** — the rules win.

## 4. Before you open a PR

- **Run the test suites** and note the results in the PR description (they run against the
  scratch DB `thingdaddy_population_test`, never live):
  ```bash
  PGDATABASE=thingdaddy_population_test node population/api/test/gate_guard.mjs
  PGDATABASE=thingdaddy_population_test node population/api/test/write_auth.mjs
  PGDATABASE=thingdaddy_population_test node population/api/test/claim_promote.mjs
  ```
- **If you touched the API, enumerate every write route** and confirm each is still
  token-gated and fail-closed — don't assume:
  ```bash
  grep -n "app\.\(post\|put\|patch\|delete\)(" population/api/server.js
  ```
  This is exactly how the ungated `/claim` route was caught. Every mutating route must
  require `INGEST_TOKEN` and fail closed (writes disabled, not open, when unconfigured).

## 5. If you're a reviewer

Scrutinize every PR on three questions:

1. **Does it preserve fail-closed behavior?** A failure, a missing/invalid token, an
   unreachable verifier, or unconfirmed authority must land the *safe* outcome
   (reject / hold / 4xx–5xx) — never an open door or a silent promotion.
2. **Does it touch a promotion path** (`/gate`, `/claim`, the DB gate, `verify.py`)? If so,
   demand extra proof — authority is resolved **server-side**, never trusted from the
   caller's payload.
3. **Are there tests proving the row stays `candidate` on rejection?** A guessed,
   unconfirmed, or unauthenticated write must leave state unchanged. The PR should assert
   that, not just the happy path.

Approve only when all three hold. When in doubt, ask for the failing-case test.
