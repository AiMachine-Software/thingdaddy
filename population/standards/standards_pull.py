#!/usr/bin/env python3
"""
standards_pull.py — pull the real public P2 (SiLA) + P3/P5 (Allotrope AFO) vocabularies and
normalize them into the configurator's palette + rule vocabulary for the P5 graph.

No membership required. Runs where there's network (the Mac).
  * SiLA 2 standard Features — the 22 Part-C standard features are embedded here (public,
    authoritative, NOT fabricated) as the declarative driver vocabulary (P2).
  * AFO classes via the OLS4 REST API — the protocol ontology (equipment/process/material/
    result/property), P3 -> P5.

Outputs (in --outdir):
  sila_features.csv       feature,description,pillar
  configurator_rules.csv  from_type,edge_type,to_type,pillar   (what may LEGALLY connect)
  afo_classes.csv         iri,label,domain,obo_id              (the AFO palette)

These are VOCABULARY / PALETTE (candidate rules), NOT registry identities. They define what the
configurator lets you drag together — protocol-legal only. Nothing minted.

Usage:
  python3 standards_pull.py --outdir .
  python3 standards_pull.py --afo-max 6000 --outdir .
  python3 standards_pull.py --no-afo --outdir .     # SiLA + rules only, no network
"""
from __future__ import annotations
import argparse, csv, json, os, sys, time
from collections import Counter
import urllib.request, urllib.error

UA = "ThingDaddy-StandardsPull/0.1 (public standards vocabulary; contact ops@thingdaddy.io)"
OLS4 = "https://www.ebi.ac.uk/ols4/api/ontologies/afo/terms"

# --- SiLA 2 standard features (Part C, public — authoritative, not fabricated) -----------
SILA_FEATURES = [
    ("SiLAService", "entry point to a SiLA Server; feature discovery"),
    ("AuthenticationService", "confirm client identity, issue access tokens"),
    ("AuthorizationService", "control access via client metadata for tokens"),
    ("AuthorizationProviderService", "validate access tokens (external user mgmt)"),
    ("AuthorizationConfigurationService", "designate which authorization provider to use"),
    ("ParameterConstraintsProvider", "disclose parameter limits by state"),
    ("LockController", "exclusive server access via lock id + timeout"),
    ("SimulationController", "simulation mode for testing"),
    ("ObservableCommandController", "pause / resume / stop observable commands"),
    ("InternationalizationService", "internationalization support"),
    ("AuditTrailService", "audit trail of actions"),
    ("ParameterDefaultsProvider", "default parameter values"),
    ("ServerDetailProvider", "server detail metadata"),
    ("InitializationController", "initialize the server / instrument"),
    ("DurationProvider", "expected command durations"),
    ("ServerMonitoringService", "monitoring / alarm / logging"),
    ("ErrorRecoveryService", "recover from errors"),
    ("TimeSyncProvider", "time normal / time sync"),
    ("KeepAliveService", "heart beat / keep alive"),
    ("DiscoveryService", "discovery / server registry"),
    ("BrokerService", "broker / late binding"),
    ("LicenseService", "license management"),
]

# --- configurator rule vocabulary: what may LEGALLY connect (protocol-legal) ------------
RULES = [
    ("instrument(GTIN)", "has_driver", "SiLA Feature", "P2"),
    ("instrument(GTIN)", "runs", "AFO process/method", "P3"),
    ("AFO process", "has_equipment", "AFO equipment", "P3"),
    ("AFO process", "has_input", "AFO material", "P3"),
    ("AFO process", "has_output", "AFO result", "P5"),
    ("instrument(GTIN)", "uses", "AFO material (reagent/consumable)", "P5"),
    ("SiLA Feature", "exposes", "SiLA Command", "P2"),
    ("SiLA Feature", "exposes", "SiLA Property", "P2"),
    ("document(GDTI)", "describes", "instrument(GTIN)", "P1"),
]

def domain_of(iri):
    u = (iri or "").lower()
    if "/equipment" in u or "afe_" in u: return "equipment"
    if "/process" in u or "afp_" in u: return "process"
    if "/material" in u or "afm_" in u: return "material"
    if "/result" in u or "afr_" in u: return "result"
    if "/property" in u or "afq_" in u or "afx_" in u: return "property"
    return "other"

def http_json(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def extract_terms(d):
    """Tolerant: OLS4 shapes vary. Return list-or-None; None means 'shape not recognized'."""
    if not isinstance(d, dict): return None
    if "_embedded" in d and isinstance(d["_embedded"], dict) and "terms" in d["_embedded"]:
        return d["_embedded"]["terms"]
    for k in ("elements", "terms", "results"):
        if isinstance(d.get(k), list): return d[k]
    return None

def term_row(t):
    iri = t.get("iri") or t.get("@id") or t.get("uri") or ""
    lab = t.get("label")
    if not lab and isinstance(t.get("labels"), list) and t["labels"]:
        lab = t["labels"][0]
    obo = t.get("obo_id") or t.get("short_form") or t.get("curie") or ""
    return (iri, lab or "", domain_of(iri), obo)

def pull_afo(afo_max, sleep):
    rows, page, size = [], 0, 200
    while len(rows) < afo_max:
        url = f"{OLS4}?size={size}&page={page}"
        try:
            d = http_json(url)
        except Exception as e:
            print(f"  [afo] page {page} failed: {e}", file=sys.stderr); break
        terms = extract_terms(d)
        if terms is None:
            keys = list(d.keys()) if isinstance(d, dict) else type(d).__name__
            print(f"  [afo] unrecognized JSON shape at page {page}; top-level keys: {keys}", file=sys.stderr)
            print("        (paste this — the OLS4 endpoint/shape may differ and I'll adjust.)", file=sys.stderr)
            break
        if not terms: break
        rows.extend(term_row(t) for t in terms)
        tp = d.get("page", {}).get("totalPages") if isinstance(d.get("page"), dict) else None
        page += 1
        if tp is not None and page >= tp: break
        time.sleep(sleep)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--afo-max", type=int, default=6000)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-afo", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    with open(os.path.join(a.outdir, "sila_features.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["feature", "description", "pillar"])
        for name, desc in SILA_FEATURES: w.writerow([name, desc, "P2"])
    with open(os.path.join(a.outdir, "configurator_rules.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["from_type", "edge_type", "to_type", "pillar"])
        for r in RULES: w.writerow(list(r))
    print(f">> SiLA features : {len(SILA_FEATURES)} (P2 driver vocabulary)  -> sila_features.csv")
    print(f">> configurator rules : {len(RULES)} legal-connection rules  -> configurator_rules.csv")

    if not a.no_afo:
        afo = pull_afo(a.afo_max, a.sleep)
        with open(os.path.join(a.outdir, "afo_classes.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["iri", "label", "domain", "obo_id"])
            for row in afo: w.writerow(list(row))
        dc = Counter(r[2] for r in afo)
        print(f">> AFO classes   : {len(afo)}  -> afo_classes.csv")
        if afo:
            print("   by domain: " + ", ".join(f"{k}={v}" for k, v in dc.most_common()))
        else:
            print("   (0 pulled — see the [afo] message above; likely the OLS4 endpoint/shape. Paste it and I'll fix.)")
    print(">> done. Vocabulary/palette only (candidate rules) — defines what the configurator may legally connect. Nothing minted.")

if __name__ == "__main__":
    main()
