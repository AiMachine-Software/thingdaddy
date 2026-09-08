#!/usr/bin/env python3
"""
render_mined_graph.py — draw the REAL protocol graph from what docmine mined.

render_p5_graph draws the *standard* constellation (AFO/SiLA vocabulary — the empty staff).
This draws the *real* one: the WHO recovered from the manuals at the center, each mined document a
node, and the actual settings + consumables/catalog/GTINs mined from inside those PDFs as the leaves.
The miner writes the notes; this renders them.

Reads a harvest outdir's docmine output:
  doc_attribution.csv   source_doc, page, company_candidate, evidence
  doc_identifiers.csv   source_doc, page, id_kind, value, gtin_if_valid, labeled, state
  doc_settings.csv      source_doc, page, param, value, unit, pillar, state

Graph:
  WHO (dominant company_candidate)
    --attributes--> document (each source_doc)
                      --setting--> "param value unit"   (real P3 params, capped per doc)
                      --consumable--> catalog / gtin / model / part   (real identifiers, capped)

Everything CANDIDATE + provenanced (each node traces to its source PDF). Nothing minted.

Usage:
  python3 render_mined_graph.py --mined-dir sites/thermo-fisher-scientific --name "Thermo Fisher Scientific" \
      --out sites/thermo-fisher-scientific/thermo-fisher-scientific_Mined_Graph.html
"""
from __future__ import annotations
import argparse, csv, html, json, os, re, urllib.parse
from collections import Counter, defaultdict

COLORS = {"who": "#f5b301", "document": "#2dd4bf", "setting": "#5b8cff",
          "gtin": "#ff6b9d", "catalog": "#ff9f43", "model": "#39d98a", "part": "#c98bff"}

def read_csv(path):
    if not path or not os.path.exists(path): return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def doc_label(url):
    base = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    base = re.sub(r"\.(pdf|html?)$", "", base, flags=re.I)
    base = re.sub(r"[-_]+", " ", base)
    return (base[:34] or "document").strip()

def main():
    ap = argparse.ArgumentParser(description="Render the real protocol graph from docmine output.")
    ap.add_argument("--mined-dir", required=True, help="harvest outdir holding doc_*.csv")
    ap.add_argument("--name", default="")
    ap.add_argument("--out", default="mined_graph.html")
    ap.add_argument("--max-docs", type=int, default=12)
    ap.add_argument("--per-doc-settings", type=int, default=6)
    ap.add_argument("--per-doc-ids", type=int, default=6)
    a = ap.parse_args()

    attr = read_csv(os.path.join(a.mined_dir, "doc_attribution.csv"))
    ids  = read_csv(os.path.join(a.mined_dir, "doc_identifiers.csv"))
    setts = read_csv(os.path.join(a.mined_dir, "doc_settings.csv"))
    if not (attr or ids or setts):
        raise SystemExit(f"no docmine output in {a.mined_dir} (run website_agent --mine first)")

    # the WHO = most-attributed company (fallback to --name)
    who_counts = Counter(r["company_candidate"] for r in attr if r.get("company_candidate"))
    who = who_counts.most_common(1)[0][0] if who_counts else (a.name or "Unrooted WHO (candidate)")

    # which docs have the richest yield -> show those
    per_doc = defaultdict(lambda: {"settings": [], "ids": []})
    for r in setts:
        d = r.get("source_doc")
        if d: per_doc[d]["settings"].append(r)
    for r in ids:
        d = r.get("source_doc")
        if d: per_doc[d]["ids"].append(r)
    ranked = sorted(per_doc.items(), key=lambda kv: len(kv[1]["settings"]) + len(kv[1]["ids"]), reverse=True)
    ranked = ranked[:a.max_docs]

    nodes, edges, idx = [], [], {}
    def add(nid, label, group, meta=""):
        if nid in idx: return nid
        idx[nid] = True
        nodes.append({"id": nid, "label": label, "group": group, "meta": meta}); return nid
    def link(s, t, ty): edges.append({"s": s, "t": t, "ty": ty})

    WHO = add("who", who, "who", "recovered from the manuals (candidate WHO)")
    for di, (doc, bundle) in enumerate(ranked):
        dn = add(f"doc:{di}", doc_label(doc), "document", doc)
        link(WHO, dn, "attributes")
        # real settings (dedup + cap)
        seen = set()
        for r in bundle["settings"]:
            key = (r.get("param"), r.get("value"), r.get("unit"))
            if key in seen: continue
            seen.add(key)
            lbl = " ".join(x for x in [r.get("value"), r.get("unit")] if x)
            pm = f'{r.get("param","")}'.strip()
            sn = add(f"set:{di}:{len(seen)}", lbl, "setting", pm)
            link(dn, sn, "setting")
            if len([1 for _ in seen]) >= a.per_doc_settings: break
        # real identifiers (consumables / catalog / gtin), cap
        cnt = 0
        seen_i = set()
        for r in bundle["ids"]:
            v = r.get("value"); kind = r.get("id_kind", "catalog")
            if not v or v in seen_i: continue
            seen_i.add(v)
            g = kind if kind in COLORS else "catalog"
            inn = add(f"id:{di}:{cnt}", (r.get("gtin_if_valid") or v), g,
                      f'{kind}{" · labeled GTIN" if r.get("labeled")=="yes" else ""}')
            link(dn, inn, "consumable")
            cnt += 1
            if cnt >= a.per_doc_ids: break

    data = {"nodes": nodes, "edges": edges, "colors": COLORS}
    counts = Counter(n["group"] for n in nodes)
    title = a.name or who
    page = (HTML.replace("__DATA__", json.dumps(data))
                .replace("__WHO__", html.escape(who))
                .replace("__TITLE__", html.escape(title)))
    with open(a.out, "w") as f: f.write(page)
    print(f">> wrote {a.out} ({len(page):,} bytes)")
    print(f"   WHO: {who}  ·  docs={counts.get('document',0)} · settings={counts.get('setting',0)} · "
          f"identifiers={sum(counts.get(k,0) for k in ('gtin','catalog','model','part'))}")
    print("   Real mined content — candidate + provenanced (each node traces to its source PDF). Nothing minted.")

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ · Mined Protocol Graph</title>
<style>
html,body{margin:0;height:100%;background:#070b12;color:#e8eef7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
#hud{position:fixed;top:0;left:0;right:0;padding:14px 18px;pointer-events:none;z-index:5}
#hud .t{font-size:15px;font-weight:800;letter-spacing:.4px}
#hud .s{font-size:12px;color:#8fa3bd;margin-top:2px;max-width:680px}
#legend{position:fixed;bottom:14px;left:18px;font-size:12px;z-index:5;background:rgba(10,16,26,.6);border:1px solid #1c2a3b;border-radius:10px;padding:9px 12px}
#legend span{display:inline-flex;align-items:center;margin-right:12px}
#legend i{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 8px currentColor}
#tip{position:fixed;pointer-events:none;z-index:9;background:rgba(9,14,22,.95);border:1px solid #26364c;border-radius:8px;padding:6px 9px;font-size:12px;max-width:280px;display:none}
#foot{position:fixed;bottom:14px;right:18px;font-size:11px;color:#5b6b82;z-index:5}
svg{width:100vw;height:100vh;display:block}
.edge{stroke-opacity:.26}
.node text{font-size:10.5px;fill:#c7d4e6;paint-order:stroke;stroke:#070b12;stroke-width:3px;pointer-events:none}
.node.who text{font-size:14px;fill:#fff;font-weight:800}
.node.document text{font-size:11px;fill:#eaf7f5;font-weight:700}
</style></head><body>
<div id=hud><div class=t>__TITLE__ · Mined Protocol Graph <span style="color:#8fa3bd;font-weight:600">— real content, from inside the PDFs</span></div>
<div class=s>WHO recovered from the manuals → each document → the real settings &amp; consumables mined inside it. Candidate + provenanced (every node traces to its source PDF); nothing minted. Hover a node; drag it.</div></div>
<div id=legend></div><div id=tip></div>
<div id=foot>docmine · real settings + identifiers · candidate</div>
<svg id=svg></svg>
<script>
const DATA=__DATA__;
const svg=document.getElementById('svg'), tip=document.getElementById('tip'), NS='http://www.w3.org/2000/svg';
let W=innerWidth,H=innerHeight;
const nodes=DATA.nodes, edges=DATA.edges, C=DATA.colors;
const byId={}; nodes.forEach((n,i)=>{byId[n.id]=n; n.x=W/2+Math.cos(i*2.399)*(90+i*6); n.y=H/2+Math.sin(i*2.399)*(90+i*5); n.vx=0; n.vy=0;});
edges.forEach(e=>{e.S=byId[e.s]; e.T=byId[e.t];});
const L=document.getElementById('legend'); const names={who:'WHO (attribution)',document:'Document',setting:'Setting (P3)',gtin:'GTIN',catalog:'Catalog',model:'Model',part:'Part'};
Object.keys(names).forEach(k=>{const s=document.createElement('span');s.innerHTML='<i style="color:'+C[k]+'"></i>'+names[k];L.appendChild(s);});
const gE=document.createElementNS(NS,'g'), gN=document.createElementNS(NS,'g'); svg.appendChild(gE); svg.appendChild(gN);
const eEls=edges.map(e=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','edge');l.setAttribute('stroke',C[e.T.group]||'#3a5878');l.setAttribute('stroke-width', e.ty==='attributes'?1.8:1);gE.appendChild(l);return l;});
const nEls=nodes.map(n=>{const g=document.createElementNS(NS,'g');g.setAttribute('class','node '+n.group);
  const c=document.createElementNS(NS,'circle');const r=n.group==='who'?14:(n.group==='document'?8:5.5);
  c.setAttribute('r',r);c.setAttribute('fill',C[n.group]);c.setAttribute('stroke',C[n.group]);c.setAttribute('stroke-opacity',.35);c.setAttribute('stroke-width',6);c.style.filter='drop-shadow(0 0 6px '+C[n.group]+')';
  const t=document.createElementNS(NS,'text');t.setAttribute('x',r+4);t.setAttribute('y',4);t.textContent=n.label;
  g.appendChild(c);g.appendChild(t);gN.appendChild(g);
  g.addEventListener('pointermove',ev=>{if(n.meta){tip.style.display='block';tip.style.left=(ev.clientX+12)+'px';tip.style.top=(ev.clientY+12)+'px';tip.innerHTML='<b>'+n.label+'</b><br>'+n.meta;}});
  g.addEventListener('pointerleave',()=>{tip.style.display='none';});
  let drag=false;
  c.addEventListener('pointerdown',ev=>{drag=true;n.fixed=true;c.setPointerCapture(ev.pointerId);});
  c.addEventListener('pointermove',ev=>{if(drag){const pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;n.x=pt.x;n.y=pt.y;}});
  c.addEventListener('pointerup',ev=>{drag=false;n.fixed=false;});
  return g;});
function tick(){
  for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j];
    let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01,d=Math.sqrt(d2);const f=2400/d2;const fx=dx/d*f,fy=dy/d*f;
    a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}}
  edges.forEach(e=>{const a=e.S,b=e.T;let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01;const L0=(a.group==='who'||b.group==='who')?150:70;const f=(d-L0)*0.02;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;});
  nodes.forEach(n=>{n.vx+=(W/2-n.x)*0.0015;n.vy+=(H/2-n.y)*0.0015;if(!n.fixed){n.vx*=0.86;n.vy*=0.86;n.x+=n.vx;n.y+=n.vy;}});
  edges.forEach((e,i)=>{eEls[i].setAttribute('x1',e.S.x);eEls[i].setAttribute('y1',e.S.y);eEls[i].setAttribute('x2',e.T.x);eEls[i].setAttribute('y2',e.T.y);});
  nodes.forEach((n,i)=>{nEls[i].setAttribute('transform','translate('+n.x+','+n.y+')');});
  requestAnimationFrame(tick);
}
addEventListener('resize',()=>{W=innerWidth;H=innerHeight;});
tick();
</script></body></html>"""

if __name__ == "__main__":
    main()
