#!/usr/bin/env python3
"""
insert_safety.py — insert-miner, slice 2: the SAFETY binding set.

Builds on section_grammar.py (slice 1 — regime detection). It does NOT reimplement
regime detection and does NOT modify section_grammar.py. After the regime is detected,
this lifts the SAFETY members the spec (insert_miner_spec.html §3) defines into a
first-class binding set:

  - allergens[]          parsed from the "Contains:" statement, mapped to the US big-9
  - adverse_reactions[]  from an "Adverse Reactions" / "Undesirable effects" section
  - contraindications[]  from a "Contraindications" section
  - interactions[]       from "Drug Interactions" / "Interactions" — emitted as EDGES

Registrar-strict (spec §3–4, §9). Everything is CANDIDATE:
  * No MedDRA code, no GDTI, no allergen code is ever fabricated (candidate:true, code:null).
  * An Rx PI with an EMPTY SAFETY set is INCOMPLETE (shape_safety_binding_present).
  * A free-text allergen off the big-9 stays CANDIDATE, never ratified (shape_allergen_controlled).
  * No medical interpretation — structure only.

Pure stdlib, no network. Contract: insert_miner_spec.html (same folder).

Usage (mirrors section_grammar.py):
  python3 insert_safety.py                 # runs the built-in SAMPLES, one binding set each
  python3 insert_safety.py --file label.txt
  echo "<label text>" | python3 insert_safety.py -
"""
from __future__ import annotations
import argparse, json, re, sys

# Reuse slice 1 — never reimplement regime detection.
from section_grammar import detect_regime, SAMPLES

# detect_regime() labels the Rx regime "Rx Prescribing Information (US PLR)".
RX_REGIME_PREFIX = "Rx Prescribing Information"


# --- US big-9 controlled allergen vocabulary (FASTER Act / 21 CFR) -------------
# Canonical member -> synonym patterns. A "Contains:" token that matches any pattern
# is a CANDIDATE mapped to that big-9 member; anything off-list stays free-text
# CANDIDATE (mapped_to=None). We never emit an allergen *code* — mapping only.
BIG9 = {
    "milk":        [r"milk", r"dairy", r"casein", r"whey", r"lactose", r"butter", r"cream", r"cheese"],
    "egg":         [r"eggs?", r"albumin", r"ovalbumin"],
    "fish":        [r"fish", r"anchov(?:y|ies)", r"\bcod\b", r"salmon", r"tuna", r"tilapia", r"pollock"],
    "crustacean shellfish": [r"crustacean", r"shellfish", r"shrimp", r"prawns?", r"crab",
                             r"lobster", r"crayfish", r"langoustine"],
    "tree nuts":   [r"tree ?nuts?", r"almonds?", r"walnuts?", r"cashews?", r"pecans?", r"pistachios?",
                    r"hazelnuts?", r"macadamias?", r"brazil ?nuts?", r"pine ?nuts?", r"chestnuts?"],
    "peanuts":     [r"peanuts?", r"groundnuts?", r"arachis"],
    "wheat":       [r"wheat", r"gluten", r"spelt", r"farro", r"semolina", r"durum"],
    "soybeans":    [r"soybeans?", r"\bsoya?\b", r"edamame", r"tofu"],
    "sesame":      [r"sesame", r"tahini", r"benne"],
}


def _map_allergen(token):
    """Map a free-text allergen token to a US big-9 member, or None (off-list)."""
    t = token.strip().lower()
    for member, pats in BIG9.items():
        if any(re.search(p, t) for p in pats):
            return member
    return None


# --- section-body extraction --------------------------------------------------
# Known insert section headings across regimes. A heading only counts when it is
# followed by a colon — this distinguishes a real heading ("CONTRAINDICATIONS:")
# from a mention in prose ("...Drug Interactions section shown."). An optional
# leading section number is allowed (PLR "6 ADVERSE REACTIONS", SmPC "4.8"). The
# same list serves as section BOUNDARIES (where one section body ends).
_HEADINGS = [
    r"indications?\s+and\s+usage", r"therapeutic indications?", r"\buses?\b", r"\bpurpose\b",
    r"active ingredients?", r"dosage\s+and\s+administration", r"dosage forms?\s+and\s+strengths?",
    r"\bdirections?\b", r"contraindications?", r"warnings?\s+and\s+precautions?", r"\bwarnings?\b",
    r"adverse\s+reactions?", r"undesirable effects?", r"drug\s+interactions?",
    r"interactions?\s+with\s+other\s+medicinal\s+products?", r"\binteractions?\b",
    r"use\s+in\s+specific\s+populations?", r"how\s+supplied", r"storage\s+and\s+handling",
    r"other\s+information", r"inactive\s+ingredients?", r"other\s+ingredients?", r"\boverdos\w*",
    r"description", r"clinical pharmacology", r"mechanism of action", r"drug abuse and dependence",
    r"nonclinical toxicology", r"patient counseling", r"supplement facts", r"serving size",
    r"amount per serving", r"servings?\s+per\s+container",
]
_NUM = r"(?:\d+(?:\.\d+)*\s+)?"                       # optional leading section number
_HEAD = r"(?:^|[\s.;)])" + _NUM + r"(?:{})\s*:"       # a heading == ...HEADING:
_BOUNDARY = re.compile(_HEAD.format("|".join(_HEADINGS)), re.I)


def _section_body(text, heading_pats):
    """Return the body under the first colon-delimited `heading_pats` match, up to
    the next section heading (or end). None if the heading is not present as a
    colon-delimited section — so a prose mention never yields a phantom section."""
    head_re = re.compile(_HEAD.format("|".join(heading_pats)), re.I)
    m = head_re.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nb = _BOUNDARY.search(rest)
    return (rest[:nb.start()] if nb else rest).strip()


def _terms(body):
    """Split a section body into candidate member terms (delimiter-based).

    TODO(slice-3): this split is coarse. Parenthetical asides (PLR frequencies like
    "(>=5%)", editorial notes) are DROPPED here rather than treated as terms, and
    proper clause/NLP-level term isolation + MedDRA mapping is a later slice. Every
    fragment stays CANDIDATE with no code, so nothing is fabricated — but term
    granularity from free prose is best-effort until the docmine section splitter
    (spec sec.7) feeds pre-segmented bodies.
    """
    if not body:
        return []
    body = re.sub(r"\([^)]*\)", " ", body)           # drop parenthetical asides
    out, seen = [], set()
    for p in re.split(r"[;,.•\n]|\band\b", body, flags=re.I):
        t = p.strip().strip("()[]-–—:").strip()
        if len(t) >= 2 and re.search(r"[a-z]", t, re.I) and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


# --- SAFETY members -----------------------------------------------------------
def _allergens(text):
    """Parse every 'Contains:' statement -> big-9 candidates; off-list = free-text candidate."""
    out = []
    for m in re.finditer(r"\bcontains?\s*:\s*(.+)", text, re.I):
        line = re.split(r"[.\n]", m.group(1), 1)[0]          # the "Contains:" line only
        for tok in re.split(r"[;,]|\band\b", line, flags=re.I):
            tok = tok.strip().strip(".-").strip()   # keep balanced parens, e.g. "Tree Nuts (Almonds)"
            if not tok or not re.search(r"[a-z]", tok, re.I):
                continue
            mapped = _map_allergen(tok)
            out.append({
                "token": tok,
                "mapped_to": mapped,                         # big-9 member, or None (free-text)
                "controlled": mapped is not None,            # shape_allergen_controlled
                "candidate": True,
                "status": "candidate",                       # free-text never ratified here
            })
    return out


def _adverse_reactions(text):
    body = _section_body(text, [r"adverse\s+reactions?", r"undesirable effects?"])
    # candidate -> MedDRA, but NEVER a real code (code=None, candidate=True).
    return [{"term": t, "coding_system": "MedDRA", "code": None,
             "candidate": True, "status": "candidate"} for t in _terms(body)]


def _contraindications(text):
    body = _section_body(text, [r"contraindications?"])
    return [{"term": t, "candidate": True, "status": "candidate"} for t in _terms(body)]


def _interactions(text):
    body = _section_body(text, [r"drug\s+interactions?",
                                r"interactions?\s+with\s+other\s+medicinal\s+products?",
                                r"\binteractions?\b"])
    # Each interaction is an EDGE (spec sec.3): subject_gtin is bound at ingest (null here),
    # object_substance is the interacting substance text. candidate identity, never resolved.
    return [{"subject_gtin": None, "object_substance": t, "candidate": True, "status": "candidate"}
            for t in _terms(body)]


# --- the SAFETY binding set (spec sec.6 output record) ------------------------
def safety_binding_set(text):
    text = text or ""
    regime = detect_regime(text)                             # slice 1 — reused
    regime_name = regime.get("regime")

    members = {
        "adverse_reactions": _adverse_reactions(text),
        "contraindications": _contraindications(text),
        "allergens":         _allergens(text),
        "interactions":      _interactions(text),
    }
    empty = not any(members.values())
    is_rx = bool(regime_name) and regime_name.startswith(RX_REGIME_PREFIX)

    reasons = []
    if is_rx and empty:                                      # shape_safety_binding_present
        reasons.append("Rx PI has an empty SAFETY set (shape_safety_binding_present)")

    # Exactly the spec's binding_set record (type + the four member lists), plus the
    # registrar-strict annotations: regime, an overall candidate status, and the
    # conformance flag that carries the INCOMPLETE mark.
    return {
        "type": "SAFETY",
        "regime": regime_name,
        "status": "candidate",                              # the whole set — never ratified here
        "adverse_reactions": members["adverse_reactions"],
        "contraindications": members["contraindications"],
        "allergens": members["allergens"],
        "interactions": members["interactions"],
        "conformance": {
            "complete": not reasons,
            "flag": "INCOMPLETE" if reasons else "OK",
            "reasons": reasons,
        },
    }


# --- CLI (mirrors section_grammar.py) -----------------------------------------
def _emit(name, text):
    print(f"── {name}")
    print(json.dumps(safety_binding_set(text), indent=2))
    print()


def main():
    ap = argparse.ArgumentParser(
        description="Insert-miner slice 2 — the SAFETY binding set (candidate-until-ratified)")
    ap.add_argument("input", nargs="?", help="path to a label text file, or '-' for stdin")
    ap.add_argument("--file")
    a = ap.parse_args()
    src = a.file or a.input
    if src == "-":
        print(json.dumps(safety_binding_set(sys.stdin.read()), indent=2))
    elif src:
        with open(src, encoding="utf-8", errors="replace") as f:
            print(json.dumps(safety_binding_set(f.read()), indent=2))
    else:
        for name, s in SAMPLES.items():
            _emit(name, s)


if __name__ == "__main__":
    main()
