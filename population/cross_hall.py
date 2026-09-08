#!/usr/bin/env python3
"""
cross_hall.py — find the edges BETWEEN halls: where one company's hall points at another's.

A fleet of ThingSites is a gallery until the halls connect. This scans the fleet's binding sets
(and mined attribution) for REAL cross-hall edges — a substitution-slot target, a linked accessory,
or a mined manufacturer that resolves to ANOTHER company in the fleet. Those are the first inter-hall
edges: the civilization wiring itself.

Two honest signals (both real, no fabrication):
  * domain match  — a binding-set target_url whose registered domain is another fleet company's domain
                    (company A's page links company B). Strong.
  * name match    — a target_label / mined attribution containing another fleet company's distinctive
                    name token (A's app note names B). Candidate.

Honest limit: within one company's own site, cross-vendor links are RARE (sites link themselves).
So expect few edges from a within-site harvest — the dense inter-hall graph comes after the
substitution-slot targets are ROOTED to WHOs (rooting resolves "this consumable" to "company B" even
with no direct link). This is the honest first layer. Candidate; nothing minted.

Reads:  <sites>/<slug>/binding_sets.csv, doc_attribution.csv, content_palette.json
Writes: <sites>/cross_hall_edges.csv       source, edge_type, target, via, evidence
        <sites>/cross_hall_graph.html       fleet companies wired by real edges (force-directed)

Usage:
  python3 cross_hall.py --sites sites
"""
from __future__ import annotations
import argparse, csv, glob, html, json, os, re, urllib.parse
from collections import defaultdict

STOP = {"the", "inc", "llc", "ltd", "gmbh", "limited", "company", "co", "corp", "corporation",
        "ag", "sa", "bv", "nv", "plc", "group", "holdings", "and", "laboratories", "technologies",
        "scientific", "life", "sciences", "labs", "lab"}

def esc(s): return html.escape(str(s if s is not None else ""))

def registered_domain(url_or_host):
    host = (url_or_host or "").lower()
    if "//" in host: host = host.split("//", 1)[1]
    host = host.split("/")[0].split(":")[0].strip(".").replace("www.", "")
    parts = host.split(".")
    if len(parts) < 2: return host
    two = {"co.uk", "com.au", "co.jp", "co.kr", "com.br", "co.in", "com.cn", "co.za"}
    if len(parts) >= 3 and ".".join(parts[-2:]) in two: return ".".join(parts[-3:])
    return ".".join(parts[-2:])

def name_tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) >= 4 and t not in STOP}

def read_csv(p):
    if not os.path.exists(p): return []
    with open(p, newline="") as f: return list(csv.DictReader(f))

def main():
    ap = argparse.ArgumentParser(description="Find inter-hall edges across a fleet of ThingSites.")
    ap.add_argument("--sites", default="sites")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    outroot = a.sites

    # discover fleet companies from each site's palette
    companies = {}   # slug -> {name, domain}
    for pal in glob.glob(os.path.join(outroot, "*", "content_palette.json")):
        slug = os.path.basename(os.path.dirname(pal))
        try:
            with open(pal) as f: p = json.load(f)
            companies[slug] = {"name": p.get("company", slug), "domain": p.get("domain", "")}
        except Exception:
            continue
    if not companies:
        raise SystemExit(f"no fleet sites under {outroot}/ (run build_fleet first)")

    # lookups: domain -> slug ; name-token -> {slug}
    dom2slug, tok2slug = {}, defaultdict(set)
    for slug, c in companies.items():
        d = registered_domain(c["domain"])
        if d: dom2slug[d] = slug
        for t in name_tokens(c["name"]): tok2slug[t].add(slug)

    edges, seen = [], set()
    def add(src, ety, tgt, via, ev):
        if src == tgt: return
        k = (src, ety, tgt, via)
        if k in seen: return
        seen.add(k); edges.append([companies[src]["name"], ety, companies[tgt]["name"], via, ev[:120]])

    for slug, c in companies.items():
        my_dom = registered_domain(c["domain"])
        # 1) binding-set targets
        for r in read_csv(os.path.join(outroot, slug, "binding_sets.csv")):
            tgt_url = r.get("target_url", ""); label = r.get("target_label", ""); kind = r.get("kind", "uses")
            tdom = registered_domain(tgt_url)
            if tdom and tdom != my_dom and tdom in dom2slug:               # domain match — strong
                add(slug, kind, dom2slug[tdom], "link", label or tgt_url)
            else:                                                          # name match in the label — candidate
                for t in name_tokens(label):
                    for other in tok2slug.get(t, ()):
                        if other != slug: add(slug, kind, other, "name", label)
        # 2) mined attribution naming another fleet company
        for r in read_csv(os.path.join(outroot, slug, "doc_attribution.csv")):
            for t in name_tokens(r.get("company_candidate", "")):
                for other in tok2slug.get(t, ()):
                    if other != slug: add(slug, "attributed", other, "mined", r.get("company_candidate", ""))

    # write edges
    epath = os.path.join(outroot, "cross_hall_edges.csv")
    with open(epath, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["source", "edge_type", "target", "via", "evidence"]); w.writerows(edges)

    # graph: every company a node; only wired companies get an edge
    deg = defaultdict(int)
    for e in edges: deg[e[0]] += 1; deg[e[2]] += 1
    nodes = [{"id": c["name"], "wired": deg.get(c["name"], 0) > 0} for c in companies.values()]
    links = [{"s": e[0], "t": e[2], "ty": e[1], "via": e[3]} for e in edges]
    data = {"nodes": nodes, "links": links}
    page = GRAPH_HTML.replace("__DATA__", json.dumps(data)) \
        .replace("__N__", str(len(nodes))).replace("__E__", str(len(edges))) \
        .replace("__W__", str(sum(1 for n in nodes if n["wired"])))
    gpath = a.out or os.path.join(outroot, "cross_hall_graph.html")
    with open(gpath, "w") as f: f.write(page)

    print(f">> cross-hall: {len(companies)} halls · {len(edges)} inter-hall edges · "
          f"{sum(1 for n in nodes if n['wired'])} halls wired")
    print(f"   -> {epath}")
    print(f"   -> {gpath}")
    if not edges:
        print("   0 edges — expected for within-site harvests (sites link themselves, not competitors).")
        print("   The dense inter-hall graph appears once substitution-slot targets are ROOTED to WHOs.")
    else:
        by = defaultdict(int)
        for e in edges: by[(e[0], e[2])] += 1
        for (s, t), n in sorted(by.items(), key=lambda kv: -kv[1])[:12]:
            print(f"   {s}  --{n}-->  {t}")
    print("   Candidate edges — compatibility/reference, not ratified supply. Nothing minted.")

GRAPH_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ThingDaddy · Cross-Hall Graph</title>
<style>
html,body{margin:0;height:100%;background:#070b12;color:#e8eef7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
#hud{position:fixed;top:0;left:0;right:0;padding:14px 18px;pointer-events:none;z-index:5}
#hud .t{font-size:15px;font-weight:800}#hud .s{font-size:12px;color:#8fa3bd;margin-top:2px;max-width:720px}
#tip{position:fixed;pointer-events:none;z-index:9;background:rgba(9,14,22,.95);border:1px solid #26364c;border-radius:8px;padding:6px 9px;font-size:12px;display:none}
#foot{position:fixed;bottom:14px;right:18px;font-size:11px;color:#5b6b82;z-index:5}
svg{width:100vw;height:100vh;display:block}.edge{stroke:#2dd4bf;stroke-opacity:.4}
.node text{font-size:12px;fill:#c7d4e6;paint-order:stroke;stroke:#070b12;stroke-width:3px;pointer-events:none}
.node.wired text{fill:#fff;font-weight:800}
</style></head><body>
<div id=hud><div class=t>ThingDaddy · Cross-Hall Graph <span style="color:#8fa3bd;font-weight:600">— the halls wiring together</span></div>
<div class=s>__W__ of __N__ halls wired · __E__ inter-hall edges. An edge means one company's hall points at another's (a substitution-slot target, a linked accessory, a mined manufacturer). Candidate — reference/compatibility, not ratified supply. Nothing minted. Drag a node.</div></div>
<div id=tip></div><div id=foot>candidate inter-hall edges · real signals only</div>
<svg id=svg></svg>
<script>
const DATA=__DATA__;const svg=document.getElementById('svg'),tip=document.getElementById('tip'),NS='http://www.w3.org/2000/svg';
let W=innerWidth,H=innerHeight;const nodes=DATA.nodes,links=DATA.links;const byId={};
nodes.forEach((n,i)=>{byId[n.id]=n;n.x=W/2+Math.cos(i*2.399)*(120+i*8);n.y=H/2+Math.sin(i*2.399)*(120+i*6);n.vx=0;n.vy=0;});
links.forEach(e=>{e.S=byId[e.s];e.T=byId[e.t];});
const gE=document.createElementNS(NS,'g'),gN=document.createElementNS(NS,'g');svg.appendChild(gE);svg.appendChild(gN);
const eEls=links.map(e=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','edge');l.setAttribute('stroke-width',1.4);gE.appendChild(l);return l;});
const nEls=nodes.map(n=>{const g=document.createElementNS(NS,'g');g.setAttribute('class','node '+(n.wired?'wired':''));
  const c=document.createElementNS(NS,'circle');const r=n.wired?11:6;c.setAttribute('r',r);
  c.setAttribute('fill',n.wired?'#f5b301':'#3a5878');c.setAttribute('stroke',n.wired?'#f5b301':'#3a5878');c.setAttribute('stroke-opacity',.35);c.setAttribute('stroke-width',6);c.style.filter='drop-shadow(0 0 6px '+(n.wired?'#f5b301':'#3a5878')+')';
  const t=document.createElementNS(NS,'text');t.setAttribute('x',r+4);t.setAttribute('y',4);t.textContent=n.id;
  g.appendChild(c);g.appendChild(t);gN.appendChild(g);
  let drag=false;c.addEventListener('pointerdown',ev=>{drag=true;n.fixed=true;c.setPointerCapture(ev.pointerId);});
  c.addEventListener('pointermove',ev=>{if(drag){const pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;n.x=pt.x;n.y=pt.y;}});
  c.addEventListener('pointerup',()=>{drag=false;n.fixed=false;});return g;});
links.forEach((e,i)=>{eEls[i].addEventListener&&0;});
function tick(){
  for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j];
    let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01,d=Math.sqrt(d2);const f=3200/d2;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}}
  links.forEach(e=>{const a=e.S,b=e.T;if(!a||!b)return;let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01;const f=(d-140)*0.02;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;});
  nodes.forEach(n=>{n.vx+=(W/2-n.x)*0.0015;n.vy+=(H/2-n.y)*0.0015;if(!n.fixed){n.vx*=0.86;n.vy*=0.86;n.x+=n.vx;n.y+=n.vy;}});
  links.forEach((e,i)=>{if(e.S&&e.T){eEls[i].setAttribute('x1',e.S.x);eEls[i].setAttribute('y1',e.S.y);eEls[i].setAttribute('x2',e.T.x);eEls[i].setAttribute('y2',e.T.y);}});
  nodes.forEach((n,i)=>{nEls[i].setAttribute('transform','translate('+n.x+','+n.y+')');});
  requestAnimationFrame(tick);
}
addEventListener('resize',()=>{W=innerWidth;H=innerHeight;});tick();
</script></body></html>"""

if __name__ == "__main__":
    main()
