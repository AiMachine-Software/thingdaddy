# ThingDaddy — Population (data / content tier)

The **Population Database** is ThingDaddy's staging + provenance spine: where party candidates are
ingested, resolved, and — only when a real prefix is confirmed — promoted to verified. This tier is
the **content engine**. The platform (`apps/web/src/platform/`) is the read/render tier; the two meet only through the
API, never by reaching into each other's code.

> One line: **ingest → resolve → ThingSite → register → verify**, at scale, candidate-until-ratified.

## Quick start
```bash
# Postgres must be running (Postgres.app or `brew services start postgresql@16`)
./db/apply.sh                      # create db `thingdaddy_population` + apply schema (idempotent)
psql -d thingdaddy_population -f db/test_gate.sql   # gate must show PASS / PASS / PASS
bash dev_up.sh                     # API on :8787, 5-pillar UI on :5173  ->  open http://localhost:5173
```

## Architecture — the loop (5 stages)
| Stage | What it does | Code |
|---|---|---|
| **1 Ingest** | land candidates only, `prefix=NULL`, `source` tagged | `loaders/load_population.py` (GDSN+GUDID), `loaders/load_gleif.py`, `data/incoming/gudid_crawler.py`, `websearch/websearch_gtin.py` → `POST /ingest` |
| **2 Resolve / root** | tie a party to a WHO (registry + GLEIF; GEPIR is manual) | `identity/identity_xref.py` |
| **3 Build ThingSite** | project a site from the spine + pillars | `website_agent.py` (harvest→page-read→doc-mine→root→render), `project_thingsite.py` (DB-projected, any party), `render_p4_cloud_edge.py` (Cloud & Edge / P4), `standards/render_p5_graph.py` |
| **4 Register / gate** | promote candidate→verified **only with a prefix** | `api/server.js`: `/ingest`, `/gate/:id`, `/claim/:id`, `/verified` |
| **5 Verify (R4)** | answerable party ratifies | go-to-market motion, not code — the gate enforces it |

## Read the code in this order (fastest way in)
1. `db/schema.sql` — the three tables (`party`, `edge`, `party_event`) and **the gate**.
2. `loaders/load_population.py` — how ingest lands candidates (`prefix=NULL`, never derived from a GLN).
3. `website_agent.py` — how the ThingSite stages chain into one engine.
4. `identity/identity_xref.py` — how a party is rooted to a WHO.
5. `api/server.js` + `api/test/*.mjs` — the registration surface **and** the acceptance tests.
6. `render_p4_cloud_edge.py` — the P4 Cloud & Edge layer (URN → {aws:arn, azure:deviceId, edge}).

## The laws (non-negotiable — see `CLAUDE.md`)
1. **The gate is inviolable.** `CHECK (state <> 'verified' OR prefix IS NOT NULL)` — enforced in SQL, never app code.
2. **Ingest lands candidates only.** Promotion happens only through the verification path, only with a confirmed prefix.
3. **No fabricated prefixes.** Unknown ⇒ `NULL` (candidate) or `exception` — never a guess, placeholder, or empty string.
4. **Synthetic is labelled** `source='synthetic'`. Kept separable from real forever.
5. **Numeric IDs; meaning in a bound label, never inside the ID.**
6. **Never couple into the platform (`apps/web/src/platform/`).** The tiers meet only through the API.

## Testing (how we verify — the contract)
```bash
psql -d thingdaddy_population -f db/test_gate.sql   # the gate
cd api && for t in test/*.mjs; do node "$t"; done   # ingest/gate/claim/node/epcis acceptance tests
```
Acceptance tests are the spec: build to green, we verify to green.

## Directory map
```
db/           schema + the gate + migrations + test_gate.sql + scale test
loaders/      GDSN/GUDID/GLEIF ingest -> POST /ingest
websearch/    open-web GTIN discovery (source=WEB)
identity/     rooting (identity_xref)
pagereader/ · docmine/ · sitemap/   the ThingSite depth stages
standards/    P5 graph, binding sets, verified_prefixes.json (the ONLY verified registry)
(apps/api)     Node registration API (the seam) + acceptance tests — moved to apps/api
(apps/web)     5-pillar React UI — moved to apps/web/src/registry (route /registry)
website_agent.py · project_thingsite.py · render_p4_cloud_edge.py   the content engine
```

## The seam to the platform
Content flows in via **`POST /ingest`** (always candidate) and is promoted via **`POST /gate/:id`**
(rejected without a prefix). Build the structure against those two contracts; the discipline travels
with the content.
