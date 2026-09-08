#!/usr/bin/env python3
"""
loop_a/run.py — Civilization Profile Loop.

Matches a GS1 prefix to each member, unifies one legal entity across many GS1 MOs
into one profile, and flags companies that need a prefix (routed to their MO).
Stages: ingest-gleif -> derive+match -> unify -> flag-needs-prefix -> export.
"""
import argparse, os, sys, json, hashlib

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.harness import Store, append_csv, CapReached
from common.resolve import normalize, block_key, score, UnionFind
from common.verify import verify_prefix, verify_match
from common.mo_resolver import mo_for_prefix, mo_for_country
from common.logging_setup import setup as log_setup
from loop_a.connectors.gleif import GleifConnector
from loop_a.connectors.openfda_gudid import GudidConnector
from loop_a.connectors.verified_by_gs1 import VerifiedByGS1Connector

DEFAULT_CFG = {
    "offline": True, "gcp_default_length": 7,
    "caps": {"gleif": 5_000_000, "gudid": 2_000_000, "verified_by_gs1": 2_000_000},
    "match": {"strong": 0.90, "probable": 0.75},
    "gleif": {"lei2_url": "", "rr_url": ""}, "gudid": {"udi_url": ""}, "net": {},
}

def load_cfg(path):
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    if path and os.path.exists(path):
        try:
            import yaml
            with open(path) as f:
                loaded = yaml.safe_load(f) or {}
            _deep_update(cfg, loaded)
        except Exception:
            pass
    return cfg

def _deep_update(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _deep_update(a[k], v)
        else:
            a[k] = v
    return a

def pid(lei):
    return "LEI:" + lei

def ingest_gleif(store, cfg):
    g = GleifConnector(store, cfg); n = 0
    try:
        for lei, name, country in g.iter_parties():
            store.put_party(pid(lei), name, normalize(name), country, lei, "verified", "gleif")
            store.put_node(pid(lei), name, "company", country, "verified", "gleif")
            n += 1
        for child, parent, rel in g.iter_ownership():
            store.put_ownership(child, parent, rel, "gleif")
    except CapReached as e:
        print(f"[cap] {e}")
    return n

def derive_and_match(store, cfg):
    gud = GudidConnector(store, cfg); vbg = VerifiedByGS1Connector(store, cfg)
    strong = cfg["match"]["strong"]; probable = cfg["match"]["probable"]
    blocks = {}
    for r in store.q("SELECT party_id,name,norm_name,country,lei FROM party"):
        blocks.setdefault(block_key(r["norm_name"], r["country"]), []).append(r)
    matched = 0; labelers = set()
    try:
        for cand in gud.iter_candidates():
            labelers.add(normalize(cand["labeler"]))
            bk = block_key(normalize(cand["labeler"]), cand["country"])
            best = None; best_s = 0.0
            pool = blocks.get(bk) or [r for rs in blocks.values() for r in rs]
            for r in pool:
                s = score(cand["labeler"], cand["country"], r["name"], r["country"])
                if s > best_s:
                    best, best_s = r, s
            if not best:
                continue
            confirm = vbg.confirm(cand["candidate_prefix"]) if cand["candidate_prefix"] else None
            tier, mstatus = verify_match(best_s, bool(confirm), strong, probable)
            if mstatus == "exception" or not cand["candidate_prefix"]:
                continue
            pstatus, length, pcite = verify_prefix("gudid", confirm)
            mo, mtype = mo_for_prefix(cand["candidate_prefix"])
            if mtype != "MO":
                continue
            gp = (cand["gtin13"] or cand["candidate_prefix"])[:3]
            store.put_prefix(cand["candidate_prefix"], best["party_id"], gp, mo, length,
                             pstatus, "gudid", pcite)
            store.put_match(best["lei"], cand["candidate_prefix"], best_s, tier, mstatus, pcite)
            matched += 1
    except CapReached as e:
        print(f"[cap] {e}")
    store.stage("_meta", "gudid_labelers", sorted(labelers))
    return matched

def unify(store, cfg):
    uf = UnionFind()
    for r in store.q("SELECT lei FROM party"):
        uf.add(pid(r["lei"]))
    for r in store.q("SELECT prefix,party_id FROM prefix"):
        uf.union(r["party_id"], "PFX:" + r["prefix"])
    for r in store.q("SELECT child_lei,parent_lei FROM ownership"):
        uf.union(pid(r["child_lei"]), pid(r["parent_lei"]))
    clusters = uf.clusters()
    for root, members in clusters.items():
        cid = "CIV-" + hashlib.sha1(root.encode()).hexdigest()[:10]
        for m in members:
            store.set_cluster(m, cid)
    return len(clusters)

def flag_needs_prefix(store, cfg):
    row = store.q("SELECT payload FROM staging WHERE source='_meta' AND natural_key='gudid_labelers'")
    labelers = set(json.loads(row[0]["payload"])) if row else set()
    prefixed = {r["party_id"] for r in store.q("SELECT DISTINCT party_id FROM prefix")}
    flagged = 0
    for r in store.q("SELECT party_id,name,norm_name,country,lei FROM party"):
        if r["party_id"] in prefixed:
            continue
        signal = None
        if r["norm_name"] in labelers:
            signal = "gudid_labeler"
        else:
            fam = store.q("SELECT cluster_id FROM cluster WHERE member_key=?", (r["party_id"],))
            if fam:
                sibs = store.q("SELECT member_key FROM cluster WHERE cluster_id=?", (fam[0]["cluster_id"],))
                if any(m["member_key"].startswith("PFX:") for m in sibs):
                    signal = "in_prefixed_family"
        if signal:
            store.put_needs_prefix(r["party_id"], r["name"], r["country"], signal,
                                   mo_for_country(r["country"]), "exception")
            flagged += 1
    return flagged

def export(store, cfg, outdir="out"):
    os.makedirs(outdir, exist_ok=True)
    cl = {}
    for r in store.q("SELECT member_key,cluster_id FROM cluster"):
        cl.setdefault(r["cluster_id"], []).append(r["member_key"])
    parties = {r["party_id"]: r for r in store.q("SELECT party_id,name,country,lei,role FROM party")}
    pref = {}
    for r in store.q("SELECT prefix,party_id,mo,status FROM prefix"):
        pref.setdefault(r["party_id"], []).append(r)
    children = {r["parent_lei"] for r in store.q("SELECT parent_lei FROM ownership")}
    childset = {r["child_lei"] for r in store.q("SELECT child_lei FROM ownership")}
    prof_rows, link_rows = [], []
    for cid, members in cl.items():
        leis = [m[4:] for m in members if m.startswith("LEI:")]
        plist = [m[4:] for m in members if m.startswith("PFX:")]
        mp = [parties[pid(l)] for l in leis if pid(l) in parties]
        if not mp:
            continue
        apex = next((p for p in mp if p["lei"] in children and p["lei"] not in childset), mp[0])
        mos, statuses, detail = set(), set(), []
        for l in leis:
            for pr in pref.get(pid(l), []):
                mos.add(pr["mo"]); statuses.add(pr["status"])
                detail.append(f"{pr['prefix']}({pr['mo']}|{pr['status']})")
        fill = "verified" if "verified" in statuses else ("candidate" if "candidate" in statuses else "exception")
        prof_rows.append([cid, apex["name"], apex["country"], len(leis), ";".join(sorted(mos)) or "-",
                          len(mos), ";".join(sorted(set(plist))) or "-", ";".join(detail) or "-",
                          apex["role"], fill])
        if len(mos) > 1:
            link_rows.append([cid, apex["name"], len(mos), ";".join(sorted(mos)), ";".join(sorted(set(plist)))])
    needs = [[r["party_id"], r["name"], r["country"], r["signal"], r["routed_mo"], r["status"]]
             for r in store.q("SELECT party_id,name,country,signal,routed_mo,status FROM needs_prefix")]
    append_csv(os.path.join(outdir, "civilization_profiles.csv"),
               ["cluster_id","apex_name","country","lei_count","member_orgs","mo_count",
                "prefixes","prefix_detail","role","fill_state"], prof_rows)
    append_csv(os.path.join(outdir, "cross_mo_links.csv"),
               ["cluster_id","apex_name","mo_count","member_orgs","prefixes"], link_rows)
    append_csv(os.path.join(outdir, "needs_prefix_queue.csv"),
               ["party_id","name","country","signal","routed_mo","status"], needs)
    return len(prof_rows), len(link_rows), len(needs)

def run_all(store, cfg, outdir="out"):
    print("[A 1/5] ingest-gleif      ->", ingest_gleif(store, cfg), "parties")
    print("[A 2/5] derive+match      ->", derive_and_match(store, cfg), "prefix matches")
    print("[A 3/5] unify (cross-MO)  ->", unify(store, cfg), "profiles")
    print("[A 4/5] flag-needs-prefix ->", flag_needs_prefix(store, cfg), "flagged")
    p, l, n = export(store, cfg, outdir)
    print(f"[A 5/5] export            -> {p} profiles, {l} cross-MO links, {n} needs-prefix")
    return {"profiles": p, "cross_mo": l, "needs_prefix": n}

def main():
    ap = argparse.ArgumentParser(description="ThingDaddy Loop A — civilization profiles")
    ap.add_argument("mode", choices=["run-all","ingest-gleif","derive-match","unify",
                                     "flag-needs-prefix","export"])
    ap.add_argument("--db", default="civilization.db")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    log_setup(name="loop_a")
    cfg = load_cfg(a.config)
    store = Store(a.db)
    if a.mode == "run-all": run_all(store, cfg, a.out)
    elif a.mode == "ingest-gleif": print("parties:", ingest_gleif(store, cfg))
    elif a.mode == "derive-match": print("matches:", derive_and_match(store, cfg))
    elif a.mode == "unify": print("profiles:", unify(store, cfg))
    elif a.mode == "flag-needs-prefix": print("flagged:", flag_needs_prefix(store, cfg))
    elif a.mode == "export": print("export:", export(store, cfg, a.out))
    store.close()

if __name__ == "__main__":
    main()
