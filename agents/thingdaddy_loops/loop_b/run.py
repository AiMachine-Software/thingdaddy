#!/usr/bin/env python3
"""
loop_b/run.py — Relationship-Edge Loop.

Turns the profile registry from Loop A into the connected physical graph by adding
edges from public-disclosure sources, each attached to a unified civilization profile:
  subsidiary_of   (SEC EDGAR Exhibit 21)
  contracts_with  (USASpending awards: recipient -> awarding agency)
  supplier_of     (USASpending subawards: subawardee -> prime)
  parent_of       (SAM.gov entity + immediate parent)

Endpoints resolve to Loop A profiles; unresolved company endpoints become provisional
nodes. The deterministic verify_edge gate stamps verified | candidate. Append-only.
"""
import argparse, os, sys, json, hashlib, datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.harness import Store, append_csv, CapReached
from common.resolve import normalize
from common.verify import verify_edge
from common.logging_setup import setup as log_setup
from loop_a.run import load_cfg
from loop_b.connectors.sec_edgar import SecEdgarConnector
from loop_b.connectors.usaspending import UsaSpendingConnector
from loop_b.connectors.sam_gov import SamGovConnector

TODAY = datetime.date.today().isoformat()

def resolve_company(store, name, country):
    """(node_key, status). Resolved -> profile node; else provisional node created."""
    key, status = store.resolve_party(name, country, threshold=0.90)
    if status == "resolved":
        return key, "resolved"
    prov = "PROV:" + hashlib.sha1(f"{normalize(name)}|{(country or '').upper()}".encode()).hexdigest()[:10]
    store.put_node(prov, name, "company_provisional", country, "candidate", "loop_b")
    return prov, "provisional"

def resolve_agency(store, name):
    key = "AGY:" + normalize(name)
    store.put_node(key, name, "agency", "US", "resolved", "usaspending")
    return key, "resolved"

def _edge(store, src_key, src_status, dst_key, dst_status, etype, source, citation):
    status = verify_edge(src_status, dst_status, source_authoritative=True)
    store.put_edge(src_key, dst_key, etype, source, status, citation, TODAY)
    return status

def edges_edgar(store, cfg):
    con = SecEdgarConnector(store, cfg)
    seeds = (cfg.get("loop_b", {}).get("edgar_seeds")) or _default_seeds(store)
    n = 0
    try:
        for e in con.iter_subsidiary_edges(seeds):
            sub_k, sub_s = resolve_company(store, e["sub"], e["sub_country"])
            par_k, par_s = resolve_company(store, e["parent"], e["parent_country"])
            _edge(store, sub_k, sub_s, par_k, par_s, "subsidiary_of", "sec_edgar", e["citation"])
            n += 1
    except CapReached as ex:
        print(f"[cap] {ex}")
    return n

def edges_usaspending(store, cfg):
    con = UsaSpendingConnector(store, cfg); n = 0
    try:
        for e in con.iter_award_edges():
            src_k, src_s = resolve_company(store, e["src"], e["src_country"])
            if e["dst_type"] == "agency":
                dst_k, dst_s = resolve_agency(store, e["dst"])
            else:
                dst_k, dst_s = resolve_company(store, e["dst"], "US")
            _edge(store, src_k, src_s, dst_k, dst_s, e["kind"], "usaspending", e["citation"])
            n += 1
    except CapReached as ex:
        print(f"[cap] {ex}")
    return n

def edges_sam(store, cfg):
    con = SamGovConnector(store, cfg); n = 0
    try:
        for e in con.iter_parent_edges():
            ent_k, ent_s = resolve_company(store, e["entity"], e["entity_country"])
            par_k, par_s = resolve_company(store, e["parent"], e["parent_country"])
            _edge(store, par_k, par_s, ent_k, ent_s, "parent_of", "sam_gov", e["citation"])
            n += 1
    except CapReached as ex:
        print(f"[cap] {ex}")
    return n

def _default_seeds(store):
    # seed EDGAR with apex names already in the profile registry
    return [r["name"] for r in store.q(
        "SELECT DISTINCT name FROM party WHERE country='US'")][:500]

def export_graph(store, cfg, outdir="out"):
    os.makedirs(outdir, exist_ok=True)
    # nodes: company profiles (from party+cluster) + provisional/agency (node table)
    node_rows = {}
    for r in store.q("SELECT party_id,name,country FROM party"):
        key = store.cluster_of(r["party_id"]) or r["party_id"]
        node_rows[key] = [key, r["name"], "company", r["country"], "verified"]
    for r in store.q("SELECT node_key,label,node_type,country,status FROM node"):
        node_rows.setdefault(r["node_key"],
                             [r["node_key"], r["label"], r["node_type"], r["country"], r["status"]])
    edge_rows = [[r["src_key"], r["dst_key"], r["edge_type"], r["source"], r["status"],
                 r["citation"], r["observed"]]
                for r in store.q("SELECT * FROM edge")]
    append_csv(os.path.join(outdir, "graph_nodes.csv"),
               ["node_key","label","node_type","country","status"], list(node_rows.values()))
    append_csv(os.path.join(outdir, "graph_edges.csv"),
               ["src_key","dst_key","edge_type","source","status","citation","observed"], edge_rows)
    with open(os.path.join(outdir, "graph.json"), "w") as f:
        json.dump({"nodes": [dict(zip(["key","label","type","country","status"], v))
                             for v in node_rows.values()],
                   "edges": [dict(zip(["src","dst","type","source","status","citation","observed"], e))
                             for e in edge_rows]}, f, indent=2)
    return len(node_rows), len(edge_rows)

def run_all(store, cfg, outdir="out"):
    print("[B 1/4] edges-edgar       ->", edges_edgar(store, cfg), "subsidiary_of edges")
    print("[B 2/4] edges-usaspending ->", edges_usaspending(store, cfg), "award edges")
    print("[B 3/4] edges-sam         ->", edges_sam(store, cfg), "parent_of edges")
    nodes, edges = export_graph(store, cfg, outdir)
    print(f"[B 4/4] export-graph      -> {nodes} nodes, {edges} edges")
    return {"nodes": nodes, "edges": edges}

def main():
    ap = argparse.ArgumentParser(description="ThingDaddy Loop B — relationship edges")
    ap.add_argument("mode", choices=["run-all","edges-edgar","edges-usaspending",
                                     "edges-sam","export-graph"])
    ap.add_argument("--db", default="civilization.db")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    log_setup(name="loop_b")
    cfg = load_cfg(a.config)
    store = Store(a.db)
    if a.mode == "run-all": run_all(store, cfg, a.out)
    elif a.mode == "edges-edgar": print("edges:", edges_edgar(store, cfg))
    elif a.mode == "edges-usaspending": print("edges:", edges_usaspending(store, cfg))
    elif a.mode == "edges-sam": print("edges:", edges_sam(store, cfg))
    elif a.mode == "export-graph": print("graph:", export_graph(store, cfg, a.out))
    store.close()

if __name__ == "__main__":
    main()
