#!/usr/bin/env python3
"""
section_grammar.py — insert-miner, slice 1: REGIME DETECTION.

Given the plain text of a package insert / label, decide which labeling regime it follows
(Rx Prescribing Information | OTC Drug Facts | EU SmPC | Supplement Facts) and report which
of that regime's REQUIRED sections are present vs missing. Registrar-strict: a regime whose
required sections are incomplete is INCOMPLETE (flagged, not issuable).

This is detection + presence only. It does NOT mint a GDTI, extract section bodies, build
SHACL shapes, or interpret content — those are later slices of spec_insert_miner.md.

Pure stdlib, no network. Usage:
  python3 section_grammar.py                 # runs the built-in samples
  python3 section_grammar.py --file label.txt
  echo "<label text>" | python3 section_grammar.py -
"""
from __future__ import annotations
import argparse, json, re, sys

# Each regime: strong SIGNATURE markers (highly discriminating) + the REQUIRED sections
# (label -> list of alt regex patterns, case-insensitive, matched anywhere in the text).
REGIMES = {
    "Supplement Facts (DSHEA / 21 CFR 101.36)": {
        "signature": [r"supplement facts",
                      r"not been evaluated by the (food and drug administration|fda)"],
        "required": {
            "Supplement Facts panel": [r"supplement facts"],
            "Serving Size": [r"serving size"],
            "Servings Per Container": [r"servings?\s+per\s+container"],
            "Amount Per Serving": [r"amount\s+per\s+serving"],
            "% Daily Value": [r"%\s*daily value", r"\bdaily value\b", r"%\s*dv\b"],
            "Other Ingredients": [r"other\s+ingredients?"],
            "Allergen 'Contains'": [r"\bcontains?\s*:"],
            "DSHEA disclaimer": [r"not been evaluated by the (food and drug administration|fda)"],
        }},
    "OTC Drug Facts (21 CFR 201.66)": {
        "signature": [r"drug facts"],
        "required": {
            "Active ingredient(s)": [r"active ingredient"],
            "Purpose": [r"\bpurpose\b"],
            "Uses": [r"\buses?\b"],
            "Warnings": [r"\bwarnings?\b"],
            "Directions": [r"\bdirections?\b"],
            "Other information": [r"other\s+information"],
            "Inactive ingredients": [r"inactive\s+ingredients?"],
        }},
    "Rx Prescribing Information (US PLR)": {
        "signature": [r"highlights of prescribing information", r"full prescribing information",
                      r"prescribing information"],
        "required": {
            "Indications and Usage": [r"indications?\s+and\s+usage"],
            "Dosage and Administration": [r"dosage\s+and\s+administration"],
            "Dosage Forms and Strengths": [r"dosage forms?\s+and\s+strengths?"],
            "Contraindications": [r"contraindications?"],
            "Warnings and Precautions": [r"warnings?\s+and\s+precautions?"],
            "Adverse Reactions": [r"adverse\s+reactions?"],
            "Drug Interactions": [r"drug\s+interactions?"],
            "Use in Specific Populations": [r"use\s+in\s+specific\s+populations?"],
            "How Supplied / Storage": [r"how\s+supplied", r"storage\s+and\s+handling"],
        }},
    "EU SmPC (QRD template)": {
        "signature": [r"summary of product characteristics", r"\bsmpc\b"],
        "required": {
            "4.1 Therapeutic indications": [r"4\.1\s+therapeutic indications", r"therapeutic indications"],
            "4.3 Contraindications": [r"4\.3\s+contraindications", r"contraindications"],
            "4.5 Interactions": [r"4\.5\s+interaction", r"interaction with other medicinal"],
            "4.8 Undesirable effects": [r"4\.8\s+undesirable effects", r"undesirable effects"],
            "4.9 Overdose": [r"4\.9\s+overdose", r"\boverdose\b"],
        }},
}

def _present(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)

def detect_regime(text):
    """Score each regime; return the best one with present/missing required sections."""
    text = text or ""
    scored = []
    for regime, spec in REGIMES.items():
        sig = sum(1 for p in spec["signature"] if re.search(p, text, re.I))
        present = [name for name, pats in spec["required"].items() if _present(text, pats)]
        missing = [name for name in spec["required"] if name not in present]
        # signature markers are strong discriminators (x3); required-section hits break ties
        score = sig * 3 + len(present)
        scored.append({"regime": regime, "signature_hits": sig, "score": score,
                       "present": present, "missing": missing,
                       "required_total": len(spec["required"])})
    scored.sort(key=lambda r: r["score"], reverse=True)
    best = scored[0]
    if best["score"] == 0:
        return {"regime": None, "confidence": "none",
                "note": "no labeling-regime markers found — not an insert/label, or unrecognized regime.",
                "present": [], "missing": [], "issuable": False, "runners_up": []}
    issuable = not best["missing"]
    conf = "high" if best["signature_hits"] else ("medium" if best["score"] >= 3 else "low")
    return {
        "regime": best["regime"], "confidence": conf,
        "signature_hits": best["signature_hits"],
        "present": best["present"], "missing": best["missing"],
        "required_total": best["required_total"],
        "issuable": issuable,
        "status": "ISSUABLE (all required sections present)" if issuable
                  else f"INCOMPLETE — missing {len(best['missing'])} required section(s)",
        "runners_up": [{"regime": r["regime"], "score": r["score"]} for r in scored[1:] if r["score"] > 0][:2],
    }

# --- built-in samples so `python3 section_grammar.py` shows it working ---------
SAMPLES = {
    "NOW Foods — Vitamin D-3 (Supplement Facts)": """
        Vitamin D-3 5,000 IU. Supplement Facts. Serving Size: 1 Softgel. Servings Per Container: 240.
        Amount Per Serving: Vitamin D-3 (as Cholecalciferol) 125 mcg (5,000 IU) 625% Daily Value.
        Other Ingredients: Extra Virgin Olive Oil, Softgel Capsule (bovine gelatin, glycerin, water).
        Contains: Fish. These statements have not been evaluated by the Food and Drug Administration.
        This product is not intended to diagnose, treat, cure or prevent any disease.
    """,
    "Generic OTC pain reliever (Drug Facts)": """
        Drug Facts. Active ingredient (in each tablet): Ibuprofen 200 mg. Purpose: Pain reliever/fever reducer.
        Uses: temporarily relieves minor aches and pains. Warnings: Allergy alert. Do not use if you have ever had
        an allergic reaction to any other pain reliever. Directions: adults take 1 tablet every 4 to 6 hours.
        Other information: store at 20-25 C. Inactive ingredients: colloidal silicon dioxide, corn starch.
    """,
    "Rx product — partial PI (INCOMPLETE on purpose)": """
        HIGHLIGHTS OF PRESCRIBING INFORMATION. INDICATIONS AND USAGE: treatment of X.
        DOSAGE AND ADMINISTRATION: 10 mg once daily. CONTRAINDICATIONS: known hypersensitivity.
        ADVERSE REACTIONS: headache, nausea. (No Warnings and Precautions or Drug Interactions section shown.)
    """,
}

def _report(name, text):
    r = detect_regime(text)
    print(f"── {name}")
    if not r["regime"]:
        print(f"   regime: (none) — {r['note']}\n")
        return
    print(f"   regime     : {r['regime']}   [confidence: {r['confidence']}]")
    print(f"   status     : {r['status']}")
    print(f"   present    : {len(r['present'])}/{r['required_total']} — {', '.join(r['present'])}")
    if r["missing"]:
        print(f"   MISSING    : {', '.join(r['missing'])}")
    if r["runners_up"]:
        ru = ", ".join(x["regime"].split(" (")[0] + "=" + str(x["score"]) for x in r["runners_up"])
        print(f"   (runners-up: {ru})")
    print()

def main():
    ap = argparse.ArgumentParser(description="Insert-miner slice 1 — detect labeling regime + required-section presence")
    ap.add_argument("input", nargs="?", help="path to a label text file, or '-' for stdin")
    ap.add_argument("--file")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of the readout")
    a = ap.parse_args()
    src = a.file or a.input
    if src == "-":
        text = sys.stdin.read()
    elif src:
        with open(src, encoding="utf-8", errors="replace") as f: text = f.read()
    else:
        for name, s in SAMPLES.items(): _report(name, s)
        return
    if a.json:
        print(json.dumps(detect_regime(text), indent=2))
    else:
        _report(src, text)

if __name__ == "__main__":
    main()
