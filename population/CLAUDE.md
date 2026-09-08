# population/ — Population Database (area rules)

This folder is the ThingDaddy **Population Database**: the staging + provenance
spine where party candidates are ingested, resolved, and (only when verified)
promoted. It is a self-contained data tier. These rules are not optional.

## Isolation

- **Never touch the platform (`apps/web/src/platform/`).** No imports, no edits, no coupling to the V4 JSX.
  The platform is the read/render tier; `population/` is the data tier. They meet
  only through explicit exports, never by reaching into each other's code.
- Keep everything under `population/`. The database is a local Postgres instance
  named **`thingdaddy_population`** (see `db/apply.sh`).
- Agents in `agents/` may later read/write this DB, but this folder owns the
  schema and the gate.

## The four laws, enforced here

1. **The gate is inviolable.** A row may only reach `state = 'verified'` if it
   carries a `prefix`. This is enforced in SQL, not in application code:
   `CHECK (state <> 'verified' OR prefix IS NOT NULL)`. Never weaken, drop, or
   work around this constraint. `db/test_gate.sql` proves it holds.
2. **Ingest lands candidates only.** Every connector / importer writes rows at
   `state = 'candidate'`. Promotion to `verified` happens only through the
   verification path, and only with a confirmed prefix. Nothing mints on a guess.
3. **No fabricated prefixes.** Never invent, guess, or placeholder a real GS1
   prefix into a row. Unknown prefix ⇒ leave it `NULL` (the row stays a
   candidate). If a party genuinely cannot be resolved, record it as
   `state = 'exception'` with an `exception_reason` — never as a fake verified.
4. **Synthetic data is labelled.** Any row that is generated/simulated rather
   than observed from a real source MUST carry `source = 'synthetic'`. This keeps
   synthetic and real populations separable at query time, forever.

## Layout

```
population/
  CLAUDE.md          — this file
  db/
    schema.sql       — party + edge + party_event; the gate; indexes; tsv trigger
    apply.sh         — idempotent create-db + apply-schema
    test_gate.sql    — proves candidate/verified/exception gate behaviour
```

## Working here

- Schema changes go in `db/schema.sql` and must stay **idempotent** (re-applying
  is a no-op): `CREATE ... IF NOT EXISTS`, `CREATE OR REPLACE`, `DROP ... IF EXISTS`.
- After any schema edit: re-run `./db/apply.sh` then `psql -d thingdaddy_population
  -f db/test_gate.sql` — the gate test must still show (a) PASS (b) PASS (c) PASS.
- Requires Postgres on PATH (Postgres.app or Homebrew `postgresql@16`).
