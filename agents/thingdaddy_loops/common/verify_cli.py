#!/usr/bin/env python3
"""
verify_cli.py — thin stdin/stdout shim over verify.verify_prefix, so a non-Python
caller (the population API's POST /gate guard) can reach the SAME deterministic
gate logic instead of reimplementing it. verify.py stays pure; this only adapts
I/O. Nothing here judges — it forwards to verify_prefix and reports the verdict.

Protocol (FAIL CLOSED):
  stdin : JSON { "derived_source": str|null,
                 "vbg_confirm": {"licensee","length","country"}|null }
  stdout: JSON { "status": "verified"|"candidate"|"exception",
                 "length": int|null, "citation": str }
  exit  : 0 when a verdict was produced (even 'exception'); non-zero only when we
          could NOT produce one. A caller MUST treat a non-zero exit or
          unparseable stdout as NOT verified — never promote on our silence.
"""
import json
import sys

from verify import verify_prefix  # sibling pure module (same directory)


def main() -> int:
    try:
        req = json.load(sys.stdin)
    except Exception as e:  # unparseable request -> a held exception, not a crash
        print(json.dumps({"status": "exception", "length": None,
                          "citation": f"bad_request:{e.__class__.__name__}"}))
        return 2

    status, length, citation = verify_prefix(
        req.get("derived_source"), req.get("vbg_confirm"))
    print(json.dumps({"status": status, "length": length, "citation": citation}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
