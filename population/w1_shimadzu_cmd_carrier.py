#!/usr/bin/env python3
"""
w1_shimadzu_cmd_carrier.py -- the CMD, a column identity carrier that is
designed to be re-pointed at a different asset.

    python3 w1_shimadzu_cmd_carrier.py            # DRY
    python3 w1_shimadzu_cmd_carrier.py --apply

SOURCE
    228-97194D  Jan. 2026  "Shimadzu Liquid Chromatograph Nexera CL series
    System Guide", 302 pp, printed folio p.281 (PDF page 293 -- they differ
    by 12 in this document and by 8 in 228-97201B, which is why the folio is
    read off the bottom-margin block and never assumed).
    https://www.shimadzu.com/an/ivd/L/228-97194.pdf

WHY THIS IS P1 AND NOT P2. The CMD is not a driver. It is a carrier: a thing
that holds a column's identity and is read in the context of the column oven.
That is law 3 -- one identity, many carriers -- appearing in a vendor's own
manual. The CL line carries column identity on a rewritable CMD device; the
general line carries it on a 2D iCMP tag. Same identity, two carriers, and
neither is "the" trigger.

THE PART THAT MAKES IT INTERESTING, quoted from p.281:
    "At the end of the column service life, the CMD can be removed from the
     column, reinitialized, and reused attached to a new column."
A carrier the maker intends to be re-pointed at a different asset. The
identity is not in the device; the device is only where it is written. Read
the other way -- the carrier persists and the asset changes -- this is the
inverse of custody transfer, and a graph that treats a carrier read as an
identity would silently inherit the previous column's history.

WHAT IS NOT RESOLVED. p.281 quotes "P/N: 228-37281-41" with no S-prefix,
while the estate already records (P1/Doctrine) that 228-92943 is the DOCUMENT
number and S228-92943 the saleable part. Both are observed; neither is
guessed into the other. The row is written as an exception naming the
conflict, not normalised to whichever form looks tidier.
"""
import os, subprocess, sys

STAGE = os.environ.get("STAGE_DB", "thingdaddy_run")
PARTY = "4151801"
DOC   = "228-97194D"
CITE  = "228-97194D Jan. 2026 Nexera CL series System Guide p.281"
APPLY = "--apply" in sys.argv
BAR   = "=" * 78
NOKEY = "key_type=none (minted=NO; key_value empty)"
SGTIN = "key_type=SGTIN (minted=NO; key_value empty)"

# (section, nm, grade, tx)
ROWS = [
 ("Consumables", "CMD · column identity carrier", "v",
  "The column management device (CMD) (P/N: 228-37281-41) \"is used to remember "
  "information about columns\" and connects \"to the computer workstation "
  "database via the column oven\". One CMD is required per column. | " + NOKEY),
 ("Consumables", "CMD · carrier_reuse", "v",
  "\"At the end of the column service life, the CMD can be removed from the "
  "column, reinitialized, and reused attached to a new column.\" A carrier the "
  "maker intends to be RE-POINTED at a different asset — the identity is not "
  "in the device. | " + NOKEY),
 ("Compatibility", "CMD · temperature_limit", "v",
  "\"CMD cannot be used at temperature settings above 85 ℃.\" The carrier is "
  "unreadable in exactly the oven conditions the column is rated for. | " + NOKEY),
 ("Parts", "CMD · af-m component_part", "slot",
  "CMD cable, 150 mm — 228-39991 | " + SGTIN),
 ("Parts", "CMD · af-m component_part", "slot",
  "CMD cable, 400 mm — 228-39991-01; required to connect a column 100 mm or "
  "shorter | " + SGTIN),
 ("Doctrine", "CMD · saleable_number_unresolved", "e",
  "p.281 quotes \"P/N: 228-37281-41\" with NO S-prefix, while this party's own "
  "doctrine row records 228-92943 as the DOCUMENT number and S228-92943 as the "
  "saleable part. Both observed. Neither guessed into the other; resolving it "
  "needs a price list, not an inference."),
 ("Doctrine", "Column identity · two carriers", "v",
  "One column identity, two carriers: a rewritable CMD device on the CL line "
  "(228-97194D p.281) and a 2D iCMP tag on the general line. Neither is \"the\" "
  "trigger. A graph that treats a carrier read AS the identity would inherit "
  "the previous column's history the first time a CMD is reinitialized. | " + NOKEY),
]


def q(sql):
    return subprocess.check_output(["psql", "-Atd", STAGE, "-c", sql], text=True)


def lit(s):
    return "'" + s.replace("'", "''") + "'"


def main():
    print(BAR); print("  SHIMADZU %s · P1 CMD CARRIER TIER — %s"
                      % (PARTY, "APPLY" if APPLY else "DRY RUN")); print(BAR)
    print("  source   %s\n" % CITE)

    nxt, new, skip = {}, [], 0
    for section, nm, grade, tx in ROWS:
        if section not in nxt:
            nxt[section] = int(q("select coalesce(max(display_order),-1)+1 from "
                                 "content_claim where party_id=%s and pillar='P1' "
                                 "and section='%s'" % (PARTY, section)).strip() or 0)
        # nm repeats inside Parts by convention, so dedupe on (section, nm, tx)
        dup = q("select count(*) from content_claim where party_id=%s and "
                "pillar='P1' and section=%s and nm=%s and tx=%s"
                % (PARTY, lit(section), lit(nm), lit(tx))).strip()
        if dup != "0":
            skip += 1; print("    skip (present)  %-13s %s" % (section, nm)); continue
        new.append((section, nxt[section], nm, grade, tx)); nxt[section] += 1
        print("    %-4s %-13s %-38s" % (grade, section, nm[:38]))
    print("\n  new %d · already present %d" % (len(new), skip))
    if not APPLY:
        print("\n  DRY RUN. Nothing written. Pass --apply."); return
    if not new:
        print("\n  Nothing to write."); return

    vals = ",".join("(%s,'P1',%s,%d,%s,NULL,%s,%s,%s)"
                    % (PARTY, lit(s), o, lit(nm), lit(g), lit(tx), lit(DOC))
                    for s, o, nm, g, tx in new)
    p = subprocess.run(["psql", "-v", "ON_ERROR_STOP=1", "-d", STAGE, "-c",
                        "begin;\ninsert into content_claim (party_id,pillar,section,"
                        "display_order,nm,identifier,grade,tx,doc_key) values %s;\n"
                        "commit;" % vals], capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr.strip()); raise SystemExit("REFUSED: rolled back.")
    print("\n  WROTE %d rows." % len(new))
    print("  P1 now %s rows."
          % q("select count(*) from content_claim where party_id=%s and pillar='P1'"
              % PARTY).strip())


if __name__ == "__main__":
    main()
