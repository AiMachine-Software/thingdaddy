#!/usr/bin/env python3
"""
binding_sets.py — turn the REAL published relationships into candidate binding sets.

page_reader already pulled the company's own typed relationships (page_edges.csv): has_driver (P2),
runs (P3), uses (P5). Those `uses` edges ARE the company's own compatibility statements — a
substitution slot grounded in real data, not fabricated. This groups them per product into the
binding set a configurator fills:

  product  --has_driver-->  driver(s)            (P2)
           --runs-------->  protocol(s)          (P3)
           --uses-------->  compatible set       (P5)  ← the substitution slot

Each target is a CANDIDATE provider link, to be rooted to a WHO (identity_xref) and ratified (R4).
Compatibility ≠ endorsement ≠ usage: "the company links these as compatible" is a candidate slot,
never an asserted supply relationship. Nothing minted; provenance = the source page.

Reads:  page_edges.csv  (source_page, edge_type, target_url, pillar, anchor)
Writes: binding_sets.csv   product, kind, pillar, target_url, target_label
        <name>_Binding_Sets.html   one card per product (driver / protocol / substitution set)

Usage:
  python3 binding_sets.py --edges sites/thermo-fisher-scientific/page_edges.csv \
      --name "Thermo Fisher Scientific" --outdir sites/thermo-fisher-scientific
"""
from __future__ import annotations
import argparse, csv, html, os, re, urllib.parse
from collections import defaultdict

KINDS = [("has_driver", "driver", "P2", "Drivers"),
         ("runs", "protocol", "P3", "Protocols"),
         ("uses", "consumable", "P5", "Compatible set (substitution slot)")]
EDGE_KIND = {e: (k, p, lbl) for e, k, p, lbl in KINDS}

def esc(s): return html.escape(str(s if s is not None else ""))

def label_from(url, anchor=""):
    a = " ".join((anchor or "").split())
    if a and 2 < len(a) < 60 and not a.lower().startswith("http"):
        return a
    seg = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1])
    seg = re.sub(r"\.(html?|aspx?|pdf)$", "", seg, flags=re.I)
    seg = re.sub(r"[-_]+", " ", seg).strip()
    return (seg[:60] or url)

def read_csv(p):
    if not p or not os.path.exists(p): return []
    with open(p, newline="") as f: return list(csv.DictReader(f))

def main():
    ap = argparse.ArgumentParser(description="Group real published edges into candidate binding sets.")
    ap.add_argument("--edges", required=True, help="page_edges.csv from page_reader")
    ap.add_argument("--name", default="")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--max-products", type=int, default=40)
    a = ap.parse_args()

    edges = read_csv(a.edges)
    if not edges:
        raise SystemExit(f"no edges in {a.edges} (run page_reader / website_agent first)")

    # product -> kind -> [(target_url, label)]
    prod = defaultdict(lambda: defaultdict(list))
    seen = set()
    for r in edges:
        et = r.get("edge_type"); src = r.get("source_page"); tgt = r.get("target_url")
        if et not in EDGE_KIND or not src or not tgt: continue
        kind, pillar, _lbl = EDGE_KIND[et]
        key = (src, kind, tgt)
        if key in seen: continue
        seen.add(key)
        prod[src][kind].append((tgt, label_from(tgt, r.get("anchor"))))

    # write the tidy binding_sets.csv
    os.makedirs(a.outdir, exist_ok=True)
    bpath = os.path.join(a.outdir, "binding_sets.csv")
    with open(bpath, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["product", "kind", "pillar", "target_url", "target_label"])
        for src, kinds in prod.items():
            for et, k, p, _lbl in KINDS:
                for tgt, lab in kinds.get(k, []):
                    w.writerow([src, k, p, tgt, lab])

    # rank products by binding richness
    ranked = sorted(prod.items(),
                    key=lambda kv: sum(len(v) for v in kv[1].values()), reverse=True)[:a.max_products]
    n_sub = sum(1 for _, kinds in prod.items() if len(kinds.get("consumable", [])) >= 2)

    # render cards
    cards = ""
    for src, kinds in ranked:
        title = label_from(src)
        secs = ""
        for et, k, pillar, lbl in KINDS:
            items = kinds.get(k, [])
            if not items: continue
            lis = "".join(f'<li><a href="{esc(t)}" target="_blank" rel="noopener">{esc(l)}</a></li>' for t, l in items)
            slot = ' <span class="slot">substitution slot</span>' if k == "consumable" and len(items) >= 2 else ""
            secs += (f'<div class="sec {k}"><div class="sh">{esc(lbl)} '
                     f'<span class="pill">{pillar}</span> <span class="cnt">{len(items)}</span>{slot}</div>'
                     f'<ul>{lis}</ul></div>')
        cards += (f'<div class="card"><a class="ptitle" href="{esc(src)}" target="_blank" rel="noopener">'
                  f'{esc(title)}</a>{secs}</div>')

    total = len(prod)
    page = HTML.replace("__TITLE__", esc(a.name or "ThingDaddy")).replace("__CARDS__", cards) \
               .replace("__TOTAL__", str(total)).replace("__NSUB__", str(n_sub))
    hpath = os.path.join(a.outdir, (re.sub(r"[^a-z0-9]+", "-", (a.name or "company").lower()).strip("-") or "company") + "_Binding_Sets.html")
    with open(hpath, "w") as f: f.write(page)

    print(f">> wrote {bpath}")
    print(f">> wrote {hpath}")
    print(f"   products with bindings: {total} · with a substitution slot (>=2 compatible): {n_sub}")
    print("   Real published edges -> candidate binding sets. Compatibility != endorsement; candidate; R4 ratifies.")

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ · Binding Sets</title>
<style>
:root{--acc:#1466b8;--ink:#12212f;--dim:#5a6b82;--line:#dde5ef;--p2:#0d7a52;--p3:#8a5cf6;--p5:#c2560a}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#f6f9fc}
.wrap{max-width:1080px;margin:0 auto;padding:24px 26px 80px}
header{border-bottom:2px solid var(--acc);padding-bottom:12px;margin-bottom:8px}
header .t{font-size:20px;font-weight:800}header .s{font-size:13px;color:var(--dim);margin-top:4px;max-width:820px;line-height:1.5}
.meta{font-size:12px;color:var(--dim);margin:14px 0 18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(20,50,90,.05)}
.ptitle{display:block;font-size:14.5px;font-weight:800;color:var(--ink);text-decoration:none;margin-bottom:8px;line-height:1.3}
.ptitle:hover{color:var(--acc)}
.sec{margin-top:9px}.sh{font-size:12px;font-weight:700;color:var(--dim);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.pill{font-size:10px;font-weight:800;color:#fff;border-radius:10px;padding:1px 6px}
.sec.driver .pill{background:var(--p2)}.sec.protocol .pill{background:var(--p3)}.sec.consumable .pill{background:var(--p5)}
.cnt{background:#eef2f8;color:var(--dim);border-radius:10px;padding:0 7px;font-size:11px;font-weight:700}
.slot{background:#fff3e6;color:var(--p5);border:1px solid #f3d3ad;border-radius:10px;padding:0 7px;font-size:10.5px;font-weight:700}
ul{margin:5px 0 0;padding-left:16px}li{font-size:12.5px;line-height:1.5;margin:2px 0}
a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}a:hover{border-color:var(--acc)}
.note{margin-top:22px;padding:12px 15px;border-left:4px solid var(--p5);background:#fff8f0;border-radius:8px;font-size:12.5px;color:#5a4a30;line-height:1.6}
</style></head><body><div class="wrap">
<header><div class="t">__TITLE__ · Binding Sets</div>
<div class="s">The company's own published relationships, grouped per product into the binding set a configurator fills:
driver (P2) · protocol (P3) · the compatible set (P5). Each target is a <b>candidate provider link</b>, to be rooted
to a WHO and ratified. Compatibility ≠ endorsement ≠ usage. Nothing minted.</div></header>
<div class="meta">__TOTAL__ products with bindings · __NSUB__ carry a substitution slot (2+ compatible items)</div>
<div class="grid">__CARDS__</div>
<div class="note"><b>Candidate, sourced, unratified.</b> A <b>uses</b> edge means the company links these as compatible —
a candidate substitution slot, not a ratified supply relationship. Each target roots to a real WHO through the
identity ladder; the answerable party ratifies (R4). This is the provider pre-build's honest first layer: real
within-company compatibility now; cross-vendor substitution as the roster roots more parties.</div>
</div></body></html>"""

if __name__ == "__main__":
    main()
