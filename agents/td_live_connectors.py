#!/usr/bin/env python3
"""
ThingDaddy Live Relationship Connectors — SEC EDGAR · USASpending · SAM.gov
===========================================================================
Real connectors for the F4 / Loop-B relationship sources. These make live
HTTPS calls from a machine with open network (your Mac mini). They are wired
into thingdaddy_agent_fleet_loopB.py via the --live flag.

Honest notes on access (June 2026):
  • SEC EDGAR   — FREE, keyless. Requires a descriptive User-Agent header
                  (SEC policy). Endpoints:
                    data.sec.gov/submissions/CIK##########.json  (filings list)
                    efts.sec.gov/LATEST/search-index?q=...        (full-text search)
                  Exhibit 21 (subsidiaries) lives inside a company's 10-K as an
                  EX-21 document; we locate the latest 10-K, fetch its EX-21, and
                  parse the subsidiary lines.
  • USASpending — FREE, keyless. POST api.usaspending.gov/api/v2/... JSON REST.
  • SAM.gov     — Entity Management API needs a FREE API key (register at sam.gov).
                  So SAM is "free" but NOT keyless. Pass sam_api_key=... or set
                  env SAM_API_KEY; without it, the SAM connector is skipped
                  (verified-or-exception: we do not fabricate SAM data).

Every record returned carries a documentary 'doc' reference so the fleet's
edge-verification (both endpoints registered + documentary source) can run.
If a live call fails (no network, rate limit), the caller falls back to the
offline seed — the loop still runs and is clearly marked as seed data.

Usage (standalone smoke test, on a networked machine):
    python td_live_connectors.py "APPLE INC"      # EDGAR subsidiaries demo
"""

from __future__ import annotations
import json, os, re, sys, time
import urllib.request, urllib.parse, urllib.error

UA = "ThingDaddy Relationship Connector (kj@thingdaddy.com)"   # SEC requires a real UA
TIMEOUT = 20


def _get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()

def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
        headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # A 4xx/5xx carries the API's specific complaint in the body — surface it.
        body = e.read().decode("utf-8", "ignore")
        print(f"[http] POST {url} -> {e.code} {e.reason}; response body: {body}", file=sys.stderr)
        raise


# ══════════════════════════════════════════════════════════════════════════════
# SEC EDGAR — Exhibit 21 subsidiaries  (parent_of edges)
# ══════════════════════════════════════════════════════════════════════════════
def edgar_cik_for(name: str) -> str | None:
    """Resolve a company name to a zero-padded CIK via EDGAR's company tickers file."""
    try:
        raw = _get("https://www.sec.gov/files/company_tickers.json")
        table = json.loads(raw)
        want = name.lower()
        for row in table.values():
            if want in row.get("title", "").lower():
                return str(row["cik_str"]).zfill(10)
    except Exception as e:
        print(f"[edgar] cik lookup failed: {e}", file=sys.stderr)
    return None


def edgar_latest_10k_accession(cik10: str) -> tuple[str, str] | None:
    """Return (accessionNoDashless, primaryDoc) for the latest 10-K."""
    try:
        raw = _get(f"https://data.sec.gov/submissions/CIK{cik10}.json")
        sub = json.loads(raw)
        recent = sub["filings"]["recent"]
        for form, acc, doc, date in zip(recent["form"], recent["accessionNumber"],
                                        recent["primaryDocument"], recent["filingDate"]):
            if form == "10-K":
                return acc.replace("-", ""), doc
    except Exception as e:
        print(f"[edgar] submissions failed: {e}", file=sys.stderr)
    return None


def edgar_exhibit21_subsidiaries(name: str, cik10: str, acc: str) -> list[dict]:
    """Fetch the filing index, find the EX-21 document, parse subsidiary names."""
    edges = []
    try:
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc}"
        idx = json.loads(_get(f"{base}/index.json"))
        ex21_name = None
        for item in idx.get("directory", {}).get("item", []):
            nm = item.get("name", "").lower()
            if "ex-21" in nm or "ex21" in nm or "exhibit21" in nm:
                ex21_name = item["name"]; break
        if not ex21_name:
            return edges
        html = _get(f"{base}/{ex21_name}").decode("utf-8", "ignore")
        text = re.sub(r"<[^>]+>", " ", html)          # strip tags
        text = re.sub(r"&[a-z]+;", " ", text)
        # subsidiary lines: capture plausible entity names (Inc/LLC/Ltd/Corp/Co)
        for m in re.finditer(r"([A-Z][A-Za-z0-9&.,'\- ]{3,60}?(?:Inc|LLC|Ltd|Corp|Corporation|Co|GmbH|B\.V\.|S\.A\.)\.?)", text):
            sub_name = re.sub(r"\s+", " ", m.group(1)).strip(" ,.")
            if sub_name.lower() == name.lower():
                continue
            edges.append({"source": "SEC-EDGAR-EX21", "subject": name, "object": sub_name,
                          "kind": "parent_of", "doc": f"{base}/{ex21_name}", "object_prefix": None})
        # de-dupe, cap
        seen, out = set(), []
        for e in edges:
            if e["object"].lower() in seen: continue
            seen.add(e["object"].lower()); out.append(e)
        return out[:40]
    except Exception as e:
        print(f"[edgar] ex-21 parse failed: {e}", file=sys.stderr)
        return edges


def edgar_subsidiary_edges(name: str) -> list[dict]:
    cik = edgar_cik_for(name)
    if not cik: return []
    time.sleep(0.2)                       # be polite to SEC
    latest = edgar_latest_10k_accession(cik)
    if not latest: return []
    acc, _doc = latest
    time.sleep(0.2)
    return edgar_exhibit21_subsidiaries(name, cik, acc)


# ══════════════════════════════════════════════════════════════════════════════
# USASpending — federal awards  (award_recipient edges)
# ══════════════════════════════════════════════════════════════════════════════
def usaspending_award_edges(name: str, limit: int = 10) -> list[dict]:
    try:
        # spending_by_award REQUIRES filters.award_type_codes (a 422 "Missing value:
        # 'filters|award_type_codes' is a required field" otherwise). "A","B","C","D"
        # are the prime-contract codes; the "fields" values must exactly match the
        # award category's allowed set — these four are valid for contracts.
        payload = {
            "filters": {"award_type_codes": ["A", "B", "C", "D"],
                        "recipient_search_text": [name],
                        "time_period": [{"start_date": "2020-01-01", "end_date": "2026-12-31"}]},
            "fields": ["Award ID", "Recipient Name", "Awarding Agency", "Award Amount"],
            "page": 1, "limit": limit, "sort": "Award Amount", "order": "desc",
        }
        res = _post_json("https://api.usaspending.gov/api/v2/search/spending_by_award/", payload)
        edges = []
        for row in res.get("results", []):
            agency = row.get("Awarding Agency") or "US Federal"
            edges.append({"source": "USASPENDING", "subject": name, "object": agency,
                          "kind": "award_recipient",
                          "doc": f"award-id {row.get('Award ID','?')} ${row.get('Award Amount','?')}",
                          "object_prefix": None})
        # de-dupe by agency
        seen, out = set(), []
        for e in edges:
            if e["object"] in seen: continue
            seen.add(e["object"]); out.append(e)
        return out
    except Exception as e:
        print(f"[usaspending] failed: {e}", file=sys.stderr)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# SAM.gov — entity registration  (registered_as edge)  — needs a free API key
# ══════════════════════════════════════════════════════════════════════════════
def sam_registration_edges(name: str, sam_api_key: str | None = None) -> list[dict]:
    key = sam_api_key or os.environ.get("SAM_API_KEY")
    if not key:
        print("[sam] no SAM_API_KEY — skipping (verified-or-exception: not fabricating)", file=sys.stderr)
        return []
    try:
        q = urllib.parse.urlencode({"api_key": key, "legalBusinessName": name, "samRegistered": "Yes"})
        res = json.loads(_get(f"https://api.sam.gov/entity-information/v3/entities?{q}"))
        edges = []
        for ent in res.get("entityData", [])[:5]:
            reg = ent.get("entityRegistration", {})
            uei = reg.get("ueiSAM", "UEI:?")
            edges.append({"source": "SAM-GOV", "subject": name, "object": f"UEI:{uei}",
                          "kind": "registered_as", "doc": "SAM entity registration",
                          "object_prefix": None})
        return edges
    except Exception as e:
        print(f"[sam] failed: {e}", file=sys.stderr)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Unified live source — drop-in replacement for relationship_sources()
# ══════════════════════════════════════════════════════════════════════════════
def live_relationship_sources(anchor_prefix: str, anchor_name: str,
                              sam_api_key: str | None = None) -> list[dict]:
    """Live EDGAR + USASpending + SAM. Returns [] on total failure so the caller
       can fall back to the offline seed."""
    out = []
    out += edgar_subsidiary_edges(anchor_name)
    out += usaspending_award_edges(anchor_name)
    out += sam_registration_edges(anchor_name, sam_api_key)
    return out


if __name__ == "__main__":
    nm = sys.argv[1] if len(sys.argv) > 1 else "APPLE INC"
    print(f"Live relationship pull for: {nm}\n" + "-" * 60)
    rows = live_relationship_sources("", nm)
    if not rows:
        print("(no live records — network blocked here, or none found. "
              "Run on a networked machine.)")
    for r in rows:
        print(f"  [{r['source']:<14}] {r['subject']} -{r['kind']}-> {r['object']}")
        print(f"       doc: {r['doc']}")
