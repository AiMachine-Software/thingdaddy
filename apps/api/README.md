# Population API (Step 3)

A small, isolated REST service over the **`thingdaddy_population`** Postgres
database (party / edge / party_event, created by `population/db/apply.sh`).

**Stack:** Node + Express + `pg`. Chosen because Node 24 is already on the Mac,
`pg` surfaces Postgres error codes directly (so `POST /gate` can defer to the DB
gate instead of re-checking in JS), and it keeps this tier decoupled from the
Python agent fleet and the React platform.

**Isolation (non-negotiable):** this service imports nothing from `platform/`
and nothing from `agents/`. Its only contract is the database. The platform's
only cross-boundary read is `GET /verified`.

**The gate lives in SQL, not here.** `POST /ingest` can only ever write
`candidate` or `exception`. `POST /gate` is the sole promotion path, and a
prefix-less verified is rejected by the DB constraint
`party_gate_prefix_required`, not by application code.

---

## Prerequisites

- Node ≥ 18 (this machine has v24).
- The population DB already applied:
  ```bash
  cd population/db && ./apply.sh      # idempotent; creates + migrates thingdaddy_population
  ```

## Install & run

```bash
cd apps/api
npm install                 # installs express, pg, dotenv into ./node_modules
cp .env.example .env        # then edit .env if your Postgres needs user/password
npm start                   # → http://localhost:8787   (npm run dev for auto-reload)
```

On a default Homebrew / Postgres.app install, the empty `PGUSER`/`PGPASSWORD` in
`.env.example` work as-is (your macOS username, no password). Set them only if
your instance requires it.

Quick liveness check once it's up:

```bash
curl -s localhost:8787/health
# {"ok":true,"service":"population-api","db":"thingdaddy_population"}
```

---

## Endpoints & curl tests

Base URL below is `http://localhost:8787`. Pretty-print by piping to
`python3 -m json.tool` if you like.

### 1. `POST /ingest` — batch upsert (always candidate | exception)

Lands rows as `candidate`; a row with `exception_reason` lands as `exception`.
Never verified, even if the payload claims so. Run this first to get data to
query.

```bash
curl -s -X POST localhost:8787/ingest \
  -H 'content-type: application/json' \
  -d '{
    "source": "manual",
    "rows": [
      { "legal_name": "Telular Corporation", "gln": "0702054000004", "mo": "GS1 US", "city": "Chicago", "country": "US" },
      { "legal_name": "Western Research 3000, Inc.", "mo": "GS1 US" },
      { "legal_name": "Ghost Party (unresolvable)", "exception_reason": "no GS1 record found in GEPIR" },
      { "legal_name": "Sneaky Verified Co", "state": "verified", "prefix": "0000001" }
    ]
  }'
```

Note the last row: it asks to be `verified`, but ingest forces it to
`candidate` (its `prefix` is retained, but promotion still has to go through
`/gate`). Response reports `inserted`/`updated` per row.

### 2. `GET /search` — paginated, max 20, keyset cursor, trigram name search

Filters: `q` (fuzzy name via pg_trgm), `state`, `mo`, `source`, `limit`
(≤ 20), `cursor` (the `next_cursor` from the previous page).

```bash
# fuzzy name search
curl -s 'localhost:8787/search?q=telular'

# filter by state + member org, small page
curl -s 'localhost:8787/search?state=candidate&mo=GS1%20US&limit=2'

# next page: pass the next_cursor from the previous response
curl -s 'localhost:8787/search?limit=2&cursor=2'
```

Response shape: `{ rows, count, has_more, next_cursor }`.

### 3. `GET /record/:id` — record + edges + event history

```bash
curl -s localhost:8787/record/1
```

Returns `{ party, edges, events }`. 404 if the id is unknown.

### 4. `GET /record/prefix/:prefix` — same, resolved by prefix

```bash
curl -s localhost:8787/record/prefix/0702054000004   # (whatever prefix you ingested)
```

### 5. `POST /gate/:id` — promote candidate → verified (prefix required)

Happy path (supply a prefix — use the id of a candidate from `/search`):

```bash
curl -s -X POST localhost:8787/gate/1 \
  -H 'content-type: application/json' \
  -d '{ "prefix": "0702054", "actor": "manual" }'
```

Gate-rejection path (no prefix on a prefix-less candidate → the DB constraint
fires and you get a clean **422**, not a 500):

```bash
curl -s -X POST localhost:8787/gate/2 \
  -H 'content-type: application/json' \
  -d '{}'
# {"error":"gate rejected: a verified party must root in a GS1 prefix",
#  "constraint":"party_gate_prefix_required","hint":"supply a non-empty \"prefix\" ..."}
```

(Use an id whose row has no prefix — e.g. "Western Research 3000" from the
ingest sample — to see the rejection. A candidate that already carries a prefix
would promote on `{}` because `COALESCE` keeps its existing prefix.)

### 6. `GET /verified` — verified-only feed (the platform's sole read)

```bash
curl -s 'localhost:8787/verified?limit=20'
```

Same keyset pagination as `/search`; optional `mo` / `source` filters. Only
`state = 'verified'` rows ever appear here.

### 7. `GET /stats` — counts by state / mo / source

```bash
curl -s localhost:8787/stats
# { "total": N, "by_state": {...}, "by_mo": {...}, "by_source": {...} }
```

---

## Notes

- **Pagination** is keyset on `id ASC` (stable, no `OFFSET` drift). A page never
  exceeds 20 rows; `limit` is clamped server-side.
- **Every write appends a `party_event`** in the same transaction (the
  provenance spine) — ingest writes `candidate_staged` / `exception` / `updated`,
  gate writes `verified`.
- **Re-ingesting a verified prefix does not downgrade it** back to candidate; the
  upsert preserves a `verified` state.
- `search_tsv` is internal and never returned by the API.
