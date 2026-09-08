#!/usr/bin/env python3
"""
verify_cli.py — vendored, authority-CHECKING prefix verifier (population/verify/).

The gate (POST /gate) shims to a verifier over stdin/stdout to answer: is this GS1
company prefix authority-confirmed, and what is its licensed length? The prior
verifier trusted a CALLER-ASSERTED Verified-by-GS1 payload (a token-holder could
assert `vbg` for any prefix). This one adds the honest upgrade the code itself
flagged as the tracked follow-up: it INDEPENDENTLY confirms the prefix against a
RECORDED authority — standards/verified_prefixes.json, our real GEPIR pulls — so a
promotion no longer depends on the caller's word.

FAILS CLOSED. `confirmed` (status=='verified' + integer length) is reachable only via:
  (i)  RECORDED AUTHORITY — the prefix is present in verified_prefixes.json with
       status=='verified'. Citation = that entry's recorded source (e.g. the GEPIR
       pull date). Length = the licensed company-prefix length (len of the prefix).
  (i-STUB) STUB FEED — OFF by default. Active ONLY when env STUB_FEED points at a
       fixtures CSV (prefix,company,status,prefix_length,mo,note). This SIMULATES the
       authority connector so the whole pipeline runs harvest->gate->verify->promote
       end-to-end with NO spend. Every stub verdict's citation is tagged
       "STUB (simulated feed — not real)" so it can NEVER be mistaken for a real GEPIR
       verify or persisted to the production registry as if authoritative. With
       STUB_FEED unset (production + every existing test) this path does not exist and
       behavior is byte-for-byte the prior verifier. Recorded (i) always outranks stub.
  (ii) Verified-by-GS1 payload — a well-formed `vbg_confirm` with an integer length.
       KEPT for backward-compat with the existing gate contract/tests; it is the
       weaker, caller-asserted path. Recorded authority (i) is preferred and needs
       no caller assertion.
Everything else is NOT verified: a real connector source -> 'candidate'; a bare
'manual' guess -> 'exception'. Nothing is minted on a guess.

Contract (unchanged shape; the server now also passes `prefix`):
  stdin : {"prefix": "...", "derived_source": "...", "vbg_confirm": {...}|null}
  stdout: {"status": "verified"|"candidate"|"exception", "length": int|null, "citation": str|null}

Self-test (no server, no DB):
  python3 verify_cli.py --self-test
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# verify_cli.py lives in population/verify/ ; the recorded registry is population/standards/.
DEFAULT_VP = os.environ.get(
    "VERIFIED_PREFIXES",
    os.path.normpath(os.path.join(HERE, "..", "standards", "verified_prefixes.json")))
# STUB feed: OFF unless env STUB_FEED points at a fixtures CSV. Never a default path.
DEFAULT_STUB = os.environ.get("STUB_FEED")


def load_recorded(path):
    """prefix(str) -> {company, source} for status=='verified' entries. Recorded authority only."""
    idx = {}
    if not os.path.exists(path):
        return idx
    try:
        with open(path) as f:
            reg = json.load(f)
    except Exception:
        return idx
    for entry in reg.values():
        if str(entry.get("status", "")).lower() != "verified":
            continue
        pfx = entry.get("prefix")
        if not pfx:
            continue
        idx[str(pfx)] = {"company": entry.get("company", ""),
                         "source": entry.get("source", "verified_prefixes.json")}
    return idx


def load_stub(path):
    """prefix(str) -> {company, prefix_length, status} from a STUB fixtures CSV. Simulated feed.

    OFF unless a path is given (env STUB_FEED). Every verdict this yields is tagged STUB by the
    caller so it is never confused with a real authority verify. Format matches gs1_authority.py's
    StubFeed: prefix,company,status,prefix_length,mo,note. Only status=='verified' rows arm."""
    idx = {}
    if not path or not os.path.exists(path):
        return idx
    try:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                p = str(row.get("prefix", "")).strip()
                if not p or (row.get("status") or "verified").strip().lower() != "verified":
                    continue
                L = str(row.get("prefix_length", "")).strip()
                idx[p] = {"company": row.get("company", ""),
                          "length": int(L) if L.isdigit() else len(p)}
    except Exception:
        return {}
    return idx


def verify(prefix, derived_source, vbg_confirm, recorded, stub=None):
    """The decision. Returns the stdout dict. FAILS CLOSED.

    Order mirrors the connector (gs1_authority.GS1Authority): RECORDED wins first (real, free),
    then the STUB feed if armed (simulated, tagged), then the weaker caller-asserted vbg, then
    fail closed. `stub` is None/empty in production and every existing test."""
    prefix = str(prefix) if prefix is not None else ""

    # (i) RECORDED AUTHORITY — independent, no caller assertion. Digits only.
    if prefix and re.fullmatch(r"[0-9]+", prefix) and prefix in recorded:
        e = recorded[prefix]
        return {"status": "verified", "length": len(prefix),
                "citation": f"{e['source']} (verified_prefixes.json{('; ' + e['company']) if e['company'] else ''})"}

    # (i-STUB) STUB FEED — armed only when env STUB_FEED is set. SIMULATED; tagged so it can never
    # pass for a real verify. Recorded (above) always outranks it; unset stub => this block vanishes.
    if stub and prefix and re.fullmatch(r"[0-9]+", prefix) and prefix in stub:
        s = stub[prefix]
        co = s.get("company", "")
        return {"status": "verified", "length": s["length"],
                "citation": f"STUB (simulated feed — not real){('; ' + co) if co else ''}"}

    # (ii) Verified-by-GS1 payload — backward-compat, caller-asserted (weaker).
    if isinstance(vbg_confirm, dict) and isinstance(vbg_confirm.get("length"), int):
        lic = vbg_confirm.get("licensee", "")
        return {"status": "verified", "length": vbg_confirm["length"],
                "citation": f"VbG:{lic}|len={vbg_confirm['length']}"}

    # FAIL CLOSED — mirror the prior verifier's candidate/exception distinction so the
    # existing gate contract (and gate_guard.mjs) is preserved: a real connector source
    # is a candidate; a bare 'manual' guess is an exception.
    ds = (derived_source or "").strip().lower()
    if ds and ds != "manual":
        return {"status": "candidate", "length": None, "citation": None}
    return {"status": "exception", "length": None, "citation": None}


def _self_test():
    rec = {"0817089": {"company": "Diazyme Laboratories", "source": "GEPIR 2026-07-20"}}
    cases = [
        # recorded authority — verified WITHOUT any vbg (the honest path)
        (("0817089", "GUDID", None), "verified", 7),
        # recorded lookup is exact — a different prefix is not confirmed by (i)
        (("0817089X", "manual", None), "exception", None),
        # backward-compat: vbg payload still confirms (weaker path)
        (("0999777001", "manual", {"licensee": "Happy Gate Co", "length": 10, "country": "US"}), "verified", 10),
        # fail closed: connector source, no vbg, not recorded -> candidate
        (("0702054", "gudid", None), "candidate", None),
        # fail closed: bare manual guess, no vbg, not recorded -> exception
        (("0702054", "manual", None), "exception", None),
    ]
    fails = 0
    for (pfx, ds, vbg), want_status, want_len in cases:
        got = verify(pfx, ds, vbg, rec)
        okc = got["status"] == want_status and got["length"] == want_len
        print(f"  {'PASS' if okc else 'FAIL'}  prefix={pfx!r} src={ds!r} vbg={'y' if vbg else 'n'} "
              f"-> {got['status']}/{got['length']}  (want {want_status}/{want_len})")
        if not okc:
            fails += 1
    # the recorded path must cite the real pull, never a fabricated authority
    cite = verify("0817089", "GUDID", None, rec)["citation"]
    okc = "GEPIR 2026-07-20" in cite
    print(f"  {'PASS' if okc else 'FAIL'}  recorded citation carries the real pull: {cite!r}")
    if not okc:
        fails += 1

    # ---- STUB feed assertions (the wired-in connector path) --------------------------------
    # With NO stub (production + every existing test): a connector-source prefix stays candidate.
    g = verify("0812345", "gudid", None, rec, None)
    okc = g["status"] == "candidate"
    print(f"  {'PASS' if okc else 'FAIL'}  stub OFF: 0812345/gudid stays candidate (prod unchanged)")
    if not okc: fails += 1
    # With the stub armed: the SAME candidate now verifies, tagged STUB with the stub length.
    stub = {"0812345": {"company": "Acme Co", "length": 7}}
    g = verify("0812345", "gudid", None, rec, stub)
    okc = g["status"] == "verified" and g["length"] == 7 and g["citation"].startswith("STUB (simulated feed")
    print(f"  {'PASS' if okc else 'FAIL'}  stub ON: 0812345 -> {g['status']}/{g['length']}  cite={g['citation']!r}")
    if not okc: fails += 1
    # Recorded ALWAYS outranks the stub — a real verify is never overwritten by a simulated one.
    stub2 = {"0817089": {"company": "WRONG", "length": 9}}
    g = verify("0817089", "gudid", None, rec, stub2)
    okc = g["status"] == "verified" and g["length"] == 7 and "GEPIR 2026-07-20" in g["citation"]
    print(f"  {'PASS' if okc else 'FAIL'}  recorded outranks stub: 0817089 -> len {g['length']} via {g['citation'][:24]!r}…")
    if not okc: fails += 1
    # A stub row is NOT a blank check: a prefix absent from the stub still fails closed.
    g = verify("0700000", "manual", None, rec, stub)
    okc = g["status"] == "exception"
    print(f"  {'PASS' if okc else 'FAIL'}  stub armed but prefix absent: 0700000/manual -> {g['status']} (fails closed)")
    if not okc: fails += 1

    print("\nALL VERIFY-CLI ASSERTIONS PASS" if fails == 0 else f"\n{fails} ASSERTION(S) FAILED")
    return 1 if fails else 0


def main():
    if "--self-test" in sys.argv[1:]:
        sys.exit(_self_test())
    recorded = load_recorded(DEFAULT_VP)
    stub = load_stub(DEFAULT_STUB)   # empty unless env STUB_FEED is set
    try:
        data = json.load(sys.stdin)
    except Exception:
        # No/!parseable input -> fail closed as an exception (never verified).
        print(json.dumps({"status": "exception", "length": None, "citation": None}))
        return
    out = verify(data.get("prefix"), data.get("derived_source"),
                 data.get("vbg_confirm"), recorded, stub)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
