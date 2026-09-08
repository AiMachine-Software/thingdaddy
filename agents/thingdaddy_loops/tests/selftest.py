#!/usr/bin/env python3
"""Combined offline self-test for both loops (no network, no keys)."""
import os, sys, tempfile, shutil
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from common.harness import Store
from loop_a.run import load_cfg, run_all as run_a, pid
from loop_b.run import run_all as run_b, edges_edgar

def main():
    tmp = tempfile.mkdtemp(prefix="tdloops_")
    db = os.path.join(tmp, "civ.db"); out = os.path.join(tmp, "out")
    cfg = load_cfg(None); cfg["offline"] = True
    store = Store(db)
    print("== Loop A ==");  run_a(store, cfg, out)
    print("== Loop B =="); run_b(store, cfg, out)

    fails = []
    def chk(c, m):
        print(("  ok  " if c else "  FAIL") + " | " + m)
        if not c: fails.append(m)

    hw_us = store.cluster_of(pid("5493HONEYWELLUS00001"))
    edges = list(store.q("SELECT src_key,dst_key,edge_type,source,status FROM edge"))

    def has(etype, status=None, dst=None, src_prefix=None):
        for e in edges:
            if e["edge_type"] != etype: continue
            if status and e["status"] != status: continue
            if dst and e["dst_key"] != dst: continue
            if src_prefix and not e["src_key"].startswith(src_prefix): continue
            return e
        return None

    chk(has("subsidiary_of", "verified", dst=hw_us) is not None,
        "EDGAR: verified subsidiary_of edge -> Honeywell US profile (Honeywell UK)")
    chk(has("subsidiary_of", "candidate", src_prefix="PROV:") is not None,
        "EDGAR: candidate subsidiary_of edge for provisional France subsidiary")
    chk(has("supplier_of", "verified", dst=hw_us) is not None,
        "USASpending: verified supplier_of edge PrazisionMed -> Honeywell (needs-prefix co. now in graph)")
    ag = has("contracts_with", "verified")
    chk(ag is not None and ag["dst_key"].startswith("AGY:"),
        "USASpending: verified contracts_with edge Honeywell -> agency node")
    chk(has("parent_of", "candidate", src=None) is not None if False else has("parent_of", "candidate") is not None,
        "SAM.gov: candidate parent_of edge (provisional entity)")

    before = len(edges)
    edges_edgar(store, cfg)  # re-run one edge stage
    after = len(list(store.q("SELECT 1 FROM edge")))
    chk(after == before, f"idempotent: re-running EDGAR adds 0 edges ({before} -> {after})")

    nodes = list(store.q("SELECT node_type,count(*) c FROM node GROUP BY node_type"))
    types = {r["node_type"]: r["c"] for r in nodes}
    chk("agency" in types and "company_provisional" in types,
        f"graph nodes include agency + provisional ({types})")

    print("\nGraph edges:")
    for e in store.q("SELECT src_key,edge_type,dst_key,source,status FROM edge ORDER BY edge_type"):
        print(f"  {e['status']:9} {e['edge_type']:14} {e['src_key'][:22]:22} -> {e['dst_key'][:22]:22} ({e['source']})")

    store.close(); shutil.rmtree(tmp)
    print("\nSELFTEST:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 0 if not fails else 1

if __name__ == "__main__":
    sys.exit(main())
