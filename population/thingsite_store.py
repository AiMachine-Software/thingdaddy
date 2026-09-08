#!/usr/bin/env python3
"""
thingsite_store.py — the ThingSite create/store manager. How sites are MADE and KEPT.

The fleet writes loose HTML into sites/<slug>/. That's not a store — it's a pile. This turns it into
a managed, validated, identity-keyed catalog:

  * REGISTER — each site becomes a template-bound INSTANCE RECORD (id, location/domain, status,
    palette, artifacts, provenance), not a folder of files.
  * VALIDATE — record-level conformance against the `thingsite` template: has a location/domain, has
    content, has its artifacts. Empty sites are flagged, not silently kept.
  * STORE — one indexed catalog (thingsite_store.json), keyed by identity (slug/domain, proxy for the
    SGLN). The store is the source of truth; the HTML is a projected artifact.
  * MANAGE — a workspace UI: every site with status badges (populated/empty · rooted/candidate ·
    conforms/incomplete), palette stats, artifact links, and fleet totals.

Node-level SHACL validation of a fully-populated instance is meta_configurator's job; this manages
the site LIFECYCLE + catalog. Candidate; nothing minted. Provenance = the harvest source.

Usage:
  python3 thingsite_store.py --sites sites                 # scan + catalog all sites
  python3 thingsite_store.py --sites sites --register sites/tecan   # (re)register one
"""
from __future__ import annotations
import argparse, csv, glob, html, json, os, time

TEMPLATE = "thingsite"; ONTOLOGY = "afo-lab"
ARTIFACTS = [("thingsite", "_ThingSite.html"), ("p5_graph", "_P5_Graph.html"),
             ("binding_sets", "_Binding_Sets.html"), ("mined_graph", "_Mined_Graph.html")]

def esc(s): return html.escape(str(s if s is not None else ""))
def have(p): return os.path.exists(p) and os.path.getsize(p) > 0

def load_palette(site_dir):
    p = os.path.join(site_dir, "content_palette.json")
    if not have(p): return None
    try:
        with open(p) as f: return json.load(f)
    except Exception: return None

def find_artifacts(site_dir, slug):
    out = {}
    for key, suffix in ARTIFACTS:
        cand = os.path.join(site_dir, f"{slug}{suffix}")
        if have(cand): out[key] = os.path.relpath(cand, os.path.dirname(site_dir))
        else:
            g = glob.glob(os.path.join(site_dir, f"*{suffix}"))
            if g and have(g[0]): out[key] = os.path.relpath(g[0], os.path.dirname(site_dir))
    return out

def validate_record(rec):
    """Record-level conformance against the thingsite template (what's knowable from a harvest)."""
    issues = []
    if not rec.get("domain"): issues.append("no location/domain anchor (SGLN proxy)")
    pal = rec.get("palette") or {}
    if (pal.get("sitemap_urls", 0) or 0) == 0 and (pal.get("documents", 0) or 0) == 0:
        issues.append("empty — 0 urls / 0 docs (needs harvest; sitemap likely blocked)")
    if "thingsite" not in (rec.get("artifacts") or {}):
        issues.append("no ThingSite artifact rendered")
    return {"conforms": not issues, "issues": issues}

def register(site_dir):
    slug = os.path.basename(site_dir.rstrip("/"))
    pal = load_palette(site_dir)
    if pal is None: return None
    palette = {"sitemap_urls": pal.get("sitemap_urls", 0),
               "documents": pal.get("documents_files", 0) or pal.get("documents_sitemap", 0),
               "edges": pal.get("edges", 0), "binding_sets": pal.get("binding_sets", 0),
               "gtins": pal.get("gtins", 0), "mined": pal.get("mined")}
    rec = {"id": slug, "name": pal.get("company", slug), "domain": pal.get("domain", ""),
           "template": TEMPLATE, "ontology": ONTOLOGY,
           "status": "rooted" if pal.get("rooted") else "candidate",
           "palette": palette, "artifacts": find_artifacts(site_dir, slug),
           "provenance": {"source": "harvest", "domain": pal.get("domain", "")}}
    rec["conformance"] = validate_record(rec)
    return rec

def scan(sites_root):
    recs = []
    for pal in sorted(glob.glob(os.path.join(sites_root, "*", "content_palette.json"))):
        rec = register(os.path.dirname(pal))
        if rec: recs.append(rec)
    return recs

def main():
    ap = argparse.ArgumentParser(description="Manage how ThingSites are created + stored.")
    ap.add_argument("--sites", default="sites")
    ap.add_argument("--register", help="register/refresh a single site dir")
    ap.add_argument("--stamp", default="", help="ISO time to stamp the catalog (optional)")
    a = ap.parse_args()

    catalog_path = os.path.join(a.sites, "thingsite_store.json")
    if a.register:
        recs = scan(a.sites)               # rebuild whole catalog (simple + idempotent)
    else:
        recs = scan(a.sites)
    if not recs:
        raise SystemExit(f"no ThingSites under {a.sites}/ (run build_fleet / website_agent first)")

    # rank: populated first, then by content richness
    recs.sort(key=lambda r: (r["conformance"]["conforms"], (r["palette"]["sitemap_urls"] or 0) +
                             (r["palette"]["documents"] or 0)), reverse=True)
    populated = sum(1 for r in recs if r["conformance"]["conforms"])
    rooted = sum(1 for r in recs if r["status"] == "rooted")
    totals = {"urls": sum(r["palette"]["sitemap_urls"] or 0 for r in recs),
              "docs": sum(r["palette"]["documents"] or 0 for r in recs),
              "bindings": sum(r["palette"]["binding_sets"] or 0 for r in recs)}
    catalog = {"version": 1, "generated": a.stamp, "sites_root": a.sites,
               "count": len(recs), "populated": populated, "rooted": rooted,
               "totals": totals, "sites": recs}
    with open(catalog_path, "w") as f: json.dump(catalog, f, indent=2)

    page = render(catalog)
    hpath = os.path.join(a.sites, "thingsite_store.html")
    with open(hpath, "w") as f: f.write(page)

    print(f">> ThingSite store · {len(recs)} sites · {populated} populated · {len(recs)-populated} empty · {rooted} rooted")
    print(f"   totals: urls={totals['urls']:,} · docs={totals['docs']:,} · bindings={totals['bindings']:,}")
    print(f"   -> catalog : {catalog_path}   (the store — source of truth, keyed by identity)")
    print(f"   -> manager : {hpath}")
    empties = [r["name"] for r in recs if not r["conformance"]["conforms"]]
    if empties:
        print(f"   flagged empty (re-harvest): {', '.join(empties[:10])}" + (" …" if len(empties) > 10 else ""))
    print("   Sites are records now, not loose HTML. Candidate; nothing minted; provenance = harvest.")

def render(cat):
    rows = ""
    for r in cat["sites"]:
        p = r["palette"]; con = r["conformance"]
        conf = '<span class=ok>conforms</span>' if con["conforms"] else '<span class=bad>incomplete</span>'
        root = '<span class=rooted>rooted</span>' if r["status"] == "rooted" else '<span class=cand>candidate</span>'
        links = " · ".join(f'<a href="{esc(v)}">{esc(k.replace("_"," "))}</a>' for k, v in (r["artifacts"] or {}).items()) or '<span class=muted>none</span>'
        mined = ""
        if p.get("mined"):
            m = p["mined"]; mined = f'<div class=mined>mined: {m.get("labeled_gtins",0)} gtins · {m.get("settings",0)} settings · {m.get("identifiers",0)} ids</div>'
        issues = ("<div class=iss>" + "; ".join(esc(i) for i in con["issues"]) + "</div>") if con["issues"] else ""
        rows += (f'<tr><td><b>{esc(r["name"])}</b><div class=dm>{esc(r["domain"])}</div>{issues}{mined}</td>'
                 f'<td>{conf} {root}</td>'
                 f'<td class=n>{p["sitemap_urls"]:,}</td><td class=n>{p["documents"]:,}</td>'
                 f'<td class=n>{p["edges"]:,}</td><td class=n>{p["binding_sets"]:,}</td>'
                 f'<td class=lk>{links}</td></tr>')
    t = cat["totals"]
    return HTML.replace("__ROWS__", rows).replace("__N__", str(cat["count"])) \
        .replace("__POP__", str(cat["populated"])).replace("__EMPTY__", str(cat["count"]-cat["populated"])) \
        .replace("__ROOTED__", str(cat["rooted"])).replace("__URLS__", f"{t['urls']:,}") \
        .replace("__DOCS__", f"{t['docs']:,}").replace("__BIND__", f"{t['bindings']:,}") \
        .replace("__ROOT__", esc(cat["sites_root"]))

HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>ThingSite Store</title>
<style>
:root{--acc:#1466b8;--ink:#12212f;--dim:#5a6b82;--line:#dde5ef;--ok:#0d7a52;--bad:#b3261e}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#f6f9fc}
.wrap{max-width:1120px;margin:0 auto;padding:24px 24px 80px}
h1{font-size:21px;margin:0}.sub{font-size:13px;color:var(--dim);margin:4px 0 16px}
.tot{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.tot div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:9px 15px}
.tot b{display:block;font-size:20px}.tot span{font-size:10.5px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}
th{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--dim);text-align:left;padding:9px 12px;border-bottom:2px solid var(--line);background:#fafcfe}
td{padding:10px 12px;border-bottom:1px solid var(--line);font-size:13px;vertical-align:top}
td.n{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.dm{font-size:11.5px;color:var(--dim)}.iss{font-size:11px;color:var(--bad);margin-top:3px}.mined{font-size:11px;color:#0a6cc4;margin-top:3px}
.ok{font-size:10.5px;background:var(--ok);color:#fff;border-radius:9px;padding:1px 7px}
.bad{font-size:10.5px;background:var(--bad);color:#fff;border-radius:9px;padding:1px 7px}
.rooted{font-size:10.5px;background:#0a6;color:#fff;border-radius:9px;padding:1px 7px}
.cand{font-size:10.5px;background:#fff3e6;color:#b4700a;border:1px solid #f0d9b8;border-radius:9px;padding:1px 7px}
td.lk a{color:var(--acc);text-decoration:none;border-bottom:1px solid var(--line);font-size:12px}
.muted{color:#93a3b8}
.note{margin-top:18px;padding:11px 15px;border-left:4px solid var(--acc);background:#eef3fb;border-radius:8px;font-size:12.5px;line-height:1.6}
</style></head><body><div class=wrap>
<h1>ThingSite Store</h1>
<div class=sub>The managed catalog — every site a template-bound instance record (`__ROOT__`/), keyed by identity, not loose HTML. Store is the source of truth; the HTML is a projected artifact.</div>
<div class=tot>
<div><b>__N__</b><span>ThingSites</span></div><div><b>__POP__</b><span>populated</span></div>
<div><b>__EMPTY__</b><span>empty (re-harvest)</span></div><div><b>__ROOTED__</b><span>rooted</span></div>
<div><b>__URLS__</b><span>urls</span></div><div><b>__DOCS__</b><span>documents</span></div><div><b>__BIND__</b><span>bindings</span></div>
</div>
<table><thead><tr><th>Site</th><th>Status</th><th>URLs</th><th>Docs</th><th>Edges</th><th>Bindings</th><th>Artifacts</th></tr></thead>
<tbody>__ROWS__</tbody></table>
<div class=note><b>Create &amp; keep, managed.</b> Registering a site validates it against the <i>thingsite</i> template (has a location/domain, has content, has its artifacts) and stores it as one record in the catalog — empty sites are <b>flagged</b> for re-harvest, not silently kept. The store is keyed by identity (slug/domain, proxy for the SGLN); node-level SHACL validation of a fully-populated instance runs in the meta-configurator. Candidate; nothing minted; provenance = harvest.</div>
</div></body></html>"""

if __name__ == "__main__":
    main()
