#!/usr/bin/env python3
"""
render_p5_graph.py — render the P5 AI Graph from the REAL standards vocabularies.

Reads standards/{afo_classes,sila_features,configurator_rules}.csv and weaves the graph the
configurator rules describe:
    instrument (GTIN)  --has_driver-->  SiLA Feature (P2)
                       --runs-------->  AFO process/method (P3)
    AFO process        --has_equipment-> AFO equipment
                       --has_input----> AFO material
                       --has_output---> AFO result (P5)
Each process is a subgraph (a protocol); all merge on the shared instrument + shared classes ->
the whole graph ("each protocol, then all of them together"). Real classes from the AFO ontology
and the SiLA standard features. Candidate; nothing minted.

Output: a self-contained interactive constellation (inline SVG + vanilla JS force layout).

Usage:
  python3 render_p5_graph.py --standards . --instrument "DZ-Lite c270 (GTIN · candidate)" --out P5_Graph.html
  python3 render_p5_graph.py --standards ../standards --out P5_Graph.html
"""
from __future__ import annotations
import argparse, csv, html, json, os

COLORS = {"instrument": "#f5b301", "sila": "#22c1c3", "process": "#c98bff",
          "equipment": "#39d98a", "material": "#ff9f43", "result": "#ff6b9d", "document": "#2dd4bf"}

def read_csv(path):
    if not path or not os.path.exists(path): return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def spread(rows, key, n):
    """Evenly-spaced sample of rows with a clean short label under `key`."""
    clean = [r for r in rows if r.get(key) and 2 < len(r[key]) < 34]
    if not clean: return []
    if len(clean) <= n: return clean
    step = len(clean) / n
    return [clean[int(i * step)] for i in range(n)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--standards", default=".")
    ap.add_argument("--instrument", default="Instrument (GTIN · candidate)")
    ap.add_argument("--out", default="P5_Graph.html")
    a = ap.parse_args()

    afo = read_csv(os.path.join(a.standards, "afo_classes.csv"))
    sila = read_csv(os.path.join(a.standards, "sila_features.csv"))

    by = {d: [r for r in afo if r.get("domain") == d] for d in ("process", "equipment", "material", "result")}
    proc = spread(by["process"], "label", 9)
    equip = spread(by["equipment"], "label", 6)
    mat = spread(by["material"], "label", 7)
    res = spread(by["result"], "label", 9)
    # a compact, meaningful SiLA driver set (fall back to first-8 of whatever's present)
    prefer = ["SiLAService", "LockController", "ObservableCommandController", "SimulationController",
              "AuditTrailService", "InitializationController", "ErrorRecoveryService", "AuthenticationService"]
    silam = {r["feature"]: r for r in sila if r.get("feature")}
    silsel = [silam[f] for f in prefer if f in silam] or list(silam.values())[:8]

    nodes, edges, idx = [], [], {}
    def add(nid, label, group):
        if nid in idx: return nid
        idx[nid] = True
        nodes.append({"id": nid, "label": label, "group": group}); return nid
    def link(s, t, ty): edges.append({"s": s, "t": t, "ty": ty})

    INS = add("instrument", a.instrument, "instrument")
    for r in silsel:
        n = add("sila:" + r["feature"], r["feature"], "sila"); link(INS, n, "has_driver")
    for i, r in enumerate(proc):
        pn = add("proc:%d" % i, r["label"], "process"); link(INS, pn, "runs")
        # each protocol wires to its own equipment / input material / output result (shared pool)
        if equip: e = equip[i % len(equip)]; link(pn, add("eq:" + e["label"], e["label"], "equipment"), "has_equipment")
        if mat:   m = mat[i % len(mat)];     link(pn, add("mat:" + m["label"], m["label"], "material"), "has_input")
        if res:   x = res[i % len(res)];     link(pn, add("res:" + x["label"], x["label"], "result"), "has_output")
    for m in mat[:3]:
        link(INS, "mat:" + m["label"], "uses")

    data = {"nodes": nodes, "edges": edges, "colors": COLORS}
    counts = {}
    for n in nodes: counts[n["group"]] = counts.get(n["group"], 0) + 1

    page = HTML.replace("__DATA__", json.dumps(data)).replace("__INSTR__", html.escape(a.instrument))
    with open(a.out, "w") as f: f.write(page)
    print(">> wrote", a.out, "(%d bytes)" % len(page))
    print("   nodes:", len(nodes), "· edges:", len(edges), "·", ", ".join("%s=%d" % (k, v) for k, v in counts.items()))
    print("   real AFO classes + SiLA features, wired by the configurator rules. Candidate; nothing minted.")

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ThingDaddy · P5 AI Graph</title>
<style>
html,body{margin:0;height:100%;background:#070b12;color:#e8eef7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
#hud{position:fixed;top:0;left:0;right:0;padding:14px 18px;pointer-events:none;z-index:5}
#hud .t{font-size:15px;font-weight:800;letter-spacing:.5px}
#hud .s{font-size:12px;color:#8fa3bd;margin-top:2px;max-width:640px}
#legend{position:fixed;bottom:14px;left:18px;font-size:12px;z-index:5;background:rgba(10,16,26,.6);border:1px solid #1c2a3b;border-radius:10px;padding:9px 12px}
#legend span{display:inline-flex;align-items:center;margin-right:12px}
#legend i{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 8px currentColor}
#foot{position:fixed;bottom:14px;right:18px;font-size:11px;color:#5b6b82;z-index:5}
svg{width:100vw;height:100vh;display:block}
.edge{stroke-opacity:.28}
.node circle{cursor:grab}
.node text{font-size:10.5px;fill:#c7d4e6;paint-order:stroke;stroke:#070b12;stroke-width:3px;pointer-events:none}
.node.instrument text{font-size:13px;fill:#fff;font-weight:800}
</style></head><body>
<div id=hud><div class=t>ThingDaddy · P5 AI Graph <span style="color:#8fa3bd;font-weight:600">— the score, playing</span></div>
<div class=s>Instrument → SiLA driver → AFO protocol → equipment · material · result. Each protocol a subgraph, all merged on the shared identity — woven from the real AFO ontology + SiLA standard features by the configurator rules. Candidate; nothing minted. Drag a node.</div></div>
<div id=legend></div>
<div id=foot>real standards · configuration, not code · protocol-legal only</div>
<svg id=svg></svg>
<script>
const DATA=__DATA__;
const svg=document.getElementById('svg'), NS='http://www.w3.org/2000/svg';
let W=innerWidth,H=innerHeight;
const nodes=DATA.nodes, edges=DATA.edges, C=DATA.colors;
const byId={}; nodes.forEach((n,i)=>{byId[n.id]=n; n.x=W/2+Math.cos(i*2.3)*(120+i*7); n.y=H/2+Math.sin(i*2.3)*(120+i*5); n.vx=0; n.vy=0;});
edges.forEach(e=>{e.S=byId[e.s]; e.T=byId[e.t];});
// legend
const L=document.getElementById('legend'); const names={instrument:'Instrument (GTIN)',sila:'SiLA driver (P2)',process:'AFO protocol (P3)',equipment:'Equipment',material:'Material',result:'Result (P5)'};
Object.keys(names).forEach(k=>{const s=document.createElement('span');s.innerHTML='<i style="color:'+C[k]+'"></i>'+names[k];L.appendChild(s);});
// build svg elements
const gE=document.createElementNS(NS,'g'), gN=document.createElementNS(NS,'g'); svg.appendChild(gE); svg.appendChild(gN);
const eEls=edges.map(e=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','edge');l.setAttribute('stroke',C[e.T.group]||'#3a5878');l.setAttribute('stroke-width', e.ty==='runs'||e.ty==='has_driver'?1.6:1);gE.appendChild(l);return l;});
const nEls=nodes.map(n=>{const g=document.createElementNS(NS,'g');g.setAttribute('class','node '+n.group);
  const c=document.createElementNS(NS,'circle');const r=n.group==='instrument'?13:(n.group==='process'?8:6);
  c.setAttribute('r',r);c.setAttribute('fill',C[n.group]);c.setAttribute('stroke',C[n.group]);c.setAttribute('stroke-opacity',.35);c.setAttribute('stroke-width',6);c.style.filter='drop-shadow(0 0 6px '+C[n.group]+')';
  const t=document.createElementNS(NS,'text');t.setAttribute('x',r+4);t.setAttribute('y',4);t.textContent=n.label;
  g.appendChild(c);g.appendChild(t);gN.appendChild(g);
  // drag
  let drag=false;
  c.addEventListener('pointerdown',ev=>{drag=true;n.fixed=true;c.setPointerCapture(ev.pointerId);c.style.cursor='grabbing';});
  c.addEventListener('pointermove',ev=>{if(drag){const pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;n.x=pt.x;n.y=pt.y;}});
  c.addEventListener('pointerup',ev=>{drag=false;n.fixed=false;c.style.cursor='grab';});
  return g;});
function tick(){
  // repulsion (O(n^2), fine for this size)
  for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j];
    let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01,d=Math.sqrt(d2);const f=2600/d2;const fx=dx/d*f,fy=dy/d*f;
    a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}}
  // springs
  edges.forEach(e=>{const a=e.S,b=e.T;let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01;const L0=(a.group==='instrument'||b.group==='instrument')?150:90;const f=(d-L0)*0.02;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;});
  // gravity + integrate
  nodes.forEach(n=>{n.vx+=(W/2-n.x)*0.0016;n.vy+=(H/2-n.y)*0.0016;if(!n.fixed){n.vx*=0.86;n.vy*=0.86;n.x+=n.vx;n.y+=n.vy;}});
  edges.forEach((e,i)=>{eEls[i].setAttribute('x1',e.S.x);eEls[i].setAttribute('y1',e.S.y);eEls[i].setAttribute('x2',e.T.x);eEls[i].setAttribute('y2',e.T.y);});
  nodes.forEach((n,i)=>{nEls[i].setAttribute('transform','translate('+n.x+','+n.y+')');});
  requestAnimationFrame(tick);
}
addEventListener('resize',()=>{W=innerWidth;H=innerHeight;});
tick();
</script></body></html>"""

if __name__ == "__main__":
    main()
