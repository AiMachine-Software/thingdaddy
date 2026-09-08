#!/usr/bin/env python3
"""
spa_extract.py — WS2 extractor value: recover identity from JS-rendered (SPA) pages.

The gap: static harvest returns an empty shell on single-page-app sites (Thorne class),
so page_reader finds no GTINs. But most SPA product pages STILL embed their identity in
structured data the site itself publishes. So we try, in order:

  Tier 0  detect_spa()          — is this an empty JS shell?
  Tier 1  extract_structured()  — JSON-LD Product / __NEXT_DATA__ / microdata / og:  (NO browser, stdlib only)
  Tier 2  render_headless()     — Playwright/Chromium fallback, only if Tier 1 is dry

Every GTIN found is a CANDIDATE and is passed through the MO-band gate (identity_xref).
Nothing minted, nothing fabricated. This reads structured data the page publishes — it is
NOT bot-block evasion; a hard 403 is still a hard 403 and we do not engineer around it.

Usage:
  python3 spa_extract.py --html page.html [--url https://site/p]   # probe a saved page
  python3 spa_extract.py --render https://site/product            # headless-render then probe
"""
from __future__ import annotations
import argparse, json, re, sys, html as _html

# --- MO-band gate (reuse the registrar's own gate; no fabrication) -----------
try:
    from identity_xref import to_gtin14, mo_for_gtin
except Exception:
    def to_gtin14(d): return d.zfill(14)
    def mo_for_gtin(g14):  # minimal fallback if run standalone
        try: p3 = int(g14[1:4])
        except ValueError: return ""
        return "GS1 (band table unavailable)" if 1 <= p3 <= 999 else ""

def _check_digit_ok(g14):
    if not g14.isdigit() or len(g14) != 14: return False
    body = [int(c) for c in g14[:-1]]
    s = sum(d * (3 if (len(body) - 1 - i) % 2 == 0 else 1) for i, d in enumerate(body))
    return (10 - (s % 10)) % 10 == int(g14[-1])

def gate_gtin(raw):
    """A scraped number -> CANDIDATE only if valid check digit AND assigned GS1 band."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) not in (8, 12, 13, 14): return None
    g14 = to_gtin14(digits)
    band = mo_for_gtin(g14)
    ok = _check_digit_ok(g14)
    return {"raw": raw, "gtin14": g14, "band": band, "check_digit": ok,
            "verdict": "CANDIDATE" if (band and ok) else "REJECT"}

# --- Tier 0: is this an empty SPA shell? -------------------------------------
_SPA_ROOTS = [r'id=["\']root["\']', r'id=["\']__next["\']', r'id=["\']app["\']',
              r'data-reactroot', r'ng-app', r'data-server-rendered', r'id=["\']q-app["\']']
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

def _visible_text(html):
    h = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", h))).strip()

def detect_spa(html):
    vis = _visible_text(html)
    shell = any(re.search(p, html, re.I) for p in _SPA_ROOTS)
    n_scripts = len(re.findall(r"<script", html, re.I))
    # empty-ish visible body + a framework mount point + script-heavy = SPA shell
    likely = (len(vis) < 400 and (shell or n_scripts >= 8))
    return {"likely_spa": likely, "visible_chars": len(vis), "shell_marker": shell, "scripts": n_scripts}

# --- Tier 1: structured-data probe (no browser) ------------------------------
_GTIN_KEYS = ("gtin14", "gtin13", "gtin12", "gtin8", "gtin", "gtinValue", "ean", "upc", "barcode")
_ID_KEYS = ("sku", "mpn", "productid", "productID", "product_id", "itemNumber", "item_number")

def _walk(obj, gtins, ids, names):
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if isinstance(v, (str, int)) and str(v).strip():
                if kl in [g.lower() for g in _GTIN_KEYS]: gtins.append(str(v))
                elif kl in [i.lower() for i in _ID_KEYS]: ids.append(str(v))
                elif kl == "name" and isinstance(v, str) and 2 < len(v) < 200: names.append(v)
            else:
                _walk(v, gtins, ids, names)
    elif isinstance(obj, list):
        for it in obj: _walk(it, gtins, ids, names)

def _json_blobs(html):
    blobs = []
    # JSON-LD
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         html, re.I | re.S):
        blobs.append(m.group(1))
    # Next.js / Nuxt / generic embedded state
    for pat in (r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>',
                r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>',
                r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>'):
        for m in re.finditer(pat, html, re.I | re.S):
            blobs.append(m.group(1))
    return blobs

def _microdata_gtins(html):
    out = []
    for m in re.finditer(r'itemprop=["\'](gtin1[234]|gtin8|gtin)["\'][^>]*?(?:content=["\']([^"\']+)["\']|>([^<]+))',
                         html, re.I):
        out.append((m.group(2) or m.group(3) or "").strip())
    return [x for x in out if x]

def _og(html, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)["\']' % re.escape(prop),
                  html, re.I)
    return m.group(1).strip() if m else ""

def extract_structured(html, url=""):
    gtins, ids, names = [], [], []
    for blob in _json_blobs(html):
        try:
            data = json.loads(blob.strip())
        except Exception:
            continue
        _walk(data, gtins, ids, names)
    gtins += _microdata_gtins(html)
    title = _og(html, "og:title")
    if title: names.insert(0, title)
    # de-dupe, gate the gtins
    seen, gated = set(), []
    for g in gtins:
        key = re.sub(r"\D", "", g)
        if not key or key in seen: continue
        seen.add(key)
        r = gate_gtin(g)
        if r: gated.append(r)
    ids = list(dict.fromkeys(i for i in ids if i))
    names = list(dict.fromkeys(n.strip() for n in names if n and n.strip()))
    return {"url": url, "product_name": names[0] if names else "",
            "gtins": gated, "other_ids": ids[:20], "names_seen": names[:5],
            "candidates": [g for g in gated if g["verdict"] == "CANDIDATE"]}

# --- Tier 2: headless render fallback (optional dependency) -------------------
def render_headless(url, wait="networkidle", timeout_ms=20000):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None, ("playwright not installed. Tier 1 needs nothing; for Tier 2 run:\n"
                      "  pip install playwright && playwright install chromium")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page(user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"))
            pg.goto(url, wait_until=wait, timeout=timeout_ms)
            html = pg.content()
            b.close()
            return html, None
    except Exception as e:
        return None, f"headless render failed: {e}"

# --- CLI ---------------------------------------------------------------------
def _report(html, url):
    spa = detect_spa(html)
    res = extract_structured(html, url)
    print(f">> SPA detect: likely={spa['likely_spa']} (visible_chars={spa['visible_chars']}, "
          f"shell={spa['shell_marker']}, scripts={spa['scripts']})")
    print(f">> product: {res['product_name'] or '(none found)'}")
    if res["gtins"]:
        print(f">> GTIN candidates ({len(res['candidates'])}/{len(res['gtins'])} pass the gate):")
        for g in res["gtins"]:
            print(f"     {g['raw']:>16} -> {g['gtin14']}  {g['band'] or '(no band)':22} "
                  f"chk={'ok' if g['check_digit'] else 'BAD'}  {g['verdict']}")
    else:
        print(">> no embedded GTINs in structured data")
    if res["other_ids"]:
        print(f">> other ids: {', '.join(res['other_ids'][:8])}")
    return res

def main():
    ap = argparse.ArgumentParser(description="Recover identity from SPA/JS-rendered pages (structured-data first)")
    ap.add_argument("--html", help="path to a saved page")
    ap.add_argument("--url", default="", help="base url (for records)")
    ap.add_argument("--render", help="URL to headless-render then probe (needs playwright)")
    a = ap.parse_args()
    if a.render:
        html, err = render_headless(a.render)
        if err: print(err); sys.exit(1 if html is None else 0)
        _report(html, a.render)
    elif a.html:
        with open(a.html, encoding="utf-8", errors="replace") as f: html = f.read()
        _report(html, a.url)
    else:
        ap.error("give --html <file> or --render <url>")

if __name__ == "__main__":
    main()
