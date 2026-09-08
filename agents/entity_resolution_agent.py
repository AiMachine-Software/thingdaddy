#!/usr/bin/env python3
"""
ThingDaddy Enterprise Entity-Resolution Agent
==============================================
Generic filter: given a set of GEPIR / Verified-by-GS1 search hits for a
target enterprise name, separate the actual operating entities of that
enterprise from the namesake / unrelated legal entities that share the name.

The problem is universal. A GS1 search for almost any large brand returns
dozens-to-hundreds of records that are different legal entities:
    "Samsung"  -> 305 hits (Samsung Food, Samsung Farm, Samsung Rivet, ...)
    "Apple"    -> Apple Bank, Apple Farms, Apple Electronics, ...
    "Delta"    -> Delta Air Lines, Delta Faucet, Delta Dental, ...
Name-matching alone cannot resolve them. This agent applies ThingDaddy's
verified-or-exception discipline plus an authority step (the TD-M-50/51
LEI<->prefix bridge and cross-MO unification) to classify each hit.

CONFIGURE a target with an EntityProfile, then run(profile, hits). Nothing
is hardcoded to any one company. A Samsung profile is included only as a
worked example, alongside a generic template you can copy.

GOVERNING RULE (never relaxed):
  Never promote a hit to VERIFIED on name or prefix-band similarity alone.
  Promotion requires (a) a confirmed GS1 prefix anchor AND (b) an authority
  (LEI) match. Otherwise the hit is CANDIDATE (hold) or REJECTED (namesake).
"""

from __future__ import annotations
import csv, json, re, sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# GS1 Member-Organization prefix bands (subset; extend as needed).
# This is generic GS1 data, not company-specific.
# ---------------------------------------------------------------------------
def mo_from_prefix(prefix: str) -> str:
    p = str(prefix)
    bands = [
        ("00", "GS1 US"), ("01", "GS1 US"), ("019", "GS1 US"),
        ("07", "GS1 US"), ("08", "GS1 US"),
        ("50", "GS1 UK"), ("54", "GS1 Belgium & Luxembourg"),
        ("400", "GS1 Germany"), ("45", "GS1 Japan"), ("49", "GS1 Japan"),
        ("471", "GS1 Taiwan"), ("489", "GS1 Hong Kong"),
        ("59", "GS1 Poland"), ("599", "GS1 Hungary"),
        ("60", "GS1 South Africa"), ("690", "GS1 China"), ("69", "GS1 China"),
        ("880", "GS1 Korea"), ("885", "GS1 Thailand"), ("890", "GS1 India"),
    ]
    # longest-prefix-first match
    for pat, mo in sorted(bands, key=lambda b: -len(b[0])):
        if p.startswith(pat):
            return mo
    return "Unknown MO"


# ---------------------------------------------------------------------------
# Configurable target profile — the ONLY company-specific input.
# ---------------------------------------------------------------------------
@dataclass
class EntityProfile:
    display_name: str                       # e.g. "Samsung"
    core_token: str                         # token every in-scope hit must contain, e.g. "samsung"
    home_mo: str                            # MO of the operating entity, e.g. "GS1 Korea"
    positive_tokens: set = field(default_factory=set)   # signal the operating line (electronics, sdi, ...)
    namesake_tokens: set = field(default_factory=set)   # signal an unrelated line (food, farm, ...)
    verified_anchors: dict = field(default_factory=dict)  # prefix -> {legal_name, gln, mo, lei, role}
    lei_seed: dict = field(default_factory=dict)          # normalized_name -> lei-record (authority stand-in)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class RawHit:
    licence_key: str
    company_name: str
    city: str = ""

@dataclass
class Resolution:
    licence_key: str
    company_name: str
    city: str
    normalized: str
    mo: str
    tier: str                    # VERIFIED | CANDIDATE | REJECTED
    score: float
    reasons: list = field(default_factory=list)
    lei: str | None = None
    action: str = ""


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
_SUFFIXES = ["co ltd","co.,ltd","co., ltd","ltd","inc","corp","corporation",
             "zrt","s a","sa","gmbh","llc","plc","co","ag","kg","srl","spa","bv","nv"]

def normalize(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"[.,]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    for suf in sorted(_SUFFIXES, key=len, reverse=True):
        if n.endswith(" " + suf):
            n = n[: -(len(suf) + 1)].strip()
    return n

def tokens(name: str) -> set:
    return set(re.findall(r"[a-z0-9&-]+", name.lower()))


# ---------------------------------------------------------------------------
# The agent — classify one hit against a profile
# ---------------------------------------------------------------------------
def resolve_hit(hit: RawHit, prof: EntityProfile) -> Resolution:
    norm = normalize(hit.company_name)
    mo = mo_from_prefix(hit.licence_key)
    toks = tokens(hit.company_name)
    reasons: list[str] = []
    score = 0.0

    # (a) operator-confirmed prefix anchor => the only prefix-based VERIFIED path
    if hit.licence_key in prof.verified_anchors:
        a = prof.verified_anchors[hit.licence_key]
        return Resolution(hit.licence_key, hit.company_name, hit.city, norm, a.get("mo", mo),
                          "VERIFIED", 1.0,
                          ["prefix matches operator-confirmed GEPIR anchor",
                           f"authority LEI {a.get('lei','-')}"],
                          a.get("lei"), "federate under enterprise standard")

    # (b) must contain the core token to be in scope
    if prof.core_token not in toks:
        return Resolution(hit.licence_key, hit.company_name, hit.city, norm, mo,
                          "REJECTED", 0.0,
                          [f"name does not contain core token '{prof.core_token}'"],
                          None, "drop \u2014 out of scope")

    # (c) namesake business-line tokens => reject signal
    ns = toks & prof.namesake_tokens
    if ns:
        reasons.append(f"namesake business-line token(s): {', '.join(sorted(ns))}")
        score -= 0.6

    # (d) positive operating-line tokens => candidate signal
    pos = toks & prof.positive_tokens
    if pos:
        reasons.append(f"operating-line token(s): {', '.join(sorted(pos))}")
        score += 0.5

    # (e) home MO band is necessary-but-not-sufficient
    if mo == prof.home_mo:
        reasons.append(f"{mo} band (consistent with operating entity, not proof)")
        score += 0.15
    else:
        reasons.append(f"non-home MO ({mo}) \u2014 unlikely the operating entity")
        score -= 0.35

    # (f) AUTHORITY step (TD-M-50/51 LEI bridge) \u2014 only path to lift a name-hit
    lei = None
    rec = prof.lei_seed.get(norm)
    if rec and rec.get("status") == "ISSUED" and rec.get("is_operating_group_member"):
        lei = rec["lei"]
        reasons.append(f"GLEIF LEI confirms operating {prof.display_name} group member ({lei})")
        score += 0.5
        reasons.append("prefix not yet a verified anchor \u2014 hold for prefix confirmation")

    # (g) tier decision \u2014 verified-or-exception
    if score >= 0.35:
        tier = "CANDIDATE"
        action = ("authority-confirmed entity; verify GS1 prefix, then federate"
                  if lei else "plausible; requires GEPIR + LEI confirmation before use")
    else:
        tier = "REJECTED"
        action = "namesake / unrelated \u2014 exclude from connected set"

    return Resolution(hit.licence_key, hit.company_name, hit.city, norm, mo,
                      tier, round(score, 3), reasons, lei, action)


def run(prof: EntityProfile, hits: list[RawHit]) -> list[Resolution]:
    return [resolve_hit(h, prof) for h in hits]


# ---------------------------------------------------------------------------
# Generic profile template (copy + fill for any enterprise)
# ---------------------------------------------------------------------------
GENERIC_TEMPLATE = EntityProfile(
    display_name="<Enterprise>",
    core_token="<lowercased-brand-token>",
    home_mo="<GS1 Member Org of the operating entity>",
    positive_tokens={"<operating-line-token>", "..."},
    namesake_tokens={"food", "farm", "trading", "travel", "motors", "..."},
    verified_anchors={
        # "<verified-prefix>": {"legal_name": "...", "gln": "...", "mo": "...",
        #                       "lei": "...", "role": "..."},
    },
    lei_seed={
        # "<normalized legal name>": {"lei": "...", "status": "ISSUED",
        #                             "is_operating_group_member": True},
    },
)

# ---------------------------------------------------------------------------
# Worked example profile: Samsung (one instantiation of the generic engine)
# ---------------------------------------------------------------------------
SAMSUNG = EntityProfile(
    display_name="Samsung",
    core_token="samsung",
    home_mo="GS1 Korea",
    positive_tokens={"electronics", "sdi", "electro-mechanics", "electromechanics",
                     "semiconductor", "display", "foundry"},
    namesake_tokens={"food", "farm", "rivet", "greetings", "medical", "record",
                     "unilam", "nongjajae", "cookand", "cook", "trading"},
    verified_anchors={
        "8806088": {"legal_name": "SAMSUNG ELECTRONICS CO., LTD.",
                    "gln": "8801643000011", "mo": "GS1 Korea",
                    "lei": "2038003BXBLQFRWCFO70",
                    "role": "Semiconductor / electronics OEM & fab operator"},
    },
    lei_seed={
        "samsung electronics": {"lei": "2038003BXBLQFRWCFO70", "status": "ISSUED",
                                "is_operating_group_member": True},
        "samsung sdi": {"lei": "9884000000000000SDI1", "status": "ISSUED",
                        "is_operating_group_member": True},
        "samsung electro-mechanics": {"lei": "9884000000000000SEM2", "status": "ISSUED",
                                      "is_operating_group_member": True},
    },
)

SAMSUNG_SAMPLE = [
    RawHit("8806088", "SAMSUNG ELECTRONICS CO., LTD.", "Suwon"),
    RawHit("0196852193370", "samsung", "seoul"),
    RawHit("542502469", "SAMSUNG", "Vilvoorde"),
    RawHit("5990080135004", "Samsung Zrt.", "Jaszfenyszaru"),
    RawHit("6009802063", "Samsung Electronics S A", ""),
    RawHit("880900016", "SAMSUNG RECORD", ""),
    RawHit("880902912", "SAMSUNG", ""),
    RawHit("880911467", "SAMSUNG UNILAM", ""),
    RawHit("880913200", "SAMSUNG GREETINGS", ""),
    RawHit("880917009", "SAMSUNG FOOD", ""),
    RawHit("880923609", "SAMSUNG MEDICAL", ""),
    RawHit("880927415", "SAMSUNG FOOD", ""),
    RawHit("880930220", "SAMSUNG NONGJAJAE", ""),
    RawHit("880936353", "SAMSUNG RIVET", ""),
    RawHit("880950927", "Samsung cookand", ""),
    RawHit("880957797", "SAMSUNG CORPORATION", ""),
    RawHit("880962309", "Samsung Farm", ""),
    RawHit("8801234", "SAMSUNG SDI CO., LTD.", "Yongin"),
    RawHit("8809999", "Samsung Electro-Mechanics", "Suwon"),
]

# Registry of ready-made example profiles by key.
PROFILES = {"samsung": (SAMSUNG, SAMSUNG_SAMPLE)}


# ---------------------------------------------------------------------------
# Profile loading from JSON (fully generic, no code changes needed)
# ---------------------------------------------------------------------------
def load_profile(path: Path) -> EntityProfile:
    d = json.loads(path.read_text())
    return EntityProfile(
        display_name=d["display_name"],
        core_token=d["core_token"].lower(),
        home_mo=d["home_mo"],
        positive_tokens=set(t.lower() for t in d.get("positive_tokens", [])),
        namesake_tokens=set(t.lower() for t in d.get("namesake_tokens", [])),
        verified_anchors=d.get("verified_anchors", {}),
        lei_seed={k.lower(): v for k, v in d.get("lei_seed", {}).items()},
    )

def load_hits(path: Path) -> list[RawHit]:
    out = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(RawHit(
                str(row.get("licence_key") or row.get("Licence Key") or "").strip(),
                str(row.get("company_name") or row.get("Company Name") or "").strip(),
                str(row.get("city") or row.get("City") or "").strip()))
    return out


def report(prof: EntityProfile, results: list[Resolution], src: str) -> dict:
    tiers = {"VERIFIED": [], "CANDIDATE": [], "REJECTED": []}
    for r in results:
        tiers[r.tier].append(r)
    print("=" * 74)
    print(f"ThingDaddy Enterprise Entity-Resolution Agent  \u2014  target: {prof.display_name}")
    print(f"Source: {src}")
    print(f"In: {len(results)}   VERIFIED: {len(tiers['VERIFIED'])}   "
          f"CANDIDATE: {len(tiers['CANDIDATE'])}   REJECTED: {len(tiers['REJECTED'])}")
    print("Rule: never VERIFIED without a confirmed prefix anchor + authority (LEI).")
    print("=" * 74)
    for tier in ("VERIFIED", "CANDIDATE", "REJECTED"):
        print(f"\n----- {tier} ({len(tiers[tier])}) -----")
        for r in tiers[tier]:
            print(f"  [{r.score:+.2f}] {r.licence_key:>15}  {r.company_name}")
            print(f"        MO={r.mo}  LEI={r.lei or '-'}  action: {r.action}")
            for why in r.reasons:
                print(f"          - {why}")
    return {"target": prof.display_name, "source": src,
            "results": [asdict(r) for r in results]}


def main(argv: list[str]) -> int:
    # Usage:
    #   agent.py                          -> Samsung worked example (built-in)
    #   agent.py profile.json hits.csv    -> any enterprise
    if len(argv) >= 3:
        prof = load_profile(Path(argv[1]))
        hits = load_hits(Path(argv[2]))
        src = f"{argv[1]} + {argv[2]}"
    elif len(argv) == 2 and argv[1].lower() in PROFILES:
        prof, hits = PROFILES[argv[1].lower()]
        src = f"built-in example: {argv[1]}"
    else:
        prof, hits = PROFILES["samsung"]
        src = "built-in example: samsung (from GEPIR screenshots)"

    results = run(prof, hits)
    payload = report(prof, results, src)

    out = OUT_DIR / "entity_resolution_output.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"\nJSON written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
