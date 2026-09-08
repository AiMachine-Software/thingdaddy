#!/usr/bin/env python3
"""
page_reader.py — the depth layer under the sitemap harvest.

Reads the actual product/document PAGES (URLs the sitemap harvest already found) and pulls
what a URL list can't give you:
  1. Real document FILES — the .pdf links on the page (driver / manual / datasheet / SDS /
     certificate), with the anchor text as title.  ← "drivers as PDFs"
  2. Real GTINs — check-digit-valid product identifiers present on the page (→ spine, source=WEB).
  3. Binding EDGES — candidate typed relationships from this page to a driver / protocol /
     accessory page:  has_driver (P2) · runs (P3) · uses (P5).

Laws: nothing fabricated. A GTIN must pass the GS1 mod-10 check digit. Edges are CANDIDATE and
only formed to protocol-legal targets (keyword-typed). No prefix derived, no URN minted for docs
(prefix-is-root). Everything provenance-bound to the source page. Bounded + polite; runs on the Mac.

Noise filters (so the edges are relationships, not site chrome):
  * cross-locale self-links dropped — a page linking to its own /de/ /fr/ twin is not a binding.
  * site-wide chrome targets dropped — a target reachable from more than --chrome-max distinct
    source pages is nav/footer, not a protocol edge.
  * junk anchor titles ("Download", "PDF", "") fall back to a clean name derived from the file URL.

Outputs (in --outdir):
  page_documents.csv  source_page,file_url,doc_type,title
  page_gtins.csv      urn,key_type,prefix,gln,mo,state,source     (spine-ready; source=WEB)
  page_edges.csv      source_page,edge_type,target_url,pillar,anchor

Usage:
  # read the driver document pages the harvest found:
  python3 page_reader.py --docs sitemap_documents.csv --doc-type driver --limit 60 --outdir .
  # or read product pages:
  python3 page_reader.py --struct sitemap_structure.csv --kind product --limit 100 --outdir .
  # or an explicit list:
  python3 page_reader.py --urls pages.txt --limit 50 --outdir .
"""
from __future__ import annotations
import argparse, csv, os, re, sys, time
# optional: structured-data recovery for SPA / JSON-LD pages (population root on path)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import spa_extract as _spa
except Exception:
    _spa = None
import urllib.request, urllib.parse, urllib.error
from html.parser import HTMLParser
from collections import defaultdict

# Browser UA — many sites 406/403 non-browser agents on public pages.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# --- GS1 check digit (self-contained) ---------------------------------------
def gtin_check_ok(d):
    if not d.isdigit() or len(d) not in (8, 12, 13, 14): return False
    body, chk = [int(c) for c in d[:-1]], int(d[-1])
    s = sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(body)))
    return (10 - (s % 10)) % 10 == chk
def to_gtin14(d): return d.zfill(14)

# --- GS1 MO band table (published prefix ranges) — the second filter ---------
# A number can pass the mod-10 check digit by coincidence (~10% of random 13-digit strings). A REAL
# GS1 GTIN's prefix lands in an assigned Member Organisation band; a coincidental one usually doesn't.
# So we gate: no MO band -> not a real GTIN -> not written (unless --no-mo-gate).
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
def mo_for_gtin(gtin14):
    try: p3 = int(gtin14[1:4])          # first 3 digits of the company-prefix region (drop indicator)
    except ValueError: return ""
    for lo, hi, name in RANGES:
        if lo <= p3 <= hi: return name
    return ""

_GTIN_RE = re.compile(r"(?<!\d)(\d{8}|\d{12}|\d{13}|\d{14})(?!\d)")

# --- typing: what a target link is ------------------------------------------
DOC_RE = re.compile(r"(manual|user-guide|owner|operat|ifu|instruction|datasheet|data-sheet|"
                    r"spec-?sheet|sds|msds|safety-data|coa|certificate|declaration|driver|firmware)", re.I)
def doc_type_for(url, text=""):
    u = (url + " " + text).lower()
    if re.search(r"(driver|firmware|/sila|connector|device-driver)", u): return "driver"
    if re.search(r"(manual|user-guide|owner|operat|ifu|instruction)", u): return "manual"
    if re.search(r"(datasheet|data-sheet|spec-?sheet|specification)", u): return "datasheet"
    if re.search(r"(sds|msds|safety-data)", u): return "sds"
    if re.search(r"(coa|certificate|declaration|conformance)", u): return "certificate"
    return "pdf"

EDGE_RE = [
    ("has_driver", "P2", r"(driver|/sila|firmware|connector|connectivity|software-download|sdk)"),
    ("runs",       "P3", r"(protocol|method|assay|application-note|app-note|workflow|procedure|allotrope)"),
    ("uses",       "P5", r"(accessor|consumable|compatib|replacement|spare|reagent|kit|selection-guide)"),
]
def edge_for(url, text=""):
    u = (url + " " + text).lower()
    for etype, pillar, pat in EDGE_RE:
        if re.search(pat, u): return etype, pillar
    return None, None

# --- title cleanup + slug (noise filters) -----------------------------------
_JUNK_TITLE = re.compile(r"^(download|pdf|download pdf|click here|here|view|view pdf|open|link|"
                         r"read more|learn more|more|details|see more)$", re.I)
def clean_title(text, url):
    """Real anchor text if it says something; else a clean name from the file URL."""
    t = " ".join((text or "").split())
    if t and len(t) > 3 and not _JUNK_TITLE.match(t):
        return t
    base = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    base = re.sub(r"\.(pdf|html?|ashx|aspx)$", "", base, flags=re.I)
    base = re.sub(r"[-_+]+", " ", base).strip()
    return base.title() if base else url

_LOCALE = re.compile(r"^[a-z]{2}([-_][a-z]{2})?$", re.I)
def _slug(url):
    """Last meaningful path segment, locale-stripped — identifies 'the same page'."""
    try:
        p = urllib.parse.urlparse(url)
    except Exception:
        return (url or "").lower()
    segs = [s for s in p.path.split("/") if s and not _LOCALE.match(s)]
    return segs[-1].lower() if segs else (p.netloc or url).lower()

# --- HTML anchor + text extraction ------------------------------------------
class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self._href = None; self._buf = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href"); self._buf = []
    def handle_data(self, data):
        if self._href is not None: self._buf.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._buf).split())[:160]))
            self._href = None; self._buf = []

def http_get(url, timeout=30):
    _host = urllib.parse.urlparse(url).netloc
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9", "Referer": f"https://{_host}/" if _host else ""})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        if "html" not in ct and "xml" not in ct and not url.lower().endswith((".htm", ".html", "/")):
            return ""  # don't download binaries (pdfs etc.) — we only want the page's HTML
        return r.read(2_000_000).decode("utf-8", "replace")  # cap 2MB/page

# --- input page lists --------------------------------------------------------
def pages_from(args):
    urls = []
    if args.urls:
        with open(args.urls) as f:
            urls += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if args.docs:
        with open(args.docs, newline="") as f:
            for r in csv.DictReader(f):
                if not args.doc_type or r.get("doc_type") == args.doc_type:
                    urls.append(r.get("url"))
    if args.struct:
        with open(args.struct, newline="") as f:
            for r in csv.DictReader(f):
                if not args.kind or r.get("kind") == args.kind:
                    urls.append(r.get("url"))
    # de-dup, keep order
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u); out.append(u)
    return out

def main():
    ap = argparse.ArgumentParser(description="Read pages -> real PDF files, GTINs, binding edges")
    ap.add_argument("--urls"); ap.add_argument("--docs"); ap.add_argument("--struct")
    ap.add_argument("--doc-type"); ap.add_argument("--kind")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--chrome-max", type=int, default=8,
                    help="drop edge targets reachable from more than this many distinct source pages (nav/footer chrome)")
    ap.add_argument("--no-mo-gate", action="store_true",
                    help="keep every check-digit-valid number as a GTIN (default: only keep ones whose prefix roots to an assigned GS1 MO band — drops check-digit-coincidence noise)")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()
    pages = pages_from(a)[:a.limit]
    if not pages:
        raise SystemExit("no input pages — pass --urls / --docs / --struct")

    os.makedirs(a.outdir, exist_ok=True)
    dfile = open(os.path.join(a.outdir, "page_documents.csv"), "w", newline="")
    gfile = open(os.path.join(a.outdir, "page_gtins.csv"), "w", newline="")
    efile = open(os.path.join(a.outdir, "page_edges.csv"), "w", newline="")
    dw, gw, ew = csv.writer(dfile), csv.writer(gfile), csv.writer(efile)
    dw.writerow(["source_page", "file_url", "doc_type", "title"])
    gw.writerow(["urn", "key_type", "prefix", "gln", "mo", "state", "source"])
    ew.writerow(["source_page", "edge_type", "target_url", "pillar", "anchor"])

    seen_docs, seen_gtins, seen_edges = set(), set(), set()
    edges_raw = []                 # collect, then filter chrome after we've seen every page
    n_doc = n_gtin = n_gtin_nomo = n_gtin_spa = 0
    print(f">> page-reader  pages={len(pages)}")
    for i, page in enumerate(pages, 1):
        try:
            html = http_get(page)
        except Exception as e:
            print(f"  [{i}] {page} -> {e}", file=sys.stderr); continue
        if not html:
            continue
        # GTINs on the page
        for m in _GTIN_RE.finditer(html):
            g = m.group(1)
            if gtin_check_ok(g):
                g14 = to_gtin14(g)
                urn = "urn:epc:id:gtin:" + g14
                if urn in seen_gtins: continue
                mo = mo_for_gtin(g14)
                if not mo and not a.no_mo_gate:
                    n_gtin_nomo += 1; continue          # check-digit-coincidence noise — no assigned band
                seen_gtins.add(urn); gw.writerow([urn, "gtin", "", "", mo, "candidate", "WEB"]); n_gtin += 1
        # structured-data recovery (SPA / JSON-LD / __NEXT_DATA__) — re-gated through our own MO gate
        if _spa is not None:
            try:
                for g in _spa.extract_structured(html, page).get("gtins", []):
                    digits = re.sub(r"\D", "", g.get("raw", ""))
                    if len(digits) not in (8, 12, 13, 14) or not gtin_check_ok(digits): continue
                    g14 = to_gtin14(digits); urn = "urn:epc:id:gtin:" + g14
                    if urn in seen_gtins: continue
                    mo = mo_for_gtin(g14)
                    if not mo and not a.no_mo_gate: n_gtin_nomo += 1; continue
                    seen_gtins.add(urn); gw.writerow([urn, "gtin", "", "", mo, "candidate", "SPA-STRUCT"])
                    n_gtin += 1; n_gtin_spa += 1
            except Exception:
                pass
        # anchors -> documents + edges
        ap_ = Anchors(); ap_.feed(html)
        for href, text in ap_.links:
            if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")): continue
            url = urllib.parse.urljoin(page, href)
            low = url.lower()
            if low.endswith(".pdf") or ".pdf?" in low:
                key = (page, url)
                if key not in seen_docs:
                    seen_docs.add(key); dw.writerow([page, url, doc_type_for(url, text), clean_title(text, url)]); n_doc += 1
            else:
                et, pil = edge_for(url, text)
                if not et: continue
                if _slug(url) == _slug(page): continue          # cross-locale / same-page self-link
                key = (page, et, url)
                if key not in seen_edges:
                    seen_edges.add(key); edges_raw.append((page, et, url, pil, text or ""))
        if i % 10 == 0:
            dfile.flush(); gfile.flush()
            print(f"   ... {i}/{len(pages)} pages · {n_doc} pdfs · {n_gtin} gtins · {len(edges_raw)} edge candidates")
        time.sleep(a.sleep)

    # --- chrome filter: a target reachable from many distinct sources is nav, not a relationship
    tgt_sources = defaultdict(set)
    for src, et, tgt, pil, anchor in edges_raw:
        tgt_sources[_slug(tgt)].add(_slug(src))
    n_edge = n_chrome = 0
    for src, et, tgt, pil, anchor in edges_raw:
        if len(tgt_sources[_slug(tgt)]) > a.chrome_max:
            n_chrome += 1; continue
        ew.writerow([src, et, tgt, pil, anchor]); n_edge += 1

    dfile.close(); gfile.close(); efile.close()
    gate_note = (f" · {n_gtin_nomo} check-digit-coincidence GTINs dropped (no assigned MO band)"
                 if n_gtin_nomo and not a.no_mo_gate else "")
    spa_note = f" · {n_gtin_spa} recovered via structured data (SPA/JSON-LD)" if n_gtin_spa else ""
    print(f">> done. {n_doc} real document files · {n_gtin} GTINs (MO-band rooted) · {n_edge} candidate edges "
          f"({n_chrome} chrome/nav targets dropped){gate_note}{spa_note}")
    print("   page_documents.csv · page_gtins.csv (spine-ready, source=WEB) · page_edges.csv")
    print("   All candidate + provenanced. GTINs check-digit-validated; edges protocol-legal, self-links + chrome filtered; no URN minted for docs.")

if __name__ == "__main__":
    main()
