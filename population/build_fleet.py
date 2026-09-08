#!/usr/bin/env python3
"""
build_fleet.py — build MANY ThingSites: run website_agent across a fleet, in PARALLEL, then render
one gallery index. Fast skeleton mode + concurrency = many halls in minutes.

The per-company engine (website_agent) is the unit; this runs it N-wide across a fleet. Each
ThingSite is CANDIDATE + sourced; nothing minted.

Speed levers:
  --fast          skeleton per company (sitemap -> ThingSite + P5 graph; skips page-read/mine). ~10-20s each.
  --parallel N    run N companies at once (default 8). Your Mac handles many; this is the 10x.
  --limit / --pages-limit   shrink the crawl for speed.

Fleet source (first that's set wins):
  --domains FILE  one company per line: "domain" | "domain|Name" | "domain|Name|accent"
  --companies "domain|Name|accent, ..."     inline
  (else) a large built-in list of real lab / analytical / instrument companies.

Outputs (in --outroot, default population/sites):
  <slug>/...              each company's ThingSite + graphs + palette
  fleet_manifest.json     rollup
  fleet_index.html        the gallery — one card per hall

Usage:
  python3 build_fleet.py --fast --parallel 10                 # many skeletons, fast
  python3 build_fleet.py --fast --parallel 12 --domains my_companies.txt
  python3 build_fleet.py --parallel 6 --limit 2000            # deeper, still parallel
"""
from __future__ import annotations
import argparse, csv, hashlib, html, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "website_agent.py")

# Real lab-automation / analytical-instrument companies in the SiLA / Allotrope orbit.
# Representative ecosystem members — roster_harvest (Stage A) is the AUTHORITATIVE membership source.
DEFAULT_FLEET = [
    "tecan.com|Tecan", "hamiltoncompany.com|Hamilton Company", "agilent.com|Agilent Technologies",
    "sartorius.com|Sartorius", "waters.com|Waters Corporation", "bruker.com|Bruker",
    "mt.com|Mettler Toledo", "eppendorf.com|Eppendorf", "beckman.com|Beckman Coulter",
    "bio-rad.com|Bio-Rad Laboratories", "revvity.com|Revvity", "cytiva.com|Cytiva",
    "shimadzu.com|Shimadzu", "promega.com|Promega", "qiagen.com|QIAGEN", "illumina.com|Illumina",
    "moleculardevices.com|Molecular Devices", "beckmancoulter.com|Beckman Coulter Life Sciences",
    "analytik-jena.com|Analytik Jena", "metrohm.com|Metrohm", "gilson.com|Gilson",
    "10xgenomics.com|10x Genomics", "danaher.com|Danaher", "corning.com|Corning Life Sciences",
]

def slugify(s): return ("".join(c.lower() if c.isalnum() else "-" for c in s)[:50].strip("-")) or "company"
def have(p): return os.path.exists(p) and os.path.getsize(p) > 0
def esc(s): return html.escape(str(s if s is not None else ""))

def name_from_domain(d):
    core = d.split("//")[-1].split("/")[0].replace("www.", "").rsplit(".", 1)[0]
    return core.replace("-", " ").title()
def accent_for(name):
    return hashlib.sha1(name.encode()).hexdigest()[:6]

def parse_spec(chunk):
    parts = [p.strip() for p in chunk.split("|")]
    if not parts or not parts[0]: return None
    domain = parts[0].replace("https://", "").replace("http://", "").strip("/")
    name = parts[1] if len(parts) > 1 and parts[1] else name_from_domain(domain)
    accent = parts[2] if len(parts) > 2 and parts[2] else accent_for(name)
    return (domain, name, accent)

def load_fleet(a):
    raw = []
    if a.domains and os.path.exists(a.domains):
        with open(a.domains) as f:
            raw = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    elif a.companies:
        raw = [c for c in a.companies.split(",")]
    else:
        raw = DEFAULT_FLEET
    fleet, seen = [], set()
    for chunk in raw:
        c = parse_spec(chunk)
        if c and c[0] not in seen:
            seen.add(c[0]); fleet.append(c)
    return fleet

def build_one(company, a):
    domain, name, accent = company
    slug = slugify(name)
    out = os.path.join(a.outroot, slug)
    cmd = ["python3", AGENT, "--domain", domain, "--name", name,
           "--limit", str(a.limit), "--pages-limit", str(a.pages_limit), "--outdir", out, "--accent", accent]
    if a.fast:  cmd.append("--fast")
    if a.mine:  cmd.append("--mine")
    if a.root:  cmd.append("--root")
    if a.gleif: cmd.append("--gleif")
    if a.force: cmd.append("--force")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
        ok = proc.returncode == 0
        err = "" if ok else (proc.stderr or proc.stdout or "")[-160:]
    except subprocess.TimeoutExpired:
        ok, err = False, "timeout"
    pal = {}
    ppath = os.path.join(out, "content_palette.json")
    if have(ppath):
        try:
            with open(ppath) as f: pal = json.load(f)
        except Exception: pal = {}
    return {"name": name, "domain": domain, "slug": slug, "accent": accent,
            "ok": ok, "err": err, "palette": pal}

def main():
    ap = argparse.ArgumentParser(description="Build a fleet of ThingSites in parallel + a gallery.")
    ap.add_argument("--domains", help="file: one company per line (domain | Name | accent)")
    ap.add_argument("--companies", help='inline: "domain|Name|accent, ..."')
    ap.add_argument("--outroot", default=os.path.join(HERE, "sites"))
    ap.add_argument("--parallel", type=int, default=8, help="companies to build at once")
    ap.add_argument("--limit", type=int, default=2500)
    ap.add_argument("--pages-limit", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=600, help="per-company seconds")
    ap.add_argument("--fast", action="store_true", help="skeleton mode (sitemap->ThingSite; fast)")
    ap.add_argument("--mine", action="store_true"); ap.add_argument("--root", action="store_true")
    ap.add_argument("--gleif", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    fleet = load_fleet(a)
    os.makedirs(a.outroot, exist_ok=True)
    mode = "fast/skeleton" if a.fast else ("deep(mine+root)" if (a.mine or a.root) else "standard")
    print(f">> FLEET BUILD · {len(fleet)} companies · mode={mode} · parallel={a.parallel}")

    manifest, done = [], 0
    with ThreadPoolExecutor(max_workers=a.parallel) as ex:
        futs = {ex.submit(build_one, c, a): c for c in fleet}
        for fut in as_completed(futs):
            m = fut.result(); manifest.append(m); done += 1
            p = m["palette"] or {}
            tag = "ok " if m["ok"] else "FAIL"
            print(f"   [{done}/{len(fleet)}] {tag} {m['name']:<26} "
                  f"urls={p.get('sitemap_urls',0):<6} docs={p.get('documents_files',0) or p.get('documents_sitemap',0):<5} "
                  f"edges={p.get('edges',0):<4} bind={p.get('binding_sets',0):<4}"
                  + ("" if m["ok"] else f"  · {m['err'][:80]}"))

    manifest.sort(key=lambda m: (not m["ok"], m["name"]))
    with open(os.path.join(a.outroot, "fleet_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # --- gallery
    cards = ""
    tot_urls = tot_docs = tot_edges = tot_bind = 0
    for m in manifest:
        p = m["palette"] or {}; slug = m["slug"]; acc = "#" + (m["accent"] or "334155")
        urls = p.get("sitemap_urls", 0); docs = p.get("documents_files", 0) or p.get("documents_sitemap", 0)
        edges = p.get("edges", 0); binds = p.get("binding_sets", 0); pills = p.get("pillars", {}) or {}
        rooted = p.get("rooted"); mined = p.get("mined") or {}
        tot_urls += urls; tot_docs += docs; tot_edges += edges; tot_bind += binds
        links = []
        for label, fn in [("ThingSite", f"{slug}_ThingSite.html"), ("P5 Graph", f"{slug}_P5_Graph.html"),
                          ("Binding Sets", f"{slug}_Binding_Sets.html"), ("Mined Graph", f"{slug}_Mined_Graph.html")]:
            if have(os.path.join(a.outroot, slug, fn)):
                links.append(f'<a href="{esc(slug)}/{esc(fn)}">{esc(label)}</a>')
        pill_bar = "".join(f'<span class="pl">{esc(k)} {v}</span>' for k, v in sorted(pills.items()))
        badge = '<span class="ok">built</span>' if m["ok"] else '<span class="bad">failed</span>'
        rootbadge = '<span class="rooted">ROOTED</span>' if rooted else '<span class="cand">candidate</span>'
        minednote = (f'<div class="mined">mined: {mined.get("labeled_gtins",0)} gtins · '
                     f'{mined.get("settings",0)} settings · {mined.get("identifiers",0)} ids</div>' if mined else "")
        cards += (f'<div class="card" style="--acc:{acc}"><div class="ct"><b>{esc(m["name"])}</b> {badge} {rootbadge}</div>'
                  f'<div class="dm">{esc(m["domain"])}</div>'
                  f'<div class="stats"><span>{urls:,} urls</span><span>{docs:,} docs</span>'
                  f'<span>{edges:,} edges</span><span>{binds:,} bindings</span></div>'
                  f'<div class="pills">{pill_bar}</div>{minednote}'
                  f'<div class="links">{" · ".join(links) or "<span class=muted>no artifacts</span>"}</div></div>')

    built = sum(1 for m in manifest if m["ok"])
    page = FLEET_HTML.replace("__CARDS__", cards).replace("__N__", str(len(manifest))) \
        .replace("__BUILT__", str(built)).replace("__URLS__", f"{tot_urls:,}").replace("__DOCS__", f"{tot_docs:,}") \
        .replace("__EDGES__", f"{tot_edges:,}").replace("__BIND__", f"{tot_bind:,}")
    ipath = os.path.join(a.outroot, "fleet_index.html")
    with open(ipath, "w") as f: f.write(page)

    print(f"\n>> FLEET DONE · {built}/{len(manifest)} built")
    print(f"   totals: urls={tot_urls:,} · docs={tot_docs:,} · edges={tot_edges:,} · bindings={tot_bind:,}")
    print(f"   -> gallery : {ipath}")
    print("   Each hall candidate + sourced; nothing minted. `open sites/fleet_index.html`")

FLEET_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ThingDaddy · Fleet</title>
<style>
:root{--ink:#0e1a2b;--dim:#5a6b82}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0e1a2b;background:#eef3f9}
.wrap{max-width:1140px;margin:0 auto;padding:26px 26px 80px}
header{border-bottom:2px solid #0e1a2b;padding-bottom:12px}
header .t{font-size:22px;font-weight:800}header .s{font-size:13px;color:#5a6b82;margin-top:4px}
.tot{display:flex;gap:14px;margin:16px 0 20px;flex-wrap:wrap}
.tot div{background:#fff;border:1px solid #d6e0ee;border-radius:10px;padding:10px 16px}
.tot b{display:block;font-size:22px}.tot span{font-size:11px;color:#5a6b82;text-transform:uppercase;letter-spacing:.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:#fff;border:1px solid #d6e0ee;border-left:5px solid var(--acc);border-radius:12px;padding:13px 15px}
.ct{font-size:15px}.ct b{color:var(--acc)}
.ok{font-size:10px;background:#0d7a52;color:#fff;border-radius:10px;padding:1px 7px;margin-left:4px}
.bad{font-size:10px;background:#b3261e;color:#fff;border-radius:10px;padding:1px 7px;margin-left:4px}
.rooted{font-size:10px;background:#0a6;color:#fff;border-radius:10px;padding:1px 7px}
.cand{font-size:10px;background:#eef2f8;color:#b4700a;border:1px solid #f0d9b8;border-radius:10px;padding:1px 7px}
.dm{font-size:12px;color:#5a6b82;margin:2px 0 8px}
.stats{display:flex;gap:10px;font-size:12.5px;font-weight:700;flex-wrap:wrap}
.pills{margin:8px 0 4px;display:flex;gap:4px;flex-wrap:wrap}
.pl{font-size:10px;background:#eef3f9;border:1px solid #d6e0ee;border-radius:6px;padding:1px 5px;color:#5a6b82}
.mined{font-size:11px;color:#0a6cc4;margin-top:4px}
.links{margin-top:8px;font-size:12.5px}.links a{color:var(--acc);text-decoration:none;border-bottom:1px solid #d6e0ee}
.muted{color:#93a3b8}
footer{margin-top:24px;font-size:12px;color:#8397b0}
</style></head><body><div class="wrap">
<header><div class="t">ThingDaddy · Fleet</div>
<div class="s">__BUILT__ / __N__ halls pre-built from public sources, in parallel. Each candidate + sourced; nothing minted.</div></header>
<div class="tot">
<div><b>__N__</b><span>companies</span></div><div><b>__URLS__</b><span>urls</span></div>
<div><b>__DOCS__</b><span>documents</span></div><div><b>__EDGES__</b><span>edges</span></div>
<div><b>__BIND__</b><span>binding sets</span></div></div>
<div class="grid">__CARDS__</div>
<footer>Pre-built candidate ThingSites · projected from each company's public site map · powered by ThingDaddy.</footer>
</div></body></html>"""

if __name__ == "__main__":
    main()
