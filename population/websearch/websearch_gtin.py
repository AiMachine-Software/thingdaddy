#!/usr/bin/env python3
"""
websearch_gtin.py — open-web GTIN discovery -> node-spine CSV (source=WEB).

The FIRST real implementation of the "web-scan GTIN engine". It was described in
population_websearch_gtin_engine.md ("we built a web-search engine...") but never
coded — verified by a full Mac search 2026-07-19. This is the code.

The four laws, honored verbatim:
  * NEVER fabricate a GTIN. Every candidate must (a) actually appear on a fetched
    source page / authority payload AND (b) pass the GS1 mod-10 check digit.
    Junk digit-runs are dropped. A number that isn't a real GTIN never lands.
  * NEVER derive a company prefix (GS1 US is variable-length; the boundary is not
    in the digits). prefix stays EMPTY -> NULL in the spine. Only the MO
    (Member Organisation) is set — deterministic and lawful from the GS1 prefix
    band, exactly like the GUDID base (mo_for_gtin, table kept in sync with
    datastore/mo_resolver.py).
  * CANDIDATE only, source=WEB. Promotion to verified happens elsewhere (R4).
  * PROVENANCE always. Every GTIN carries the exact URL it was seen on.

Output (two files, in --outdir):
  spine_gtin_web.csv            headerless node rows: urn,key_type,prefix,gln,mo,state,source
                                -> loads via load_web_spine.sql into <db>.node (source=WEB),
                                   the SAME door as the 4.5M GUDID export.
  spine_gtin_web.provenance.csv urn,source_url,name,brand,adapter,seen_at

This script NEVER writes to a database. Discovery -> CSV only. The guarded loader
(run_web_scan.sh -> load_web_spine.sql) is the only thing that touches the DB, and
it lands on scratch first.

Adapters (--source):
  openfoodfacts  free, no key. --query / --brand / --category -> products (code + url).
  urls           --url U (repeatable) or --urls FILE. Fetch each, regex-extract +
                 check-digit-validate GTINs, provenance = that URL. Point it at any
                 manufacturer catalog / retailer / barcode page.
  search         OPTIONAL. Needs SERPAPI_KEY. --query -> result URLs -> urls adapter.
                 If no key is set it prints how to enable and exits that adapter.

Usage:
  python3 websearch_gtin.py --source openfoodfacts --query "cold brew coffee" --limit 200
  python3 websearch_gtin.py --source openfoodfacts --brand "Nestle" --limit 500
  python3 websearch_gtin.py --source urls --urls targets.txt --limit 300
  # then load onto scratch (guarded):
  POP_DB=thingdaddy_population_test ./run_web_scan.sh
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys, time
import urllib.request, urllib.parse, urllib.error

UA = "ThingDaddy-WebScan/0.1 (GTIN discovery; contact ops@thingdaddy.io)"

# --- GS1 Member-Organisation table (verbatim from datastore/mo_resolver.py) ---
RANGES = [
    (1,19,"GS1 US"),(20,29,"Restricted (regional)"),(30,39,"GS1 US"),(40,49,"Restricted (company)"),
    (50,59,"GS1 US (reserved)"),(60,139,"GS1 US"),(200,299,"Restricted (regional)"),
    (300,379,"GS1 France"),(380,380,"GS1 Bulgaria"),(383,383,"GS1 Slovenija"),(385,385,"GS1 Croatia"),
    (387,387,"GS1 BIH"),(389,389,"GS1 Montenegro"),(400,440,"GS1 Germany"),(450,459,"GS1 Japan"),
    (460,469,"GS1 Russia"),(470,470,"GS1 Kyrgyzstan"),(471,471,"GS1 Chinese Taipei"),(474,474,"GS1 Estonia"),
    (475,475,"GS1 Latvia"),(476,476,"GS1 Azerbaijan"),(477,477,"GS1 Lithuania"),(478,478,"GS1 Uzbekistan"),
    (479,479,"GS1 Sri Lanka"),(480,480,"GS1 Philippines"),(481,481,"GS1 Belarus"),(482,482,"GS1 Ukraine"),
    (483,483,"GS1 Turkmenistan"),(484,484,"GS1 Moldova"),(485,485,"GS1 Armenia"),(486,486,"GS1 Georgia"),
    (487,487,"GS1 Kazakstan"),(488,488,"GS1 Tajikistan"),(489,489,"GS1 Hong Kong"),(490,499,"GS1 Japan"),
    (500,509,"GS1 UK"),(520,521,"GS1 Greece"),(528,528,"GS1 Lebanon"),(529,529,"GS1 Cyprus"),
    (530,530,"GS1 Albania"),(531,531,"GS1 Macedonia"),(535,535,"GS1 Malta"),(539,539,"GS1 Ireland"),
    (540,549,"GS1 Belgium & Luxembourg"),(560,560,"GS1 Portugal"),(569,569,"GS1 Iceland"),
    (570,579,"GS1 Denmark"),(590,590,"GS1 Poland"),(594,594,"GS1 Romania"),(599,599,"GS1 Hungary"),
    (600,601,"GS1 South Africa"),(603,603,"GS1 Ghana"),(604,604,"GS1 Senegal"),(607,607,"GS1 Oman"),
    (608,608,"GS1 Bahrain"),(609,609,"GS1 Mauritius"),(611,611,"GS1 Morocco"),(613,613,"GS1 Algeria"),
    (615,615,"GS1 Nigeria"),(616,616,"GS1 Kenya"),(617,617,"GS1 Cameroon"),(618,618,"GS1 Cote d'Ivoire"),
    (619,619,"GS1 Tunisia"),(620,620,"GS1 Tanzania"),(621,621,"GS1 Syria"),(622,622,"GS1 Egypt"),
    (624,624,"GS1 Libya"),(625,625,"GS1 Jordan"),(626,626,"GS1 Iran"),(627,627,"GS1 Kuwait"),
    (628,628,"GS1 Saudi Arabia"),(629,629,"GS1 Emirates"),(630,630,"GS1 Qatar"),(631,631,"GS1 Namibia"),
    (640,649,"GS1 Finland"),(680,681,"GS1 China"),(690,699,"GS1 China"),(700,709,"GS1 Norway"),
    (729,729,"GS1 Israel"),(730,739,"GS1 Sweden"),(740,740,"GS1 Guatemala"),(741,741,"GS1 El Salvador"),
    (742,742,"GS1 Honduras"),(743,743,"GS1 Nicaragua"),(744,744,"GS1 Costa Rica"),(745,745,"GS1 Panama"),
    (746,746,"GS1 Dominican Republic"),(750,750,"GS1 Mexico"),(754,755,"GS1 Canada"),(759,759,"GS1 Venezuela"),
    (760,769,"GS1 Switzerland"),(770,771,"GS1 Colombia"),(773,773,"GS1 Uruguay"),(775,775,"GS1 Peru"),
    (777,777,"GS1 Bolivia"),(778,779,"GS1 Argentina"),(780,780,"GS1 Chile"),(784,784,"GS1 Paraguay"),
    (786,786,"GS1 Ecuador"),(789,790,"GS1 Brasil"),(800,839,"GS1 Italy"),(840,849,"GS1 Spain"),
    (850,850,"GS1 Cuba"),(858,858,"GS1 Slovakia"),(859,859,"GS1 Czech"),(860,860,"GS1 Serbia"),
    (865,865,"GS1 Mongolia"),(867,867,"GS1 North Korea"),(868,869,"GS1 Turkiye"),(870,879,"GS1 Netherlands"),
    (880,881,"GS1 South Korea"),(883,883,"GS1 Myanmar"),(884,884,"GS1 Cambodia"),(885,885,"GS1 Thailand"),
    (888,888,"GS1 Singapore"),(890,890,"GS1 India"),(893,893,"GS1 Vietnam"),(896,896,"GS1 Pakistan"),
    (899,899,"GS1 Indonesia"),(900,919,"GS1 Austria"),(930,939,"GS1 Australia"),(940,949,"GS1 New Zealand"),
    (950,950,"GS1 Global Office"),(951,951,"GS1 Global Office (GM number)"),(952,952,"Demo/examples"),
    (955,955,"GS1 Malaysia"),(958,958,"GS1 Macau"),(960,969,"Global Office GTIN-8"),
    (977,977,"Serial publications (ISSN)"),(978,979,"Bookland (ISBN)"),(980,980,"Refund receipts"),
    (981,983,"GS1 coupon (common currency)"),(990,999,"GS1 coupon"),
]

def mo_for_gtin(gtin14: str) -> str:
    if len(gtin14) < 4 or not gtin14.isdigit():
        return "unknown"
    body = gtin14[1:]                 # drop the GTIN-14 packaging-indicator digit
    p3 = int(body[:3])
    for lo, hi, mo in RANGES:
        if lo <= p3 <= hi:
            return mo
    return "reserved/unassigned"

# --- GS1 check digit (mod 10) ------------------------------------------------
def gtin_check_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) not in (8, 12, 13, 14):
        return False
    body, check = [int(c) for c in digits[:-1]], int(digits[-1])
    s = sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(body)))
    return (10 - (s % 10)) % 10 == check

def to_gtin14(digits: str) -> str:
    return digits.zfill(14)

def urn_for(gtin14: str) -> str:
    return f"urn:epc:id:gtin:{gtin14}"

# --- extract valid GTINs from arbitrary text/HTML ----------------------------
_GTIN_RE = re.compile(r"(?<!\d)(\d{8}|\d{12}|\d{13}|\d{14})(?!\d)")
def extract_gtins(text: str):
    out = set()
    for m in _GTIN_RE.finditer(text or ""):
        g = m.group(1)
        if gtin_check_ok(g):
            out.add(to_gtin14(g))
    return out

# --- HTTP --------------------------------------------------------------------
def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

# --- adapters: each yields dicts {gtin14, name, brand, url} -------------------
def adapter_openfoodfacts(args, cursor):
    key = f"openfoodfacts:{args.query or args.brand or args.category or 'all'}"
    page = cursor.get(key, 0) + 1
    yielded = 0
    while yielded < args.limit:
        params = {"json": 1, "action": "process",
                  "page_size": min(100, args.limit - yielded), "page": page,
                  "fields": "code,product_name,brands,url"}
        if args.query:    params["search_terms"] = args.query
        if args.brand:    params.update({"tagtype_0": "brands", "tag_contains_0": "contains", "tag_0": args.brand})
        if args.category: params.update({"tagtype_1": "categories", "tag_contains_1": "contains", "tag_1": args.category})
        url = "https://world.openfoodfacts.org/cgi/search.pl?" + urllib.parse.urlencode(params)
        try:
            data = json.loads(http_get(url))
        except Exception as e:
            print(f"  [off] page {page} fetch failed: {e}", file=sys.stderr); break
        prods = data.get("products", []) or []
        if not prods:
            break
        for p in prods:
            code = re.sub(r"\D", "", str(p.get("code") or ""))
            if len(code) not in (8, 12, 13, 14) or not gtin_check_ok(code):
                continue
            yield {"gtin14": to_gtin14(code),
                   "name": (p.get("product_name") or "").strip()[:200],
                   "brand": (p.get("brands") or "").strip()[:120],
                   "url": (p.get("url") or f"https://world.openfoodfacts.org/product/{code}")}
            yielded += 1
            if yielded >= args.limit:
                break
        cursor[key] = page
        page += 1
        time.sleep(args.sleep)

def _iter_urls(args):
    if args.url:
        for u in args.url: yield u
    if args.urls:
        with open(args.urls, encoding="utf-8", errors="replace") as f:
            for line in f:
                u = line.strip()
                if u and not u.startswith("#"): yield u

def adapter_urls(args, cursor):
    yielded = 0
    for u in _iter_urls(args):
        if yielded >= args.limit: break
        try:
            html = http_get(u)
        except Exception as e:
            print(f"  [urls] {u} failed: {e}", file=sys.stderr); continue
        for g in extract_gtins(html):
            yield {"gtin14": g, "name": "", "brand": "", "url": u}
            yielded += 1
            if yielded >= args.limit: break
        time.sleep(args.sleep)

def adapter_search(args, cursor):
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("  [search] SERPAPI_KEY not set. To enable open-web search discovery:\n"
              "    export SERPAPI_KEY=...   (serpapi.com)\n"
              "  Then: --source search --query \"...\". Falling through with 0 results.",
              file=sys.stderr)
        return
    if not args.query:
        print("  [search] needs --query", file=sys.stderr); return
    q = urllib.parse.urlencode({"engine": "google", "q": args.query, "num": 20, "api_key": api_key})
    try:
        data = json.loads(http_get("https://serpapi.com/search.json?" + q))
    except Exception as e:
        print(f"  [search] serpapi failed: {e}", file=sys.stderr); return
    urls = [r.get("link") for r in data.get("organic_results", []) if r.get("link")]
    # reuse the urls adapter over the result pages
    class _A:  # minimal shim carrying the resolved URL list
        pass
    shim = _A(); shim.__dict__.update(vars(args)); shim.url = urls; shim.urls = None
    yield from adapter_urls(shim, cursor)

ADAPTERS = {"openfoodfacts": adapter_openfoodfacts, "urls": adapter_urls, "search": adapter_search}

# --- cursor persistence (resumable, BL-4) ------------------------------------
def load_cursor(path):
    try:
        with open(path) as f: return json.load(f)
    except Exception:
        return {}
def save_cursor(path, cur):
    try:
        with open(path, "w") as f: json.dump(cur, f)
    except Exception as e:
        print(f"  [cursor] save failed: {e}", file=sys.stderr)

# --- main --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Open-web GTIN discovery -> node-spine CSV (source=WEB)")
    ap.add_argument("--source", required=True, choices=list(ADAPTERS))
    ap.add_argument("--query"); ap.add_argument("--brand"); ap.add_argument("--category")
    ap.add_argument("--url", action="append", help="a target URL (repeatable) for --source urls")
    ap.add_argument("--urls", help="file of target URLs, one per line, for --source urls")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--sleep", type=float, default=0.5, help="politeness delay between requests (s)")
    ap.add_argument("--reset", action="store_true", help="ignore the saved cursor and start fresh")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    spine_path = os.path.join(a.outdir, "spine_gtin_web.csv")
    prov_path  = os.path.join(a.outdir, "spine_gtin_web.provenance.csv")
    cur_path   = os.path.join(a.outdir, "websearch_cursor.json")
    cursor = {} if a.reset else load_cursor(cur_path)

    seen, mo_counts, kept = set(), {}, 0
    t0 = time.time()
    # append-friendly: read urns already in the spine CSV so re-runs don't dup rows
    if os.path.exists(spine_path):
        with open(spine_path, newline="") as f:
            for row in csv.reader(f):
                if row: seen.add(row[0])

    spine_new = open(spine_path, "a", newline="")
    prov_new  = open(prov_path,  "a", newline="")
    sw, pw = csv.writer(spine_new), csv.writer(prov_new)
    if os.path.getsize(prov_path) == 0:
        pw.writerow(["urn", "source_url", "name", "brand", "adapter", "seen_at"])

    print(f">> web-scan GTIN discovery  source={a.source}  limit={a.limit}")
    try:
        for rec in ADAPTERS[a.source](a, cursor):
            urn = urn_for(rec["gtin14"])
            if urn in seen:
                continue
            seen.add(urn)
            mo = mo_for_gtin(rec["gtin14"])
            mo_counts[mo] = mo_counts.get(mo, 0) + 1
            # node-spine row — prefix EMPTY (never derived), gln empty, candidate, WEB
            sw.writerow([urn, "gtin", "", "", mo, "candidate", "WEB"])
            pw.writerow([urn, rec.get("url", ""), rec.get("name", ""),
                         rec.get("brand", ""), a.source, int(time.time())])
            kept += 1
            if kept % 50 == 0:
                spine_new.flush(); prov_new.flush(); save_cursor(cur_path, cursor)
                print(f"   ... {kept} kept")
    finally:
        spine_new.close(); prov_new.close(); save_cursor(cur_path, cursor)

    dt = round(time.time() - t0, 1)
    print(f">> done. {kept} new candidate GTINs in {dt}s")
    print(f"   spine CSV : {spine_path}  (load with run_web_scan.sh)")
    print(f"   provenance: {prov_path}")
    if mo_counts:
        top = sorted(mo_counts.items(), key=lambda x: -x[1])[:8]
        print("   MO breakdown: " + ", ".join(f"{m}={n}" for m, n in top))
    print("   prefix on every row = NULL (candidate, unrooted — the law). MO set from the GS1 band.")

if __name__ == "__main__":
    main()
