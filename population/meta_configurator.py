#!/usr/bin/env python3
"""
meta_configurator.py — the meta-configurator. We don't build ontologies and we don't build
instances; we author the TEMPLATES in between, and validate instances against them.

The flow KJ specified:
    load an ONTOLOGY  ->  author a TEMPLATE (SHACL-style)  ->  configure an INSTANCE  ->  VALIDATE

Three layers, one generic engine:
  * ONTOLOGY  — the vocabulary (domains, key-by-domain, legal edges). Inherited. Pluggable — swap it
    and everything below still works ("apply SHACL to every industry ontology").
  * TEMPLATE  — what we author: named slots + declarative shape rules. This is the product: a
    reusable, verifiable configuration type (a "thingsite" type, a "protocol" type). Candidate.
  * INSTANCE  — configured against a template by filling slots + drawing edges. Candidate; no URN minted.

The engine is DOMAIN-NEUTRAL: it interprets shape rules against any (ontology, template, instance).
Nothing is minted; a template composes from the ontology, an instance conforms or throws an exception.

Outputs (--outdir):
  templates.json        the authored templates (the asset)
  conformance.json      validation results for the demo instances
  meta_configurator.html a template + conformance view

Usage:
  python3 meta_configurator.py --outdir .
"""
from __future__ import annotations
import argparse, html, json, os
from collections import Counter

# ============================================================================
# ONTOLOGIES — pluggable vocabulary. Swap freely; the engine + shape rules are unchanged.
# ============================================================================
ONTOLOGIES = {
    "afo-lab": {
        "name": "Allotrope AFO · life-science lab",
        "domains": ["location", "equipment", "material", "process", "result",
                    "document", "user", "component", "returnable", "driver", "cloud"],
        "key_by_domain": {"location": "sgln", "equipment": "giai", "material": "sgtin",
                          "process": "gdti", "result": "", "document": "gdti", "user": "gsrn",
                          "component": "cpid", "returnable": "grai", "driver": "", "cloud": ""},
        "edges": [   # legal (from_domain, edge_type, to_domain)
            ("location", "contains", "equipment"), ("location", "contains", "process"),
            ("equipment", "has_driver", "driver"), ("equipment", "bound_to", "cloud"),
            ("equipment", "runs", "process"), ("process", "uses", "material"),
            ("process", "yields", "result"), ("document", "describes", "equipment"),
            ("user", "operates", "process"), ("component", "part_of", "equipment"),
            ("returnable", "at", "location"),
        ],
    },
    "mfg": {   # a DIFFERENT industry vocabulary — proves the engine is domain-neutral
        "name": "Manufacturing · OPC-UA / work-cell",
        "domains": ["location", "machine", "part", "operation", "output", "controller", "cloud"],
        "key_by_domain": {"location": "sgln", "machine": "giai", "part": "sgtin",
                          "operation": "gdti", "output": "", "controller": "", "cloud": ""},
        "edges": [
            ("location", "contains", "machine"), ("machine", "has_driver", "controller"),
            ("machine", "bound_to", "cloud"), ("machine", "runs", "operation"),
            ("operation", "consumes", "part"), ("operation", "yields", "output"),
        ],
    },
}

# ============================================================================
# TEMPLATES — what WE author. Declarative slots + shape rules. The reusable asset.
# ============================================================================
TEMPLATES = {
    "thingsite": {
        "ontology": "afo-lab",
        "title": "ThingSite (a location, fully populated)",
        "slots": [   # name, domain, min, max (None = unbounded)
            {"slot": "location", "domain": "location", "min": 1, "max": 1},
            {"slot": "instrument", "domain": "equipment", "min": 1, "max": None},
            {"slot": "protocol", "domain": "process", "min": 0, "max": None},
            {"slot": "consumable", "domain": "material", "min": 0, "max": None},
        ],
        "shapes": [   # generic rules the engine interprets
            {"rule": "key_matches_domain"},
            {"rule": "slot_cardinality"},
            {"rule": "edge_legal"},
            {"rule": "required_out_edge", "domain": "equipment", "edge": "has_driver", "min": 1,
             "why": "every instrument must declare a driver (P2) — how you talk to it"},
            {"rule": "required_out_edge", "domain": "equipment", "edge": "bound_to", "min": 1,
             "why": "every instrument must bind to a cloud/edge (P4) — where it runs"},
        ],
    },
    "protocol": {
        "ontology": "afo-lab",
        "title": "Protocol (a method + its materials)",
        "slots": [
            {"slot": "protocol", "domain": "process", "min": 1, "max": 1},
            {"slot": "consumable", "domain": "material", "min": 1, "max": None},
        ],
        "shapes": [
            {"rule": "key_matches_domain"},
            {"rule": "slot_cardinality"},
            {"rule": "edge_legal"},
            {"rule": "required_out_edge", "domain": "process", "edge": "uses", "min": 1,
             "why": "a protocol must use at least one material (the substitution slot)"},
        ],
    },
    "workcell": {   # authored on the MANUFACTURING ontology — same engine
        "ontology": "mfg",
        "title": "Work-cell (a machine + its operation)",
        "slots": [
            {"slot": "location", "domain": "location", "min": 1, "max": 1},
            {"slot": "machine", "domain": "machine", "min": 1, "max": None},
            {"slot": "operation", "domain": "operation", "min": 0, "max": None},
        ],
        "shapes": [
            {"rule": "key_matches_domain"},
            {"rule": "slot_cardinality"},
            {"rule": "edge_legal"},
            {"rule": "required_out_edge", "domain": "machine", "edge": "has_driver", "min": 1,
             "why": "every machine must declare a controller"},
        ],
    },
}

# ============================================================================
# GENERIC ENGINE — validate any instance against any template on any ontology.
# instance = {"nodes":[{id,label,domain,key,slot}], "edges":[{s,t,type}]}
# ============================================================================
def _legal_edges(onto):
    return {(f, t, d) for f, t, d in onto["edges"]}

def shape_key_matches_domain(inst, tmpl, onto):
    v = []
    for n in inst["nodes"]:
        want = onto["key_by_domain"].get(n["domain"], None)
        if want is None:
            v.append((n["id"], f"domain '{n['domain']}' not in ontology '{onto['name']}'"))
        elif want and n.get("key") != want:
            v.append((n["id"], f"key '{n.get('key')}' != required '{want}' for domain '{n['domain']}'"))
    return v

def shape_slot_cardinality(inst, tmpl, onto):
    v = []; counts = Counter(n.get("slot", "") for n in inst["nodes"])
    for s in tmpl["slots"]:
        c = counts.get(s["slot"], 0)
        if c < s["min"]:
            v.append((s["slot"], f"slot '{s['slot']}' has {c}, needs >= {s['min']}"))
        if s["max"] is not None and c > s["max"]:
            v.append((s["slot"], f"slot '{s['slot']}' has {c}, allows <= {s['max']}"))
    return v

def shape_edge_legal(inst, tmpl, onto):
    v = []; legal = _legal_edges(onto); dom = {n["id"]: n["domain"] for n in inst["nodes"]}
    for e in inst["edges"]:
        fd, td = dom.get(e["s"]), dom.get(e["t"])
        if fd is None or td is None:
            v.append((e.get("type"), f"edge endpoint not a node: {e['s']}->{e['t']}")); continue
        if (fd, e["type"], td) not in legal:
            v.append((e["type"], f"illegal edge: {fd} --{e['type']}--> {td} (not in ontology)"))
    return v

def shape_required_out_edge(inst, tmpl, onto, domain, edge, min, why=""):
    v = []; dom = {n["id"]: n["domain"] for n in inst["nodes"]}
    out = Counter()
    for e in inst["edges"]:
        if e["type"] == edge and dom.get(e["s"]) == domain: out[e["s"]] += 1
    for n in inst["nodes"]:
        if n["domain"] == domain and out.get(n["id"], 0) < min:
            v.append((n["id"], f"missing '{edge}' (>= {min}) — {why}"))
    return v

RULES = {"key_matches_domain": shape_key_matches_domain, "slot_cardinality": shape_slot_cardinality,
         "edge_legal": shape_edge_legal, "required_out_edge": shape_required_out_edge}

def validate(inst, tmpl_name):
    tmpl = TEMPLATES[tmpl_name]; onto = ONTOLOGIES[tmpl["ontology"]]
    report = {}
    for shape in tmpl["shapes"]:
        fn = RULES[shape["rule"]]
        params = {k: v for k, v in shape.items() if k not in ("rule", "why")}
        if shape["rule"] == "required_out_edge": params["why"] = shape.get("why", "")
        report[shape["rule"] + (":" + shape.get("edge", "") if shape["rule"] == "required_out_edge" else "")] = fn(inst, tmpl, onto, **params)
    viols = [(s, nid, msg) for s, vs in report.items() for nid, msg in vs]
    return {"template": tmpl_name, "ontology": tmpl["ontology"], "conforms": not viols,
            "violations": viols, "by_shape": report}

# ============================================================================
# EXAMPLE INSTANCES — configured against templates (candidate; no URN minted)
# ============================================================================
def node(nid, label, domain, slot):
    return {"id": nid, "label": label, "domain": domain,
            "key": ONTOLOGIES_KEY(domain), "slot": slot, "state": "candidate", "urn": None}

def ONTOLOGIES_KEY(domain):   # helper: default afo-lab key for a domain
    return ONTOLOGIES["afo-lab"]["key_by_domain"].get(domain, "")

def thingsite_instance(break_it=False):
    """The complete node, configured against the 'thingsite' template."""
    nodes = [node("loc", "51 Allen Way (SGLN)", "location", "location")]
    inst = [("eq:magmax", "MagMax"), ("eq:accufill", "AccuFill"), ("eq:quant", "QuantStudio")]
    edges = []
    for eid, lbl in inst:
        nodes.append(node(eid, lbl, "equipment", "instrument"))
        nodes.append({"id": "drv:" + eid, "label": "SiLA driver", "domain": "driver", "key": "", "slot": "driver"})
        nodes.append({"id": "cloud:" + eid, "label": "AWS IoT", "domain": "cloud", "key": "", "slot": "cloud"})
        edges.append({"s": "loc", "t": eid, "type": "contains"})
        edges.append({"s": eid, "t": "cloud:" + eid, "type": "bound_to"})
        if not (break_it and eid == "eq:magmax"):           # break: drop MagMax's driver edge
            edges.append({"s": eid, "t": "drv:" + eid, "type": "has_driver"})
    nodes.append(node("proc:pgx", "PGx protocol", "process", "protocol"))
    edges.append({"s": "loc", "t": "proc:pgx", "type": "contains"})
    for i, c in enumerate(["Protease", "Lysis Buffer", "Elution Buffer"]):
        cid = "mat:%d" % i; nodes.append(node(cid, c, "material", "consumable"))
        edges.append({"s": "proc:pgx", "t": cid, "type": "uses"})
    for eid, _ in inst: edges.append({"s": eid, "t": "proc:pgx", "type": "runs"})
    return {"nodes": nodes, "edges": edges}

def workcell_instance():
    """A manufacturing work-cell, configured against the 'workcell' template on the MFG ontology."""
    K = ONTOLOGIES["mfg"]["key_by_domain"]
    def mn(nid, label, domain, slot): return {"id": nid, "label": label, "domain": domain, "key": K.get(domain, ""), "slot": slot}
    nodes = [mn("loc", "Fab bay (SGLN)", "location", "location"),
             mn("m:cnc", "CNC mill", "machine", "machine"),
             mn("ctrl", "OPC-UA controller", "controller", "controller"),
             mn("cloud", "Azure IoT", "cloud", "cloud"),
             mn("op:mill", "Milling operation", "operation", "operation"),
             mn("part:blank", "Aluminium blank", "part", "part")]
    edges = [{"s": "loc", "t": "m:cnc", "type": "contains"}, {"s": "m:cnc", "t": "ctrl", "type": "has_driver"},
             {"s": "m:cnc", "t": "cloud", "type": "bound_to"}, {"s": "m:cnc", "t": "op:mill", "type": "runs"},
             {"s": "op:mill", "t": "part:blank", "type": "consumes"}]
    return {"nodes": nodes, "edges": edges}

def main():
    ap = argparse.ArgumentParser(description="The meta-configurator: author templates, validate instances.")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    print(">> META-CONFIGURATOR")
    print(f"   ontologies: {', '.join(o['name'] for o in ONTOLOGIES.values())}")
    print(f"   templates authored: {', '.join(TEMPLATES)}")

    runs = []
    # 1) configure the complete node against the thingsite template -> conforms
    good = thingsite_instance()
    rg = validate(good, "thingsite"); runs.append(("thingsite (complete node)", rg))
    print(f"\n>> configure INSTANCE against template 'thingsite' -> {'CONFORMS ✓' if rg['conforms'] else 'VIOLATIONS'}")

    # 2) break it (drop an instrument's driver) -> exception
    bad = thingsite_instance(break_it=True)
    rb = validate(bad, "thingsite"); runs.append(("thingsite (broken: no driver on MagMax)", rb))
    print(f">> break it (MagMax has no driver) -> {'CONFORMS' if rb['conforms'] else 'EXCEPTION ✗'}")
    for s, nid, msg in rb["violations"]: print(f"     [{nid}] {msg}   ({s})")

    # 3) swap ontology: validate a manufacturing work-cell with the SAME engine
    mc = workcell_instance()
    rm = validate(mc, "workcell"); runs.append(("workcell (manufacturing ontology)", rm))
    print(f">> SWAP ONTOLOGY -> configure a work-cell against template 'workcell' (mfg) -> "
          f"{'CONFORMS ✓' if rm['conforms'] else 'VIOLATIONS'}   (same engine, different vocabulary)")

    # emit
    with open(os.path.join(a.outdir, "templates.json"), "w") as f:
        json.dump({"ontologies": ONTOLOGIES, "templates": TEMPLATES}, f, indent=2)
    with open(os.path.join(a.outdir, "conformance.json"), "w") as f:
        json.dump([{"case": c, "conforms": r["conforms"], "violations": r["violations"]} for c, r in runs], f, indent=2)
    page = render(runs)
    with open(os.path.join(a.outdir, "meta_configurator.html"), "w") as f: f.write(page)
    print(f"\n   -> {os.path.join(a.outdir,'templates.json')}  (the authored asset)")
    print(f"   -> {os.path.join(a.outdir,'conformance.json')}")
    print(f"   -> {os.path.join(a.outdir,'meta_configurator.html')}")
    print("   Author the template once; configure infinitely many instances; validate generically. "
          "Swap the ontology, reuse the engine. Candidate; nothing minted.")

def esc(s): return html.escape(str(s if s is not None else ""))
def render(runs):
    tcards = ""
    for tname, t in TEMPLATES.items():
        slots = "".join(f'<li><b>{esc(s["slot"])}</b> · {esc(s["domain"])} '
                        f'<span class=card>{s["min"]}..{"∞" if s["max"] is None else s["max"]}</span></li>' for s in t["slots"])
        shapes = "".join(f'<li>{esc(sh["rule"])}{(" · "+esc(sh.get("edge",""))) if sh.get("edge") else ""}'
                         f'{(" — "+esc(sh["why"])) if sh.get("why") else ""}</li>' for sh in t["shapes"])
        tcards += (f'<div class=tmpl><div class=th>{esc(t["title"])} '
                   f'<span class=onto>{esc(ONTOLOGIES[t["ontology"]]["name"])}</span></div>'
                   f'<div class=sec>SLOTS</div><ul>{slots}</ul>'
                   f'<div class=sec>SHAPES</div><ul class=sh>{shapes}</ul></div>')
    rcards = ""
    for case, r in runs:
        badge = '<span class=ok>CONFORMS</span>' if r["conforms"] else '<span class=bad>EXCEPTION</span>'
        viols = "".join(f'<li>[{esc(nid)}] {esc(msg)}</li>' for s, nid, msg in r["violations"]) or "<li class=muted>— all shapes pass —</li>"
        rcards += f'<div class=run><div class=rh>{esc(case)} {badge}</div><ul>{viols}</ul></div>'
    return HTML.replace("__TEMPLATES__", tcards).replace("__RUNS__", rcards)

HTML = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Meta-Configurator</title>
<style>
:root{--acc:#1466b8;--ink:#12212f;--dim:#5a6b82;--line:#dde5ef;--ok:#0d7a52;--bad:#b3261e}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#f6f9fc}
.wrap{max-width:1080px;margin:0 auto;padding:26px 26px 80px}
h1{font-size:22px;margin:0 0 4px}.sub{font-size:13px;color:var(--dim);margin-bottom:18px;max-width:820px;line-height:1.5}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin:26px 0 10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.tmpl{background:#fff;border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:12px;padding:12px 15px}
.th{font-size:15px;font-weight:800}.onto{display:block;font-size:11px;color:var(--dim);font-weight:600;margin-top:2px}
.sec{font-size:11px;letter-spacing:.06em;color:var(--dim);margin:10px 0 3px;font-weight:700}
ul{margin:2px 0;padding-left:16px}li{font-size:12.5px;line-height:1.5;margin:2px 0}
.card{background:#eef2f8;border-radius:6px;padding:0 6px;font-size:11px;color:var(--dim)}
ul.sh li{color:#3a4a5e}
.run{background:#fff;border:1px solid var(--line);border-radius:12px;padding:11px 15px;margin-bottom:10px}
.rh{font-size:14px;font-weight:700}
.ok{font-size:11px;background:var(--ok);color:#fff;border-radius:10px;padding:1px 8px;margin-left:6px}
.bad{font-size:11px;background:var(--bad);color:#fff;border-radius:10px;padding:1px 8px;margin-left:6px}
.muted{color:#93a3b8;list-style:none;margin-left:-14px}
.note{margin-top:22px;padding:12px 15px;border-left:4px solid var(--acc);background:#eef3fb;border-radius:8px;font-size:12.5px;line-height:1.6}
</style></head><body><div class=wrap>
<h1>The Meta-Configurator</h1>
<div class=sub>We don't build the ontologies (inherited) or the instances (users configure). We author the <b>templates</b> in between — reusable, SHACL-shaped configuration types — and one generic engine validates any instance against any template on any ontology. Author once; configure infinitely; swap the ontology and reuse the engine. Candidate; nothing minted.</div>
<h2>Authored templates (the asset)</h2>
<div class=grid>__TEMPLATES__</div>
<h2>Configure &amp; validate (the engine)</h2>
__RUNS__
<div class=note><b>The product is the middle layer.</b> A template says what's <i>issuable</i> — it constrains an open ontology into a verifiable type. Configuring an instance fills the slots and draws the edges; the engine either conforms it or throws an exception at the exact violation (a missing driver, an illegal edge, a wrong key). The manufacturing work-cell validates on the <i>same engine</i> as the lab ThingSite — that's "apply SHACL to every industry ontology." A neutral template library on GS1 identity.</div>
</div></body></html>"""

if __name__ == "__main__":
    main()
