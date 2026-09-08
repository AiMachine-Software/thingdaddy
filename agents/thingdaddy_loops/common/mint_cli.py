#!/usr/bin/env python3
"""
mint_cli.py — thin stdin/stdout shim over the reference engine's mint(), so the
population API (POST /party/:id/asset) can reach the SOLE URN constructor instead
of hand-building a GIAI. Mirrors verify_cli.py exactly. The engine stays pure;
this only adapts I/O and forwards refusals.

MAP NOTE: shims to td_engine_ref (the reference stand-in). Pom's authoritative
engine replaces td_engine_ref behind the same mint() signature — nothing else changes.

Protocol (FAIL CLOSED):
  stdin : JSON { "key":"giai", "prefix":str, "component":str,
                 "carriers":[str]|null, "source":str|null }
  stdout: JSON { "ok":true, "urn":str } on success
          JSON { "ok":false, "error":str, "kind":"MintError|CarrierError|RefusalError" } on refusal
  exit  : 0 when a verdict was produced (mint or a clean refusal); non-zero only
          when we could NOT produce one. A caller MUST treat non-zero / unparseable
          stdout as NOT minted — never fabricate a URN on our silence.
"""
import json
import sys

from td_engine_ref import mint, MintError, CarrierError, RefusalError


def main() -> int:
    try:
        req = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"bad_request:{e.__class__.__name__}", "kind": "MintError"}))
        return 2
    try:
        urn = mint(
            req.get("key", "giai"),
            req.get("prefix"),
            req.get("component"),
            tuple(req["carriers"]) if req.get("carriers") else ("RAIN-96", "GS1-128", "DL"),
            req.get("source") or "SYNTHETIC",
        )
        print(json.dumps({"ok": True, "urn": urn}))
        return 0
    except (MintError, CarrierError, RefusalError) as e:
        print(json.dumps({"ok": False, "error": str(e), "kind": e.__class__.__name__}))
        return 0  # a clean refusal IS a produced verdict — fail closed, don't mint.


if __name__ == "__main__":
    sys.exit(main())
