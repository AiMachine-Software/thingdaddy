#!/usr/bin/env python3
"""
physical_ai_graph.py — the COMPLETE Physical AI Graph node: one real location, fully populated.

Everything at one place, wired: all seven GS1 identity types + every pillar binding.

  Location (SGLN)                                  — the ThingSite anchor
    contains  Instruments (GIAI)                   — the edge nodes
                has_driver -> SiLA driver (P2)      — how you talk to it
                bound_to   -> Cloud / Edge (P4)      — where it runs
                runs       -> Protocol (GDTI, P3)    — the score it plays
                                uses -> Consumables (SGTIN, P5)  — substitution slots
                                yields -> Result
                has_part   -> Component (CPID)        — made_by a supplier (fractal)
              Documents (GDTI)  describes -> Instrument
              User / Agent (GSRN) operates -> Protocol
              Returnable (GRAI) at -> Location

All CANDIDATE. No URN is minted — key types assigned, prefix-is-root holds, R4 ratifies. The SGLN, GIAI and SGTIN example values use a fenced DEMO prefix (990 - not a GS1 assignment);
replace with the party's real, ratified prefix when known. prefix-is-root holds; nothing minted.

Output: physical_ai_graph.html — one interactive, pillar/key-colored graph.

Usage:  python3 physical_ai_graph.py --out physical_ai_graph.html
"""
from __future__ import annotations
import argparse, html, json, os

# --- the complete node (candidate; example URNs sourced to KJ's slide, not minted here) -----
LOCATION = {"id": "loc", "label": "51 Allen Way, San Diego  ·  SGLN 990.12345.400",
            "group": "location", "key": "sgln"}

# instruments (GIAI) — each gets a SiLA driver (P2) + a cloud/edge bind (P4)
INSTRUMENTS = [
    {"id": "eq:magmax",      "label": "MagMax DNA Isolation System",     "driver": "SiLAService+LockController",       "cloud": "aws"},
    {"id": "eq:accufill",    "label": "OpenArray AccuFill System",       "driver": "ObservableCommandController",       "cloud": "aws"},
    {"id": "eq:quantstudio", "label": "QuantStudio 12K Flex",            "driver": "SimulationController+AuditTrail",   "cloud": "azure"},
    {"id": "eq:alleletyper", "label": "AlleleTyper Software",            "driver": "AuthenticationService",             "cloud": "edge"},
    {"id": "eq:iontorrent",  "label": "Ion Torrent  ·  GIAI 990.17320509", "driver": "InitializationController",   "cloud": "gcp"},
]
CLOUDS = {"aws": "AWS IoT (P4)", "azure": "Azure (P4)", "gcp": "Google Cloud (P4)", "edge": "Edge Gateway (P4)"}

CONSUMABLES = [   # SGTIN — the protocol's substitution slots
    "Swab (DNA)", "Protease", "Lysis Buffer", "Beads Solution",
    "Wash Buffer 1", "Wash Buffer 2", "Elution Buffer", "PCR Mix",
    "1kb Plus DNA Ladder  ·  SGTIN 990.012345.62852",
]
PROTOCOL = {"id": "proc:pgx", "label": "PGx Genotyping Protocol (GDTI, P3)", "key": "gdti"}
RESULTS  = [("res:dna", "Extracted DNA"), ("res:geno", "Genotype calls")]
DOCUMENT = {"id": "doc:ifu", "label": "User Guide / IFU (GDTI)", "key": "gdti"}
USER     = {"id": "usr:agent", "label": "Lab agent / operator (GSRN)", "key": "gsrn"}
COMPONENT= {"id": "cpid:sensor", "label": "Temp sensor (CPID) → made_by supplier", "key": "cpid"}
RETURN   = {"id": "grai:rack", "label": "Returnable rack (GRAI)", "key": "grai"}

def build():
    nodes, edges, seen = [], [], set()
    def add(nid, label, group, key=""):
        if nid in seen: return
        seen.add(nid); nodes.append({"id": nid, "label": label, "group": group, "key": key})
    def link(s, t, ty): edges.append({"s": s, "t": t, "ty": ty})

    add(LOCATION["id"], LOCATION["label"], "location", "sgln")
    # clouds/edge
    for cid, clabel in CLOUDS.items():
        add("cloud:" + cid, clabel, "cloud", "")
    # instruments + their driver + cloud + protocol
    for ins in INSTRUMENTS:
        add(ins["id"], ins["label"], "instrument", "giai")
        link(LOCATION["id"], ins["id"], "contains")
        add("drv:" + ins["id"], ins["driver"] + " (P2)", "driver", "")
        link(ins["id"], "drv:" + ins["id"], "has_driver")
        link(ins["id"], "cloud:" + ins["cloud"], "bound_to")
        link(ins["id"], PROTOCOL["id"], "runs")
    # protocol + consumables + results
    add(PROTOCOL["id"], PROTOCOL["label"], "protocol", "gdti")
    link(LOCATION["id"], PROTOCOL["id"], "contains")
    for i, c in enumerate(CONSUMABLES):
        cid = "mat:%d" % i; add(cid, c, "consumable", "sgtin"); link(PROTOCOL["id"], cid, "uses")
    for rid, rlabel in RESULTS:
        add(rid, rlabel, "result", ""); link(PROTOCOL["id"], rid, "yields")
    # the other identity types
    add(DOCUMENT["id"], DOCUMENT["label"], "document", "gdti"); link(DOCUMENT["id"], INSTRUMENTS[0]["id"], "describes")
    add(USER["id"], USER["label"], "user", "gsrn"); link(USER["id"], PROTOCOL["id"], "operates")
    add(COMPONENT["id"], COMPONENT["label"], "component", "cpid"); link(COMPONENT["id"], INSTRUMENTS[2]["id"], "part_of")
    add(RETURN["id"], RETURN["label"], "returnable", "grai"); link(RETURN["id"], LOCATION["id"], "at")
    return {"nodes": nodes, "edges": edges}

COLORS = {"location": "#5b8cff", "instrument": "#39d98a", "consumable": "#ff9f43", "driver": "#22c1c3",
          "protocol": "#c98bff", "cloud": "#7aa2ff", "result": "#ff6b9d", "document": "#2dd4bf",
          "user": "#f5b301", "component": "#b07cff", "returnable": "#c98b5a"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="physical_ai_graph.html")
    a = ap.parse_args()
    data = build(); data["colors"] = COLORS
    counts = {}
    for n in data["nodes"]: counts[n["group"]] = counts.get(n["group"], 0) + 1
    page = HTML.replace("__DATA__", json.dumps(data))
    with open(a.out, "w") as f: f.write(page)
    keys = sorted({n["key"] for n in data["nodes"] if n["key"]})
    print(f">> Physical AI Graph · {len(data['nodes'])} nodes · {len(data['edges'])} edges")
    print(f"   ID types present: {', '.join(k.upper() for k in keys)}")
    print(f"   {counts.get('instrument',0)} instruments (each: SiLA driver P2 + cloud/edge P4 + runs protocol P3)")
    print(f"   -> {a.out}")
    print("   One real location, fully populated. Candidate; nothing minted; SGLN/GIAI/SGTIN sourced to the slide.")

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Physical AI Graph · one node, fully populated</title>
<style>
html,body{margin:0;height:100%;background:#060a11;color:#e8eef7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
#hud{position:fixed;top:0;left:0;right:0;padding:14px 18px;pointer-events:none;z-index:5}
#hud .t{font-size:15px;font-weight:800}#hud .s{font-size:12px;color:#8fa3bd;margin-top:2px;max-width:760px}
#legend{position:fixed;bottom:12px;left:14px;font-size:11.5px;z-index:5;background:rgba(9,14,22,.62);border:1px solid #1c2a3b;border-radius:10px;padding:8px 11px;max-width:70vw}
#legend span{display:inline-flex;align-items:center;margin:2px 10px 2px 0}#legend i{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 8px currentColor}
#foot{position:fixed;bottom:12px;right:16px;font-size:11px;color:#5b6b82;z-index:5}
svg{width:100vw;height:100vh;display:block}.edge{stroke-opacity:.26}
.node text{font-size:10px;fill:#c7d4e6;paint-order:stroke;stroke:#060a11;stroke-width:3px;pointer-events:none}
.node.location text{font-size:12.5px;fill:#fff;font-weight:800}
</style></head><body>
<div id=hud><div class=t>Physical AI Graph <span style="color:#8fa3bd;font-weight:600">— one location, fully populated</span></div>
<div class=s>One real ThingSite (SGLN) with all seven GS1 identity types and every pillar binding: instruments (GIAI) each with a SiLA driver (P2), a cloud/edge bind (P4), and the PGx protocol (P3) using consumables (SGTIN, P5); plus document (GDTI), user (GSRN), component (CPID), returnable (GRAI). Candidate; nothing minted. Drag a node.</div></div>
<div id=legend></div><div id=foot>7 ID types · P2 driver · P3 protocol · P4 cloud/edge · P5 uses · candidate</div>
<svg id=svg></svg>
<script>
const DATA=__DATA__;const svg=document.getElementById('svg'),NS='http://www.w3.org/2000/svg';let W=innerWidth,H=innerHeight;
const nodes=DATA.nodes,edges=DATA.edges,C=DATA.colors;const byId={};
nodes.forEach((n,i)=>{byId[n.id]=n;n.x=W/2+Math.cos(i*2.399)*(70+i*7);n.y=H/2+Math.sin(i*2.399)*(70+i*6);n.vx=0;n.vy=0;});
edges.forEach(e=>{e.S=byId[e.s];e.T=byId[e.t];});
const L=document.getElementById('legend');
const names={location:'Location (SGLN)',instrument:'Instrument (GIAI)',consumable:'Consumable (SGTIN)',driver:'SiLA driver (P2)',protocol:'Protocol (GDTI·P3)',cloud:'Cloud/Edge (P4)',result:'Result',document:'Document (GDTI)',user:'User/Agent (GSRN)',component:'Component (CPID)',returnable:'Returnable (GRAI)'};
Object.keys(names).forEach(k=>{const s=document.createElement('span');s.innerHTML='<i style="color:'+C[k]+'"></i>'+names[k];L.appendChild(s);});
const gE=document.createElementNS(NS,'g'),gN=document.createElementNS(NS,'g');svg.appendChild(gE);svg.appendChild(gN);
const eEls=edges.map(e=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','edge');l.setAttribute('stroke',C[e.T.group]||'#3a5878');l.setAttribute('stroke-width',(e.ty==='runs'||e.ty==='has_driver'||e.ty==='contains')?1.5:1);gE.appendChild(l);return l;});
const nEls=nodes.map(n=>{const g=document.createElementNS(NS,'g');g.setAttribute('class','node '+n.group);
  const c=document.createElementNS(NS,'circle');const r=n.group==='location'?15:(n.group==='instrument'||n.group==='protocol'?9:6);
  c.setAttribute('r',r);c.setAttribute('fill',C[n.group]);c.setAttribute('stroke',C[n.group]);c.setAttribute('stroke-opacity',.35);c.setAttribute('stroke-width',6);c.style.filter='drop-shadow(0 0 6px '+C[n.group]+')';
  const t=document.createElementNS(NS,'text');t.setAttribute('x',r+4);t.setAttribute('y',4);t.textContent=n.label;g.appendChild(c);g.appendChild(t);gN.appendChild(g);
  let drag=false;c.addEventListener('pointerdown',ev=>{drag=true;n.fixed=true;c.setPointerCapture(ev.pointerId);});
  c.addEventListener('pointermove',ev=>{if(drag){const pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;n.x=pt.x;n.y=pt.y;}});
  c.addEventListener('pointerup',()=>{drag=false;n.fixed=false;});return g;});
function tick(){
  for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j];
    let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01,d=Math.sqrt(d2);const f=2500/d2;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}}
  edges.forEach(e=>{const a=e.S,b=e.T;if(!a||!b)return;let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01;const L0=(a.group==='location'||b.group==='location')?150:80;const f=(d-L0)*0.02;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;});
  nodes.forEach(n=>{n.vx+=(W/2-n.x)*0.0014;n.vy+=(H/2-n.y)*0.0014;if(!n.fixed){n.vx*=0.87;n.vy*=0.87;n.x+=n.vx;n.y+=n.vy;}});
  edges.forEach((e,i)=>{if(e.S&&e.T){eEls[i].setAttribute('x1',e.S.x);eEls[i].setAttribute('y1',e.S.y);eEls[i].setAttribute('x2',e.T.x);eEls[i].setAttribute('y2',e.T.y);}});
  nodes.forEach((n,i)=>{nEls[i].setAttribute('transform','translate('+n.x+','+n.y+')');});
  requestAnimationFrame(tick);
}
addEventListener('resize',()=>{W=innerWidth;H=innerHeight;});tick();
</script></body></html>"""

if __name__ == "__main__":
    main()
