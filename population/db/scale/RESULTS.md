# Step 4 — Population DB scale test (4M rows)

Proves the population database holds **4,000,007 rows** with **sub-second name
search** and that the **verified-requires-prefix gate still holds at scale**.

Run on the Mac mini, Postgres 16, against `thingdaddy_population`.

## Reproduce

```bash
# 1. seed the 7 real verified records (verified + prefix + provenance event)
psql -d thingdaddy_population -f population/db/scale/seed_verified.sql

# 2. bulk-load ~4,000,000 synthetic candidates (source='synthetic', prefix=NULL)
#    drops GIN indexes, loads in 8x500k batches, rebuilds indexes, ANALYZE
psql -d thingdaddy_population -f population/db/scale/load_4m.sql

# 3. timed name searches (EXPLAIN ANALYZE against the full 4M)
psql -d thingdaddy_population -f population/db/scale/search_timing.sql

# 4. gate-still-holds (raw SQL path; rolled back, no test row persists)
psql -d thingdaddy_population -f population/db/scale/gate_at_scale.sql

# purge the synthetic rows whenever you want the DB lean again:
psql -d thingdaddy_population -c "DELETE FROM party WHERE source='synthetic';"
```

## Results

**Load** (4M synthetic): insert 48.2s, GIN index rebuild 15.4s + 14.0s,
ANALYZE 0.2s. `party` + indexes on disk: **1,576 MB**.

**Population**
| metric | value |
|---|---|
| total rows | 4,000,007 |
| by state | candidate 4,000,000 · verified 7 |
| by source | synthetic 4,000,000 · seed 7 |
| synthetic rows carrying a prefix | 0 |
| synthetic rows verified | 0 |

**Name search over the full 4M** — live `/search` endpoint, HTTP round-trip
(`curl -w %{time_total}`):

| query | rows | time |
|---|---|---|
| `q=Photonics` (333k candidates) | 20 | 9.6 ms |
| `q=Cyberdyne` (250k candidates) | 20 | 2.5 ms |
| `q=Samsung` (verified) | 1 | 1.9 ms |
| `q=Honeywell` (verified) | 1 | 1.4 ms |
| `q=Robotics GmbH` | 20 | 4.9 ms |
| `q=Cyberdyne&mo=GS1 US` (filtered, has matches) | 3 | 5.6 ms |
| `/verified` feed | 7 | 1.6 ms |
| `/stats` (3× GROUP BY over 4M) | — | 185 ms |

SQL `EXPLAIN ANALYZE` execution times: 0.02–0.09 ms (trigram GIN index for
selective terms; PK-ordered walk for common terms). `/search` uses
trigram-accelerated `ILIKE` substring matching (index `ix_party_legal_name_trgm`).

**Known narrow edge:** a *high-frequency* search term intersected with a filter
that excludes *all* its matches (e.g. `q=Cyberdyne&mo=GS1 Korea`, an empty set in
the synthetic modulo scheme) degrades to ~1.18s, because `ORDER BY id LIMIT 20`
makes the planner walk the primary key and it scans deep before finding nothing.
A genuinely-unknown term (`Zzzznomatch`) is 1.2 ms (trigram bitmap returns empty
instantly), and any filtered query with matches is single-digit ms. This is a
planner cross-column-selectivity limitation, not a general search problem.

**Gate holds at 4M — both paths reject:**
- raw SQL `INSERT … verified, prefix=NULL` → `party_gate_prefix_required`
  violation (rolled back).
- live API `POST /gate/:id` on a synthetic candidate (prefix NULL) → **HTTP 422**,
  row provably unchanged (still candidate, still NULL prefix). Verified count
  stayed at 7.
