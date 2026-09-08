#!/usr/bin/env python3
"""
ThingDaddy Agent Fleet - Loop B + Driver/Binding loops (F4 / F5 / F6)
=====================================================================
Extends thingdaddy_agent_fleet.py with the next executable loops, all under
the same verified-or-exception discipline and GSRN-passport governance.

Loop B - Relationship & Graph (F4)
    Source Connectors (SEC EDGAR Exhibit 21, USASpending, SAM.gov)
        -> TD-A-15 Relationship Discovery  : raw filings -> candidate edges
        -> TD-A-16 Partner-Table Builder   : verified prefixes -> role-chains
        -> TD-A-18 Edge Inferrer   [IP]    : graph -> likely-but-unstated edges
        -> TD-A-17 Graph Assembler         : things + edges -> AI graph
    Edges are CANDIDATE by default (illustrative). An edge is promoted to
    VERIFIED only when BOTH endpoints are registered parties AND the edge has a
    documentary source (an Exhibit-21 line, an award record). Never guessed.

Driver / Binding loops (F5 / F6)
    -> TD-A-19 Driver-Authoring (Encoder)  : instrument GIAI -> SiLA driver
    -> TD-A-20 Workflow / Protocol Agent   : driver -> Allotrope-style protocol
    -> TD-A-21 Capability Mapper           : carriers+features -> capability profile
    -> TD-A-24 No-Assumption Guard         : block parent-brand; force record/GLN
    -> TD-A-22 Binding Agent               : commission -> factory test-bind + GDTI
    -> TD-A-23 Re-home Agent               : custody change -> operator GLN

Requires thingdaddy_agent_fleet.py in the same directory (imports its
RunContext, agent_gsrn, orchestrate, register flow, and seed).

Usage:
    python thingdaddy_agent_fleet_loopB.py            # built-in demo (Samsung + fab)
    python thingdaddy_agent_fleet_loopB.py --edges-only
    python thingdaddy_agent_fleet_loopB.py --drivers-only
"""

from __future__ import annotations
import json, re, sys, uuid
from pathlib import Path

# import the core fleet primitives
from thingdaddy_agent_fleet import (
    RunContext, agent_gsrn, now, new_id,
    orchestrate, source_connectors, OUT_DIR,
)

LOOPB_LEDGER = OUT_DIR / "agent_fleet_loopB_ledger.json"


# ══════════════════════════════════════════════════════════════════════════════
# F4 - LOOP B : RELATIONSHIP & GRAPH
# ══════════════════════════════════════════════════════════════════════════════

# ── TD-A-06 (extended): relationship source connectors (offline seed) ──
# TODO(live): replace with real pulls:
#   SEC EDGAR   -> company Exhibit 21 (subsidiaries)         edge: parent_of
#   USASpending -> federal award recipients + parents        edge: awarded / recipient_parent
#   SAM.gov     -> entity registration + hierarchy (UEI/CAGE) edge: registered_as
def relationship_sources(anchor_prefix: str, anchor_name: str) -> list[dict]:
    """Return raw relationship records as (source, subject, object, kind, doc)."""
    # Illustrative Loop-B records for the Samsung anchor. Each carries a
    # documentary 'doc' reference (what a real Exhibit-21 / award row would give).
    return [
        {"source":"SEC-EDGAR-EX21", "subject":anchor_name, "object":"Samsung Semiconductor, Inc.",
         "kind":"parent_of", "doc":"EX-21.1 subsidiary list", "object_prefix":None},
        {"source":"SEC-EDGAR-EX21", "subject":anchor_name, "object":"Samsung SDI Co., Ltd.",
         "kind":"parent_of", "doc":"EX-21.1 subsidiary list", "object_prefix":"8801234"},
        {"source":"USASPENDING",    "subject":"Samsung Semiconductor, Inc.", "object":"US Federal (CHIPS)",
         "kind":"award_recipient", "doc":"award-id FA8xxx", "object_prefix":None},
        {"source":"SAM-GOV",        "subject":"Samsung Semiconductor, Inc.", "object":"UEI:SAMS...",
         "kind":"registered_as", "doc":"SAM entity registration", "object_prefix":None},
        # a deliberately weak/unsourced record to show it stays candidate:
        {"source":"WEB",            "subject":anchor_name, "object":"Some Supplier LLC",
         "kind":"supplies", "doc":None, "object_prefix":None},
    ]


# ── TD-A-15 Relationship Discovery [IP -> IP-C-10] ──
def relationship_discovery(ctx: RunContext, raw_rel: list[dict]) -> list[dict]:
    """Raw filings -> candidate edges. Every edge starts CANDIDATE (illustrative)."""
    edges = []
    for r in raw_rel:
        edge = {
            "edgeId": new_id("edge"),
            "subject": r["subject"], "object": r["object"], "kind": r["kind"],
            "source": r["source"], "doc": r.get("doc"),
            "object_prefix": r.get("object_prefix"),
            "state": "candidate",
            "reasons": [f"from {r['source']}"],
        }
        edges.append(edge)
        ctx.emit("TD-A-15", "candidate_edge", {"edge": f"{r['subject']} -{r['kind']}-> {r['object']}", "source": r["source"]})
    return edges


# ── TD-A-16 Partner-Table Builder ──
def partner_table_builder(ctx: RunContext, edges: list[dict], registry: dict) -> list[dict]:
    """Verified prefixes -> role-chains for the demo builder. Only chains whose
       object is (or can become) a registered party are surfaced as partner rows."""
    rows = []
    for e in edges:
        obj_registered = e.get("object_prefix") in registry if e.get("object_prefix") else False
        rows.append({"subject": e["subject"], "object": e["object"], "kind": e["kind"],
                     "object_prefix": e.get("object_prefix"),
                     "partner_ready": bool(obj_registered)})
    ctx.emit("TD-A-16", "partner_table", {"rows": len(rows), "ready": sum(1 for r in rows if r["partner_ready"])})
    return rows


# ── TD-A-18 Edge Inferrer [IP -> IP-C-10] ──
def edge_inferrer(ctx: RunContext, edges: list[dict]) -> list[dict]:
    """Graph -> likely-but-unstated edges. Inferred edges are ALWAYS candidate and
       clearly flagged inferred=True. They never mint or verify anything."""
    inferred = []
    # simple transitive hint: A parent_of B, B award_recipient X  =>  A related_to X (inferred)
    parents = [e for e in edges if e["kind"] == "parent_of"]
    awards  = [e for e in edges if e["kind"] == "award_recipient"]
    for p in parents:
        for a in awards:
            if p["object"] == a["subject"]:
                inferred.append({
                    "edgeId": new_id("edge"),
                    "subject": p["subject"], "object": a["object"], "kind": "related_to",
                    "source": "INFERRED", "doc": None, "object_prefix": None,
                    "state": "candidate", "inferred": True,
                    "reasons": [f"transitive via {p['object']}"],
                })
                ctx.emit("TD-A-18", "inferred_edge", {"edge": f"{p['subject']} ~related~> {a['object']}"})
    return inferred


# ── TD-A-09 (edge verification) + TD-A-10 gate, applied to edges ──
def verify_edges(ctx: RunContext, edges: list[dict], registry: dict) -> list[dict]:
    """An edge is VERIFIED only if BOTH endpoints resolve to registered parties
       AND it has a documentary source. Otherwise it stays candidate/exception."""
    name_to_prefix = {p["orgName"].lower(): pfx for pfx, p in registry.items()}
    for e in edges:
        if e.get("inferred"):
            e["reasons"].append("inferred - stays candidate"); continue
        subj_reg = e["subject"].lower() in name_to_prefix
        obj_reg  = (e.get("object_prefix") in registry) if e.get("object_prefix") else (e["object"].lower() in name_to_prefix)
        if subj_reg and obj_reg and e.get("doc"):
            e["state"] = "verified"
            e["reasons"].append("both endpoints registered + documentary source")
            ctx.emit("TD-A-09", "verified_edge", {"edge": f"{e['subject']} -{e['kind']}-> {e['object']}"})
        elif not e.get("doc"):
            e["state"] = "exception"
            e["reasons"].append("no documentary source - held")
            ctx.emit("TD-A-10", "edge_exception", {"edge": f"{e['subject']} -{e['kind']}-> {e['object']}", "why": "no source"})
        else:
            e["reasons"].append("endpoint(s) not yet registered - candidate")
    return edges


# ── TD-A-17 Graph Assembler ──
def graph_assembler(ctx: RunContext, registry: dict, edges: list[dict]) -> dict:
    """Things + edges -> AI graph. Nodes = registered parties; edges carry state."""
    nodes = [{"id": pfx, "label": p["orgName"], "roles": p.get("roles", []),
              "verified": True} for pfx, p in registry.items()]
    graph = {"nodes": nodes,
             "edges": [{"subject": e["subject"], "object": e["object"], "kind": e["kind"],
                        "state": e["state"], "source": e["source"],
                        "inferred": e.get("inferred", False)} for e in edges]}
    by_state = {}
    for e in edges: by_state[e["state"]] = by_state.get(e["state"], 0) + 1
    ctx.emit("TD-A-17", "graph_assembled", {"nodes": len(nodes), "edges": len(edges), "edge_states": by_state})
    return graph


def run_loop_b(ctx: RunContext, registry: dict, live: bool = False, sam_api_key=None) -> dict:
    if not registry:
        ctx.emit("TD-A-00", "loopB_skip", {"why": "no registered parties to anchor relationships"})
        return {"nodes": [], "edges": []}
    anchor_prefix = next(iter(registry))
    anchor_name = registry[anchor_prefix]["orgName"]
    ctx.emit("TD-A-00", "loopB_start", {"anchor": anchor_name, "prefix": anchor_prefix, "mode": "live" if live else "seed"})

    raw = []
    if live:
        try:
            from td_live_connectors import live_relationship_sources
            raw = live_relationship_sources(anchor_prefix, anchor_name, sam_api_key)
            # Per-connector breakdown so we can see which live sources actually returned.
            by_source = {}
            for e in raw:
                by_source[e.get("source", "?")] = by_source.get(e.get("source", "?"), 0) + 1
            edgar_live = sum(n for s, n in by_source.items() if s.startswith("SEC-EDGAR"))
            ctx.emit("TD-A-06", "live_sources", {"count": len(raw), "by_source": by_source,
                                                 "edgar_live": edgar_live})
            print(f"  [EDGAR] {'LIVE — ' + str(edgar_live) + ' subsidiary edge(s)' if edgar_live else 'no live rows (EDGAR returned nothing this run)'}")
        except Exception as e:
            ctx.emit("TD-A-06", "live_failed", {"error": str(e)})
    if not raw:
        raw = relationship_sources(anchor_prefix, anchor_name)   # offline seed fallback
        ctx.emit("TD-A-06", "seed_fallback", {"count": len(raw)})
        print("  [EDGAR] fell back to offline seed (no live rows from any connector)")

    edges = relationship_discovery(ctx, raw)          # TD-A-15
    edges += edge_inferrer(ctx, edges)                # TD-A-18 (adds inferred)
    edges = verify_edges(ctx, edges, registry)        # TD-A-09 / TD-A-10
    partner_table_builder(ctx, edges, registry)       # TD-A-16
    graph = graph_assembler(ctx, registry, edges)     # TD-A-17
    ctx.emit("TD-A-00", "loopB_end", {"edges": len(edges)})
    return graph


# ══════════════════════════════════════════════════════════════════════════════
# F5 / F6 - DRIVER / BINDING LOOPS
# ══════════════════════════════════════════════════════════════════════════════

# ── TD-A-24 No-Assumption Guard ──
def no_assumption_guard(ctx: RunContext, instrument: dict, registry: dict) -> tuple[bool, str]:
    """Block a bind that would attach to a parent-brand prefix without the
       instrument's own record/GLN. Force an explicit record. Never assume."""
    pfx = instrument.get("owner_prefix")
    if not pfx:
        ctx.emit("TD-A-24", "blocked", {"instrument": instrument["model"], "why": "no owner prefix"})
        return False, "no owner prefix - blocked (never assume parent brand)"
    if pfx not in registry:
        ctx.emit("TD-A-24", "blocked", {"instrument": instrument["model"], "why": f"prefix {pfx} not a registered party"})
        return False, f"prefix {pfx} not registered - blocked"
    return True, "owner prefix is a registered party"


# ── TD-A-19 Driver-Authoring (Encoder) ──
def encoder_agent(ctx: RunContext, instrument: dict) -> dict:
    """Instrument GIAI -> SiLA driver bound to identity (EpcIdentityProvider)."""
    giai = instrument["giai"]
    driver = {
        "driverId": new_id("drv"),
        "feature": "EpcIdentityProvider (SiLA 2)",
        "GetDeviceIdentity": {
            "machine_giai": giai,
            "components": instrument.get("cpis", []),
            "verification": "DEMO-CANDIDATE" if instrument.get("demo") else "VERIFIED",
        },
        "transport": instrument.get("transport", "gRPC over Modbus/4-20mA"),
    }
    ctx.emit("TD-A-19", "driver_authored", {"giai": giai, "components": len(instrument.get("cpis", []))})
    return driver


# ── TD-A-20 Workflow / Protocol Agent ──
def workflow_agent(ctx: RunContext, instrument: dict, driver: dict) -> dict:
    """Driver -> Allotrope-style protocol (ADF) with identity annotation."""
    adf = {
        "@id": instrument["giai"],
        "thingdaddy:instrumentGIAI": instrument["giai"],
        "afo:measurement": {
            "afo:measurementType": instrument.get("measures", "generic-measurement"),
            "thingdaddy:sourcedByCPI": (instrument.get("cpis") or [None])[0],
        },
        "thingdaddy:verification": driver["GetDeviceIdentity"]["verification"],
    }
    ctx.emit("TD-A-20", "workflow_authored", {"giai": instrument["giai"], "type": instrument.get("measures")})
    return adf


# ── TD-A-21 Capability Mapper ──
def capability_mapper(ctx: RunContext, instrument: dict) -> dict:
    carriers = instrument.get("carriers", ["gRPC"])
    profile = {"giai": instrument["giai"], "carriers": carriers,
               "capabilities": instrument.get("capabilities", ["measure", "report"])}
    ctx.emit("TD-A-21", "capability_profiled", {"giai": instrument["giai"], "carriers": carriers})
    return profile


# ── TD-A-22 Binding Agent ──
def binding_agent(ctx: RunContext, instrument: dict, cloud: str) -> dict:
    """Commission -> factory test-bind + GDTI cert + trust mark."""
    gdti = f"urn:epc:id:gdti:{instrument.get('owner_prefix','0DEMO001')}.CERT.{uuid.uuid4().hex[:6]}"
    bind = {"bindId": new_id("bind"), "giai": instrument["giai"], "cloud": cloud,
            "gdti_cert": gdti, "trust_mark": "factory-test-bind OK", "at": now()}
    ctx.emit("TD-A-22", "bound", {"giai": instrument["giai"], "cloud": cloud, "gdti": gdti})
    return bind


# ── TD-A-23 Re-home Agent ──
def rehome_agent(ctx: RunContext, bind: dict, from_op: str, to_op_gln: str) -> dict:
    """Custody change -> bind moved to operator GLN (Caterpillar->Butterfly)."""
    rehomed = {**bind, "rehomedTo": to_op_gln, "from": from_op,
               "originGIAI": bind["giai"], "at": now()}
    ctx.emit("TD-A-23", "rehomed", {"giai": bind["giai"], "to": to_op_gln, "origin_preserved": True})
    return rehomed


def run_driver_binding(ctx: RunContext, registry: dict) -> list[dict]:
    # Demo instrument: an ASML-class scanner owned by a registered party (Samsung fab).
    owner_prefix = next(iter(registry)) if registry else None
    instrument = {
        "model": "ASML NXE:3600D EUV Scanner",
        "giai": "urn:epc:id:giai:0DEMO001.ASML-NXE3600D-00427",
        "owner_prefix": owner_prefix,             # must be a registered party
        "demo": True,
        "measures": "overlay-registration",
        "cpis": ["urn:epc:id:cpi:0DEMO206.STAGE-IFM.001",
                 "urn:epc:id:cpi:0DEMO181.SRC-THERMAL.014"],
        "carriers": ["gRPC", "RAIN-RFID", "2D-DataMatrix"],
        "capabilities": ["measure-overlay", "report", "self-identify"],
    }
    ctx.emit("TD-A-00", "driverloop_start", {"instrument": instrument["model"]})

    ok, why = no_assumption_guard(ctx, instrument, registry)   # TD-A-24
    if not ok:
        ctx.emit("TD-A-00", "driverloop_halt", {"why": why})
        return [{"halted": why}]

    driver  = encoder_agent(ctx, instrument)                    # TD-A-19
    adf     = workflow_agent(ctx, instrument, driver)           # TD-A-20
    profile = capability_mapper(ctx, instrument)                # TD-A-21
    bind    = binding_agent(ctx, instrument, cloud="Azure IoT Hub / Digital Twins")  # TD-A-22
    rehomed = rehome_agent(ctx, bind, from_op="ASML",
                           to_op_gln=f"urn:epc:id:sgln:{owner_prefix}.0.0")           # TD-A-23

    ctx.emit("TD-A-00", "driverloop_end", {"giai": instrument["giai"]})
    return [{"driver": driver, "workflow": adf, "capability": profile,
             "binding": bind, "rehomed": rehomed}]


# ══════════════════════════════════════════════════════════════════════════════
# Driver
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# Export the loop graph in the V4 SemanticGraphModule SEED_ASSOCIATIONS shape,
# so the platform UI renders exactly the edges this loop produced.
# ══════════════════════════════════════════════════════════════════════════════
_REL_TO_TYPE = {
    "parent_of": "PGLN", "award_recipient": "GDTI", "registered_as": "GSRN",
    "related_to": "GLN", "supplies": "GLN",
}

def graph_to_seed_associations(registry: dict, graph: dict) -> list[dict]:
    anchors = []
    for pfx, p in registry.items():
        assoc = []
        for e in graph.get("edges", []):
            if e["subject"].lower() != p["orgName"].lower():
                continue
            rel = e["kind"].upper()
            typ = _REL_TO_TYPE.get(e["kind"], "GLN")
            oid = (f"urn:epc:id:pgln:{e['object_prefix']}.000001"
                   if e.get("object_prefix") else
                   f"td:edge:{re.sub(r'[^a-z0-9]+','-',e['object'].lower())}")
            assoc.append({"rel": rel, "type": typ, "id": oid, "label": e["object"],
                          "state": e["state"], "source": e["source"],
                          "inferred": bool(e.get("inferred"))})
        anchors.append({
            "anchor_type": "PGLN",
            "anchor_id": f"urn:epc:id:pgln:{pfx}.000001",
            "anchor_label": p["orgName"],
            "industry": "Loop-B / Relationship",
            "associations": assoc,
        })
    return anchors


def main(argv):
    edges_only   = "--edges-only" in argv
    drivers_only = "--drivers-only" in argv
    live         = "--live" in argv

    # First run the base fleet (population->verify->register) to get a registry.
    base = orchestrate("Samsung", "GS1 Korea", source_connectors("Samsung"))
    ctx = base

    graph, driver_out = {"nodes": [], "edges": []}, []
    if not drivers_only:
        graph = run_loop_b(ctx, ctx.registry, live=live)
    if not edges_only:
        driver_out = run_driver_binding(ctx, ctx.registry)

    # ── report ──
    print("=" * 72)
    print(f"ThingDaddy Agent Fleet - Loop B + Driver/Binding   [{'LIVE' if live else 'seed'} mode]")
    print("=" * 72)
    print(f"registered parties: {list(ctx.registry.keys())}")
    if not drivers_only:
        es = {}
        for e in graph["edges"]: es[e["state"]] = es.get(e["state"], 0) + 1
        print(f"\nF4 graph: {len(graph['nodes'])} node(s), {len(graph['edges'])} edge(s)  states={es}")
        for e in graph["edges"]:
            tag = "~inferred" if e["inferred"] else e["source"]
            print(f"   [{e['state']:<9}] {e['subject']} -{e['kind']}-> {e['object']}  ({tag})")
    if not edges_only:
        print("\nF5/F6 driver+binding:")
        if driver_out and driver_out[0].get("halted"):
            print("   HALTED:", driver_out[0]["halted"])
        else:
            d = driver_out[0]
            print(f"   driver:   {d['driver']['feature']} for {d['driver']['GetDeviceIdentity']['machine_giai']}")
            print(f"   workflow: ADF {d['workflow']['afo:measurement']['afo:measurementType']}")
            print(f"   binding:  {d['binding']['cloud']}  cert {d['binding']['gdti_cert']}")
            print(f"   re-home:  origin preserved -> {d['rehomed']['rehomedTo']}")

    print(f"\naudit events (this run): {len(ctx.events)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOOPB_LEDGER.write_text(json.dumps({
        "ranAt": now(), "mode": "live" if live else "seed",
        "registry": ctx.registry, "graph": graph,
        "driver_binding": driver_out, "events": ctx.events,
    }, indent=2, default=str))
    print(f"ledger written: {LOOPB_LEDGER}")

    # export the platform-ready SEED_ASSOCIATIONS block
    seed = graph_to_seed_associations(ctx.registry, graph)
    seed_path = OUT_DIR / "loopB_seed_associations.json"
    seed_path.write_text(json.dumps(seed, indent=2, default=str))
    print(f"platform graph export: {seed_path}  ({len(seed)} anchor(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
