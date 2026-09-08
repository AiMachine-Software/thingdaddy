#!/usr/bin/env python3
"""
render_fleet.py — rebuild the fleet gallery (fleet_index.html + fleet_manifest.json) from the
CURRENT content_palette.json files. No network, no re-harvest — just re-reads what's on disk, so
it reflects whatever the mine/root/re-render produced. Adds honest TIER badges (deep/medium/thin/
empty) and VERIFIED/candidate root badges (from verified_prefixes.json).

Usage:  python3 render_fleet.py [--sites sites] [--out sites/fleet_index.html]
"""
from __future__ import annotations
import argparse, csv, json, os, re, html
from collections import Counter

PILL = ["P1", "P2", "P3", "P4", "P5"]

def esc(s): return html.escape(str(s if s is not None else ""))

def bare_domain(d):
    d = re.sub(r"^https?://", "", (d or "").strip().lower()).split("/")[0]
    return re.sub(r"^www\.", "", d)

def load_verified(sites_dir):
    for c in (os.path.join(sites_dir, "..", "standards", "verified_prefixes.json"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "standards", "verified_prefixes.json"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "verified_prefixes.json")):
        if os.path.exists(c):
            try:
                with open(c) as f: return json.load(f)
            except Exception: pass
    return {}

def tier(p):
    urls = int(p.get("sitemap_urls") or 0)
    mined = p.get("mined") or {}
    settings = int(mined.get("settings") or 0) if isinstance(mined, dict) else 0
    binds = int(p.get("binding_sets") or 0)
    if urls == 0: return ("empty", "#b4700a", "empty — re-harvest")
    if settings > 0: return ("deep", "#137a4c", "deep · mined PDFs")
    if binds > 0: return ("medium", "#1f6feb", "medium · bindings")
    return ("thin", "#5a6b82", "thin · pages only")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default="sites")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = a.out or os.path.join(a.sites, "fleet_index.html")
    verified = load_verified(a.sites)

    rows = []
    for slug in sorted(os.listdir(a.sites)):
        pal = os.path.join(a.sites, slug, "content_palette.json")
        if not os.path.exists(pal): continue
        try:
            with open(pal) as f: p = json.load(f)
        except Exception: continue
        p["_slug"] = slug
        rows.append(p)

    tot = Counter()
    cards = ""
    n_deep = n_verified = 0
    for p in rows:
        slug = p["_slug"]; name = p.get("company") or slug; dom = p.get("domain") or ""
        urls = int(p.get("sitemap_urls") or 0); docs = int(p.get("documents_sitemap") or 0)
        edges = int(p.get("edges") or 0); binds = int(p.get("binding_sets") or 0)
        gtins = int(p.get("gtins") or 0)
        mined = p.get("mined") or {}
        settings = int(mined.get("settings") or 0) if isinstance(mined, dict) else 0
        tkey, tcol, tlbl = tier(p)
        if tkey == "deep": n_deep += 1
        tot["urls"] += urls; tot["docs"] += docs; tot["edges"] += edges
        tot["binds"] += binds; tot["settings"] += settings
        # root badge
        v = verified.get(bare_domain(dom))
        if v and str(v.get("status", "")).lower() == "verified":
            n_verified += 1
            rootbadge = f'<span class="b ok">✓ ROOT {esc(v.get("prefix",""))}</span>'
        else:
            rootbadge = '<span class="b cand">◇ candidate</span>'
        # pillar bar
        pills = p.get("pillars") or {}
        pill_bar = "".join(f'<span class="pl">{k} {int(pills.get(k,0))}</span>' for k in PILL if pills.get(k))
        # links to rich views that exist
        d = os.path.join(a.sites, slug)
        links = []
        for label, suf in (("ThingSite", "_ThingSite.html"), ("P5 Graph", "_P5_Graph.html"),
                           ("Binding Sets", "_Binding_Sets.html"), ("Mined Graph", "_Mined_Graph.html"), ("Cloud & Edge", "_Cloud_Edge.html")):
            if os.path.exists(os.path.join(d, slug + suf)):
                links.append(f'<a href="{slug}/{slug}{suf}">{label}</a>')
        minednote = (f'<div class="mn">mined: {int(mined.get("labeled_gtins") or 0)} gtins · '
                     f'{int(mined.get("identifiers") or 0)} ids · {settings} settings</div>'
                     if settings else "")
        cards += (f'<div class="card" style="--acc:{tcol}">'
                  f'<div class="ct"><b>{esc(name)}</b> <span class="b tier">{esc(tlbl)}</span> {rootbadge}</div>'
                  f'<div class="dm">{esc(dom)}</div>'
                  f'<div class="stats"><span>{urls:,} urls</span><span>{docs:,} docs</span>'
                  f'<span>{gtins:,} gtins</span><span>{edges:,} edges</span><span>{binds:,} bindings</span></div>'
                  f'<div class="pills">{pill_bar}</div>{minednote}'
                  f'<div class="links">{" · ".join(links) or "<span class=muted>no artifacts</span>"}</div></div>')

    manifest = {"companies": len(rows), "deep": n_deep, "verified_roots": n_verified,
                "totals": dict(tot)}
    with open(os.path.join(a.sites, "fleet_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ThingDaddy · Fleet</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0e2a4a;background:#eef2f7}}
.wrap{{max-width:1120px;margin:0 auto;padding:22px 24px 70px}}
header{{border-bottom:2px solid #0e2a4a;padding-bottom:12px}}
.t{{font-size:22px;font-weight:800}} .s{{color:#5a6b82;font-size:13px;margin-top:3px}}
.tot{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}}
.tot div{{background:#fff;border:1px solid #d6e0ee;border-radius:10px;padding:10px 16px;min-width:96px}}
.tot b{{display:block;font-size:22px;font-weight:800}} .tot span{{font-size:11px;color:#5a6b82;text-transform:uppercase;letter-spacing:.04em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}}
.card{{background:#fff;border:1px solid #d6e0ee;border-left:5px solid var(--acc);border-radius:12px;padding:13px 15px}}
.ct{{font-size:15px}} .ct b{{margin-right:6px}} .dm{{color:#5a6b82;font-size:12px;margin:2px 0 8px;font-family:ui-monospace,Menlo,monospace}}
.b{{display:inline-block;font-size:10.5px;font-weight:700;border-radius:20px;padding:1px 8px;vertical-align:middle}}
.b.tier{{background:#eef2f8;color:var(--acc);border:1px solid #dde5ef}}
.b.ok{{background:#e8f6ee;color:#137a4c;border:1px solid #bfe6cd;font-family:ui-monospace,Menlo,monospace}}
.b.cand{{background:#fbf7ef;color:#b4700a;border:1px solid #ecdcbc}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;font-size:12.5px;font-weight:600;margin:2px 0}}
.stats span{{color:#0e2a4a}} .pills{{margin:6px 0}}
.pl{{display:inline-block;background:#f4f8fc;border:1px solid #e2eaf3;border-radius:5px;padding:0 6px;font-size:11px;margin:2px 4px 0 0;color:#5a6b82}}
.mn{{font-size:11.5px;color:#137a4c;margin:4px 0}}
.links{{margin-top:6px;font-size:12.5px}} .links a{{color:#1f6feb;text-decoration:none;border-bottom:1px solid #cfe0fb}} .muted{{color:#8397b0}}
footer{{margin-top:24px;color:#8397b0;font-size:12px}}
</style></head><body><div class="wrap">
<header><div class="t">ThingDaddy · Fleet</div>
<div class="s">{len(rows)} ThingSites from public sources · {n_deep} deep · {n_verified} verified root · rest candidate. Nothing minted; candidate shown as candidate.</div></header>
<div class="tot">
<div><b>{len(rows)}</b><span>companies</span></div>
<div><b>{tot['urls']:,}</b><span>urls</span></div>
<div><b>{tot['docs']:,}</b><span>documents</span></div>
<div><b>{tot['edges']:,}</b><span>edges</span></div>
<div><b>{tot['binds']:,}</b><span>binding sets</span></div>
<div><b>{tot['settings']:,}</b><span>mined settings</span></div></div>
<div class="grid">{cards}</div>
<footer>Fleet gallery · rebuilt from current palettes (no re-harvest) · tiers + roots honest. Powered by ThingDaddy.</footer>
</div></body></html>"""
    with open(out, "w") as f: f.write(page)
    print(f">> fleet gallery -> {out}")
    print(f"   {len(rows)} companies · {n_deep} deep · {n_verified} verified root")
    print(f"   totals: urls={tot['urls']:,} · docs={tot['docs']:,} · edges={tot['edges']:,} · "
          f"bindings={tot['binds']:,} · mined-settings={tot['settings']:,}")

if __name__ == "__main__":
    main()
