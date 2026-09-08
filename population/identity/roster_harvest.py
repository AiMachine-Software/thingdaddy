#!/usr/bin/env python3
"""
roster_harvest.py — STAGE A: harvest standards-body member/supporter rosters into candidate parties.

The SiLA supported-vendors list and the Allotrope members list are ready-made rosters of real WHOs.
Each entry becomes a CANDIDATE party with a real path to a prefix — feed it to identity_xref
(`--parties`) to root, then use each rooted vendor's domain to seed website_agent. The roster roots
the graph; it also becomes the seed list for the whole harvest.

What it does: fetch each roster page (polite urllib), pull entries from anchors + nested <img>
alt/title (logo grids carry the name in alt= and the site in the link href). Emit one candidate row
per external vendor link. Deny-list social/CDN/self hosts. Dedup by registered domain. If a page is
JS-rendered and static fetch yields little, it REPORTS the low yield — it never fabricates names.

Laws: every entry candidate. "Supports SiLA / Allotrope member" is a candidate CLAIM the standards
body published; the vendor ratifies (R4). No prefix derived. Provenance = the roster URL.

Output (--out):  name, domain, role, claim, source_url, state

Usage:
  python3 roster_harvest.py --source sila       --out rosters/sila_parties.csv
  python3 roster_harvest.py --source allotrope  --out rosters/allotrope_parties.csv
  python3 roster_harvest.py --url https://sila-standard.org/members/ --role sila-vendor \
      --claim "supports SiLA" --out rosters/sila_parties.csv
"""
from __future__ import annotations
import argparse, csv, os, re, sys, time
import urllib.request, urllib.parse, urllib.error
from html.parser import HTMLParser

UA = "ThingDaddy-RosterHarvest/0.1 (public roster -> candidate parties; contact ops@thingdaddy.io)"

# Known public roster pages (URLs drift — override with --url if a default 404s / yields little).
SOURCES = {
    "sila": {
        "role": "sila-vendor", "claim": "listed SiLA supporter",
        "urls": ["https://sila-standard.org/members/",
                 "https://sila-standard.org/vendors/",
                 "https://sila-standard.org/"],
    },
    "allotrope": {
        "role": "allotrope-member", "claim": "listed Allotrope member",
        "urls": ["https://www.allotrope.org/members",
                 "https://www.allotrope.org/our-members",
                 "https://www.allotrope.org/"],
    },
}

# Hosts that are never a vendor entry (social, infra, the standards bodies themselves).
DENY_HOST = re.compile(
    r"(^|\.)(twitter|x|linkedin|facebook|instagram|youtube|youtu|vimeo|github|medium|"
    r"google|gstatic|googleapis|gmail|apple|microsoft|bing|cloudflare|cloudfront|akamai|"
    r"jsdelivr|unpkg|fontawesome|fonts|w3|schema|creativecommons|wordpress|wp|cdn|"
    r"sila-standard|allotrope|mailto)\b", re.I)
DENY_EXT = (".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".ico", ".woff", ".woff2", ".pdf", ".xml", ".zip")

def registered_domain(host):
    """Best-effort registered domain (last two labels; three for common 2-level ccTLDs)."""
    host = (host or "").lower().split(":")[0].strip(".")
    parts = host.split(".")
    if len(parts) < 2: return host
    two_level = {"co.uk","org.uk","ac.uk","com.au","co.jp","co.kr","com.br","co.in","com.cn","co.za"}
    if len(parts) >= 3 and ".".join(parts[-2:]) in two_level:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])

class RosterParser(HTMLParser):
    """Collect (href, best-name) for every anchor, using inner text and nested <img alt/title>."""
    def __init__(self):
        super().__init__()
        self.entries = []           # (href, name)
        self._href = None; self._txt = []; self._imgname = None
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a":
            self._href = d.get("href"); self._txt = []; self._imgname = None
        elif tag == "img" and self._href is not None:
            self._imgname = self._imgname or d.get("alt") or d.get("title")
    def handle_data(self, data):
        if self._href is not None: self._txt.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            name = " ".join("".join(self._txt).split()) or (self._imgname or "").strip()
            self.entries.append((self._href, name[:120]))
            self._href = None; self._txt = []; self._imgname = None

def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        if "html" not in ct and not url.lower().rstrip("/").endswith((".htm", ".html")):
            if "html" not in ct and ct:      # a non-HTML default URL — skip
                return ""
        return r.read(3_000_000).decode("utf-8", "replace")

def name_from_domain(domain):
    core = domain.rsplit(".", 1)[0].replace("-", " ")
    return core.title()

def harvest(url, role, claim, host_of_page):
    try:
        html = http_get(url)
    except Exception as e:
        print(f"  [roster] {url} -> {e}", file=sys.stderr); return []
    if not html:
        return []
    p = RosterParser(); p.feed(html)
    by_domain = {}
    for href, name in p.entries:
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")): continue
        full = urllib.parse.urljoin(url, href)
        pr = urllib.parse.urlparse(full)
        if pr.scheme not in ("http", "https"): continue
        host = pr.netloc
        if not host or host == host_of_page: continue          # internal link, not a vendor
        if DENY_HOST.search(host): continue
        if full.lower().endswith(DENY_EXT): continue
        dom = registered_domain(host)
        if not dom or "." not in dom: continue
        nm = name if (name and len(name) > 1 and not name.lower().startswith("http")) else name_from_domain(dom)
        # keep the first (usually the logo/name link); prefer a longer real name if we see one later
        if dom not in by_domain or (len(nm) > len(by_domain[dom][0]) and not by_domain[dom][0]):
            by_domain.setdefault(dom, (nm, full))
    rows = [[nm, dom, role, claim, url, "candidate"] for dom, (nm, _link) in by_domain.items()]
    return rows

def main():
    ap = argparse.ArgumentParser(description="Harvest a standards-body roster into candidate parties.")
    ap.add_argument("--source", choices=list(SOURCES.keys()), help="built-in roster (sila|allotrope)")
    ap.add_argument("--url", help="explicit roster URL (overrides / augments --source)")
    ap.add_argument("--role", help="role label when using --url (e.g. sila-vendor)")
    ap.add_argument("--claim", help="candidate claim when using --url")
    ap.add_argument("--out", default="roster_parties.csv")
    ap.add_argument("--sleep", type=float, default=0.5)
    a = ap.parse_args()

    if not a.source and not a.url:
        raise SystemExit("pass --source sila|allotrope, or --url with --role/--claim")

    jobs = []   # (url, role, claim)
    if a.source:
        s = SOURCES[a.source]
        for u in s["urls"]: jobs.append((u, a.role or s["role"], a.claim or s["claim"]))
    if a.url:
        jobs.insert(0, (a.url, a.role or (SOURCES.get(a.source or "", {}).get("role") or "roster-member"),
                        a.claim or (SOURCES.get(a.source or "", {}).get("claim") or "listed roster member")))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    seen_dom, rows = set(), []
    for url, role, claim in jobs:
        host = urllib.parse.urlparse(url).netloc
        got = harvest(url, role, claim, host)
        added = 0
        for r in got:
            if r[1] in seen_dom: continue
            seen_dom.add(r[1]); rows.append(r); added += 1
        print(f"   {url} -> {added} candidate parties" + ("" if added else "  (low/zero yield — page may be JS-rendered; try --url)"))
        if rows and a.source:     # first URL that yields is enough for a built-in source
            break
        time.sleep(a.sleep)

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "domain", "role", "claim", "source_url", "state"])
        w.writerows(rows)

    print(f">> {len(rows)} candidate parties -> {a.out}")
    if not rows:
        print("   0 harvested. The roster is likely a JS-rendered logo grid — pass the real members URL "
              "with --url, or hand the page to the miner later. Nothing fabricated.")
    else:
        print("   All candidate + sourced (provenance = the roster URL). Root them: "
              f"identity_xref.py --parties {a.out} --gleif")

if __name__ == "__main__":
    main()
