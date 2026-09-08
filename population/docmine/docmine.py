#!/usr/bin/env python3
"""
docmine.py — STAGE B: read INSIDE the manual/protocol PDFs and mine the identity graph.

page_reader gets the PDF *link*. The graph lives *inside* the PDF. This stage opens the documents
page_reader found and extracts what a link can't give you:

  * ATTRIBUTION (the WHO)  — manufacturer from cover / copyright line / "Manufactured by".
  * IDENTIFIERS            — labeled GTIN/UDI (high confidence), catalog #, model, part #.
  * SETTINGS (P3 config)   — parameter:value:unit from protocols (°C, min, µL, rpm, nm, cycles…).

It is the agent face of Andy's domain — the MAN segment, MSDS, user guides, implementation guides.

Laws (all candidate, nothing minted):
  * A GTIN must pass the GS1 mod-10 check digit; a labeled GTIN/UDI is flagged higher-confidence.
  * A catalog / model / part number is a CANDIDATE identifier — never asserted AS a GTIN.
  * NO GIAI is minted from a document — a serialized unit's identity enters at the warranty event.
  * Settings are candidate method params, not registry truth.
  * Provenance = the PDF URL + page number. Scanned / no-text PDFs are flagged and skipped (OCR is a
    separate, later decision — not this stage).

Needs a PDF text library on the Mac (either is fine):
    pip install pymupdf        # fast, per-page  (preferred)
    pip install pdfminer.six   # pure-python fallback

Input:  page_documents.csv  (source_page,file_url,doc_type,title) — from page_reader.
Outputs (--outdir):
  doc_attribution.csv   source_doc, page, company_candidate, evidence
  doc_identifiers.csv   source_doc, page, id_kind, value, gtin_if_valid, labeled, state
  doc_settings.csv      source_doc, page, param, value, unit, pillar, state

Usage:
  python3 docmine.py --docs sites/thermo-fisher-scientific/page_documents.csv --doc-type manual --limit 40 --outdir sites/thermo-fisher-scientific
  python3 docmine.py --docs .../page_documents.csv --doc-type application-note --limit 40 --outdir .
"""
from __future__ import annotations
import argparse, csv, os, re, sys, time
import urllib.request, urllib.parse, urllib.error

# Public manuals are often served behind a CDN that 403s non-browser agents. A normal browser UA
# fetches the same public documents (no auth, no CAPTCHA bypass — just not advertising as a bot).
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# --- GS1 check digit --------------------------------------------------------
def gtin_check_ok(d):
    if not d.isdigit() or len(d) not in (8, 12, 13, 14): return False
    body, chk = [int(c) for c in d[:-1]], int(d[-1])
    s = sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(body)))
    return (10 - (s % 10)) % 10 == chk
def to_gtin14(d): return d.zfill(14)

# --- attribution (the WHO) --------------------------------------------------
_ATTR = [
    re.compile(r"©\s*\d{4}[,\s]+([A-Z][A-Za-z0-9&.\-'’ ]{2,55}?)(?:\.|,|\s+all rights|\s+all Rights|\n|$)", re.I),
    re.compile(r"manufactured\s+by[:\s]+([A-Z][A-Za-z0-9&.\-'’ ]{2,55})", re.I),
    re.compile(r"manufacturer[:\s]+([A-Z][A-Za-z0-9&.\-'’ ]{2,55})", re.I),
    re.compile(r"\bfor\s+in\s+vitro.*?\n([A-Z][A-Za-z0-9&.\-'’ ]{3,55})", re.I),  # IFU footer name (loose)
]
_ATTR_STOP = re.compile(r"(all rights|reserved|inc\.?|llc|gmbh|ag|ltd|corp|company|laboratories|scientific)", re.I)
def _clean_company(name):
    name = re.split(r"\s*\.(?:\s*\.){1,}", name)[0]     # cut at a dotted leader ". . . ."
    name = re.sub(r"[\s.\-,\d]+$", "", name)            # strip trailing page numbers / punct
    return " ".join(name.split()).strip(" .,-")
def _looks_company(name, forced):
    if len(name) < 3: return False
    if forced: return True                              # explicit "Manufactured by" is trusted
    if _ATTR_STOP.search(name): return True             # has Inc/LLC/GmbH/Scientific/Laboratories…
    return len(name.split()) >= 2 and (name.istitle() or name.isupper())
def extract_attribution(text):
    out, seen = [], set()
    for rx in _ATTR:
        forced = rx.pattern.startswith("manufact")
        for m in rx.finditer(text):
            name = _clean_company(" ".join(m.group(1).split()))
            if not _looks_company(name, forced): continue
            low = name.lower()
            if low not in seen:
                seen.add(low)
                ev = " ".join(text[max(0, m.start()-10):m.end()+10].split())[:120]
                out.append((name, ev))
    return out[:6]

# --- identifiers ------------------------------------------------------------
_GTIN_LABELED = re.compile(r"(?:GTIN|UDI(?:[-\s]?DI)?|\(01\)|global\s+trade\s+item\s+number)"
                           r"\s*[:#]?\s*(\d{8}|\d{12}|\d{13}|\d{14})(?!\d)", re.I)
_GTIN_BARE    = re.compile(r"(?<!\d)(\d{8}|\d{12}|\d{13}|\d{14})(?!\d)")
_CATALOG = re.compile(r"(?:cat(?:alog|\.)?\s*(?:no\.?|number|#)|\bref\b|order\s*(?:no\.?|number)|"
                      r"product\s*(?:no\.?|number)|\bP/?N\b|\bSKU\b)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-]{2,19})", re.I)
_MODEL   = re.compile(r"\bmodel\s*(?:no\.?|number|name)?\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-]{1,19})", re.I)
_PART    = re.compile(r"(?:part\s*(?:no\.?|number)|spare\s*part)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-]{1,19})", re.I)

def extract_identifiers(text, want_bare_gtins=True):
    rows, seen = [], set()
    def add(kind, val, gtin, labeled):
        key = (kind, val)
        if val and key not in seen:
            seen.add(key); rows.append((kind, val, gtin, labeled))
    for m in _GTIN_LABELED.finditer(text):
        g = m.group(1)
        add("gtin", g, to_gtin14(g) if gtin_check_ok(g) else "", "yes")
    for rx, kind in ((_CATALOG, "catalog"), (_MODEL, "model"), (_PART, "part")):
        for m in rx.finditer(text):
            v = m.group(1).strip()
            if v.lower() in ("no", "number", "name", "the"): continue
            # a real catalog/model/part is code-like: has a digit, or a hyphenated all-caps code
            # (e.g. ND-ONE-W). Prose words after "Model"/"Part" ("helps", "requirements") are dropped.
            code_like = any(c.isdigit() for c in v) or ("-" in v and any(c.isupper() for c in v))
            if not code_like: continue
            add(kind, v, "", "")
    if want_bare_gtins:
        labeled_vals = {v for k, v, *_ in rows if k == "gtin"}
        for m in _GTIN_BARE.finditer(text):
            g = m.group(1)
            if g in labeled_vals: continue
            if gtin_check_ok(g):
                add("gtin", g, to_gtin14(g), "")     # bare = lower confidence (labeled empty)
    return rows

# --- settings (P3 method config) --------------------------------------------
# unit alternation: longer / more specific first so µL matches before L, °C before C, etc.
_UNITS = (r"°C|°F|℃|℉|deg(?:ree)?s?\s?C|deg(?:ree)?s?\s?F|nm|µm|um|rpm|×g|xg|mL|µL|uL|"
          r"mmol/L|mol/L|mM|µM|nM|mg/mL|µg/mL|ng/mL|g/L|"
          r"cycles?|min(?:ute)?s?|sec(?:ond)?s?|hrs?|hours?|µs|ms|kPa|psi|bar|pH|%|nm/min")
# find EVERY value+unit pair (multiple per line), then best-effort label from preceding words.
_UNIT_ONLY = re.compile(r"(?<![A-Za-z0-9])(\d{1,5}(?:\.\d{1,3})?)\s*(" + _UNITS + r")\b", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]+")
_LABEL_STOP = re.compile(r"^(and|the|for|with|of|to|at|in|on|is|are|a|an|by|per|approx|about|then)$", re.I)
def _label_from(pre):
    words = _WORD.findall(pre)
    while words and _LABEL_STOP.match(words[-1]):
        words.pop()
    if not words: return "(value)"
    lab = " ".join(words[-2:]) if len(words[-1]) <= 4 and len(words) >= 2 else words[-1]
    return lab.strip()
def extract_settings(text, cap=60):
    rows, seen = [], set()
    for m in _UNIT_ONLY.finditer(text):
        val, unit = m.group(1), m.group(2)
        label = _label_from(text[max(0, m.start() - 45):m.start()])
        key = (label.lower(), val, unit.lower())
        if key in seen: continue
        seen.add(key); rows.append((label, val, unit))
        if len(rows) >= cap: break
    return rows

# --- PDF text (per page) ----------------------------------------------------
def _pages_pymupdf(data):
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    return [(i + 1, doc[i].get_text() or "") for i in range(doc.page_count)]
def _pages_pdfminer(data):
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer
    import io
    out = []
    for i, layout in enumerate(extract_pages(io.BytesIO(data)), 1):
        txt = "".join(el.get_text() for el in layout if isinstance(el, LTTextContainer))
        out.append((i, txt))
    return out
def pick_extractor():
    """Choose a PDF text extractor ONCE at startup. Fail early with the real reason if none works."""
    try:
        import fitz  # noqa: F401  (PyMuPDF — preferred: fast, per-page, self-contained)
        return _pages_pymupdf, "pymupdf"
    except ImportError:
        pass
    try:
        import pdfminer.high_level, pdfminer.layout  # noqa: F401  (may fail if cryptography missing)
        return _pages_pdfminer, "pdfminer.six"
    except ImportError as e:
        raise SystemExit(
            "No working PDF library. Install the fast, self-contained one:\n"
            "    pip install pymupdf\n"
            f"  (pdfminer.six is present but its high_level import failed: {e} — likely a missing "
            "'cryptography'. pymupdf avoids this entirely.)")

def http_get_pdf(url, cap_bytes, timeout=45):
    host = urllib.parse.urlparse(url).netloc
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/pdf,application/octet-stream,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://{host}/" if host else "",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(cap_bytes)

def docs_from(path, doc_type):
    urls = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if doc_type and r.get("doc_type") != doc_type: continue
            u = r.get("file_url") or r.get("url")
            if u: urls.append(u)
    seen, out = set(), []
    for u in urls:
        if u not in seen: seen.add(u); out.append(u)
    return out

def main():
    ap = argparse.ArgumentParser(description="Stage B — mine identity out of manual/protocol PDFs (candidate; nothing minted).")
    ap.add_argument("--docs", required=True, help="page_documents.csv from page_reader")
    ap.add_argument("--doc-type", help="only mine this doc_type (e.g. manual, application-note); default all")
    ap.add_argument("--limit", type=int, default=40, help="max PDFs to read")
    ap.add_argument("--max-pages", type=int, default=30, help="max pages per PDF")
    ap.add_argument("--cap-mb", type=float, default=25.0, help="max MB downloaded per PDF")
    ap.add_argument("--no-bare-gtins", action="store_true", help="only keep labeled GTIN/UDI (drop coincidental bare)")
    ap.add_argument("--sleep", type=float, default=0.6)
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    docs = docs_from(a.docs, a.doc_type)[:a.limit]
    if not docs:
        raise SystemExit(f"no PDFs in {a.docs}" + (f" with doc_type={a.doc_type}" if a.doc_type else ""))
    extractor, libname = pick_extractor()      # fail early if no PDF lib; else pick one
    os.makedirs(a.outdir, exist_ok=True)
    af = open(os.path.join(a.outdir, "doc_attribution.csv"), "w", newline="")
    idf = open(os.path.join(a.outdir, "doc_identifiers.csv"), "w", newline="")
    sf = open(os.path.join(a.outdir, "doc_settings.csv"), "w", newline="")
    aw, iw, sw = csv.writer(af), csv.writer(idf), csv.writer(sf)
    aw.writerow(["source_doc", "page", "company_candidate", "evidence"])
    iw.writerow(["source_doc", "page", "id_kind", "value", "gtin_if_valid", "labeled", "state"])
    sw.writerow(["source_doc", "page", "param", "value", "unit", "pillar", "state"])

    cap = int(a.cap_mb * 1_000_000)
    n_attr = n_id = n_set = 0
    n_scanned = n_fail = 0
    print(f">> docmine  pdfs={len(docs)} · pdf-lib={libname}"
          + (f" · doc_type={a.doc_type}" if a.doc_type else "") + f" · outdir={a.outdir}")
    for i, url in enumerate(docs, 1):
        try:
            data = http_get_pdf(url, cap)
        except Exception as e:
            n_fail += 1; print(f"  [{i}] {url} -> {e}", file=sys.stderr); continue
        try:
            pages = extractor(data)[:a.max_pages]
        except Exception as e:
            n_fail += 1; print(f"  [{i}] parse {url} -> {e}", file=sys.stderr); continue
        text_total = 0
        for pageno, text in pages:
            if not text or not text.strip(): continue
            text_total += len(text)
            for name, ev in extract_attribution(text):
                aw.writerow([url, pageno, name, ev]); n_attr += 1
            for kind, val, gtin, labeled in extract_identifiers(text, want_bare_gtins=not a.no_bare_gtins):
                iw.writerow([url, pageno, kind, val, gtin, labeled, "candidate"]); n_id += 1
            for param, val, unit in extract_settings(text):
                sw.writerow([url, pageno, param, val, unit, "P3", "candidate"]); n_set += 1
        if text_total == 0:
            n_scanned += 1        # no extractable text -> scanned/image PDF
        if i % 10 == 0:
            af.flush(); idf.flush(); sf.flush()
            print(f"   ... {i}/{len(docs)} · attrib={n_attr} · ids={n_id} · settings={n_set} · scanned={n_scanned}")
        time.sleep(a.sleep)
    af.close(); idf.close(); sf.close()
    print(f">> done. attribution={n_attr} · identifiers={n_id} · settings={n_set}")
    print(f"   skipped: {n_scanned} scanned/no-text PDF(s), {n_fail} fetch/parse failure(s)")
    print("   doc_attribution.csv · doc_identifiers.csv · doc_settings.csv")
    print("   All candidate + provenanced (url+page). Labeled GTIN/UDI flagged; catalog/model/part are")
    print("   candidate identifiers (NOT GTINs); no GIAI minted; settings are candidate P3 method params.")

if __name__ == "__main__":
    main()
