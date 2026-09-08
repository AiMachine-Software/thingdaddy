#!/usr/bin/env python3
"""
ThingDaddy Population loader — GLEIF (Level 1 LEI records) -> POST /ingest.

Isolation: lives under population/. Talks to the Population DB ONLY through the
REST API's POST /ingest (never a direct DB write). It does not import from or
touch platform/ or the loop_a harness — only the GLEIF record-nesting knowledge
(entity.legalName.name / entity.legalAddress.country) is harvested from
loop_a/gleif.py and reimplemented here in the population tier. Reads are used
solely for the pre-check dedup snapshot (a read-only psql query on lei).

The four laws, honored here:
  - Prefix is root / no fabricated prefixes: GLEIF carries an LEI but NO GS1
    company prefix, so EVERY row lands prefix=None. The LEI rides along as a
    cross-reference seed that the TD-M-51 LEI->prefix bridge resolves LATER; it
    never becomes a prefix and never promotes a row on its own.
  - Ingest lands candidates only: this loader omits `state` entirely, so /ingest
    derives 'candidate'. It NEVER sends 'verified'. GLEIF has no rejection concept
    here, so it also never writes exception_reason (that would invent a status);
    unusable records are skipped-and-counted, not turned into phantom exceptions.
  - Never guess an MO: `mo` is derived from the record's ISO2 country via a local
    map, degrading to None for any country not in the map. Never fabricated.

Access: GLEIF REST API (api.gleif.org/api/v1/lei-records), keyless, JSON:API,
paginated via links.next. Bounded first pull by default (a few hundred records)
to prove the pipeline — NOT the full ~3M index, NOT the Golden Copy dump.

Usage:
  python3 load_gleif.py --limit 20 --dry-run
  python3 load_gleif.py --limit 300
  python3 load_gleif.py --country US --limit 200
  python3 load_gleif.py --name "samsung" --limit 50
  python3 load_gleif.py --limit 1000 --page-size 200      # larger bounded pull
"""
import argparse
import json
import os
import sys
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error

API = os.environ.get("POP_API", "http://localhost:8787")
POP_DB = os.environ.get("POP_DB", "thingdaddy_population")
GLEIF_BASE = "https://api.gleif.org/api/v1/lei-records"
UA = "ThingDaddy Population GLEIF loader (kj@thingdaddy.com)"
TIMEOUT = 60
INGEST_BATCH = 500            # <= API hard cap of 1000
GLEIF_MAX_PAGE = 200          # GLEIF's max page[size]
DEFAULT_LIMIT = 300           # bounded first pull; raise with --limit for more

# GLEIF returns ISO 3166-1 alpha-2 country codes (e.g. "US", "DE", "KR") — NOT
# the full names load_population.py's COUNTRY_TO_MO keys on. So we map by ISO2
# here. This is a HEURISTIC candidate hint (the true MO is set by the prefix's
# numeric band at verification, never by country). Unknown code -> None, never a
# guess.
ISO2_TO_MO = {
    "US": "GS1 US",
    "MX": "GS1 Mexico",
    "DE": "GS1 Germany",
    "CA": "GS1 Canada",
    "FR": "GS1 France",
    "GB": "GS1 UK",
    "CN": "GS1 China",
    "JP": "GS1 Japan",
    "KR": "GS1 Korea",
    "BR": "GS1 Brasil",
    "IN": "GS1 India",
    "IT": "GS1 Italy",
    "ES": "GS1 Spain",
    "NL": "GS1 Netherlands",
}


# --- HTTP helpers ------------------------------------------------------------

def _require_ingest_token():
    """Return INGEST_TOKEN or fail fast. The population API gates /ingest behind a
    shared secret (requireWriteToken); a tokenless POST would just 401/503. We
    refuse to send one — a clear stop beats a confusing HTTP error mid-batch."""
    token = os.environ.get("INGEST_TOKEN")
    if not token:
        raise SystemExit(
            "INGEST_TOKEN is not set — refusing to POST /ingest without the write token.\n"
            "Set it to match the population API's INGEST_TOKEN, e.g.:\n"
            "  export INGEST_TOKEN=... && python3 load_gleif.py ...")
    return token


def _ingest_post(rows, source="GLEIF"):
    token = _require_ingest_token()
    data = json.dumps({"source": source, "rows": rows}).encode()
    req = urllib.request.Request(
        f"{API}/ingest", data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _gleif_get(url, retries=5):
    """GET a GLEIF JSON:API page. Self-throttles via backoff on 429/5xx and
       network errors, honoring Retry-After. Surfaces other 4xx and raises."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "application/vnd.api+json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                wait = min(2 ** attempt, 30)
                ra = e.headers.get("Retry-After")
                if ra and str(ra).isdigit():
                    wait = int(ra)
                print(f"[gleif] {e.code} {e.reason}; backoff {wait}s "
                      f"(attempt {attempt + 1}/{retries})", file=sys.stderr)
                time.sleep(wait)
                continue
            body = e.read().decode("utf-8", "ignore")
            print(f"[gleif] GET {url} -> {e.code} {e.reason}: {body[:300]}", file=sys.stderr)
            raise
        except urllib.error.URLError as e:
            last = e
            wait = min(2 ** attempt, 30)
            print(f"[gleif] network error: {e}; backoff {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
    raise SystemExit(f"[gleif] giving up after {retries} attempts: {last}")


# --- pre-check dedup (safe re-runs) ------------------------------------------
# LEI is a globally-unique key, so it is the natural dedup handle for GLEIF. We
# take a ONE-SHOT read-only snapshot of the LEIs already in the DB (across ALL
# sources, since lei is global) and skip rows already present — plus dedup within
# the run. This is the SAME idempotent pre-check load_population.py uses for
# GDSN(gln)/GUDID(legal_name). All WRITES still go exclusively through POST
# /ingest; this is the only (read-only) direct DB touch.

def _existing_leis():
    sql = "SELECT DISTINCT lei FROM party WHERE lei IS NOT NULL"
    out = subprocess.run(["psql", "-d", POP_DB, "-tAc", sql],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"dedup snapshot failed: {out.stderr.strip()}")
    return set(line for line in out.stdout.splitlines() if line)


# --- GLEIF fetch + map -------------------------------------------------------

def _first_url(page_size, country=None, name=None):
    params = [("page[size]", str(min(page_size, GLEIF_MAX_PAGE))), ("page[number]", "1")]
    if country:
        params.append(("filter[entity.legalAddress.country]", country))
    if name:
        params.append(("filter[entity.legalName]", name))
    return f"{GLEIF_BASE}?{urllib.parse.urlencode(params)}"


def _map_record(rec):
    """Map one JSON:API lei-record to the candidate shape, or None to skip."""
    attrs = rec.get("attributes", {}) or {}
    lei = attrs.get("lei") or rec.get("id")
    entity = attrs.get("entity", {}) or {}
    ln = entity.get("legalName")
    name = ln.get("name") if isinstance(ln, dict) else ln
    addr = entity.get("legalAddress", {}) or {}
    country = addr.get("country") or None

    name = (name or "").strip() or None
    if not name or not lei:
        return None                        # skip: no identity, or no dedup/seed key

    return {
        "legal_name": name,
        "country": country,                # ISO2 or None
        "lei": lei,                        # cross-reference seed (TD-M-51 later)
        "prefix": None,                    # law: GLEIF carries no GS1 prefix, ever
        "mo": ISO2_TO_MO.get(country) if country else None,   # None when unknown
        "source": "GLEIF",
        # NOTE: no `state`, no `exception_reason` — /ingest derives 'candidate'.
    }


def fetch(limit, page_size, max_pages, country, name):
    """Page GLEIF (following links.next), map records, skip unusable ones.
       Returns (rows, stats)."""
    url = _first_url(page_size, country, name)
    rows, skipped_bad, pages = [], 0, 0
    while url:
        payload = _gleif_get(url)
        data = payload.get("data", []) or []
        for rec in data:
            cand = _map_record(rec)
            if cand is None:
                skipped_bad += 1
                continue
            rows.append(cand)
            if limit and len(rows) >= limit:
                return rows[:limit], {"pages": pages + 1, "skipped_bad": skipped_bad}
        pages += 1
        if max_pages and pages >= max_pages:
            break
        url = (payload.get("links") or {}).get("next")
        if url:
            time.sleep(0.25)               # be polite between pages
    return rows, {"pages": pages, "skipped_bad": skipped_bad}


# --- ingest ------------------------------------------------------------------

def ingest(rows, dry_run=False, dedup=True):
    if dedup:
        seen = _existing_leis()
        kept, skipped = [], 0
        for r in rows:
            k = r["lei"]
            if k and k in seen:            # already present (or seen this run)
                skipped += 1
                continue
            kept.append(r)
            if k:
                seen.add(k)                # in-run dedup too
        if skipped:
            print(f"[GLEIF] pre-check dedup: skipped {skipped} already-present, "
                  f"{len(kept)} new")
        rows = kept

    if dry_run:
        print(f"[GLEIF] DRY RUN — {len(rows)} rows would POST /ingest. Sample:")
        for r in rows[:5]:
            print("   ", json.dumps(r, ensure_ascii=False))
        return {"dry_run": True, "would_ingest": len(rows)}

    totals = {"ingested": 0, "inserted": 0, "updated": 0}
    for i in range(0, len(rows), INGEST_BATCH):
        chunk = rows[i:i + INGEST_BATCH]
        status, body = _ingest_post(chunk, "GLEIF")
        if status != 201:
            print(f"[GLEIF] batch {i}: HTTP {status}: {json.dumps(body)[:400]}",
                  file=sys.stderr)
            raise SystemExit(1)
        totals["ingested"] += body.get("ingested", 0)
        for k, v in body.get("summary", {}).items():
            totals[k] = totals.get(k, 0) + v
        print(f"[GLEIF] batch {i // INGEST_BATCH}: {body.get('ingested')} rows "
              f"-> {body.get('summary')}")
    return totals


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="ThingDaddy GLEIF loader (Level 1 -> /ingest candidates)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"cap candidates kept/posted (default {DEFAULT_LIMIT}; "
                         f"bounded first pull — raise explicitly for more)")
    ap.add_argument("--page-size", type=int, default=GLEIF_MAX_PAGE,
                    help=f"GLEIF page[size] (max {GLEIF_MAX_PAGE})")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="hard cap on pages fetched (otherwise bounded by --limit)")
    ap.add_argument("--country", default=None, help="filter by ISO2 country code (e.g. US)")
    ap.add_argument("--name", default=None, help="filter by legal name substring")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-dedup", action="store_true",
                    help="skip the pre-check dedup (faster; may duplicate on re-run)")
    args = ap.parse_args()

    rows, stats = fetch(args.limit, args.page_size, args.max_pages, args.country, args.name)
    print(f"[GLEIF] fetched {len(rows)} candidates across {stats['pages']} page(s); "
          f"skipped {stats['skipped_bad']} unusable (no name/lei)")
    print("[GLEIF] result:", json.dumps(ingest(rows, args.dry_run, not args.no_dedup)))


if __name__ == "__main__":
    main()
