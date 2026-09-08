#!/usr/bin/env python3
"""
td_authority.py — the authority read register.

    python3 td_authority.py                  check production against it
    python3 td_authority.py --worklist       what still needs reading
    python3 td_authority.py --json
    python3 td_authority.py --init           write the register file if absent

READ ONLY against every database.

──────────────────────────────────────────────────────────────────────────────
WHY THIS EXISTS

On 20 July the remedy for the 0614141 ghost wrote ONE entry into the file the
population agent roots against:

    diazyme.com → 0817089   "(GEPIR-verified, 184 GUDID)"

GEPIR HAD BEEN RETIRED FOR NINETEEN MONTHS. No authority was consulted.
0817089 is a plausible parse of the GLN and it was never a licence key.

On 5 September, Verified by GS1 showed the truth:

    081708902   GS1 Company Prefix   GLN 0817089020009   updated 1 Jul 2026
    081730202   GS1 Company Prefix   GLN 0817089020009   updated 7 Jul 2026

and the GS1 encoder put the boundary in the same place on both.

The value survived seven weeks because our own hand-written GIAI
`giai:0817089.2`, rendered without its dot, IS `081708902` — the real licence
key. THE ERROR VALIDATED ITSELF.

──────────────────────────────────────────────────────────────────────────────
WHAT A READ MUST CARRY, AND WHY EACH FIELD IS THERE

    licence_key      what the authority displays. NOT what we parsed.
    licence_type     "GS1 Company Prefix" or "GLN" — a GLN-type licence
                     licenses a LOCATION, not a prefix, and no company prefix
                     may be derived from it.
    authority        the surface actually consulted, ON THE DAY.
    read_at          when a human looked.
    read_by          who looked. A hand-read is a person's assertion.
    capture          THE SCREEN. A hand-read whose source image is not in the
                     record is a claim citing a document the register does not
                     hold — which GATE_PRODUCTION_CONTRACT §1 forbids.
    authority_updated  the date the AUTHORITY says its record changed.

An entry missing `capture` is graded `unverified-transcription`. It is not a
hand-read. It is somebody's note about one.
"""

import argparse
import json
import os
import subprocess
import sys

RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"; CYA="\033[36m"

PROD = os.environ.get("PROD_DB", "thingdaddy_population")
HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "population", "standards", "authority_reads.json")

# ── the register ─────────────────────────────────────────────────────────────
# CONFIRMED entries were read from the authority on 5 September with the screen
# captured. TRANSCRIBED entries are prose in the record whose capture is not in
# the repo — they are NOT hand-reads until the image is filed.
SEED = {
  "register": "thingdaddy.authority_reads.v1",
  "note": "The authority's own display, read by a human, with the screen filed. "
          "Nothing here is parsed, derived or inferred. A GLN that happens to "
          "split cleanly is NOT a licence key.",
  "grades": {
    "confirmed": "read from the authority, screen captured and filed",
    "unverified-transcription": "prose in the record; the capture is not in the "
                                "repo. NOT a hand-read.",
    "owed": "never read from any live authority",
  },
  "reads": [
    {"licence_key":"081708902","licence_type":"GS1 Company Prefix",
     "company":"Diazyme Laboratories, Inc","city":"Poway","country":"US",
     "gln":"0817089020009","mo":"GS1 US",
     "authority":"Verified by GS1 · gs1.org","read_at":"2026-09-05","read_by":"KJ",
     "authority_updated":"2026-07-01","capture":"IMG_6519.PNG","grade":"confirmed",
     "corroboration":["GS1 encoder: (8004) 08170890245678 → giai:081708902.45678",
                      "GCP Length Table: prefix 0817 → gcpLength 9"],
     "supersedes":"0817089 — a plausible GLN parse, never a licence key"},

    {"licence_key":"081730202","licence_type":"GS1 Company Prefix",
     "company":"Diazyme Laboratories, Inc","city":"Poway","country":"US",
     "gln":"0817089020009","mo":"GS1 US",
     "authority":"Verified by GS1 · gs1.org","read_at":"2026-09-05","read_by":"KJ",
     "authority_updated":"2026-07-07","capture":"IMG_6520.PNG","grade":"confirmed",
     "corroboration":["GS1 encoder: (8004) 0817302028765 → giai:081730202.8765"],
     "note":"A SECOND Diazyme licence. It appears nowhere in the record before "
            "5 September. VBG displays the same GLN against both records — worth "
            "a look, not a conclusion."},

    # ── the eight from PREFIX DAY, 26 July. Prose in the record; captures NOT
    #    in the repo. If 0817089 was never read from an authority, these need
    #    confirming before they can be relied on.
    {"licence_key":"42503175","company":"Chromsystems Instruments + Chemicals GmbH",
     "gln":"4250317500007","mo":"GS1 Germany","authority":"recorded in-session",
     "read_at":"2026-07-26","read_by":"KJ","capture":None,
     "grade":"unverified-transcription"},
    {"licence_key":"0781410","company":"Honeywell International Inc.",
     "gln":"0662498000001","mo":"GS1 US","authority":"recorded in-session",
     "read_at":"2026-07-26","read_by":"KJ","capture":None,
     "grade":"unverified-transcription",
     "note":"GLN issued under sibling prefix 0662498 — same entity, two licences."},
    {"licence_key":"0662498","company":"Honeywell International Inc.","mo":"GS1 US",
     "authority":"recorded in-session","read_at":"2026-07-26","read_by":"KJ",
     "capture":None,"grade":"unverified-transcription"},
    {"licence_key":"081577302","company":"Thermo Fisher Scientific (Asheville) LLC",
     "gln":"0815773020007","mo":"GS1 US","authority":"recorded in-session",
     "read_at":"2026-07-26","read_by":"KJ","capture":None,
     "grade":"unverified-transcription"},
    {"licence_key":"081693402","company":"Thermo Fisher Scientific (Asheville) LLC",
     "mo":"GS1 US","authority":"recorded in-session","read_at":"2026-07-26",
     "read_by":"KJ","capture":None,"grade":"unverified-transcription"},
    {"licence_key":"0850000184","company":"Thermo Fisher Scientific (Madison WI)",
     "gln":"0850000184008","mo":"GS1 US","authority":"recorded in-session",
     "read_at":"2026-07-26","read_by":"KJ","capture":None,
     "grade":"unverified-transcription"},
    {"licence_key":"08600008927","company":"Thermo Fisher Scientific (Madison WI)",
     "mo":"GS1 US","authority":"recorded in-session","read_at":"2026-07-26",
     "read_by":"KJ","capture":None,"grade":"unverified-transcription",
     "note":"ELEVEN digits. The lengths in this register run 7,8,9,10,11 — which "
            "is why AUTHORITY SETS LENGTH PER COMPANY and a range default cannot."},
    {"licence_key":"0884883","company":"Thermo Fisher Scientific, CDX Fremont",
     "gln":"0884883000001","mo":"GS1 US","authority":"recorded in-session",
     "read_at":"2026-07-26","read_by":"KJ","capture":None,
     "grade":"unverified-transcription"},
  ],
  "superseded": [
    {"value":"0817089","why":"a plausible parse of GLN 0817089020009, written into "
     "verified_prefixes.json on 2026-07-20 labelled GEPIR-verified. GEPIR was "
     "retired 31 December 2023 — no authority could have been consulted.",
     "superseded_by":"081708902","on":"2026-09-05",
     "note":"NOT DELETED. It is cited in a published book 41 times and roots 252 "
            "nodes. A superseded reading stays visible as evidence the record "
            "improved."},
    {"value":"0614141","why":"the GS1 encoder's own worked example, recorded as a "
     "verified Honeywell root on a first-party claim with no authority behind it.",
     "superseded_by":None,"on":"2026-07-20","note":"evicted. Crash-test dummy #1."},
  ],
}


def psql(sql):
    p = subprocess.run(["psql","-qAt","-F","\t","-v","ON_ERROR_STOP=1","-d",PROD,"-f","-"],
                       input="SET default_transaction_read_only = on;\n"+sql,
                       capture_output=True, text=True, timeout=600)
    if p.returncode:
        e=(p.stderr or "").strip().splitlines()
        return None,(e[-1] if e else "unknown error")
    return [l.split("\t") for l in p.stdout.split("\n") if l], None


def load():
    if os.path.isfile(REG):
        return json.load(open(REG)), REG
    return SEED, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--worklist", action="store_true")
    ap.add_argument("--init", action="store_true")
    a = ap.parse_args()

    if a.init:
        os.makedirs(os.path.dirname(REG), exist_ok=True)
        if os.path.isfile(REG):
            print(f"\n  {YEL}{REG} already exists — not overwritten.{RESET}\n"); sys.exit(0)
        json.dump(SEED, open(REG,"w"), indent=2)
        print(f"\n  wrote {REG}\n"); sys.exit(0)

    reg, path = load()
    reads = reg["reads"]
    keys = {r["licence_key"]: r for r in reads}
    superseded = {s["value"]: s for s in reg.get("superseded", [])}

    rows, err = psql("SELECT prefix, legal_name, state, source FROM party "
                     "WHERE prefix IS NOT NULL GROUP BY 1,2,3,4 ORDER BY prefix;")
    if err:
        print(f"\n  {RED}REFUSED{RESET}  {err}\n"); sys.exit(2)

    agree, disagree, unread, ghosts = [], [], [], []
    seen = set()
    for pfx, name, state, src in rows:
        if pfx in keys:
            agree.append({"prefix":pfx,"company":name,"state":state,"source":src,
                          "read":keys[pfx]}); seen.add(pfx)
        elif pfx in superseded:
            ghosts.append({"prefix":pfx,"company":name,"state":state,"source":src,
                           "superseded":superseded[pfx]})

    for k, r in keys.items():
        if k not in seen:
            unread.append({"licence_key":k,"company":r.get("company"),
                           "grade":r.get("grade"),
                           "why":"the authority holds this licence and PRODUCTION DOES NOT"})

    worklist = [r for r in reads if r.get("grade") != "confirmed"]

    out = {
      "record":"thingdaddy.authority_check.v1",
      "register": path or "(seed, not yet written to disk — run --init)",
      "reads_held": len(reads),
      "confirmed": sum(1 for r in reads if r.get("grade")=="confirmed"),
      "unverified_transcriptions": len(worklist),
      "in_production_and_agrees": agree,
      "in_production_but_superseded": ghosts,
      "authority_holds_but_production_does_not": unread,
      "worklist": [{"licence_key":r["licence_key"],"company":r.get("company"),
                    "grade":r.get("grade"),"read_at":r.get("read_at"),
                    "capture":r.get("capture")} for r in worklist],
      "policy":
        "AN ENTRY WITHOUT A CAPTURE IS NOT A HAND-READ. It is somebody's note about one. "
        "0817089 was recorded as GEPIR-verified nineteen months after GEPIR was retired, "
        "and it stood for seven weeks.",
    }

    if a.json: print(json.dumps(out, indent=2)); sys.exit(0)

    print(f"\n{BOLD}td_authority{RESET}   the authority read register   {DIM}READ ONLY{RESET}")
    print(f"{DIM}  what the authority displays, read by a human, with the screen filed.{RESET}")
    print(f"\n  register: {out['register']}")
    print(f"  {GRN}{out['confirmed']} confirmed{RESET} · "
          f"{YEL}{out['unverified_transcriptions']} unverified transcription(s){RESET} "
          f"of {out['reads_held']} read(s)")

    if a.worklist:
        print(f"\n{BOLD}WORKLIST — needs reading from a live authority{RESET}")
        for w in out["worklist"]:
            print(f"  {YEL}·{RESET} {w['licence_key']:<12} {w['company'] or ''}")
            print(f"    {DIM}recorded {w['read_at']} · capture: {w['capture'] or 'NONE'}{RESET}")
        print(f"\n  {CYA}{out['policy']}{RESET}\n"); sys.exit(0)

    if ghosts:
        print(f"\n{BOLD}{RED}IN PRODUCTION, BUT SUPERSEDED{RESET}")
        for g in ghosts:
            s = g["superseded"]
            print(f"  {RED}{g['prefix']}{RESET}  {g['company']}  [{g['state']}/{g['source']}]")
            print(f"    {DIM}{s['why']}{RESET}")
            if s.get("superseded_by"):
                print(f"    {GRN}→ should be {s['superseded_by']}{RESET}")

    if unread:
        print(f"\n{BOLD}{YEL}THE AUTHORITY HOLDS IT, PRODUCTION DOES NOT{RESET}")
        for u in unread:
            print(f"  {YEL}{u['licence_key']}{RESET}  {u['company'] or ''}  {DIM}[{u['grade']}]{RESET}")

    if agree:
        print(f"\n{BOLD}{GRN}AGREES WITH THE AUTHORITY{RESET}")
        for x in agree:
            print(f"  {GRN}{x['prefix']}{RESET}  {x['company']}  {DIM}[{x['state']}]{RESET}")

    print(f"\n{BOLD}WHAT THIS CANNOT TELL YOU{RESET}")
    print(f"  {DIM}whether an 'unverified-transcription' is RIGHT. It only says the capture is")
    print(f"  not in the repo, so the claim cannot be checked against its source.{RESET}")
    print(f"\n  {CYA}{out['policy']}{RESET}\n")
    sys.exit(1 if (ghosts or unread) else 0)


if __name__ == "__main__":
    main()
