#!/usr/bin/env python3
"""
promote_harvest_to_stage.py — THE FIRST HANDOFF

Promotes a PREFIX from thingdaddy_harvest (harvest_company) into thingdaddy_run
(party + company_prefix).  The mirror of promote_stage_to_production.py, one
hop earlier.

    ONE PREFIX = ONE THINGSITE.  This tool promotes a prefix, never a company.
    It does not create party rows, it does not merge them, it does not choose
    between namesakes, and it does not retire anything.  The harvest is READ
    ONLY here — nothing is written back into thingdaddy_harvest.

    root_method travels with the prefix (company_prefix.root_method) and the
    harvest ancestor travels with the party (party.stage_ancestor = the
    harvest company_key), so HOW a prefix was rooted and WHERE it came from
    are recordable by construction — audit A2 asked for exactly this.

Source:  harvest_company  where grade = 'rooted' and prefix is not null   (default)
         --register gudid: gudid_company_prefix joined to gudid_company on duns,
         one row per (duns, prefix), the name from gudid_company. The staging
         row is keyed 'gudid:<duns>' and carries root_method, source_di,
         n_devices, first_seen and n_companies_on_prefix off the register.
Target:  party + company_prefix in the run database

DEFAULT IS DRY.  Nothing is written without --apply, and --apply also requires
--i-am-kj so it cannot be reached by an agent or by a stray shell history line.

    python3 promote_harvest_to_stage.py --company demetech
    python3 promote_harvest_to_stage.py --prefix 0652927
    python3 promote_harvest_to_stage.py --register gudid --limit 300
    python3 promote_harvest_to_stage.py --prefix 0652927 --apply --i-am-kj

Exit codes:  0 clean · 10 refusals present · 20 preflight failed · 30 reconciliation break
"""

import argparse, sys, os, re, json, datetime

# ── driver: psycopg 3 or psycopg2, whichever is present. Imported lazily so
#    --help and the founder gate work on a machine without a driver. ─────────
_pg = None
def _driver():
    global _pg
    if _pg: return _pg
    try:
        import psycopg as m
    except ImportError:
        try:
            import psycopg2 as m
        except ImportError:
            sys.exit("no postgres driver. `pip3 install 'psycopg[binary]'` "
                     "or `pip3 install psycopg2-binary`")
    _pg = m
    return _pg


def connect(db):
    dsn = f"dbname={db}"
    for k, e in (("host", "PGHOST"), ("port", "PGPORT"), ("user", "PGUSER"), ("password", "PGPASSWORD")):
        v = os.environ.get(e)
        if v:
            dsn += f" {k}={v}"
    return _driver().connect(dsn)


def rows(cur):
    """dict rows, both drivers"""
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def fold(name):
    """the run database's name_fold: lower-case, letters and digits only"""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


# ── the vocabularies the fifth gate holds the harvest to ─────────────────────
# The nine key types a ThingSite is built from. harvest_row's CHECK admits
# twelve; the three it admits beyond these (method-schema, method-schema-claim,
# gated-claim) are pipeline shapes, not ThingSite slots, and a company that
# carries one is refused here until a slot exists for it.
KEY_TYPES = ("identity", "driver", "method", "document", "binding", "edge",
             "vocabulary", "exception", "device-identifier")
# The claim grades. v verified · c candidate · e exception · b our-shape-over-
# theirs · slot an empty, named absence. NULL is not a grade.
GRADES = ("v", "c", "e", "b", "slot")


# ── the gates ────────────────────────────────────────────────────────────────
# Each returns None to admit, or a (code, message) to refuse.
# Every refusal is TYPED. A generic "denied" is not a refusal, it is a dead end.

def g1_length(s):
    """Arithmetic, not a lookup."""
    p = (s.get("prefix") or "").strip()
    if not p.isdigit():
        return ("length/non-numeric", f"prefix {p!r} is not all digits")
    if not (4 <= len(p) <= 12):
        return ("length/out-of-range",
                f"prefix {p} is {len(p)} digits; a company prefix is 4-12 "
                f"(GenSpecs 26.0 s1.2.3.3). Arithmetic, not a lookup.")
    return None


def read_licence(s, hcur):
    """The licence is READ from a register, never inferred. If harvest_company
    already carries one, that stands. Otherwise the regulators are asked.

    THE JOIN KEY. harvest_company carries no DUNS and no USCC, so the link to
    the device registers is the rooted prefix itself, then out to the labeler:
        GUDID  harvest_company.prefix = gudid_device.prefix  -> gudid_device.duns
               -> every gudid_device row on that duns, counted by issuing_agency
        NMPA   harvest_company.prefix = nmpa_device.prefix   -> nmpa_device.tyshxydm
               -> every nmpa_device row on that USCC, counted by cpbsbmtxmc
    The widening to the labeler is the point: a register only cuts a prefix on
    a GS1 device (gd_non_gs1_is_not_a_failed_cut), so counting under the prefix
    alone would never see a HIBCC or MA-code device and could never say mixed.

    KJ ruling 2026-08-30 (audit B2, the attestation inversion): a regulator's
    filing attests the DI and the labeler together — the issuing agency
    delegated the space, the regulator attested the filing, two authorities
    agreeing. So when EVERY device the regulator holds for the labeler names
    GS1 as the issuing agency, the licence is read: 'GS1 Company Prefix' from
    'regulator:GUDID' (or NMPA). Mixed agencies are not read; they are refused.

    Fills s['licence_type'], s['licence_type_source'], s['licence_counts'].
    Returns nothing; g2 judges."""
    s["licence_counts"] = {}
    if (s.get("licence_type") or "").strip():
        return                              # the harvest already read it
    p = s["prefix"]
    # two indexed steps each, never one semi-join: the planner walks the whole
    # 6M-row NMPA table for the nested form (22 s a company; 0.02 s this way).
    hcur.execute("select distinct duns from gudid_device where prefix=%s and duns is not null", (p,))
    duns = [r[0] for r in hcur.fetchall()]
    gudid = {}
    if duns:
        hcur.execute("""select issuing_agency, count(*) from gudid_device
                         where duns = any(%s) group by 1 order by 2 desc""", (duns,))
        gudid = dict(hcur.fetchall())
    hcur.execute("select distinct tyshxydm from nmpa_device where prefix=%s and tyshxydm is not null", (p,))
    uscc = [r[0] for r in hcur.fetchall()]
    nmpa = {}
    if uscc:
        hcur.execute("""select cpbsbmtxmc, count(*) from nmpa_device
                         where tyshxydm = any(%s) group by 1 order by 2 desc""", (uscc,))
        nmpa = dict(hcur.fetchall())
    if gudid: s["licence_counts"]["GUDID"] = gudid
    if nmpa:  s["licence_counts"]["NMPA"] = nmpa
    if not s["licence_counts"]:
        return                              # no regulator holds this labeler
    if all(set(c) == {"GS1"} for c in s["licence_counts"].values()):
        s["licence_type"] = "GS1 Company Prefix"
        s["licence_type_source"] = "regulator:" + "+".join(s["licence_counts"])
        s["licence_ruling"] = "KJ ruling 2026-08-30"


def g2_licence(s):
    """READ from the authority, never inferred. Absent means not read — and a
    prefix whose licence was never read does not leave the harvest
    (GenSpecs 26.0 s1.2.3). read_licence() has already asked the regulators;
    a labeler whose devices name more than one issuing agency is refused with
    the counts, because a licence that is read is read whole."""
    mixed = {reg: c for reg, c in (s.get("licence_counts") or {}).items()
             if set(c) != {"GS1"}}
    if mixed:
        parts = []
        for reg, c in mixed.items():
            parts.append(reg + " " + ", ".join(f"{k}={v}" for k, v in c.items()))
        return ("licence/mixed-issuing-agency",
                f"prefix {s['prefix']}: the labeler's devices name more than one "
                f"issuing agency — {'; '.join(parts)}. A licence is read whole or "
                f"not at all.")
    lt = (s.get("licence_type") or "").strip()
    src = (s.get("licence_type_source") or "").strip().lower()
    if not lt:
        return ("licence/licence_type-not-read",
                f"prefix {s['prefix']}: licence_type was never read from the "
                f"authority and no regulator holds this labeler. Absent is not a "
                f"value; it stays in the harvest.")
    if src == "inferred":
        return ("licence/inferred",
                f"prefix {s['prefix']}: licence_type {lt!r} is marked inferred. "
                f"A licence is read, never inferred.")
    return None


def g3_gln_rooting(s):
    """The root derives from the GLN's OWN digits, never from a licence key
    displayed beside it."""
    gln, p = (s.get("gln") or "").strip(), (s.get("prefix") or "").strip()
    if not gln:
        return None                       # no GLN to check against
    if not gln.isdigit() or len(gln) != 13:
        return ("gln/malformed", f"gln {gln!r} is not 13 digits")
    if gln[:len(p)] != p:
        return ("gln/rooting-conflict",
                f"gln {gln} does not root in prefix {p}: its first {len(p)} "
                f"digits are {gln[:len(p)]}. The root must come from the GLN's "
                f"own digits.")
    return None


def g4_one_prefix_one_row(s, here, holders, key_of, batch):
    """A prefix belongs to one party row in the run. This is NOT a
    de-duplication of companies — two party rows may carry the same NAME and
    that is a fact about the register. It refuses when the register itself
    cuts the prefix for more than one company (n_companies_on_prefix), and
    when the same PREFIX is already held in the run by a different party,
    i.e. a different company_key."""
    p = s["prefix"]
    n = s.get("n_companies_on_prefix")
    if n is not None and n > 1:
        return ("prefix/shared-on-register",
                f"prefix {p} is held by {n} companies on the register itself. One "
                f"prefix, one row applies before it reaches the run; a shared cut "
                f"is not a root. Not resolved here — this is KJ's.")
    others = [h for h in holders if h["id"] != s["target_party_id"]]
    if others:
        h = others[0]
        k = key_of.get(h["id"])
        return ("prefix/held-elsewhere",
                f"prefix {p} is already on party {h['id']} ({h.get('legal_name')}) "
                f"via {h['via']}"
                + (f", harvest key {k!r}" if k else ", no harvest key points there")
                + f". This company is {s['company_key']!r} -> party "
                f"{s['target_party_id']}. One prefix, one row. Not resolved "
                f"here — this is KJ's.")
    if here and here.get("prefix") and here["prefix"] != p:
        return ("party/holds-other-prefix",
                f"party {s['target_party_id']} already holds prefix "
                f"{here['prefix']}. A party may hold several prefixes, but "
                f"each is its own row — this promote would overwrite one.")
    earlier = batch.get(s["target_party_id"])
    if earlier and earlier != p:
        return ("party/holds-other-prefix",
                f"party {s['target_party_id']} was admitted for prefix {earlier} "
                f"earlier in this queue. A party may hold several prefixes, but "
                f"each is its own row — this promote would overwrite one.")
    return None


def g5_slot_vocabulary(s, kinds, grades):
    """Every harvest_row for the company must be one of the nine key types,
    and every grade it carries must be one of the five grades. A row outside
    the vocabulary has no slot in a ThingSite, so the prefix waits."""
    bad_k = sorted(k for k in kinds if k not in KEY_TYPES)
    bad_g = sorted((g if g is not None else "NULL") for g in grades
                   if g not in GRADES)
    if bad_k or bad_g:
        parts = []
        if bad_k:
            parts.append(f"artifact_kind outside the nine key types: {', '.join(bad_k)}")
        if bad_g:
            parts.append(f"grade outside v/c/e/b/slot: {', '.join(bad_g)}")
        return ("slot/vocabulary", f"company {s['company_key']!r}: " + "; ".join(parts))
    return None


def grade_for(s):
    """state is READ, never assumed.  verified ONLY on a hand-read.
    Anything else is a candidate, and the reason travels with it."""
    rm = (s.get("root_method") or "").strip().lower()
    lt = (s.get("licence_type") or "").strip()
    if not lt:
        return "candidate", "licence_type-not-read"   # GenSpecs 26.0 s1.2.3
    if rm == "hand-read":
        return "verified", None
    if not rm:
        return "candidate", "root_method-not-recorded"
    return "candidate", f"root_method-{rm}-is-not-a-hand-read"


def licence_for(s):
    """READ from the authority, never inferred (g2 has already held this)."""
    lt = (s.get("licence_type") or "").strip()
    if lt:
        return lt, (s.get("licence_type_source") or "harvest")  # regulator:… when read here
    return None, None


# ── preflight: refuse rather than assume a column exists ─────────────────────
NEED_PARTY = ["id", "prefix", "gln", "legal_name", "mo", "country", "state", "source",
              "exception_reason", "verified_at", "last_updated",
              "licence_type", "licence_type_source", "url", "url_source",
              "name_fold", "stage_ancestor"]
NEED_CP = ["id", "party_id", "prefix", "root_method", "register", "n_devices"]
NEED_HC = ["company_key", "company_name", "prefix", "prefix_state", "root_method",
           "grade", "gln", "mo", "country", "pop_party_id",
           "licence_type", "licence_type_source", "url", "url_source", "first_seen"]
NEED_HR = ["id", "company_key", "artifact_kind", "pillar"]
NEED_GD = ["di", "issuing_agency", "duns", "prefix"]
NEED_GCP = ["id", "duns", "prefix", "root_method", "source_di", "n_devices",
            "n_companies_on_prefix", "first_seen"]
NEED_GC = ["duns", "company", "url", "url_source"]
NEED_ND = ["cpbsbmtxmc", "tyshxydm", "prefix"]


def columns(cur, table):
    cur.execute("""select column_name from information_schema.columns
                   where table_schema='public' and table_name=%s""", (table,))
    return {r[0] for r in cur.fetchall()}


def preflight(hcur, rcur, verbose, register):
    ok = True
    src = ((hcur, "gudid_company_prefix", NEED_GCP, "harvest"),
           (hcur, "gudid_company", NEED_GC, "harvest")) if register == "gudid" else ()
    for cur, table, need, where in src + ((rcur, "party", NEED_PARTY, "run"),
                                    (rcur, "company_prefix", NEED_CP, "run"),
                                    (hcur, "harvest_company", NEED_HC, "harvest"),
                                    (hcur, "harvest_row", NEED_HR, "harvest"),
                                    (hcur, "gudid_device", NEED_GD, "harvest"),
                                    (hcur, "nmpa_device", NEED_ND, "harvest")):
        have = columns(cur, table)
        missing = [c for c in need if c not in have]
        if missing:
            print(f"  PREFLIGHT FAIL  {where}.{table} is missing: {', '.join(missing)}")
            ok = False

    # what else exists that we read or write, if it is there
    extras = {t: columns(rcur, t) for t in ("party_event", "party_origin", "company_key")}
    for t, cols in extras.items():
        print(f"  {t:<14} {'present · ' + str(len(cols)) + ' columns' if cols else 'ABSENT — will not be used'}")

    # where the claim grade lives. harvest_row carries no grade column today;
    # the graded harvest artifact is doc_claim. payload->>'grade' is the
    # COMPANY grade (rooted/shared/…) and is never read as a claim grade.
    hr = columns(hcur, "harvest_row")
    dc = columns(hcur, "doc_claim")
    extras["harvest_row.grade"] = "grade" in hr
    extras["doc_claim"] = dc
    print(f"  {'harvest_row.grade':<14} {'present' if 'grade' in hr else 'ABSENT — grade is read from doc_claim.grade only'}")
    print(f"  {'doc_claim':<14} {'present · ' + str(len(dc)) + ' columns' if dc else 'ABSENT — no claim grades to hold'}")

    # the constraints we must satisfy, read from the database rather than assumed
    cons = []
    for t in ("party", "company_prefix"):
        rcur.execute("""select conname, pg_get_constraintdef(oid)
                        from pg_constraint
                        where conrelid=%s::regclass and contype in ('c','u')
                        order by conname""", (f"public.{t}",))
        got = rows(rcur)
        cons += got
        print(f"  constraints on {t}: {len(got)}")
        if verbose:
            for c in got:
                print(f"      {c['conname']}  {c['pg_get_constraintdef'][:110]}")
    return ok, extras, cons


# ── resolving the harvest company to its party row in the run ────────────────
def resolve_party(s, rcur, extras):
    """The run party this company already IS. In order of authority: the
    harvest's own pop_party_id; for a register row, its DUNS through the run's
    company_key crosswalk and then party.duns; the crosswalk on the company
    key; a single exact name_fold match. Returns (party_row, how) or
    (None, why). Never creates."""
    if s.get("pop_party_id"):
        rcur.execute("select * from party where id=%s", (s["pop_party_id"],))
        got = rows(rcur)
        if got:
            return got[0], "pop_party_id"
        return None, ("party/pop_party_missing",
                      f"harvest says pop_party_id {s['pop_party_id']} but no such party "
                      f"is in the run database")
    if s.get("duns"):
        if extras.get("company_key"):
            rcur.execute("""select p.* from company_key ck join party p on p.id = ck.party_id
                            where ck.key_type = 'duns' and ck.key_value = %s""", (s["duns"],))
            got = rows(rcur)
            if len(got) == 1:
                return got[0], "company_key:duns"
            if len(got) > 1:
                return None, ("party/ambiguous",
                              f"duns {s['duns']} resolves to {len(got)} parties via the "
                              f"crosswalk: {[g['id'] for g in got]}")
        rcur.execute("select * from party where duns = %s", (s["duns"],))
        got = rows(rcur)
        if len(got) == 1:
            return got[0], "party.duns"
        if len(got) > 1:
            return None, ("party/ambiguous",
                          f"duns {s['duns']} is on {len(got)} run parties {[g['id'] for g in got]}")
    if extras.get("company_key"):
        rcur.execute("""select p.*, ck.key_type from company_key ck
                        join party p on p.id = ck.party_id
                        where upper(ck.key_value) = upper(%s)""", (s["company_key"],))
        got = rows(rcur)
        if len(got) == 1:
            return got[0], f"company_key:{got[0]['key_type']}"
        if len(got) > 1:
            return None, ("party/ambiguous",
                          f"company_key {s['company_key']!r} resolves to {len(got)} "
                          f"parties via the crosswalk: {[g['id'] for g in got]}")
    nf = fold(s["company_name"])
    if nf:
        rcur.execute("select * from party where name_fold=%s", (nf,))
        got = rows(rcur)
        if len(got) == 1:
            return got[0], "name_fold"
        if len(got) > 1:
            return None, ("party/ambiguous",
                          f"name {s['company_name']!r} folds to {len(got)} run parties "
                          f"{[g['id'] for g in got]}. Namesakes are a fact about the "
                          f"register; choosing between them is not this tool's.")
    return None, ("party/not-in-stage",
                  f"company {s['company_key']!r} ({s['company_name']}) is not in the "
                  f"run database. This tool attaches a prefix to a party that is "
                  f"already there; it does not create parties.")


def holders_of(rcur, prefix):
    """every run party that holds this prefix, by either carrier: the scalar
    party.prefix column, or a company_prefix row."""
    rcur.execute("""select p.id, p.legal_name, 'party.prefix' as via
                      from party p where p.prefix=%s
                    union
                    select p.id, p.legal_name, 'company_prefix' as via
                      from company_prefix cp join party p on p.id=cp.party_id
                     where cp.prefix=%s
                    order by 1, 3""", (prefix, prefix))
    return rows(rcur)


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest-db", default="thingdaddy_harvest")
    ap.add_argument("--run-db", default="thingdaddy_run")
    ap.add_argument("--prefix", help="promote one prefix. Omit to see the whole queue.")
    ap.add_argument("--register", choices=("harvest", "gudid"), default="harvest",
                    help="harvest: harvest_company (default). gudid: gudid_company_prefix "
                         "x gudid_company on duns, one row per (duns, prefix).")
    ap.add_argument("--company", help="a company_key, duns, or a fragment of the key or name")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--apply", action="store_true", help="write. Requires --i-am-kj.")
    ap.add_argument("--i-am-kj", action="store_true",
                    help="the founder gate. An agent cannot pass this.")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.apply and not a.i_am_kj:
        sys.exit("--apply requires --i-am-kj. An agent proposes; the answerable party ratifies.")

    mode = "APPLY" if a.apply else "DRY"
    print(f"\npromote_harvest_to_stage   {mode}   {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  {a.harvest_db} ({a.register})  ->  {a.run_db}")
    print(f"  ONE PREFIX = ONE THINGSITE. This promotes a prefix, never a company.")
    print(f"  It does not create or merge party rows, and the harvest is read only.\n")

    harvest, run = connect(a.harvest_db), connect(a.run_db)
    hcur, rcur = harvest.cursor(), run.cursor()

    print("PREFLIGHT")
    ok, extras, cons = preflight(hcur, rcur, a.verbose, a.register)
    if not ok:
        print("\n  refusing to run against a schema that is missing what this tool writes.")
        sys.exit(20)
    print()

    # ── the queue ────────────────────────────────────────────────────────────
    if a.register == "gudid":
        sql = """select 'gudid:' || gcp.duns as company_key, gc.company as company_name,
                        gcp.duns, gcp.prefix, null::text as prefix_state, gcp.root_method,
                        gcp.source_di, gcp.n_devices, gcp.n_companies_on_prefix, gcp.first_seen,
                        null::text as gln, null::text as mo, null::text as country,
                        null::bigint as pop_party_id, null::text as licence_type,
                        null::text as licence_type_source, gc.url, gc.url_source
                 from gudid_company_prefix gcp
                 join gudid_company gc on gc.duns = gcp.duns
                 where gcp.prefix is not null"""
        args = []
        if a.prefix:
            sql += " and gcp.prefix = %s"
            args.append(a.prefix)
        if a.company:
            sql += " and (gcp.duns = %s or gc.company ilike %s)"
            args += [a.company, f"%{a.company}%"]
        sql += " order by gcp.first_seen, gcp.id limit %s"
    else:
        sql = """select company_key, company_name, null::text as duns, prefix, prefix_state,
                        root_method, null::text as source_di, null::int as n_devices,
                        n_companies_on_prefix, first_seen, gln, mo, country, pop_party_id,
                        licence_type, licence_type_source, url, url_source
                 from harvest_company
                 where grade = 'rooted' and prefix is not null"""
        args = []
        if a.prefix:
            sql += " and prefix = %s"
            args.append(a.prefix)
        if a.company:
            sql += " and (company_key = %s or company_key ilike %s or company_name ilike %s)"
            args += [a.company, f"%{a.company}%", f"%{a.company}%"]
        sql += " order by first_seen limit %s"
    args.append(a.limit)
    hcur.execute(sql, args)
    queue = rows(hcur)
    print(f"QUEUE  {len(queue)} {'register (duns, prefix) row(s)' if a.register == 'gudid' else 'rooted harvest compan(ies)'}\n")
    if not queue:
        print("  nothing to promote. An empty queue is not a success; it is an empty queue.")
        sys.exit(0)

    # which harvest key already points at which run party — so a held-elsewhere
    # refusal can name the other company_key, not just the other party id
    hcur.execute("select pop_party_id, company_key from harvest_company where pop_party_id is not null")
    key_of = {}
    for pid, key in hcur.fetchall():
        key_of.setdefault(pid, key)

    admitted, refused, unchanged = [], [], []
    batch = {}                      # party_id -> prefix admitted earlier in this queue

    for s in queue:
        # the run party this company already is
        here, how = resolve_party(s, rcur, extras)
        if here is None:
            refused.append((s, how, []))
            continue
        s["target_party_id"] = here["id"]
        s["resolved_by"] = how

        # every holder of the prefix in the run, by either carrier
        holders = holders_of(rcur, s["prefix"])

        # the company's harvest rows: the kinds it carries and the grades it carries
        # the company's harvest rows. A register row has none under its own
        # key; its harvest company is the one on the same prefix (harvest_company
        # is unique on prefix), and its rows are the ones g5 holds.
        hkey = s["company_key"]
        if a.register == "gudid":
            hcur.execute("select company_key from harvest_company where prefix=%s", (s["prefix"],))
            got = hcur.fetchone()
            hkey = got[0] if got else None
        s["harvest_key"] = hkey
        hcur.execute("select distinct artifact_kind from harvest_row where company_key=%s", (hkey,))
        kinds = [r[0] for r in hcur.fetchall()]
        grades = []
        if extras.get("harvest_row.grade"):
            hcur.execute("select distinct grade from harvest_row where company_key=%s", (hkey,))
            grades += [r[0] for r in hcur.fetchall()]
        if extras.get("doc_claim") and "grade" in extras["doc_claim"]:
            hcur.execute("select distinct grade from doc_claim where company_key=%s", (hkey,))
            grades += [r[0] for r in hcur.fetchall()]
        s["n_kinds"] = len(kinds)

        # the licence, read from the regulators when the harvest has none
        read_licence(s, hcur)

        # every gate is asked, so a refusal names everything that stands in the
        # way. The FIRST refusal is the one counted; the rest ride along.
        verdicts = [v for v in (g1_length(s), g2_licence(s), g3_gln_rooting(s),
                                g4_one_prefix_one_row(s, here, holders, key_of, batch),
                                g5_slot_vocabulary(s, kinds, grades)) if v]
        if verdicts:
            refused.append((s, verdicts[0], verdicts[1:]))
            continue

        cp_here = any(h["id"] == here["id"] and h["via"] == "company_prefix" for h in holders)
        if here.get("prefix") == s["prefix"] and cp_here:
            unchanged.append(s)          # idempotent: already promoted, both carriers
            continue
        s["cp_exists"] = cp_here
        batch[here["id"]] = s["prefix"]
        admitted.append(s)

    # ── report ───────────────────────────────────────────────────────────────
    print("REFUSALS BY GATE          (the gate refusing is the product)")
    by_gate = {}
    for s, (code, msg), more in refused:
        by_gate.setdefault(code.split("/")[0], []).append((s, code, msg, more))
    for gate in ("length", "licence", "gln", "prefix", "party", "slot"):
        items = by_gate.get(gate, [])
        codes = {}
        for _, code, _, _ in items:
            codes[code.split("/", 1)[1]] = codes.get(code.split("/", 1)[1], 0) + 1
        split = "  (" + " · ".join(f"{c} {n}" for c, n in sorted(codes.items())) + ")" if codes else ""
        print(f"  {gate:<10} {len(items)}{split}")
    print()
    for gate, items in by_gate.items():
        for s, code, msg, more in items[:12]:
            print(f"  REFUSED  {s['prefix']:<12} {s['company_key']:<28} {code}")
            print(f"           {msg}")
            for mcode, mmsg in more:
                print(f"           also {mcode}: {mmsg}")
        if len(items) > 12:
            print(f"  ... {len(items) - 12} more under {gate}")
    if refused:
        print()

    print(f"ADMITTED   {len(admitted)}")
    for s in admitted:
        state, why = grade_for(s)
        print(f"  {s['prefix']:<12} {s['company_key']:<28} -> party {s['target_party_id']} "
              f"({s['resolved_by']}) {state:<10} {s['root_method'] or 'root_method-not-recorded'}"
              f"  {s['n_kinds']} kind(s)"
              + (f"  {s['n_devices']} devices" if s.get("n_devices") is not None else ""))
        if why:
            print(f"               state is candidate: {why}")
        if s.get("licence_ruling"):
            counts = "; ".join(f"{r} GS1={c['GS1']}" for r, c in s["licence_counts"].items())
            print(f"               licence {s['licence_type']} read from {s['licence_type_source']}"
                  f" ({counts}) — {s['licence_ruling']}")
        if s.get("cp_exists"):
            print(f"               company_prefix row already there; party.prefix will be set")
    print(f"UNCHANGED  {len(unchanged)}   (already promoted; this tool is idempotent)")
    print(f"REFUSED    {len(refused)}\n")

    if not a.apply:
        print("DRY RUN. Nothing was written. Add --apply --i-am-kj to write.")
        sys.exit(10 if refused else 0)

    # ── write, one transaction, and reconcile before commit ──────────────────
    try:
        for s in admitted:
            state, why = grade_for(s)
            lt, lts = licence_for(s)
            rcur.execute("""
                update party set
                  prefix              = %s,
                  gln                 = coalesce(gln, %s),
                  mo                  = coalesce(mo, %s),
                  country             = coalesce(country, %s),
                  licence_type        = coalesce(licence_type, %s),
                  licence_type_source = coalesce(licence_type_source, %s),
                  url                 = coalesce(url, %s),
                  url_source          = coalesce(url_source, %s),
                  state               = %s,
                  exception_reason    = %s,
                  verified_at         = case when %s = 'verified' then now() else verified_at end,
                  stage_ancestor      = %s,
                  last_updated        = now()
                where id = %s
            """, (s["prefix"], s.get("gln"), s.get("mo"), s.get("country"), lt, lts,
                  s.get("url"), s.get("url_source"), state, why, state,
                  s["company_key"], s["target_party_id"]))

            if not s.get("cp_exists"):
                rcur.execute("""insert into company_prefix
                                  (party_id, prefix, root_method, register, source_di, n_devices)
                                values (%s, %s, %s, %s, %s, %s)""",
                             (s["target_party_id"], s["prefix"], s["root_method"],
                              a.register, s.get("source_di"), s.get("n_devices")))

            if extras.get("party_event"):
                cols = extras["party_event"]
                if {"party_id", "event_type"} <= cols:
                    detail = json.dumps({"prefix": s["prefix"], "state": state,
                                         "root_method": s.get("root_method"),
                                         "prefix_state": s.get("prefix_state"),
                                         "register": a.register,
                                         "source_di": s.get("source_di"),
                                         "n_devices": s.get("n_devices"),
                                         "harvest_company_key": s.get("harvest_key"),
                                         "resolved_by": s["resolved_by"]})
                    f = ["party_id", "event_type"]; v = [s["target_party_id"], "prefix_claimed"]
                    if "detail" in cols: f.append("detail"); v.append(detail)
                    if "source" in cols: f.append("source"); v.append("promote_harvest_to_stage")
                    if "actor"  in cols: f.append("actor");  v.append("KJ")
                    rcur.execute(f"insert into party_event ({','.join(f)}) "
                                 f"values ({','.join(['%s']*len(v))})", v)

        # reconciliation before commit — on DISTINCT OUTCOMES, never on statement
        # counts. The outcome promised for each admitted company is one party
        # that holds the prefix on BOTH carriers and names its harvest ancestor.
        # Every promised outcome must exist, and no prefix may have gained a
        # second holder. Anything else rolls back.
        promised = {(s["target_party_id"], s["prefix"], s["company_key"]) for s in admitted}
        missing = []
        for pid, pfx, key in sorted(promised):
            rcur.execute("""select 1 from party p
                              join company_prefix cp on cp.party_id = p.id and cp.prefix = p.prefix
                             where p.id = %s and p.prefix = %s and p.stage_ancestor = %s""",
                         (pid, pfx, key))
            if rcur.fetchone() is None:
                missing.append((pid, pfx, key))
        if missing:
            run.rollback()
            print(f"RECONCILIATION BREAK  {len(promised)} outcome(s) promised, "
                  f"{len(promised) - len(missing)} found. Rolled back.")
            for pid, pfx, key in missing:
                print(f"  missing: party {pid} prefix {pfx} ancestor {key!r}")
            print("  No row is dropped silently.")
            sys.exit(30)

        if promised:
            rcur.execute("""select prefix, count(distinct party_id) as n
                              from company_prefix where prefix = any(%s)
                             group by prefix having count(distinct party_id) > 1""",
                         (sorted({pfx for _, pfx, _ in promised}),))
            dup = rows(rcur)
            if dup:
                run.rollback()
                print(f"RECONCILIATION BREAK  {len(dup)} prefix(es) now have more than one "
                      f"holder in company_prefix. Rolled back.")
                for d in dup:
                    print(f"  {d['prefix']}  {d['n']} parties")
                sys.exit(30)

        rcur.execute("select count(*) from party where prefix is not null")
        rooted = rcur.fetchone()[0]
        run.commit()
        print(f"COMMITTED  {len(promised)} outcome(s).  the run now holds {rooted} rooted part(ies).")
        print("  Nothing was minted. The customer mints; we register and resolve.")
        sys.exit(10 if refused else 0)

    except SystemExit:
        raise
    except Exception as e:
        run.rollback()
        print(f"\nROLLED BACK — {type(e).__name__}: {e}")
        print("  Nothing was written. Read the error before changing a constraint:")
        print("  a gate refusing a write is the gate working.")
        sys.exit(30)


if __name__ == "__main__":
    main()
