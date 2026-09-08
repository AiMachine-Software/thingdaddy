#!/usr/bin/env python3
"""
td_mirror.py — the mirror held to ourselves.

    python3 td_mirror.py                      check every claimed artefact
    python3 td_mirror.py --json
    python3 td_mirror.py --lost               only what is claimed and gone
    python3 td_mirror.py --roots ~/a ~/b      extra places to look

READ ONLY. Touches nothing.

WHY
  Between 9 July and 6 September the record claimed 92 artefacts as BUILT,
  SHIPPED, DELIVERED or COMMITTED. On 5 September six files turned out to
  live in exactly one place and one was gone. On 24 July a doc said the GLEIF
  tools were "delivered" and they were not on disk — "delivered-to-chat is
  not saved-to-disk."

  A register that audits its data and not its own build claims is asking to
  be taken on faith about the second thing. This is td_audit.py pointed at
  the project instead of the database.

WHAT IT CHECKS, PER ARTEFACT
  on disk         found under any root, exact filename
  tracked         git ls-files finds it in whichever repo holds it
  where           every path it was found at — MORE THAN ONE is its own
                  finding (which copy is canonical?)
  claimed         first and last date the record said it existed, and by
                  which document

STATES
  SOLID           on disk AND tracked in git
  DARK            on disk, NOT tracked — one laptop from gone
  LOST            claimed, not on disk anywhere
  MULTIPLE        on disk in more than one place — drift risk

The claims come from mirror_claims.json, extracted from the project record
on 6 September. Regenerate it when the record grows; do not hand-edit it.
"""

import argparse
import json
import os
import subprocess
import sys

RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"; CYA="\033[36m"

HOME = os.path.expanduser("~")
DEFAULT_ROOTS = [
    os.path.join(HOME, "thingdaddy"),
    os.path.join(HOME, "thingdaddy-engine"),
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "Downloads"),
]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "gudid_archive", "aws"}
CLAIMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirror_claims.json")


def walk(roots):
    """filename → [paths]. One pass over every root."""
    idx = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in fns:
                idx.setdefault(fn, []).append(os.path.join(dp, fn))
    return idx


def git_root(path):
    try:
        r = subprocess.run(["git", "-C", os.path.dirname(path), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def tracked(path):
    root = git_root(path)
    if not root:
        return False, None
    rel = os.path.relpath(path, root)
    r = subprocess.run(["git", "-C", root, "ls-files", "--error-unmatch", rel],
                       capture_output=True, text=True, timeout=10)
    return r.returncode == 0, root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lost", action="store_true")
    ap.add_argument("--roots", nargs="*", default=[])
    ap.add_argument("--claims", default=CLAIMS)
    a = ap.parse_args()

    if not os.path.isfile(a.claims):
        print(f"\n  {RED}REFUSED{RESET}  {a.claims} not found. The claims file is extracted from "
              f"the project record; it must sit beside this script.\n"); sys.exit(2)
    claims = json.load(open(a.claims))
    roots = DEFAULT_ROOTS + [os.path.expanduser(r) for r in a.roots]

    if not a.json:
        print(f"\n{BOLD}td_mirror{RESET}   the mirror held to ourselves   {DIM}READ ONLY{RESET}")
        print(f"{DIM}  every artefact the record claims was built, checked against disk and git.{RESET}")
        print(f"  claims: {len(claims)}   roots: {', '.join(r.replace(HOME,'~') for r in roots)}")
        print(f"  {DIM}indexing…{RESET}", end="", flush=True)
    idx = walk(roots)
    if not a.json:
        print(f" {len(idx):,} filenames")

    results = []
    for c in claims:
        name = c["artefact"]
        paths = idx.get(name, [])
        tr = []
        for p in paths:
            ok, root = tracked(p)
            tr.append({"path": p.replace(HOME, "~"), "tracked": ok,
                       "repo": (root or "").replace(HOME, "~") or None})
        if not paths:
            state = "LOST"
        elif len(paths) > 1:
            state = "MULTIPLE"
        elif tr[0]["tracked"]:
            state = "SOLID"
        else:
            state = "DARK"
        results.append({**c, "state": state, "found": tr})

    order = {"LOST": 0, "DARK": 1, "MULTIPLE": 2, "SOLID": 3}
    results.sort(key=lambda r: (order[r["state"]], r["first_claimed"]))
    counts = {k: sum(1 for r in results if r["state"] == k) for k in order}

    rec = {
        "record": "thingdaddy.mirror.v1",
        "shaped_for": "a consumer that has never seen the terminal",
        "read_only": True,
        "claims": len(claims),
        "roots": [r.replace(HOME, "~") for r in roots],
        "summary": counts,
        "states": {
            "SOLID": "on disk and tracked in git",
            "DARK": "on disk, not tracked — one laptop from gone",
            "LOST": "claimed by the record, not on disk anywhere searched",
            "MULTIPLE": "on disk in more than one place — which copy is canonical?",
        },
        "results": results,
        "policy": "DELIVERED-TO-CHAT IS NOT SAVED-TO-DISK. SAVED-TO-DISK IS NOT COMMITTED. "
                  "A build claim is a candidate until git holds the file.",
        "cannot_check": [
            "whether a found file is the VERSION the record describes — only that a file "
            "with that name exists",
            "whether a file works — this checks presence, not function",
            "artefacts the record never named by filename",
        ],
    }

    if a.json:
        print(json.dumps(rec, indent=2)); sys.exit(1 if counts["LOST"] else 0)

    def show(state, col):
        rows = [r for r in results if r["state"] == state]
        if not rows: return
        print(f"\n{BOLD}{col}{state}{RESET}  {DIM}{rec['states'][state]}{RESET}")
        for r in rows:
            if a.lost and state != "LOST": continue
            print(f"  {col}{r['artefact']:46s}{RESET} {DIM}claimed {r['first_claimed']}"
                  f"{'..'+r['last_claimed'] if r['last_claimed']!=r['first_claimed'] else ''}"
                  f" · in {r['n_files']} doc(s){RESET}")
            if state == "LOST":
                for ctx in r["context"][:1]:
                    print(f"      {DIM}{ctx[:120]}{RESET}")
                print(f"      {DIM}{r['claimed_in'][0]}{RESET}")
            else:
                for f in r["found"][:3]:
                    mark = GRN + "tracked" + RESET if f["tracked"] else YEL + "UNTRACKED" + RESET
                    print(f"      {f['path']}  [{mark}{DIM} {f['repo'] or 'no repo'}{RESET}]")

    if a.lost:
        show("LOST", RED)
    else:
        show("LOST", RED); show("DARK", YEL); show("MULTIPLE", CYA); show("SOLID", GRN)

    print(f"\n{BOLD}SUMMARY{RESET}")
    print(f"  {RED}{counts['LOST']} lost{RESET} · {YEL}{counts['DARK']} dark{RESET} · "
          f"{CYA}{counts['MULTIPLE']} in multiple places{RESET} · {GRN}{counts['SOLID']} solid{RESET}"
          f"   of {len(claims)} claimed")
    print(f"\n  {CYA}{rec['policy']}{RESET}")
    print(f"\n{DIM}  cannot check: {' · '.join(rec['cannot_check'])}{RESET}\n")
    sys.exit(1 if counts["LOST"] else 0)


if __name__ == "__main__":
    main()
