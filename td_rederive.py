#!/usr/bin/env python3
"""
td_rederive.py — repeat the experiment.

    python3 td_rederive.py --selftest          positive control ONLY
    python3 td_rederive.py                     replicate staging cuts
    python3 td_rederive.py --json
    python3 td_rederive.py --claims            replicate production CLAIM values
    python3 td_rederive.py --limit 5000

READ ONLY against every database.

──────────────────────────────────────────────────────────────────────────────
THE SCIENTIFIC METHOD, APPLIED TO A NUMBER

  A CLAIM IS A MINIATURE PAPER.

    observation   this company's prefix is 0817089
    method        gcp_cut against the GCP Length Table
    inputs        source DI 00817089020658 · table version 2026-02-17
    result        0817089
    grade         verified

  AND A RESULT THAT CANNOT BE REPRODUCED IS NOT A RESULT.

  On 5 September the register held 081708902 — nine digits on a seven-digit
  hand-read licence, graded `v`, carrying this:

    "cut with gcp_cut from this company's own GUDID DIs, indicator stripped,
     GCP Length Table 2026-02-17 · 192,979 entries. A GUDID filing attests
     the DI and the labeler together under 21 CFR 830"

  A FLAWLESS METHODS SECTION FOR AN EXPERIMENT THAT WAS NEVER RUN. It was
  hardcoded. The sentence fooled a careful reader for a full response,
  because a sentence is all it was.

  This tool repeats the experiment from the recorded inputs and reports one
  of three outcomes. THE THIRD IS THE HONEST ONE AND IT IS USUALLY THE
  ANSWER:

    REPRODUCED    re-running the method on the recorded inputs returns the
                  recorded value
    REFUTED       it returns something else. The claim is wrong, and now
                  demonstrably so.
    CANNOT-REPEAT the inputs were not recorded. THIS IS NOT A PASS. It is a
                  methods section with the method missing, and it is exactly
                  the state that let 081708902 stand.

──────────────────────────────────────────────────────────────────────────────
POSITIVE CONTROL FIRST

  This script implements gcp_cut from the published table format. That
  implementation is itself a hypothesis. It is tested against KNOWN-GOOD
  hand-reads before it is allowed to judge anything, and IT REFUSES TO RUN
  IF THE CONTROL FAILS. A tool that cannot reproduce a value KJ read with
  his own eyes has no standing to call anything refuted.
"""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"; CYA="\033[36m"

PROD = os.environ.get("PROD_DB", "thingdaddy_population")
RUN  = os.environ.get("RUN_DB",  "thingdaddy_run")

TABLE_CANDIDATES = [
    "population/standards/gs1/GCPPrefixFormatList.xml",
    "population/standards/GCPPrefixFormatList.xml",
    "GCPPrefixFormatList.xml",
]

# Hand-reads. Verified by GS1, read by KJ. THE CONTROL — never re-derived,
# never re-litigated, and the thing this implementation must reproduce.
CONTROL = [
    ("00817089020658", "0817089", "Diazyme · hand-read, Verified by GS1"),
]


def psql(db, sql):
    p = subprocess.run(["psql","-qAt","-F","\t","-v","ON_ERROR_STOP=1","-d",db,"-f","-"],
                       input="SET default_transaction_read_only = on;\n"+sql,
                       capture_output=True, text=True, timeout=900)
    if p.returncode:
        e=(p.stderr or "").strip().splitlines()
        return None, (e[-1] if e else "unknown error")
    return [l.split("\t") for l in p.stdout.split("\n") if l], None


# ── the table ────────────────────────────────────────────────────────────────
def load_table(path=None):
    """The GS1 GCP Length Table. Entries map a leading digit string to a length."""
    cands = [path] if path else TABLE_CANDIDATES
    for c in cands:
        if c and os.path.isfile(c):
            entries = {}
            for _, el in ET.iterparse(c, events=("end",)):
                tag = el.tag.split("}")[-1]
                if tag in ("entry", "prefixLength", "gcpLengthEntry"):
                    pfx = el.get("prefix") or el.get("gs1CompanyPrefix")
                    ln  = el.get("gcpLength") or el.get("length")
                    if pfx and ln and str(ln).isdigit():
                        entries[pfx] = int(ln)
                    el.clear()
            if entries:
                return entries, c, None
            return None, c, "the file parsed but yielded no entries — the element or attribute names differ from what this parser expects. READ THE FILE; DO NOT GUESS."
    return None, None, ("GCPPrefixFormatList.xml not found. Looked in: " + " · ".join(TABLE_CANDIDATES))


def normalise(di):
    """A GTIN-14 is a GTIN-13 with an indicator on the front. A UPC-12 is a
       GTIN-13 with a leading zero. The table is keyed on the 13-digit form."""
    d = "".join(ch for ch in str(di or "") if ch.isdigit())
    if len(d) == 14: return d[1:], "GTIN-14, indicator stripped"
    if len(d) == 13: return d, "GTIN-13 / EAN-13, as found"
    if len(d) == 12: return "0" + d, "UPC-12, leading zero prepended"
    return None, f"length {len(d)} — NOT A GTIN SHAPE. There is no company prefix to cut."


def gcp_cut(di, table):
    """Longest matching table entry wins. Returns (prefix, length, matched_entry, why)."""
    norm, how = normalise(di)
    if norm is None:
        return None, None, None, how
    best = None
    for n in range(len(norm), 0, -1):
        k = norm[:n]
        if k in table:
            best = k; break
    if best is None:
        return None, None, None, "no table entry matches these leading digits"
    ln = table[best]
    if ln <= 0 or ln > len(norm):
        return None, None, best, f"table says length {ln}, which is not cuttable from {len(norm)} digits"
    return norm[:ln], ln, best, how


def selftest(table):
    print(f"\n{BOLD}POSITIVE CONTROL{RESET}  {DIM}hand-reads this implementation must reproduce{RESET}")
    ok = True
    for di, expect, note in CONTROL:
        got, ln, entry, why = gcp_cut(di, table)
        good = (got == expect)
        ok = ok and good
        col = GRN if good else RED
        print(f"  {col}{'REPRODUCED' if good else 'FAILED':>11}{RESET}  {di} → {got or '—'}"
              f"   {DIM}expected {expect} · table entry {entry or '—'} · length {ln or '—'}{RESET}")
        print(f"               {DIM}{note} · {why}{RESET}")
    return ok


# ── the experiment ───────────────────────────────────────────────────────────
def replicate(rows, table, label):
    out = {"reproduced": [], "refuted": [], "cannot_repeat": []}
    for r in rows:
        rec = dict(zip(label, r))
        di = rec.get("source_di")
        claimed = rec.get("prefix")
        if not di or not di.strip():
            rec["outcome"] = "cannot-repeat"
            rec["why"] = "no source DI recorded. The methods section is incomplete."
            out["cannot_repeat"].append(rec); continue
        got, ln, entry, why = gcp_cut(di, table)
        rec["rederived"] = got; rec["table_entry"] = entry; rec["gcp_length"] = ln
        rec["normalisation"] = why
        if got is None:
            rec["outcome"] = "cannot-repeat"; rec["why"] = why
            out["cannot_repeat"].append(rec)
        elif got == claimed:
            rec["outcome"] = "reproduced"; out["reproduced"].append(rec)
        else:
            rec["outcome"] = "refuted"
            rec["why"] = (f"the recorded value is {claimed}; repeating the method on the "
                          f"recorded DI returns {got}")
            out["refuted"].append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table"); ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--selftest", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--claims", action="store_true",
                    help="replicate production CLAIM values instead of staging cuts")
    ap.add_argument("--samples", type=int, default=8)
    a = ap.parse_args()

    table, path, err = load_table(a.table)
    if err:
        msg = {"record":"thingdaddy.rederive.v1","error":err}
        print(json.dumps(msg,indent=2) if a.json else f"\n  {RED}REFUSED{RESET}  {err}\n")
        sys.exit(2)

    if not a.json:
        print(f"\n{BOLD}td_rederive{RESET}   repeat the experiment   {DIM}READ ONLY{RESET}")
        print(f"{DIM}  a result that cannot be reproduced is not a result.{RESET}")
        print(f"\n  table: {path}   {DIM}{len(table):,} entries{RESET}")

    ok = selftest(table) if not a.json else all(
        gcp_cut(di, table)[0] == exp for di, exp, _ in CONTROL)
    if not ok:
        m = ("THE POSITIVE CONTROL FAILED. This implementation cannot reproduce a value read "
             "by hand against Verified by GS1, so it has NO STANDING to call anything refuted. "
             "Read the table format and re-cut the parser. Nothing was judged.")
        print(json.dumps({"record":"thingdaddy.rederive.v1","error":m},indent=2) if a.json
              else f"\n  {RED}REFUSED{RESET}  {m}\n")
        sys.exit(2)
    if a.selftest:
        print(f"\n  {GRN}control holds.{RESET} The implementation may now judge.\n"); sys.exit(0)

    if a.claims:
        label = ["party_id","prefix","claim_id","nm","grade","source_di"]
        sql = ("SELECT p.id::text, c.identifier, c.id::text, c.nm, coalesce(c.grade,'—'), "
               "coalesce((SELECT cp.source_di FROM company_prefix cp "
               "          WHERE cp.prefix = c.identifier LIMIT 1),'') "
               "FROM content_claim c JOIN party p ON p.id=c.party_id "
               "WHERE c.identifier ~ '^[0-9]{4,12}$' "
               f"ORDER BY c.id LIMIT {a.limit};")
        rows, e = psql(PROD, sql.replace("company_prefix", "company_prefix"))
        if e:
            # company_prefix lives in staging, not production — say so plainly.
            rows, e2 = psql(PROD, "SELECT p.id::text, c.identifier, c.id::text, c.nm, "
                            f"coalesce(c.grade,'—'), '' FROM content_claim c JOIN party p "
                            f"ON p.id=c.party_id WHERE c.identifier ~ '^[0-9]{{4,12}}$' "
                            f"ORDER BY c.id LIMIT {a.limit};")
            if e2:
                print(f"\n  {RED}REFUSED{RESET}  {e2}\n"); sys.exit(2)
        src = "production content_claim (prefix-shaped identifiers)"
    else:
        label = ["party_id","prefix","root_method","register","source_di"]
        rows, e = psql(RUN, "SELECT party_id::text, prefix, coalesce(root_method,'—'), "
                       f"coalesce(register,'—'), coalesce(source_di,'') FROM company_prefix "
                       f"WHERE prefix IS NOT NULL ORDER BY id LIMIT {a.limit};")
        if e:
            print(f"\n  {RED}REFUSED{RESET}  {e}\n"); sys.exit(2)
        src = "staging company_prefix"

    res = replicate(rows, table, label)
    n = len(rows)
    rec = {
      "record": "thingdaddy.rederive.v1",
      "shaped_for": "a consumer that has never seen the terminal",
      "read_only": True,
      "source": src, "table": path, "table_entries": len(table),
      "examined": n,
      "summary": {
        "reproduced": len(res["reproduced"]),
        "refuted": len(res["refuted"]),
        "cannot_repeat": len(res["cannot_repeat"]),
      },
      "outcome_policy":
        "CANNOT-REPEAT IS NOT A PASS. It is a methods section with the method missing, and it "
        "is exactly the state that let a hardcoded nine-digit value stand under a flawless "
        "gcp_cut provenance sentence.",
      "control": [{"di":d,"expected":e,"note":nt} for d,e,nt in CONTROL],
      "refuted": res["refuted"][:200],
      "cannot_repeat_examples": res["cannot_repeat"][:a.samples],
      "scope":
        "This repeats gcp_cut ONLY. It does not test whether the DI itself is genuine, whether "
        "the issuing agency was GS1, or whether the table version used originally is the one "
        "loaded here. Those are named gaps, not silent ones.",
    }

    if a.json:
        print(json.dumps(rec, indent=2)); sys.exit(1 if res["refuted"] else 0)

    print(f"\n{BOLD}EXPERIMENT{RESET}  {DIM}{src} · {n:,} row(s){RESET}")
    print(f"  {GRN}{len(res['reproduced']):>7,} reproduced{RESET}   "
          f"{DIM}re-running the method on the recorded inputs returns the recorded value{RESET}")
    print(f"  {RED}{len(res['refuted']):>7,} refuted{RESET}      "
          f"{DIM}it returns something else{RESET}")
    print(f"  {YEL}{len(res['cannot_repeat']):>7,} cannot repeat{RESET}"
          f"{DIM}  the inputs were not recorded{RESET}")

    if res["refuted"]:
        print(f"\n{BOLD}{RED}REFUTED{RESET}")
        for r in res["refuted"][:a.samples]:
            print(f"  {r.get('prefix')} ← recorded    {r.get('rederived')} ← re-derived")
            print(f"    {DIM}DI {r.get('source_di')} · table entry {r.get('table_entry')} · "
                  f"length {r.get('gcp_length')} · {r.get('normalisation')}{RESET}")
            print(f"    {DIM}party {r.get('party_id')} · {r.get('root_method') or r.get('nm')}{RESET}")

    if res["cannot_repeat"]:
        print(f"\n{BOLD}{YEL}CANNOT REPEAT{RESET}  {DIM}— and this is not a pass{RESET}")
        seen = set()
        for r in res["cannot_repeat"][:a.samples]:
            k = r.get("why")
            if k in seen: continue
            seen.add(k)
            print(f"  {r.get('prefix')}  {DIM}{k}{RESET}")
        print(f"\n  {CYA}{rec['outcome_policy']}{RESET}")

    print(f"\n{DIM}  SCOPE: {rec['scope']}{RESET}\n")
    sys.exit(1 if res["refuted"] else 0)


if __name__ == "__main__":
    main()
