#!/usr/bin/env python3
"""
w1_p3_afo_template.py -- the P3 AFO block, DERIVED FROM DISK EVIDENCE.

    python3 w1_p3_afo_template.py --self-test

Not derived from a model of what the estate should look like. Every grade and
every case below is read off what is actually in content_claim and in
diazyme_ferritin_p3.sql, and the gate is that it reproduces the Diazyme rows
that are already there.

WHAT THE DISK SAYS, and it is not what a fresh design would guess:

  The 16,976 rows in "Grounded methods — AFO-shaped, cited" are
      slot 16,968 · c 6 · e 2
  99.95% SLOT. The estate's honest P3 position is that almost nothing is
  grounded yet, and the template that runs 2,300 times must produce that
  shape, not a shape that looks fuller.

  Diazyme's own P3 rows grade the STRUCTURE 'b' -- BUILT:
      AFO model              Equipment · Material · Process    b   "built · AFO / BFO"
      Conformance verdict    CONFORMS / exception naming       b   "built"
      Workflow · Event       what it runs (AFO) + its log      b   "built"
      Issuance gate          no key against an unsourced field b   "built"
  and the ANALYTES 'c':
      Ferritin · DZ526A · Hitachi 917 · 560 nm · 37°C   gdti:...  c
      Homocysteine · DZ568B · enzyme cycling            gdti:...  c

  'b' IS THE POINT. The AFO upper structure -- af-p / af-e / af-r -- is OUR
  CONSTRUCTION over AFO's shape. It is built, not verified: no authority
  asserted it about this company, and no IRI is attached to it. Grading it 'v'
  would say an authority confirmed something nobody confirmed.

THE TWO AXES, and they are separated at EVERY level, not only the technique:
    domain_availability   a fact about ALLOTROPE  -- does AFO model this domain
    td_grounded           a fact about OUR RECORD -- have we attached anything
  A row is graded on td_grounded ALONE. domain_availability never raises a
  grade: AFO calling a domain "Public" is AFO's release status, not our
  evidence. That is the collapse Zeiss exposed and it recurs one level down --
  a structure row graded 'v' while its exact_iri is None is the same
  contradiction as "grade c with zero IRIs".

THREE CASES, by registry lookup, never a word match.
"""
import argparse, json, sys

AFO_PURL = "http://purl.allotrope.org/voc/afo"
AFO_ATTRIB = "Allotrope Foundation Ontologies (AFO) 2.1.2, CC-BY. Attribution required."
TD_EXT_NS = "https://thingdaddy.com/afo-ext"

# AFO maturity is DOMAIN AVAILABILITY ONLY. It is deliberately NOT a grade map:
# the previous template had {"Public": "v"}, which lets AFO's release status
# mint a verified ThingDaddy claim.
AFO_MATURITY = {"chromatography": "Public"}
AFO_CANDIDATE = {
    "injection","lc","lc-uv","uv","lc-ms","mass-spectrometry","gc","sfc","nmr","ir","raman",
    "optical-microscopy","qpcr","cell-counting","cell-culture","titration","ph",
    "electrochemistry","weighing","calibration","detection","filtration","mixing","sampling",
    "pumping","plumbing","dsc","tga","thermal-analysis","dvs","bet-analysis","bga",
    "bulk-density","coating","dosage-form","osmometry","particle-size-distribution",
    "turbidity","x-ray-diffraction","fingerprinting","pat","electric-engineering",
    "class-coordination",
}
AFO_UNMODELED = {
    "clinical-chemistry","immunoassay","photometric-clinical-chemistry","sequencing",
    "enzyme-assay","nephelometry","electrophoresis","flow-cytometry","spr",
    "surface-area-analysis",
}
# THE GRADE VOCABULARY, read off content_claim, not designed. It is also
# enforced: content_claim_grade_valid CHECKs grade IN (v,c,e,b,slot), so
# 'pending' is not merely absent, the database would reject it.
#     v 189,904 · slot 130,105 · c 25,989 · b 6,964 · e 1,927   (3 Sep, snapshot)
#
# CORRECTED 6 Sep. The first version of this file said "P3 v ZERO -- no P3 row
# in the estate has ever been graded 'v'". That was true when measured on
# 3 Sep and is now false: 31 P3 rows carry 'v', all written 3 Sep, all on
# Shimadzu 4151801 from 228-92358H / 228-92943 / 228-97524A. The corpus is
# live and every figure here is a snapshot, not a law.
#     P3 today: slot 23,923 · c 2,006 · e 145 · v 31 · b 9
#
# THE BEHAVIOUR DOES NOT CHANGE, because the reason was never the count. Those
# 31 are maker specifications read off a cited page -- "190 nm to 800 nm",
# "wavelength accuracy +/- 1 nm". An authority stated them, so 'v' is right.
# AFO STRUCTURE IS NOT THAT. af-p / af-e / af-r is OUR shape over AFO's,
# asserted by nobody, carrying no IRI. It is 'b'. The old justification
# ("nothing in P3 is ever verified") was too broad and would have been wrong
# even when the count supported it.
GRADES = {"v", "c", "e", "b", "slot"}

STRUCTURE = [("process","af-p","the method run"), ("equipment","af-e","the instrument"),
             ("result","af-r","the measured result"), ("material","af-m","sample or reagent")]


def classify(domain):
    """(case, domain_availability). NEITHER is a grade."""
    d = (domain or "").strip().lower()
    if d in AFO_MATURITY: return "modeled", "modeled·Public"
    if d in AFO_CANDIDATE: return "modeled", "modeled·Candidate"
    if d in AFO_UNMODELED: return "closed", "not-modeled"
    return "open", "no-module"


def grade_of(td_grounded, has_iri):
    """THE ONLY GRADE RULE. td_grounded alone; domain_availability never lifts it."""
    if td_grounded and has_iri: return "c"
    if td_grounded: return "c"
    return "slot"


def build_p3(company_key, prefix=None, technique=None, domain=None, instruments=None,
             method_doc_gdti=None, analytes=None, unfound=None, source=None):
    case, avail = classify(domain)
    analytes = analytes or []
    instruments = instruments or []
    td_grounded = bool(analytes)

    rows = []
    # STRUCTURE IS 'b' -- BUILT. Our construction over AFO's shape, no IRI attached.
    for name, ns, means in STRUCTURE:
        if name == "material" and not analytes:
            continue
        rows.append(dict(nm="AFO %s" % name, identifier="%s · %s" % (ns, means),
                         grade="b", axis_domain=avail, axis_grounded=False,
                         why="built · AFO upper shape. No IRI attached, so not 'v'."))
    # THE TECHNIQUE
    if case == "closed":
        for a in analytes:
            rows.append(dict(nm="%s · %s" % (a, technique),
                             identifier="%s/%s/%s/%s" % (TD_EXT_NS, prefix or "UNROOTED",
                                                         domain, str(a).lower().replace(" ", "-")),
                             grade="c", axis_domain=avail, axis_grounded=True,
                             why="AFO does not model %s. Company-scoped extension, "
                                 "NEVER a core af-p:AFP_xxxx." % domain))
    elif case == "modeled":
        rows.append(dict(nm="technique · %s" % technique, identifier=domain,
                         grade=grade_of(td_grounded, False), axis_domain=avail,
                         axis_grounded=td_grounded,
                         why="AFO models this domain (%s). %s" % (avail,
                             "IRIs attached." if td_grounded else
                             "NOTHING ATTACHED — a slot in OUR record, not a gap in AFO.")))
    else:
        rows.append(dict(nm="technique · %s" % technique, identifier="no AFO module",
                         grade="slot", axis_domain=avail, axis_grounded=False,
                         why="AFO 2.1.2 has no module for '%s'. A slot, not an exception." % domain))
    # THE ENSEMBLE
    for i in instruments:
        rows.append(dict(nm="equipment · %s" % i.get("name"), identifier=i.get("giai") or "UNROOTED",
                         grade="c" if i.get("giai") else "slot", axis_domain=avail,
                         axis_grounded=bool(i.get("giai")),
                         why=("delegates its command set to %s" % i["controlled_by"])
                             if i.get("controlled_by") else "no GIAI — nothing minted"))
    # 'e' -- EXCEPTION. A field that was LOOKED FOR and was not found. On disk:
    # "Unfound field / missing MSDS | lights as a gap | e". Distinct from 'slot',
    # which is a field nobody has reached yet. A slot is silence; an exception is
    # a NAMED miss, and collapsing the two would hide every search that failed.
    for f in (unfound or []):
        rows.append(dict(nm="Unfound field · %s" % f, identifier="lights as a gap",
                         grade="e", axis_domain=avail, axis_grounded=False,
                         why="looked for and not found. An exception, NOT a slot."))
    rows.append(dict(nm="score · method document", identifier=method_doc_gdti or "UNRESOLVED",
                     grade="c" if method_doc_gdti else "slot", axis_domain=avail,
                     axis_grounded=bool(method_doc_gdti),
                     why="a score you cannot cite is not a score"))
    return dict(company=company_key, prefix=prefix, case=case, domain_availability=avail,
                td_grounded=td_grounded, afo_version="2.1.2", afo_attribution=AFO_ATTRIB,
                rows=rows, source=source, state="CANDIDATE — nothing minted")


# THE GATE: reproduce the Diazyme rows that are ALREADY IN content_claim.
DIAZYME = dict(company_key="diazyme", prefix="0817089", technique="photometric clinical chemistry",
               domain="clinical-chemistry", analytes=["Ferritin", "Homocysteine"],
               method_doc_gdti="gdti:0817089.00002.1",
               instruments=[{"name": "DZ-Lite 3000 Plus", "giai": "urn:epc:id:giai:0817089.2"}],
               unfound=["missing MSDS"],
               source="diazyme_ferritin_p3.sql + content_claim")


def gate():
    r = build_p3(**DIAZYME)
    g = {x["grade"] for x in r["rows"]}
    struct = [x for x in r["rows"] if x["nm"].startswith("AFO ")]
    ana = [x for x in r["rows"] if "Ferritin" in x["nm"] or "Homocysteine" in x["nm"]]
    checks = [
        ("case is CLOSED — AFO does not model clinical chemistry", r["case"] == "closed"),
        ("structure rows exist and are graded 'b' (built), as on disk",
         bool(struct) and all(x["grade"] == "b" for x in struct)),
        ("NO structure row is graded 'v' -- that is the Zeiss collapse",
         not any(x["grade"] == "v" for x in struct)),
        ("both analytes present, graded 'c', as on disk", len(ana) == 2 and all(x["grade"] == "c" for x in ana)),
        ("every analyte IRI is company-scoped, never purl.allotrope.org",
         all(TD_EXT_NS in x["identifier"] and "purl.allotrope.org" not in x["identifier"] for x in ana)),
        # scoped to the AFO block, NOT an estate-wide claim -- 31 P3 rows
        # elsewhere are legitimately 'v' (maker specs on a cited page).
        ("no grade 'v' in the AFO block: none of it is authority-asserted",
         "v" not in g),
        ("the exception state 'e' is reachable -- a named miss, not a slot",
         any(x["grade"] == "e" for x in r["rows"])),
        ("every grade emitted is in the estate's vocabulary; no 'pending'",
         {x["grade"] for x in r["rows"]} <= GRADES),
        ("the two axes are separate fields on every row",
         all("axis_domain" in x and "axis_grounded" in x for x in r["rows"])),
        ("domain_availability never lifts a grade: closed domain, analytes still 'c'",
         r["domain_availability"] == "not-modeled" and all(x["grade"] == "c" for x in ana)),
    ]
    bad = 0
    for label, ok in checks:
        print("    %s  %s" % ("pass" if ok else "FAIL", label))
        if not ok: bad += 1
    print("\n  %d/%d pass." % (len(checks) - bad, len(checks)))
    return bad == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    print("=" * 72); print("  W1 P3 AFO TEMPLATE · DIAZYME EXEMPLAR GATE"); print("=" * 72)
    ok = gate()
    sys.exit(0 if ok else 1)
