#!/usr/bin/env python3
"""
e2e_stub_pipeline.py — proves harvest -> admit -> gate -> verify(STUB) -> promote -> verified,
end-to-end, with NO spend and NO Postgres, driving the REAL verify_cli.py over stdin/stdout
the exact way population/api/server.js's resolvePrefixAuthority() drives it (execFile + stdin
JSON + stdout JSON; promote decision = status=='verified' AND integer length).

Why this exists: the node route test (gate_stub_feed.mjs) needs express+pg+Postgres, which live
in the team's CI, not in a scratch box. This harness models the gate's state machine in-process so
the WHOLE loop is runnable anywhere python3 is — and it calls the same verifier the server calls, so
a green run here means the seam is wired, not mocked.

The gate law it enforces (mirrors server.js):
  - promoteGate flips a row to 'verified' ONLY on confirmed = (status=='verified' AND int length).
  - promoteGate NEVER consults the verifier itself — it acts on the resolved authority verdict.
  - A stub verdict is tagged STUB in the citation and is written to the row's authority field as
    STUB — never laundered into a real-GEPIR verify.

Run:
  python3 e2e_stub_pipeline.py            # full end-to-end, self-checking
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(HERE, "verify_cli.py")


# ── the gate's verifier call — a faithful port of server.js resolvePrefixAuthority ───────────
def resolve_prefix_authority(prefix, derived_source, vbg_confirm=None, env=None):
    """Spawn verify_cli.py exactly as the server does: JSON on stdin, JSON on stdout, inherited
    env (so STUB_FEED, if set on this process, reaches the child — same as execFile). FAILS CLOSED:
    any spawn/parse failure -> confirmed:false, unreachable:true (never promotes)."""
    child_env = dict(os.environ)
    if env:
        child_env.update(env)
    payload = json.dumps({"prefix": prefix, "derived_source": derived_source,
                          "vbg_confirm": vbg_confirm})
    try:
        out = subprocess.run([sys.executable, VERIFY], input=payload, text=True,
                             capture_output=True, timeout=8, env=child_env)
    except Exception as e:
        return {"confirmed": False, "unreachable": True, "reason": f"verifier unavailable: {e}"}
    try:
        v = json.loads(out.stdout)
    except Exception:
        return {"confirmed": False, "unreachable": True, "reason": "unparseable verifier output"}
    confirmed = v.get("status") == "verified" and isinstance(v.get("length"), int)
    return {"confirmed": confirmed, "status": v.get("status"),
            "length": v.get("length") if isinstance(v.get("length"), int) else None,
            "citation": v.get("citation")}


# ── the party table + the state machine (the parts of server.js the seam touches) ────────────
class Party:
    def __init__(self, pid, legal_name, source):
        self.id, self.legal_name, self.source = pid, legal_name, source
        self.state, self.prefix, self.length, self.authority = "candidate", None, None, None
        self.events = []

def admit(store, legal_name, source):
    """POST /ingest — a harvested party is ADMITTED as a candidate. No prefix, not verified."""
    pid = len(store) + 1
    p = Party(pid, legal_name, source); p.events.append(("admitted", source)); store[pid] = p
    return p

def promote_gate(party, prefix, resolved):
    """POST /gate/:id — flip to 'verified' ONLY on a confirmed authority verdict. NEVER re-runs the
    verifier; acts on `resolved`. Records the authority citation (STUB or real) on the row + event."""
    if not resolved.get("confirmed"):
        party.events.append(("gate_rejected", resolved.get("reason") or resolved.get("status")))
        return False
    party.state = "verified"; party.prefix = prefix
    party.length = resolved["length"]; party.authority = resolved["citation"]
    party.events.append(("verified", resolved["citation"]))
    return True

def gate(store, party, prefix, derived_source, env=None, vbg_confirm=None):
    """The full gate step: resolve authority for `prefix`, then promote iff confirmed."""
    resolved = resolve_prefix_authority(prefix, derived_source, vbg_confirm, env=env)
    promoted = promote_gate(party, prefix, resolved)
    return promoted, resolved


# ── the end-to-end proof ─────────────────────────────────────────────────────────────────────
def main():
    stub_csv = os.path.join(HERE, "stub_feed.csv")
    if not os.path.exists(stub_csv):
        with open(stub_csv, "w") as f:
            f.write("prefix,company,status,prefix_length,mo,note\n"
                    "0812345,Acme Diagnostics,verified,7,GS1 US,SIMULATED — replace with real GEPIR\n")
    # Resolve the recorded registry the same way verify_cli.py does: env override, else the
    # sibling standards/ copy (its real home), else a local copy (cloud scratch). Portable across
    # the vendored layout (population/verify next to population/standards) and a flat scratch dir.
    _cands = [os.environ.get("VERIFIED_PREFIXES"),
              os.path.join(HERE, "verified_prefixes.json"),
              os.path.normpath(os.path.join(HERE, "..", "standards", "verified_prefixes.json"))]
    vp = next((p for p in _cands if p and os.path.exists(p)), _cands[-1])
    base_env = {"VERIFIED_PREFIXES": vp}                       # recorded registry (real Diazyme)
    stub_env = {**base_env, "STUB_FEED": stub_csv}             # + stub armed
    fails = 0
    def ck(label, cond):
        nonlocal fails
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond: fails += 1

    print("[e2e] STUB OFF — a harvested candidate with only a GUDID-derived prefix must NOT promote")
    store = {}
    acme = admit(store, "Acme Diagnostics", "GUDID")
    ck("admitted as candidate (no prefix, not verified)", acme.state == "candidate" and acme.prefix is None)
    promoted, r = gate(store, acme, "0812345", "gudid", env=base_env)
    ck("gate does NOT promote (stub off -> candidate)", promoted is False and r["status"] == "candidate")
    ck("row still candidate, still no prefix", acme.state == "candidate" and acme.prefix is None)

    print("\n[e2e] STUB ARMED — the SAME candidate now runs the full loop to 'verified', tagged STUB")
    store = {}
    acme = admit(store, "Acme Diagnostics", "GUDID")
    promoted, r = gate(store, acme, "0812345", "gudid", env=stub_env)
    ck("gate promotes on the stub verdict", promoted is True)
    ck("row.state = 'verified'", acme.state == "verified")
    ck("row.prefix set to 0812345", acme.prefix == "0812345")
    ck("licensed length = 7 (from the stub, not derived from GTINs)", acme.length == 7)
    ck("authority on the row is TAGGED STUB (never laundered to real)",
       (acme.authority or "").startswith("STUB (simulated feed"))
    ck("last event is 'verified' carrying the STUB citation",
       acme.events[-1][0] == "verified" and "STUB" in acme.events[-1][1])

    print("\n[e2e] RECORDED still outranks the stub — a real GEPIR verify is never overwritten")
    store = {}
    diaz = admit(store, "Diazyme Laboratories", "GUDID")
    promoted, r = gate(store, diaz, "0817089", "gudid", env=stub_env)   # stub armed, but recorded wins
    ck("Diazyme promotes via RECORDED authority", promoted is True and diaz.state == "verified")
    ck("length 7, citation is the real GEPIR pull (not STUB)",
       diaz.length == 7 and "GEPIR 2026-07-20" in (diaz.authority or "") and "STUB" not in (diaz.authority or ""))

    print("\n[e2e] fail-closed holds under the stub — a prefix absent from the stub does NOT promote")
    store = {}
    ghost = admit(store, "Ghost Corp", "manual")
    promoted, r = gate(store, ghost, "0700000", "manual", env=stub_env)
    ck("unknown prefix stays candidate (exception, not promoted)",
       promoted is False and ghost.state == "candidate")

    print("\nALL E2E STUB-PIPELINE ASSERTIONS PASS" if fails == 0 else f"\n{fails} ASSERTION(S) FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
