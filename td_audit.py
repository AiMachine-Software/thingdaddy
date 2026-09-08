#!/usr/bin/env python3
"""
td_audit.py — the register audits itself, agent-first.

    python3 td_audit.py                     human view
    python3 td_audit.py --json              THE RECORD. Machine-first.
    python3 td_audit.py --save              write a dated record to audits/
    python3 td_audit.py --compare           this run against the last saved one
    python3 td_audit.py --section C --samples 10 --quiet

READ ONLY. Every statement runs inside a read-only transaction. This tool
cannot write to any register, cannot promote and cannot repair. It reports.

──────────────────────────────────────────────────────────────────────────────
TWO LAYERS, AND THE SECOND IS THE POINT

  LAYER 1  THE DATA'S PROVENANCE
           where each value came from, and whether it holds up.

  LAYER 2  THE REGISTER'S OWN PROVENANCE
           WHY EACH RULE EXISTS, WHEN IT WAS MADE, AND WHAT OBSERVATION
           FORCED IT. Every check below carries `since` and `because`.

           A register that cannot say why its own rules exist is asking to be
           taken on faith. This one can name the day, the finding, and the
           ruling — and --compare shows whether it is getting better.

THE RULE EVERY CHECK OBEYS
  A CHECK MUST BE ABLE TO RETURN ITS OWN FAILURE. Each reports CHECKED as
  well as FOUND. A check that examined zero rows is NOT a pass — it never
  fired, and "0 found" and "0 examined" look identical on a screen while
  meaning opposite things.

WHAT THIS AUDIT CANNOT DO, STATED IN ITS OWN OUTPUT
  It proves the register is INTERNALLY CONSISTENT. It does not prove any
  value is CORRECT. A register can be perfectly self-consistent and entirely
  fabricated. See `cannot_check` in the record.

EXIT  0 clean · 1 findings · 2 could not run
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"; CYA="\033[36m"

PROD = os.environ.get("PROD_DB", "thingdaddy_population")
RUN  = os.environ.get("RUN_DB",  "thingdaddy_run")
HARVEST = os.environ.get("HARVEST_DB", "thingdaddy_harvest")   # DB1 — the cuts live here
AUDIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audits")
RECORD = "thingdaddy.audit.v1"


def psql(db, sql):
    p = subprocess.run(
        ["psql", "-qAt", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-d", db, "-f", "-"],
        input="SET default_transaction_read_only = on;\n" + sql,
        capture_output=True, text=True, timeout=900)
    if p.returncode:
        err = (p.stderr or "").strip().splitlines()
        return None, (err[-1] if err else "unknown error")
    return [l.split("\t") for l in p.stdout.split("\n") if l], None


# ═══ THE CHECKS ══════════════════════════════════════════════════════════════
# since   — the date the rule was ratified
# because — THE OBSERVATION THAT FORCED IT. This is the register's own
#           provenance: not "we have a rule" but "we have this rule because on
#           this day the data did this."
CHECKS = [

dict(id="A1", sec="A", db=PROD, title="NOT VALID constraints",
     rule="A NOT VALID constraint is a gate that has never been asked about the data it guards. "
          "IT DOES NOT JUST SKIP THE CHECK — IT CONCEALS A POPULATION. The rows read fine and "
          "pass every SELECT, until the first write reveals they never conformed.",
     where="GATE_REGISTER.md §0 · tape 2026-09-05", since="2026-09-03",
     because="W6 enumerated 254 CHECK constraints and reported NOT VALID: ZERO. Three now exist, "
             "added after that survey. On 5 September one of them — node_urn_epc_valid — refused "
             "a no-op UPDATE on a row that had been invalid since 23 July, and 976 of the "
             "spine's 1,127 EPC URNs turned out to be in the same state. See A4.",
     count="SELECT (SELECT count(*) FROM pg_constraint WHERE contype='c')::text, "
           "count(*)::text FROM pg_constraint WHERE contype='c' AND NOT convalidated;",
     sample="SELECT conrelid::regclass::text, conname, "
            "'UNVALIDATED — run the table''s own check to see what it hides' "
            "FROM pg_constraint WHERE contype='c' AND NOT convalidated LIMIT %(n)s;"),

dict(id="A4", sec="A", db=PROD, title="the frozen spine — rows that would fail an unvalidated gate",
     rule="node_urn_epc_valid is NOT VALID, so it never checked the existing rows — AND IT "
          "ENFORCES ON EVERY WRITE. A row that fails it cannot be updated at all: not its state, "
          "not its prefix, not even last_updated. THE ROW IS READ-ONLY AND NOTHING SAYS SO.",
     where="tape 2026-09-05", since="2026-09-05",
     because="The Diazyme re-root was refused by a no-op update on node 90799. The URN is "
             "urn:epc:id:sgtin:00817089020016 — A GTIN-14 WEARING A SERIALISED SCHEME NAME, with "
             "no dots and no serial anywhere. That is the 974-row defect ruled on 7 August: "
             "'the SCHEME is wrong, not the type. Fix at the producer, never the engine.' "
             "Unfixed, and invisible until something tried to write.",
     note="EVERY ROW COUNTED HERE IS FROZEN. No correction can reach it until the scheme is "
          "fixed at the producer.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE NOT epc_urn_valid(urn))::text "
           "FROM node WHERE urn IS NOT NULL AND left(urn,11)='urn:epc:id:';",
     sample="SELECT id::text, key_type, urn, coalesce(prefix,'—') FROM node "
            "WHERE urn IS NOT NULL AND left(urn,11)='urn:epc:id:' "
            "AND NOT epc_urn_valid(urn) LIMIT %(n)s;"),

dict(id="A2", sec="A", db=PROD, title="root_method is unrecordable in production",
     rule="Staging makes a prefix without a method impossible (cp_prefix_needs_method). "
          "Production has no such column, so HOW a prefix was rooted is unrecordable.",
     where="tape 2026-09-04 §B.1", since="2026-09-05",
     because="Item 3 asked which path rooted 53,995 parties. The answer was: unanswerable by "
             "construction. The column that would say was never there.",
     count="SELECT (SELECT count(*) FROM party WHERE prefix IS NOT NULL)::text, "
           "CASE WHEN EXISTS (SELECT 1 FROM information_schema.columns "
           "WHERE table_name='party' AND column_name='root_method') THEN '0' "
           "ELSE (SELECT count(*) FROM party WHERE prefix IS NOT NULL)::text END;",
     sample=None),

dict(id="A3", sec="A", db=PROD, title="a CHECK that passes on NULL",
     rule="content_claim_grade_valid is `grade = ANY(...)`, and a CHECK PASSES ON NULL. "
          "The constraint reads as enforced and is not.",
     where="stage_to_production.py, 30 Aug", since="2026-08-30",
     because="Production would have accepted 13,736 ungraded rows. stage_to_production refuses "
             "them on the RULE rather than the constraint: a constraint that cannot see NULL "
             "is not permission.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE grade IS NULL)::text FROM content_claim;",
     sample="SELECT id::text, pillar, nm, coalesce(left(tx,60),'—') FROM content_claim "
            "WHERE grade IS NULL LIMIT %(n)s;"),

dict(id="B1", sec="B", db=PROD, title="verified on a retired or seeded source",
     rule="GEPIR was retired 31 December 2023. A row whose source is 'seed' was attested by "
          "nobody. Neither can carry a verified grade.",
     where="canon §3 · tape 2026-09-05", since="2026-09-05",
     because="The verified set was 8 seed rows and ~62 gepir rows, while 21,397 "
             "regulator-attested GUDID rows sat at candidate. KJ: 'that number is way wrong'.",
     count="SELECT (SELECT count(*) FROM party WHERE state='verified')::text, count(*)::text "
           "FROM party WHERE state='verified' AND (source LIKE 'gepir%' OR source='seed');",
     sample="SELECT prefix, legal_name, source, coalesce(verified_at::text,'—') FROM party "
            "WHERE state='verified' AND (source LIKE 'gepir%' OR source='seed') LIMIT %(n)s;"),

dict(id="B2", sec="B", db=PROD, title="the attestation inversion",
     rule="A GUDID filing attests the DI and the labeler together under 21 CFR 830. TWO "
          "AUTHORITIES AGREEING — the issuing agency delegated the space, the regulator "
          "attested the filing, and neither can produce the other's half.",
     where="KJ ruling 2026-08-30", since="2026-08-30",
     because="It is stronger evidence than a hand-read, which is one person reading one screen. "
             "The grading never followed the ruling.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE state <> 'verified')::text "
           "FROM party WHERE source='GUDID' AND prefix IS NOT NULL;",
     sample="SELECT prefix, legal_name, state FROM party WHERE source='GUDID' "
            "AND prefix IS NOT NULL AND state<>'verified' LIMIT %(n)s;"),

dict(id="B3", sec="B", db=PROD, title="rooted on a pooled feed",
     rule="GDSN IS NOT ATTESTED — a pooled feed is not a filing.",
     where="ruling 2026-09-03", since="2026-09-03",
     because="53,926 of 54,133 rooted rows came from GDSN, and 138 from the regulator. "
             "99.6% of the spine rests on the source the ruling says is not a filing.",
     count="SELECT (SELECT count(*) FROM party WHERE prefix IS NOT NULL)::text, count(*)::text "
           "FROM party WHERE prefix IS NOT NULL AND source='GDSN';",
     sample="SELECT prefix, legal_name, state FROM party WHERE prefix IS NOT NULL "
            "AND source='GDSN' LIMIT %(n)s;"),

dict(id="B4", sec="B", db=HARVEST, title="a rooted GUDID prefix with no cut row in DB1",
     rule="EVERY ROOTED GUDID PREFIX IN PRODUCTION WAS CUT SOMEWHERE, AND DB1 KEEPS THE CUT: "
          "one gudid_company_prefix row per (duns, prefix), root_method and source_di both NOT "
          "NULL. A production prefix with no such row is a root nobody can re-derive.",
     where="td_audit B4 · 2026-09-06", since="2026-09-06",
     because="This audit's own cannot_check said the agency and the DI of a cut were not stored. "
             "They are — in DB1, per device and per cut. What never crossed is the agency, and "
             "most of the DIs. First run: 138 rooted GUDID prefixes in production, 137 with a "
             "DB1 cut row, 1 without — 0817089, Diazyme's hand-read seven digits.",
     note="CROSS-DATABASE. The prefixes are read from production and looked up in DB1. "
          "checked = rooted GUDID prefixes in production · found = those with no DB1 row "
          "carrying root_method and source_di.",
     feed=dict(db=PROD, sql="SELECT DISTINCT prefix FROM party WHERE source='GUDID' "
                            "AND prefix IS NOT NULL ORDER BY 1;"),
     count="WITH p(prefix) AS (VALUES %(feed)s), "
           "j AS (SELECT p.prefix, EXISTS (SELECT 1 FROM gudid_company_prefix g WHERE "
           "g.prefix=p.prefix AND g.root_method IS NOT NULL AND g.source_di IS NOT NULL) AS cut "
           "FROM p) "
           "SELECT count(*)::text, count(*) FILTER (WHERE NOT cut)::text, "
           "'with a DB1 cut row: '||count(*) FILTER (WHERE cut)||' · without: '||"
           "count(*) FILTER (WHERE NOT cut) FROM j;",
     sample="WITH p(prefix) AS (VALUES %(feed)s) SELECT p.prefix, "
            "(SELECT count(*) FROM gudid_device d WHERE d.prefix=p.prefix)::text"
            "||' device rows cut to it in DB1', "
            "coalesce((SELECT string_agg(g.root_method||' ← DI '||g.source_di, ' | ') "
            "FROM gudid_company_prefix g WHERE g.prefix=p.prefix), 'no gudid_company_prefix row') "
            "FROM p WHERE NOT EXISTS (SELECT 1 FROM gudid_company_prefix g WHERE g.prefix=p.prefix "
            "AND g.root_method IS NOT NULL AND g.source_di IS NOT NULL) LIMIT %(n)s;"),

dict(id="C1", sec="C", db=PROD, title="containment in party.prefix",
     rule="GS1 licences DO NOT NEST. Allocation is downward from a delegation, so a prefix "
          "that is a strict leading substring of another is impossible. A FACT, NEVER A "
          "VERDICT — a bad cut, a mis-filing, a subsidiary and misuse look identical.",
     where="tape 2026-09-05 §B.2", since="2026-09-05",
     because="A search for Diazyme's hand-read 0817089 returned MedFare LLC holding 081708901. "
             "Nobody asked for the finding; it surfaced in the ordinary course of resolving.",
     count="SELECT (SELECT count(*) FROM party WHERE prefix IS NOT NULL)::text, count(*)::text "
           "FROM party a WHERE a.prefix IS NOT NULL AND EXISTS (SELECT 1 FROM "
           "generate_series(4, greatest(length(a.prefix)-1,4)) n JOIN party p "
           "ON p.prefix=left(a.prefix,n) AND p.prefix<>a.prefix);",
     sample="SELECT a.prefix, a.legal_name, a.source, b.prefix, b.legal_name FROM party a "
            "JOIN LATERAL (SELECT p.prefix, p.legal_name FROM "
            "generate_series(4, greatest(length(a.prefix)-1,4)) n JOIN party p "
            "ON p.prefix=left(a.prefix,n) AND p.prefix<>a.prefix LIMIT 1) b ON true "
            "WHERE a.prefix IS NOT NULL LIMIT %(n)s;"),

dict(id="C2", sec="C", db=PROD, title="containment in CLAIM values — C1's blind spot",
     rule="C1 reads party.prefix only. A prefix-shaped value in content_claim is invisible to it.",
     where="tape 2026-09-05", since="2026-09-05",
     because="C1 found someone else's over-cut and MISSED ONE OF OUR OWN: 081708902, nine "
             "digits, graded v, on a seven-digit hand-read licence — carrying a full gcp_cut "
             "provenance sentence for a derivation that never ran.",
     count="SELECT count(*)::text, count(*)::text FROM (SELECT c.identifier FROM content_claim c "
           "JOIN party p ON p.id=c.party_id WHERE p.prefix IS NOT NULL "
           "AND c.identifier ~ '^[0-9]{4,12}$' AND c.identifier <> p.prefix "
           "AND c.identifier LIKE p.prefix || '%') t;",
     sample="SELECT p.prefix, c.identifier, c.nm, c.grade, p.legal_name FROM content_claim c "
            "JOIN party p ON p.id=c.party_id WHERE p.prefix IS NOT NULL "
            "AND c.identifier ~ '^[0-9]{4,12}$' AND c.identifier <> p.prefix "
            "AND c.identifier LIKE p.prefix || '%' LIMIT %(n)s;"),

dict(id="C3", sec="C", db=PROD, title="prefix outside the arithmetic length gate",
     rule="A GCP is 4 to 12 digits. The gate is arithmetic, never a lookup.",
     where="promote_stage_to_production", since="2026-09-04",
     because="The length gate refused 0 of 23,910 at full volume. A gate that never refuses "
             "must still be able to.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE length(prefix)<4 OR length(prefix)>12)::text "
           "FROM party WHERE prefix IS NOT NULL;",
     sample="SELECT prefix, length(prefix)::text, legal_name FROM party WHERE prefix IS NOT NULL "
            "AND (length(prefix)<4 OR length(prefix)>12) LIMIT %(n)s;"),

dict(id="C4", sec="C", db=RUN, title="a cut taken from a non-GTIN source",
     rule="A GS1 company prefix may only be cut from a GS1-issued DI. GUDID also carries HIBCC "
          "and ICCBBA identifiers, which have no company prefix to find.",
     where="tape 2026-09-05", since="2026-09-05",
     because="Issuing-agency counts show mixed estates everywhere — HIBCC 2,625 · GS1 43 on one "
             "company. Cutting a HIBCC DI produces a WELL-FORMED NUMBER THAT MEANS NOTHING.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE source_di IS NOT NULL "
           "AND length(source_di) NOT IN (12,13,14))::text FROM company_prefix WHERE prefix IS NOT NULL;",
     sample="SELECT party_id::text, prefix, source_di, length(source_di)::text, register "
            "FROM company_prefix WHERE prefix IS NOT NULL AND source_di IS NOT NULL "
            "AND length(source_di) NOT IN (12,13,14) LIMIT %(n)s;"),

dict(id="C5", sec="C", db=RUN, title="mo-band as a root method",
     rule="Deriving the member organisation from prefix digits is FORBIDDEN.",
     where="SOLID ruling 2026-07-18", since="2026-07-18",
     because="D1 recorded 69,758 of 69,830 party.mo values as band-derived — a column named "
             "after an authority it was never read from.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE root_method='mo-band')::text "
           "FROM company_prefix WHERE prefix IS NOT NULL;",
     sample="SELECT party_id::text, prefix, root_method FROM company_prefix "
            "WHERE root_method='mo-band' LIMIT %(n)s;"),

dict(id="D1", sec="D", db=PROD, title="a value that can only be read by eye",
     rule="An identifier holding several values joined for display is NOT IN CONTEXT.",
     where="tape 2026-09-05", since="2026-07-12",
     because="Claim 988 holds four prefixes in one middot-joined string. An agent asking who "
             "holds 08478170 gets a SUBSTRING. Ratified machine-first: a bare number is only a "
             "candidate for context.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE identifier LIKE '%·%')::text "
           "FROM content_claim WHERE identifier IS NOT NULL;",
     sample="SELECT id::text, pillar, nm, left(identifier,70) FROM content_claim "
            "WHERE identifier LIKE '%·%' LIMIT %(n)s;"),

dict(id="D2", sec="D", db=PROD, title="provenance that claims a derivation, in prose",
     rule="A tx naming a method, a table and a version is a SENTENCE, not a check. It cannot be "
          "re-derived and it cannot be refuted.",
     where="tape 2026-09-05", since="2026-09-05",
     because="081708902 carried: 'cut with gcp_cut … GCP Length Table 2026-02-17 · 192,979 "
             "entries'. IT WAS HARDCODED. The sentence fooled this audit's own author for a "
             "full response.",
     note="THIS CHECK COUNTS PROSE. It cannot re-cut. See cannot_check.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE tx ILIKE '%gcp_cut%' "
           "OR tx ILIKE '%GCP Length Table%')::text FROM content_claim;",
     sample="SELECT id::text, nm, identifier, grade FROM content_claim "
            "WHERE tx ILIKE '%gcp_cut%' OR tx ILIKE '%GCP Length Table%' LIMIT %(n)s;"),

dict(id="D3", sec="D", db=PROD, title="verified with nothing to point at",
     rule="Every row graded AND SOURCED. tx is where the source lives.",
     where="stage_to_production.py, 30 Aug", since="2026-08-30",
     because="A grade without a source is an assertion. The register's whole claim is that it "
             "never makes one.",
     count="SELECT count(*) FILTER (WHERE grade='v')::text, count(*) FILTER "
           "(WHERE grade='v' AND (tx IS NULL OR btrim(tx)=''))::text FROM content_claim;",
     sample="SELECT id::text, pillar, nm, identifier FROM content_claim "
            "WHERE grade='v' AND (tx IS NULL OR btrim(tx)='') LIMIT %(n)s;"),

dict(id="E1", sec="E", db=PROD, title="an orphaned spine",
     rule="A node carrying a legacy party_id that resolves to no party points at nothing.",
     where="tape 2026-09-05", since="2026-09-05",
     because="89,933 pgln nodes resolve and node 8 — Diazyme, 190 associations, the richest in "
             "the database — pointed at party 4081955, which does not exist.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM party p "
           "WHERE p.id=(n.legacy->>'party_id')::bigint))::text FROM node n "
           "WHERE n.key_type='pgln' AND n.legacy->>'party_id' ~ '^[0-9]+$';",
     sample="SELECT n.id::text, n.legal_name, n.legacy->>'party_id' FROM node n "
            "WHERE n.key_type='pgln' AND n.legacy->>'party_id' ~ '^[0-9]+$' AND NOT EXISTS "
            "(SELECT 1 FROM party p WHERE p.id=(n.legacy->>'party_id')::bigint) LIMIT %(n)s;"),

dict(id="E2", sec="E", db=PROD, title="rooted with no event behind it",
     rule="A prefix that reached production through the gate carries an event. One with none "
          "was rooted by a path that recorded nothing.",
     where="tape 2026-09-04 §B.1", since="2026-09-04",
     because="448 rows committed and rooted parties rose by 137. The reconcile counted "
             "STATEMENTS, not distinct outcomes, and read clean while ~312 prefixes overwrote "
             "each other.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM party_event e "
           "WHERE e.party_id=p.id))::text FROM party p WHERE p.prefix IS NOT NULL;",
     sample="SELECT prefix, legal_name, source FROM party p WHERE p.prefix IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM party_event e WHERE e.party_id=p.id) LIMIT %(n)s;"),

dict(id="E3", sec="E", db=PROD, title="a demo row that could reach a customer",
     rule="NOTHING FAKE IS EVER PUBLIC. A demo row is fenced and may never be verified.",
     where="party_demo_not_verified · canon", since="2026-07-22",
     because="The one line GoDaddy never had to hold, and the one an identity register cannot "
             "survive breaking.",
     count="SELECT count(*)::text, count(*) FILTER (WHERE is_demo)::text FROM party;",
     sample="SELECT prefix, legal_name, state, coalesce(demo_urn,'—') FROM party "
            "WHERE is_demo LIMIT %(n)s;"),
]

CANNOT_CHECK = [
 dict(what="WHICH rows a NOT VALID constraint hides, in general",
      why="A4 checks node_urn_epc_valid specifically, because its validator epc_urn_valid() is "
          "callable from SQL. The other two NOT VALID constraints — node_urn_has_provenance and "
          "asset_urn_has_provenance — are checked here only by A1's count. EACH NOT VALID "
          "CONSTRAINT NEEDS ITS OWN A4.",
      needs="one check per NOT VALID constraint, running that constraint's own predicate over "
            "the existing rows. Until then, 'unvalidated' is a count and not a consequence."),
 dict(what="that any value is CORRECT",
      why="This audit proves INTERNAL CONSISTENCY. A register can be perfectly self-consistent "
          "and entirely fabricated. D2 counts prose; it cannot re-cut a DI and compare.",
      needs="source_di stored beside the CLAIM · the GCP Length Table readable at runtime · "
            "a callable cut function. The table is in git; the engine has giai/admit/transfer "
            "and NO CUT."),
 dict(what="the issuing agency and source DI of a cut, ANYWHERE PAST DB1",
      why="THEY ARE STORED — in DB1 (thingdaddy_harvest), per device and per cut. "
          "gudid_device.issuing_agency is NOT NULL, indexed (ix_gudid_device_agency) and "
          "constrained: gd_gs1_cut_xor_reason (a GS1 row carries a prefix or a cut_reason, "
          "exactly one) and gd_non_gs1_is_not_a_failed_cut (a non-GS1 row carries no prefix, "
          "no method, no reason). gudid_company_prefix carries root_method and source_di per "
          "row, both NOT NULL. WHAT IS MISSING IS THE CROSSING. No company_prefix in DB2 or "
          "DB3 carries issuing_agency. DB2's company_prefix has root_method and source_di "
          "columns, but on 6 Sep 2026 source_di was filled on 3,659 of its 18,472 gudid rows. "
          "DB3 has no company_prefix table at all; there the cut survives only as a display "
          "string in content_claim. B4 checks the DB1 side of this; nothing here checks the "
          "crossing.",
      needs="issuing_agency and source_di carried onto the prefix row in DB2 and DB3, NOT NULL "
            "when root_method='gcp-length-table', so the precondition that decides whether a "
            "cut is legitimate sits beside the cut where the cut is used."),
 dict(what="whether a running build serves its routes",
      why="A stale build and an honest empty answer are both 404 and differ only in the "
          "response body. On 5 September a build two weeks old served 'no route' under a banner "
          "reading LIVE, for an afternoon.",
      needs="an HTTP check. demo_up.sh does it."),
 dict(what="whether a file exists in more than one place",
      why="Six files lived in exactly one place on 5 September and one was lost.",
      needs="a filesystem and git check."),
 dict(what="whether a cited document says what the claim says",
      why="GATE_PRODUCTION_CONTRACT §1: a claim cites a document THE DATABASE ALREADY HOLDS. "
          "Without the document there is nothing to round-trip a span against.",
      needs="doc_fetch rows with sha256 recorded at fetch time."),
]

SEC_NAMES = {"A":"SCHEMA AND GATES","B":"GRADING","C":"DERIVATION",
             "D":"PROVENANCE","E":"COVERAGE"}


def run_checks(args):
    results, errors = [], []
    for c in CHECKS:
        if args.section and c["sec"] != args.section.upper():
            continue
        count_sql, sample_sql = c["count"], c.get("sample")
        if c.get("feed"):
            # CROSS-DATABASE: read a key list from one database, look it up in another.
            # An empty feed is written as a NULL row that matches nothing, so the count
            # runs, examines zero rows and reports NEVER FIRED — not a pass.
            frows, ferr = psql(c["feed"]["db"], c["feed"]["sql"])
            if ferr:
                errors.append({"id": c["id"], "error": f"feed from {c['feed']['db']}: {ferr}"}); continue
            keys = [r[0] for r in frows if r and r[0]]
            values = ",".join("(" + "'" + k.replace("'", "''") + "')" for k in keys) or "(NULL::text)"
            if not keys: count_sql = count_sql.replace("VALUES %(feed)s", "VALUES (NULL::text) LIMIT 0")
            count_sql = count_sql.replace("%(feed)s", values)
            if sample_sql: sample_sql = sample_sql.replace("%(feed)s", values)
        rows, err = psql(c["db"], count_sql)
        if err:
            errors.append({"id": c["id"], "error": err}); continue
        try:
            checked, found = int(rows[0][0]), int(rows[0][1])
        except Exception:
            errors.append({"id": c["id"], "error": "unreadable count"}); continue
        detail = rows[0][2] if len(rows[0]) > 2 else None

        state = "never-fired" if checked == 0 else ("finding" if found else "pass")
        r = {"id": c["id"], "section": c["sec"], "title": c["title"],
             "db": c["db"], "checked": checked, "found": found, "state": state,
             "rule": c["rule"], "rule_recorded_in": c["where"],
             "rule_since": c["since"], "rule_because": c["because"]}
        if c.get("note"): r["note"] = c["note"]
        if c.get("feed"): r["feed_db"] = c["feed"]["db"]
        if detail: r["detail"] = detail
        if found and sample_sql:
            srows, serr = psql(c["db"], sample_sql.replace("%(n)s", str(args.samples)))
            r["samples"] = ([{"row": x} for x in srows[:args.samples]] if not serr
                            else [{"sample_error": serr[:160]}])
        results.append(r)
    return results, errors


def record(results, errors):
    f = [r for r in results if r["state"] == "finding"]
    nf = [r for r in results if r["state"] == "never-fired"]
    return {
      "record": RECORD,
      "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
      "shaped_for": "a consumer that has never seen the terminal",
      "read_only": True,
      "databases": {"production": PROD, "staging": RUN, "harvest_db1": HARVEST},
      "summary": {"checks_run": len(results), "findings": len(f),
                  "never_fired": len(nf), "errors": len(errors),
                  "clean": not f and not errors},
      "never_fired_policy":
        "A CHECK THAT EXAMINED ZERO ROWS IS NOT A PASS. It never fired. "
        "'0 found' and '0 examined' look identical on a screen and mean opposite things.",
      "checks": results,
      "errors": errors,
      "cannot_check": CANNOT_CHECK,
      "audit_scope":
        "This proves the register is INTERNALLY CONSISTENT. It does NOT prove any value is "
        "correct. Internal consistency is not provenance.",
      "evolution":
        "Every check carries `rule_since` and `rule_because` — the date the rule was ratified "
        "and THE OBSERVATION THAT FORCED IT. Run with --save and --compare to show the register "
        "getting better, or not, over time. A register that cannot say why its own rules exist "
        "is asking to be taken on faith.",
    }


def human(rec, args):
    print(f"\n{BOLD}td_audit{RESET}   the register audits itself   {DIM}READ ONLY · "
          f"{rec['generated_at'][:19]}Z{RESET}")
    print(f"{DIM}  every check is a defect this register actually produced.{RESET}")
    print(f"{DIM}  each one names the day it was ruled and the observation that forced it.{RESET}")
    sec = None
    for r in rec["checks"]:
        if r["section"] != sec:
            sec = r["section"]; print(f"\n{BOLD}{sec} · {SEC_NAMES.get(sec,'')}{RESET}")
        col, mark = ((YEL, "NEVER FIRED") if r["state"] == "never-fired"
                     else (GRN, "pass") if r["state"] == "pass" else (RED, "FOUND"))
        print(f"  {col}{mark:>11}{RESET}  {BOLD}{r['id']}{RESET} {r['title']}")
        print(f"               {DIM}checked {r['checked']:,} · found {r['found']:,} · {r['db']}"
              + (f" ← {r['feed_db']}" if r.get("feed_db") else "") + f"{RESET}")
        if r.get("detail"): print(f"               {DIM}{r['detail']}{RESET}")
        if r["state"] == "finding" and not args.quiet:
            print(f"               {CYA}{r['rule']}{RESET}")
            print(f"               {DIM}ruled {r['rule_since']} · {r['rule_recorded_in']}{RESET}")
            print(f"               {DIM}because: {r['rule_because']}{RESET}")
            if r.get("note"): print(f"               {YEL}{r['note']}{RESET}")
            for s in r.get("samples", []):
                if "row" in s: print(f"               {DIM}·{RESET} " + "  ".join(x[:40] for x in s["row"]))
                else: print(f"               {YEL}{s['sample_error']}{RESET}")
            print()
    for e in rec["errors"]:
        print(f"  {YEL}      ERROR{RESET}  {e['id']}  {DIM}{e['error'][:130]}{RESET}")

    print(f"\n{BOLD}WHAT THIS AUDIT CANNOT CHECK{RESET}")
    print(f"{DIM}  named, so an absence here is never read as a pass.{RESET}")
    for c in rec["cannot_check"]:
        print(f"  {YEL}·{RESET} {BOLD}{c['what']}{RESET}")
        print(f"    {DIM}{c['why']}{RESET}")
        print(f"    {DIM}needs: {c['needs']}{RESET}")

    s = rec["summary"]
    print(f"\n{BOLD}SUMMARY{RESET}")
    print(f"  {RED}{s['findings']} finding(s){RESET} · {YEL}{s['never_fired']} never fired{RESET}"
          f" · {YEL}{s['errors']} error(s){RESET} · {s['checks_run']} checks run")
    nf = [r['id'] for r in rec['checks'] if r['state']=='never-fired']
    if nf: print(f"  {YEL}{rec['never_fired_policy']}{RESET}\n  {YEL}never fired: {', '.join(nf)}{RESET}")
    print(f"\n{DIM}  {rec['audit_scope']}{RESET}\n")


def compare(rec):
    if not os.path.isdir(AUDIT_DIR):
        print(f"\n  no previous audit in {AUDIT_DIR} — nothing to compare.\n"); return
    prev = sorted(f for f in os.listdir(AUDIT_DIR) if f.endswith(".json"))
    if not prev:
        print(f"\n  no previous audit — nothing to compare.\n"); return
    old = json.load(open(os.path.join(AUDIT_DIR, prev[-1])))
    o = {c["id"]: c for c in old["checks"]}
    print(f"\n{BOLD}EVOLUTION{RESET}   {DIM}against {prev[-1]}{RESET}")
    moved = False
    for c in rec["checks"]:
        p = o.get(c["id"])
        if not p:
            print(f"  {CYA}NEW CHECK{RESET}   {c['id']} {c['title']}"); moved = True; continue
        if p["found"] != c["found"] or p["state"] != c["state"]:
            d = c["found"] - p["found"]
            col = GRN if d < 0 else RED if d > 0 else YEL
            print(f"  {col}{p['found']:,} → {c['found']:,}{RESET}  {c['id']} {c['title']}")
            moved = True
    for cid in o:
        if cid not in {c["id"] for c in rec["checks"]}:
            print(f"  {YEL}CHECK GONE{RESET}  {cid} — a check that disappears is a finding")
            moved = True
    if not moved: print(f"  {DIM}nothing moved.{RESET}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section"); ap.add_argument("--samples", type=int, default=4)
    ap.add_argument("--quiet", action="store_true"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--save", action="store_true"); ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()

    for db in (PROD, RUN):
        _, err = psql(db, "SELECT 1;")
        if err:
            msg = {"record": RECORD, "error": f"cannot read {db}: {err}"}
            print(json.dumps(msg, indent=2) if a.json else
                  f"\n  {RED}REFUSED{RESET}  cannot read {db}: {err}\n")
            sys.exit(2)

    results, errors = run_checks(a)
    rec = record(results, errors)

    if a.json: print(json.dumps(rec, indent=2))
    else: human(rec, a)

    if a.compare: compare(rec)

    if a.save:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        p = os.path.join(AUDIT_DIR, rec["generated_at"][:19].replace(":", "") + ".json")
        json.dump(rec, open(p, "w"), indent=2)
        if not a.json: print(f"  saved {p}\n")

    sys.exit(1 if (rec["summary"]["findings"] or errors) else 0)


if __name__ == "__main__":
    main()
