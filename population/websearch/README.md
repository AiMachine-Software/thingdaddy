# population/websearch — the open-web GTIN engine (built 2026-07-19)

The first real implementation of the web-scan GTIN engine. It was described in
`population_websearch_gtin_engine.md` but never coded (verified by a full Mac search
2026-07-19). This is the code.

## What it does
Discovers real GTINs on the open web, validates them, and lands them as **candidates**
in the one node spine with **source=WEB** — the same door as the 4.5M GUDID export,
just a different source. It complements GUDID/GDSN (authority data we already have); it
targets the GTINs those authorities *don't* cover.

## The laws it honors
- **Never fabricates.** Every GTIN must appear on a real fetched page/payload AND pass the
  GS1 mod-10 check digit. Junk is dropped. (Proven: a wrong-check UPC is rejected.)
- **Never derives a prefix.** `prefix` is always NULL (GS1 US is variable-length). Only the
  **MO** is set — a lawful, deterministic fact from the GS1 prefix band (same table as
  `datastore/mo_resolver.py`).
- **Candidate only, source=WEB.** Promotion to verified happens elsewhere (R4).
- **Provenance always.** Every GTIN carries the exact source URL.

## Files
- `websearch_gtin.py` — discovery → `spine_gtin_web.csv` (+ `.provenance.csv`). No DB access.
- `load_web_spine.sql` — loads that CSV into `<db>.node` (dedup on urn).
- `run_web_scan.sh` — the guarded loader (scratch-first; refuses prod without `ALLOW_PROD=1`;
  requires the `node` table = the spine cutover gate).

## Run it (scratch-first, like GDSN)
```bash
cd ~/thingdaddy/population/websearch

# 1) discover (no DB touched) — pick an adapter:
python3 websearch_gtin.py --source openfoodfacts --query "cold brew coffee" --limit 200 --outdir .
#   or point it at pages you choose:
python3 websearch_gtin.py --source urls --urls targets.txt --limit 300 --outdir .

# 2) eyeball the output
head -5 spine_gtin_web.csv
head -5 spine_gtin_web.provenance.csv

# 3) load onto scratch (guarded; asks y/N)
POP_DB=thingdaddy_population_test ./run_web_scan.sh
```

Adapters: `openfoodfacts` (free, no key — proves the pipeline today), `urls` (any pages you
feed it), `search` (optional, needs `SERPAPI_KEY` for true open-web search). Resumable via
`websearch_cursor.json`; `--reset` to start fresh.

## Storage (decided 2026-07-19)
Web hits get their OWN raw store (these CSVs), never the GUDID mirror. They ingest into the
ONE spine, stamped `source=WEB, state=candidate`, segregated by source+state — they can't
pollute the verified set (R4). See `decision_websearch_gtin_storage.md`.
