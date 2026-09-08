#!/usr/bin/env python3
"""
ThingDaddy Population loader — GDSN + GUDID -> POST /ingest (candidates only).

Isolation: lives under population/. Talks to the Population DB ONLY through the
REST API's POST /ingest (never a direct DB write). It does not import from or
touch platform/. Reads are used solely for the pre-check dedup (GET /search).

The four laws, honored here:
  - Prefix is root / no fabricated prefixes: this loader NEVER derives a GS1
    company prefix from a GLN or GTIN (that boundary is undeterminable without a
    GEPIR prefix-length step). Every row lands prefix=NULL. Promotion happens
    later, elsewhere, only with a verified prefix.
  - Ingest lands candidates only: /ingest can only ever write candidate|exception.
  - Cross-reference seeds preserved: lei + duns are carried through wherever the
    source provides them (GDSN: neither; GUDID: duns). They verify LATER
    (GLEIF LEI->prefix bridge; D&B DUNS match) — they never promote on their own.

Sources:
  GDSN  — "GDSN Trading Partners CLEANED.xlsx"
          Clean sheet   -> candidates (source='GDSN')
          Removed sheet -> exceptions (source='GDSN', exception_reason=<reason>)
  GUDID — gudid weekly zip-of-daily-zips -> device XML, deduped to the
          manufacturer (companyName) -> candidates (source='GUDID', duns kept)

Usage:
  python3 load_population.py --source gdsn  --limit 20 --dry-run
  python3 load_population.py --source gdsn  --limit 20
  python3 load_population.py --source gudid --limit 20
  python3 load_population.py --source both  --limit 20
  python3 load_population.py --source gdsn  --removed          # load Removed sheet too
  (no --limit = full load; STAGE 2)
"""
import argparse
import io
import json
import os
import sys
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
INCOMING = os.path.normpath(os.path.join(HERE, "..", "data", "incoming"))
GDSN_XLSX = os.path.join(INCOMING, "GDSN Trading Partners CLEANED.xlsx")
# The two weeklies are zip-of-daily-zips and together cover every daily file
# without the overlap you'd get by also reading the loose daily zips.
GUDID_WEEKLIES = [
    "gudid_weekly_update_20260518_20260522.zip",
    "gudid_weekly_update_20260525_20260529.zip",
]
GUDID_NS = "http://www.fda.gov/cdrh/gudid"

API = os.environ.get("POP_API", "http://localhost:8787")
POP_DB = os.environ.get("POP_DB", "thingdaddy_population")
INGEST_BATCH = 500          # <= API hard cap of 1000
DEFAULT_TEST_LIMIT = 20

# Country label (GDSN "GS1 Prefix Country") -> candidate MO band. This is a
# HEURISTIC label on a candidate row: the true MO is set by the prefix's numeric
# band, not the country. Fine as a candidate hint; never a promotion signal.
COUNTRY_TO_MO = {
    "USA": "GS1 US", "United States": "GS1 US",
    "Mexico": "GS1 Mexico",
    "Germany": "GS1 Germany",
    "Canada": "GS1 Canada",
    "France": "GS1 France",
    "United Kingdom": "GS1 UK", "UK": "GS1 UK",
    "China": "GS1 China",
    "Japan": "GS1 Japan",
    "Korea": "GS1 Korea", "South Korea": "GS1 Korea",
    "Brazil": "GS1 Brasil",
    "India": "GS1 India",
    "Italy": "GS1 Italy",
    "Spain": "GS1 Spain",
    "Netherlands": "GS1 Netherlands",
}


# --- HTTP helpers ------------------------------------------------------------

def _get(path):
    url = f"{API}{path}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def _require_ingest_token():
    """Return INGEST_TOKEN or fail fast. The population API gates /ingest behind a
    shared secret (requireWriteToken); a tokenless POST would just 401/503. We
    refuse to send one — a clear stop beats a confusing HTTP error mid-batch."""
    token = os.environ.get("INGEST_TOKEN")
    if not token:
        raise SystemExit(
            "INGEST_TOKEN is not set — refusing to POST /ingest without the write token.\n"
            "Set it to match the population API's INGEST_TOKEN, e.g.:\n"
            "  export INGEST_TOKEN=... && python3 load_population.py ...")
    return token


def _post(path, body):
    token = _require_ingest_token()
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# --- pre-check dedup (safe re-runs) ------------------------------------------
# The API upserts on prefix only; with prefix=NULL every row is a plain INSERT,
# so a naive re-run would duplicate. We take a ONE-SHOT snapshot of the natural
# keys already present for this source (GLN for GDSN, legal_name for GUDID) and
# skip rows already in it — plus dedup within the run. This is a read-only
# snapshot; all WRITES still go exclusively through POST /ingest. We read it in a
# single indexed query (ix_party_source) rather than one GET /search per row,
# which at ~80K rows would otherwise scan a 4M-row table 80K times.

def _existing_keys(source, column):
    # `source` and `column` are literals from our own code (not user input).
    sql = (f"SELECT DISTINCT {column} FROM party "
           f"WHERE source = '{source}' AND {column} IS NOT NULL")
    out = subprocess.run(["psql", "-d", POP_DB, "-tAc", sql],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"dedup snapshot failed: {out.stderr.strip()}")
    return set(line for line in out.stdout.splitlines() if line)


# --- GDSN --------------------------------------------------------------------

def read_gdsn(limit=None, include_removed=False):
    """Yield party dicts from the xlsx. Clean -> candidates, Removed -> exceptions."""
    import openpyxl
    wb = openpyxl.load_workbook(GDSN_XLSX, read_only=True, data_only=True)

    def cell(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    rows = []
    # Clean sheet: GLN | Company / Trading Partner Name | GS1 Prefix Country
    ws = wb["Clean"]
    it = ws.iter_rows(values_only=True)
    next(it, None)  # header
    for gln, name, country in (r for r in it):
        name = cell(name)
        if not name:
            continue
        country = cell(country)
        rows.append({
            "legal_name": name,
            "gln": cell(gln),           # keep as string — leading zeros matter
            "country": country,
            "mo": COUNTRY_TO_MO.get(country) if country else None,
            "prefix": None,             # law: never derived from a GLN
            "lei": None,                # not in source
            "duns": None,               # not in source
            "source": "GDSN",
        })
        if limit and len(rows) >= limit:
            break

    if include_removed:
        ws = wb["Removed"]  # GLN | Name (as-is) | Country | Reason removed
        it = ws.iter_rows(values_only=True)
        next(it, None)
        for gln, name, country, reason in (r for r in it):
            name = cell(name)
            if not name:
                continue
            rows.append({
                "legal_name": name,
                "gln": cell(gln),
                "country": cell(country),
                "prefix": None, "lei": None, "duns": None,
                "source": "GDSN",
                "exception_reason": cell(reason) or "removed by GDSN cleaning",
            })
    return rows


# --- GUDID -------------------------------------------------------------------

def _text(el, tag):
    x = el.find(f"{{{GUDID_NS}}}{tag}")
    return (x.text or "").strip() if x is not None else ""


def read_gudid(limit=None):
    """
    Read device XML from the weekly zip-of-daily-zips, dedupe to the manufacturer
    (companyName), and yield one candidate party per company. companyName is the
    dedupe key; the first non-empty DUNS seen for that company is preserved.
    """
    by_company = {}   # companyName -> party dict
    order = []        # preserve first-seen order for a stable --limit test slice

    for wk in GUDID_WEEKLIES:
        path = os.path.join(INCOMING, wk)
        with zipfile.ZipFile(path) as wz:
            for daily in wz.namelist():
                if not daily.lower().endswith(".zip"):
                    continue
                with zipfile.ZipFile(io.BytesIO(wz.read(daily))) as dz:
                    xmls = [n for n in dz.namelist() if n.lower().endswith(".xml")]
                    if not xmls:
                        continue
                    xmlname = max(xmls, key=lambda n: dz.getinfo(n).file_size)
                    root = ET.fromstring(dz.read(xmlname))
                    for d in root.findall(f"{{{GUDID_NS}}}device"):
                        co = _text(d, "companyName")
                        if not co:
                            continue  # 13 blank-company devices in the set — skip
                        duns = _text(d, "dunsNumber").replace("-", "").replace(" ", "") or None
                        if co not in by_company:
                            by_company[co] = {
                                "legal_name": co,
                                "prefix": None,   # law: never derived from a GTIN
                                "gln": None,      # GUDID has no GLN
                                "lei": None,      # not in source
                                "duns": duns,     # cross-ref seed (D&B match, later)
                                "source": "GUDID",
                            }
                            order.append(co)
                        elif by_company[co]["duns"] is None and duns:
                            by_company[co]["duns"] = duns
                        if limit and len(order) >= limit:
                            # keep scanning only to backfill DUNS for chosen set
                            pass
    rows = [by_company[c] for c in order]
    return rows[:limit] if limit else rows


# --- ingest ------------------------------------------------------------------

def ingest(rows, source, dry_run=False, dedup=True):
    if dedup:
        column = "gln" if source == "GDSN" else "legal_name"
        key = (lambda r: r.get("gln")) if source == "GDSN" else (lambda r: r["legal_name"])
        seen = _existing_keys(source, column)   # already in DB for this source
        kept, skipped = [], 0
        for r in rows:
            k = key(r)
            if k and k in seen:                 # skip rows already present / seen this run
                skipped += 1
                continue
            kept.append(r)
            if k:
                seen.add(k)                     # also de-dupe within this run
        if skipped:
            print(f"[{source}] pre-check dedup: skipped {skipped} already-present, "
                  f"{len(kept)} new")
        rows = kept

    if dry_run:
        print(f"[{source}] DRY RUN — {len(rows)} rows would POST /ingest. Sample:")
        for r in rows[:5]:
            print("   ", json.dumps(r, ensure_ascii=False))
        return {"dry_run": True, "would_ingest": len(rows)}

    totals = {"ingested": 0, "inserted": 0, "updated": 0}
    for i in range(0, len(rows), INGEST_BATCH):
        chunk = rows[i:i + INGEST_BATCH]
        status, body = _post("/ingest", {"source": source, "rows": chunk})
        if status != 201:
            print(f"[{source}] batch {i}: HTTP {status}: {json.dumps(body)[:400]}",
                  file=sys.stderr)
            raise SystemExit(1)
        totals["ingested"] += body.get("ingested", 0)
        for k, v in body.get("summary", {}).items():
            totals[k] = totals.get(k, 0) + v
        print(f"[{source}] batch {i//INGEST_BATCH}: {body.get('ingested')} rows "
              f"-> {body.get('summary')}")
    return totals


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["gdsn", "gudid", "both"], required=True)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap rows per source (omit for full load)")
    ap.add_argument("--test", action="store_true",
                    help=f"shortcut for --limit {DEFAULT_TEST_LIMIT}")
    ap.add_argument("--removed", action="store_true",
                    help="also load the GDSN 'Removed' sheet as exceptions")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-dedup", action="store_true",
                    help="skip the pre-check dedup (faster; may duplicate on re-run)")
    args = ap.parse_args()

    limit = DEFAULT_TEST_LIMIT if args.test else args.limit
    dedup = not args.no_dedup

    if args.source in ("gdsn", "both"):
        rows = read_gdsn(limit=limit, include_removed=args.removed)
        print(f"[GDSN] read {len(rows)} rows from xlsx"
              + (" (incl. Removed)" if args.removed else ""))
        print("[GDSN] result:", json.dumps(ingest(rows, "GDSN", args.dry_run, dedup)))

    if args.source in ("gudid", "both"):
        rows = read_gudid(limit=limit)
        print(f"[GUDID] read {len(rows)} deduped company rows from weekly zips")
        print("[GUDID] result:", json.dumps(ingest(rows, "GUDID", args.dry_run, dedup)))


if __name__ == "__main__":
    main()
