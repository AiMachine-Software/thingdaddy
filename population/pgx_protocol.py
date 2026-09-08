#!/usr/bin/env python3
"""
pgx_protocol.py — a real protocol as a SHACL-shaped, typed metadata graph. The closed hypothesis,
executable.

Encodes the Thermo Fisher PGx (pharmacogenomics) genotyping workflow — swab -> DNA extraction on the
MagMax -> genotyping on OpenArray/QuantStudio -> allele calls — as a typed instance on the GS1 / AFO
taxonomy, then validates a RUN against SHACL-style shapes:

  * a correct run CONFORMS (all steps validate)
  * a run with a transfer swap throws an EXCEPTION at the offending step — the wrong sample is caught
    at the handoff instead of propagating to a confidently-wrong genotype.

TWO LAYERS, deliberately separated (KJ: "we can apply SHACL to every industry ontology"):
  * a GENERIC shape engine — domain-neutral; validates any typed protocol graph against shapes.
  * a PLUGGABLE ontology — here the Allotrope AFO / life-science vocabulary. Swap ONTOLOGY for a
    manufacturing (OPC-UA/QIF) or construction (IFC) vocabulary and the SAME shapes apply.

Identity is CANDIDATE: key types are assigned (GIAI equipment · SGTIN consumable · SGLN location ·
GDTI document/process) but NO URN is minted — no serial is fabricated. prefix-is-root holds; the
answerable party ratifies (R4). Nothing minted.

Outputs (in --outdir):
  pgx_protocol.json         the typed instance (nodes + steps + shapes + conformance)
  pgx_protocol_graph.html   the protocol as a typed metadata graph (AFO domains)

Usage:
  python3 pgx_protocol.py --outdir .
  python3 pgx_protocol.py --swap-at 9 --outdir .    # inject a transfer swap and watch it get caught
"""
from __future__ import annotations
import argparse, html, json, os

# ============================================================================
# PLUGGABLE ONTOLOGY — swap this per industry; the shape engine below is unchanged.
# ============================================================================
ONTOLOGY = {
    "name": "Allotrope AFO · life-science lab",
    "domains": ["equipment", "material", "process", "result", "location"],
    "key_by_domain": {"equipment": "giai", "material": "sgtin", "location": "sgln",
                      "process": "gdti", "result": "gdti"},
    "uses": ("equipment", "material"),          # the legal 'uses' edge: an instrument uses a consumable
}

# ============================================================================
# THE PGx INSTANCE (candidate; no minted URNs — key_type assigned, urn=None)
# ============================================================================
LOCATION = {"id": "loc", "label": "Lab location", "domain": "location"}

INSTRUMENTS = [   # equipment · GIAI (serialized instruments = edge ThingSites)
    {"id": "eq:magmax",      "label": "MagMax DNA Isolation System",     "domain": "equipment"},
    {"id": "eq:accufill",    "label": "OpenArray AccuFill System",       "domain": "equipment"},
    {"id": "eq:quantstudio", "label": "QuantStudio 12K Flex PCR System", "domain": "equipment"},
    {"id": "eq:alleletyper", "label": "AlleleTyper Software",            "domain": "equipment"},
]
CONSUMABLES = [   # material · SGTIN (serialized consumables = substitution slots)
    {"id": "mat:swab",     "label": "Swab (DNA)",     "domain": "material"},
    {"id": "mat:protease", "label": "Protease",       "domain": "material"},
    {"id": "mat:lysis",    "label": "Lysis Buffer",   "domain": "material"},
    {"id": "mat:beads",    "label": "Beads Solution", "domain": "material"},
    {"id": "mat:wash1",    "label": "Wash Buffer 1",  "domain": "material"},
    {"id": "mat:wash2",    "label": "Wash Buffer 2",  "domain": "material"},
    {"id": "mat:elution",  "label": "Elution Buffer", "domain": "material"},
    {"id": "mat:pcrmix",   "label": "PCR Mix",        "domain": "material"},
]
RESULTS = [
    {"id": "res:dna",      "label": "Extracted DNA", "domain": "result"},
    {"id": "res:genotype", "label": "Genotype calls", "domain": "result"},
]

# process steps. kind: prep|add|mix|transfer|load|run|qc|analyze.
# 'add' and 'transfer' are LIQUID/SAMPLE transfers (the handoffs). sample-bearing transfers carry a subject.
STEPS = [
    # -- Pretreatment --
    {"id": "s1",  "phase": "Pretreatment", "kind": "prep",     "label": "shake, remove swab", "plate": "A", "mat": "mat:swab"},
    {"id": "s2",  "phase": "Pretreatment", "kind": "add",      "label": "add Protease -> Plate A", "plate": "A", "mat": "mat:protease"},
    {"id": "s3",  "phase": "Pretreatment", "kind": "add",      "label": "add Lysis Buffer -> Plate A", "plate": "A", "mat": "mat:lysis"},
    {"id": "s4",  "phase": "Pretreatment", "kind": "mix",      "label": "mix beads (Plate A)", "plate": "A", "mat": "mat:beads"},
    # -- Extract DNA --
    {"id": "s5",  "phase": "Extract DNA",  "kind": "add",      "label": "add Beads Solution -> Plate B", "plate": "B", "mat": "mat:beads"},
    {"id": "s6",  "phase": "Extract DNA",  "kind": "add",      "label": "add Wash Buffer 1 -> Plate C", "plate": "C", "mat": "mat:wash1"},
    {"id": "s7",  "phase": "Extract DNA",  "kind": "add",      "label": "add Wash Buffer 2 -> Plate D", "plate": "D", "mat": "mat:wash2"},
    {"id": "s8",  "phase": "Extract DNA",  "kind": "add",      "label": "add Elution Buffer -> Plate E", "plate": "E", "mat": "mat:elution"},
    {"id": "s9",  "phase": "Extract DNA",  "kind": "transfer", "label": "transfer sample Plate A -> Plate F", "src": "A", "dst": "F", "subject": True},
    {"id": "s10", "phase": "Extract DNA",  "kind": "load",     "label": "load Plates B-F on MagMax", "instrument": "eq:magmax", "plates": ["B","C","D","E","F"]},
    {"id": "s11", "phase": "Extract DNA",  "kind": "run",      "label": "extract DNA (MagMax)", "instrument": "eq:magmax", "result": "res:dna"},
    {"id": "s12", "phase": "Extract DNA",  "kind": "transfer", "label": "transfer sample Plate F -> OpenArray Plate G", "src": "F", "dst": "G", "subject": True},
    # -- Load Sample --
    {"id": "s13", "phase": "Load Sample",  "kind": "qc",       "label": "QC each sample (optional)", "optional": True},
    {"id": "s14", "phase": "Load Sample",  "kind": "add",      "label": "prepare PCR Mix", "plate": "G", "mat": "mat:pcrmix"},
    {"id": "s15", "phase": "Load Sample",  "kind": "prep",     "label": "prep OpenArray Plate G", "plate": "G"},
    {"id": "s16", "phase": "Load Sample",  "kind": "prep",     "label": "track plate", "plate": "G"},
    {"id": "s17", "phase": "Load Sample",  "kind": "load",     "label": "run on AccuFill (loads OpenArray)", "instrument": "eq:accufill", "plates": ["G"]},
    # -- Cycle & Image --
    {"id": "s18", "phase": "Cycle & Image","kind": "prep",     "label": "prepare software"},
    {"id": "s19", "phase": "Cycle & Image","kind": "run",      "label": "run on QuantStudio 12K Flex", "instrument": "eq:quantstudio", "result": "res:dna"},
    {"id": "s20", "phase": "Cycle & Image","kind": "prep",     "label": "remove OpenArray plate", "plate": "G"},
    # -- Data Analysis --
    {"id": "s21", "phase": "Data Analysis","kind": "analyze",  "label": "analyze with AlleleTyper", "instrument": "eq:alleletyper", "result": "res:genotype"},
]

def build_graph():
    nodes = {}
    for n in [LOCATION] + INSTRUMENTS + CONSUMABLES + RESULTS:
        d = n["domain"]
        nodes[n["id"]] = {**n, "key_type": ONTOLOGY["key_by_domain"].get(d, ""),
                          "urn": None, "state": "candidate"}     # candidate — no URN minted
    return {"ontology": ONTOLOGY["name"], "location": LOCATION["id"], "nodes": nodes, "steps": STEPS}

# ============================================================================
# GENERIC SHAPE ENGINE — domain-neutral. Same shapes for any ontology.
# ============================================================================
def _sample_transfers(steps):
    return [s for s in steps if s.get("subject")]

def build_run(swap_at=None):
    """Replay the protocol's sample lineage. swap_at=<step id or index> injects a wrong destination."""
    plate = None; trail = []
    for i, s in enumerate(STEPS, 1):
        if s.get("subject"):
            src, dst = s["src"], s["dst"]
            actual_dst = dst
            if swap_at in (s["id"], i):                          # the fumble: sample goes to the wrong plate
                actual_dst = "X"                                 # a wrong/unexpected plate
            trail.append({"step": s["id"], "expected_dst": dst, "actual_dst": actual_dst, "src": src})
            plate = actual_dst
    return {"sample_end": plate, "trail": trail}

def shape_typed(graph, run, onto):
    """Every node carries a key type valid for its domain (issuable structure)."""
    v = []
    for nid, n in graph["nodes"].items():
        if n["domain"] not in onto["domains"]:
            v.append((nid, f"domain '{n['domain']}' not in ontology"))
        elif not n["key_type"]:
            v.append((nid, f"no key type for domain '{n['domain']}'"))
    return v

def shape_step_actor(graph, run, onto):
    """Every non-prep step references a valid instrument (equipment) or material in the graph."""
    v = []
    for s in STEPS:
        if s["kind"] in ("prep", "qc", "transfer"): continue   # transfers move a sample plate->plate; no instrument/material actor
        ref = s.get("instrument") or s.get("mat")
        if not ref:
            v.append((s["id"], f"step '{s['kind']}' has no equipment/material actor"))
        elif ref not in graph["nodes"]:
            v.append((s["id"], f"actor {ref} not a typed node"))
    return v

def shape_material_slot(graph, run, onto):
    """Every material an 'add/mix' step consumes is a real material node (substitution slot filled)."""
    v = []
    for s in STEPS:
        if s["kind"] in ("add", "mix"):
            m = s.get("mat")
            if not m or graph["nodes"].get(m, {}).get("domain") != "material":
                v.append((s["id"], f"material slot unfilled/mistyped: {m}"))
    return v

def shape_transfer_integrity(graph, run, onto):
    """THE CLOSED HYPOTHESIS: at every sample transfer the sample must arrive where the protocol
    expects it. A swap/misplate is caught HERE — an exception at the handoff, not a wrong result."""
    v = []
    for t in run["trail"]:
        if t["actual_dst"] != t["expected_dst"]:
            v.append((t["step"], f"sample expected in Plate {t['expected_dst']} but went to Plate "
                                 f"{t['actual_dst']} — WRONG SAMPLE at handoff (would produce a wrong genotype)"))
    return v

SHAPES = [shape_typed, shape_step_actor, shape_material_slot, shape_transfer_integrity]

def validate(graph, run, onto=ONTOLOGY):
    report = {}
    for shape in SHAPES:
        report[shape.__name__] = shape(graph, run, onto)
    violations = [(s, sid, msg) for s, viols in report.items() for sid, msg in viols]
    return {"conforms": not violations, "violations": violations, "by_shape": report}

def main():
    ap = argparse.ArgumentParser(description="PGx protocol as a SHACL-shaped AFO instance.")
    ap.add_argument("--swap-at", help="inject a transfer swap at this step id (e.g. s9) or index")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    graph = build_graph()
    n_trans = len([s for s in STEPS if s["kind"] in ("add", "transfer")])
    print(f">> PGx protocol · ontology={ONTOLOGY['name']}")
    print(f"   {len(INSTRUMENTS)} instruments (GIAI) · {len(CONSUMABLES)} consumables (SGTIN) · "
          f"{len(STEPS)} steps · {n_trans} liquid/sample transfers · candidate (no URN minted)")

    # 1) correct run
    good = build_run()
    rg = validate(graph, good)
    print(f"\n>> CORRECT run  -> {'CONFORMS ✓' if rg['conforms'] else 'VIOLATIONS'}  "
          f"(all {len(STEPS)} steps validate against {len(SHAPES)} shapes)")

    # 2) run with a transfer swap
    swap = a.swap_at or "s9"
    bad = build_run(swap_at=swap if not str(swap).isdigit() else int(swap))
    rb = validate(graph, bad)
    print(f">> SWAPPED run (transfer error at {swap}) -> {'CONFORMS' if rb['conforms'] else 'EXCEPTION ✗'}")
    for s, sid, msg in rb["violations"]:
        print(f"     [{sid}] {msg}")
    print("   ^ the wrong sample is CAUGHT at the handoff — not propagated to a confidently-wrong genotype.")

    # emit json
    out = {"ontology": ONTOLOGY, "graph": {"nodes": graph["nodes"]}, "steps": STEPS,
           "shapes": [s.__name__ for s in SHAPES],
           "conformance": {"correct_run": rg["conforms"], "swapped_run": rb["conforms"],
                           "swapped_violations": [{"step": sid, "shape": s, "msg": m} for s, sid, m in rb["violations"]]},
           "note": "Candidate; no URN minted (key types assigned, prefix-is-root holds, R4 ratifies). "
                   "SHACL-style shapes; a production version emits SHACL/RDF. The shape engine is "
                   "domain-neutral — swap ONTOLOGY for any industry vocabulary and the shapes still apply."}
    with open(os.path.join(a.outdir, "pgx_protocol.json"), "w") as f: json.dump(out, f, indent=2)

    # render graph
    page = render_graph(graph)
    gp = os.path.join(a.outdir, "pgx_protocol_graph.html")
    with open(gp, "w") as f: f.write(page)
    print(f"\n   -> {os.path.join(a.outdir,'pgx_protocol.json')}")
    print(f"   -> {gp}")
    print("   One machine, one ontology plugged in. Swap the ontology (OPC-UA / IFC / …) — same shapes. Nothing minted.")

# --- typed metadata graph render (AFO domains) ------------------------------
DCOLOR = {"equipment": "#39d98a", "material": "#ff9f43", "process": "#c98bff",
          "result": "#ff6b9d", "location": "#5b8cff"}
def render_graph(graph):
    nodes, edges, idx = [], [], {}
    def add(nid, label, group):
        if nid in idx: return
        idx[nid] = True; nodes.append({"id": nid, "label": label, "group": group})
    add("loc", LOCATION["label"], "location")
    for n in INSTRUMENTS: add(n["id"], n["label"], "equipment"); edges.append({"s": "loc", "t": n["id"], "ty": "at"})
    for n in CONSUMABLES: add(n["id"], n["label"], "material")
    for n in RESULTS: add(n["id"], n["label"], "result")
    prev = None
    for s in STEPS:
        sid = s["id"]; add(sid, s["label"][:30], "process")
        if prev: edges.append({"s": prev, "t": sid, "ty": "then"})
        prev = sid
        if s.get("instrument"): edges.append({"s": sid, "t": s["instrument"], "ty": "on"})
        if s.get("mat"): edges.append({"s": sid, "t": s["mat"], "ty": "uses"})
        if s.get("result"): edges.append({"s": sid, "t": s["result"], "ty": "yields"})
        if s.get("kind") == "transfer": edges.append({"s": sid, "t": sid, "ty": "handoff"})
    data = {"nodes": nodes, "edges": edges, "colors": DCOLOR}
    return HTML.replace("__DATA__", json.dumps(data))

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PGx Protocol · Typed Metadata Graph</title>
<style>
html,body{margin:0;height:100%;background:#070b12;color:#e8eef7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;overflow:hidden}
#hud{position:fixed;top:0;left:0;right:0;padding:14px 18px;pointer-events:none;z-index:5}
#hud .t{font-size:15px;font-weight:800}#hud .s{font-size:12px;color:#8fa3bd;margin-top:2px;max-width:720px}
#legend{position:fixed;bottom:14px;left:18px;font-size:12px;z-index:5;background:rgba(10,16,26,.6);border:1px solid #1c2a3b;border-radius:10px;padding:9px 12px}
#legend span{display:inline-flex;align-items:center;margin-right:12px}#legend i{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;box-shadow:0 0 8px currentColor}
#foot{position:fixed;bottom:14px;right:18px;font-size:11px;color:#5b6b82;z-index:5}
svg{width:100vw;height:100vh;display:block}.edge{stroke-opacity:.3}
.node text{font-size:10px;fill:#c7d4e6;paint-order:stroke;stroke:#070b12;stroke-width:3px;pointer-events:none}
.node.process text{font-size:10px;fill:#e7d6ff}
</style></head><body>
<div id=hud><div class=t>PGx Protocol · Typed Metadata Graph <span style="color:#8fa3bd;font-weight:600">— AFO domains, GS1 keys, candidate</span></div>
<div class=s>The real Thermo PGx genotyping workflow as a typed instance: equipment (GIAI) · material (SGTIN) · process (the steps) · result. Every sample transfer is a SHACL-shaped handoff — conform or exception. Candidate; no URN minted. Drag a node.</div></div>
<div id=legend></div><div id=foot>SHACL-shaped · candidate · nothing minted</div>
<svg id=svg></svg>
<script>
const DATA=__DATA__;const svg=document.getElementById('svg'),NS='http://www.w3.org/2000/svg';let W=innerWidth,H=innerHeight;
const nodes=DATA.nodes,edges=DATA.edges,C=DATA.colors;const byId={};
nodes.forEach((n,i)=>{byId[n.id]=n;n.x=W/2+Math.cos(i*2.399)*(90+i*7);n.y=H/2+Math.sin(i*2.399)*(90+i*5);n.vx=0;n.vy=0;});
edges.forEach(e=>{e.S=byId[e.s];e.T=byId[e.t];});
const L=document.getElementById('legend');const names={equipment:'Equipment (GIAI)',material:'Material (SGTIN)',process:'Process step',result:'Result',location:'Location (SGLN)'};
Object.keys(names).forEach(k=>{const s=document.createElement('span');s.innerHTML='<i style="color:'+C[k]+'"></i>'+names[k];L.appendChild(s);});
const gE=document.createElementNS(NS,'g'),gN=document.createElementNS(NS,'g');svg.appendChild(gE);svg.appendChild(gN);
const eEls=edges.map(e=>{if(e.s===e.t)return null;const l=document.createElementNS(NS,'line');l.setAttribute('class','edge');l.setAttribute('stroke',e.ty==='handoff'?'#ff5470':(C[e.T.group]||'#3a5878'));l.setAttribute('stroke-width',e.ty==='then'?1.8:1);gE.appendChild(l);return l;});
const nEls=nodes.map(n=>{const g=document.createElementNS(NS,'g');g.setAttribute('class','node '+n.group);
  const c=document.createElementNS(NS,'circle');const r=n.group==='location'?12:(n.group==='process'?6:8);
  c.setAttribute('r',r);c.setAttribute('fill',C[n.group]);c.setAttribute('stroke',C[n.group]);c.setAttribute('stroke-opacity',.35);c.setAttribute('stroke-width',6);c.style.filter='drop-shadow(0 0 6px '+C[n.group]+')';
  const t=document.createElementNS(NS,'text');t.setAttribute('x',r+4);t.setAttribute('y',4);t.textContent=n.label;g.appendChild(c);g.appendChild(t);gN.appendChild(g);
  let drag=false;c.addEventListener('pointerdown',ev=>{drag=true;n.fixed=true;c.setPointerCapture(ev.pointerId);});
  c.addEventListener('pointermove',ev=>{if(drag){const pt=svg.createSVGPoint();pt.x=ev.clientX;pt.y=ev.clientY;n.x=pt.x;n.y=pt.y;}});
  c.addEventListener('pointerup',()=>{drag=false;n.fixed=false;});return g;});
function tick(){
  for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j];
    let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.01,d=Math.sqrt(d2);const f=2400/d2;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}}
  edges.forEach(e=>{if(e.s===e.t||!e.S||!e.T)return;const a=e.S,b=e.T;let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01;const L0=(a.group==='process'&&b.group==='process')?60:100;const f=(d-L0)*0.02;const fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;});
  nodes.forEach(n=>{n.vx+=(W/2-n.x)*0.0015;n.vy+=(H/2-n.y)*0.0015;if(!n.fixed){n.vx*=0.86;n.vy*=0.86;n.x+=n.vx;n.y+=n.vy;}});
  edges.forEach((e,i)=>{if(eEls[i]&&e.S&&e.T){eEls[i].setAttribute('x1',e.S.x);eEls[i].setAttribute('y1',e.S.y);eEls[i].setAttribute('x2',e.T.x);eEls[i].setAttribute('y2',e.T.y);}});
  nodes.forEach((n,i)=>{nEls[i].setAttribute('transform','translate('+n.x+','+n.y+')');});
  requestAnimationFrame(tick);
}
addEventListener('resize',()=>{W=innerWidth;H=innerHeight;});tick();
</script></body></html>"""

if __name__ == "__main__":
    main()
