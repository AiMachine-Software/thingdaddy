#!/usr/bin/env python3
"""
promote_stage_to_production.py — THE SECOND HANDOFF

Promotes a PREFIX from thingdaddy_run into thingdaddy_population.

    ONE PREFIX = ONE THINGSITE.  This tool promotes a prefix, never a company.
    It does not merge party rows, it does not choose between duplicate names,
    and it does not retire anything.  A ThingSite is a mirror.

DEFAULT IS DRY.  Nothing is written without --apply, and --apply also requires
--i-am-kj so it cannot be reached by an agent or by a stray shell history line.

    python3 promote_stage_to_production.py --prefix 0817089
    python3 promote_stage_to_production.py --prefix 0817089 --apply --i-am-kj

Exit codes:  0 clean · 10 refusals present · 20 preflight failed · 30 reconciliation break
"""

import argparse, sys, os, json, datetime

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


# ── the gates ────────────────────────────────────────────────────────────────
# Each returns None to admit, or a (code, message) to refuse.
# Every refusal is TYPED. A generic "denied" is not a refusal, it is a dead end.

def g1_length(s):
    p = (s.get("prefix") or "").strip()
    if not p.isdigit():
        return ("length/non-numeric", f"prefix {p!r} is not all digits")
    if not (4 <= len(p) <= 12):
        return ("length/out-of-range",
                f"prefix {p} is {len(p)} digits; a company prefix is 4-12 "
                f"(GenSpecs 26.0 s1.2.3.3). Arithmetic, not a lookup.")
    return None


def g2_gln_rooting(s):
    """The root derives from the GLN's OWN digits, never from a licence key
    displayed beside it."""
    gln, p = (s.get("gln") or "").strip(), (s.get("prefix") or "").strip()
    if not gln:
        return None                       # no GLN to check against
    if not gln.isdigit() or len(gln) != 13:
        return ("gln/malformed", f"gln {gln!r} is not 13 digits")
    if not gln.startswith(p):
        return ("gln/rooting-conflict",
                f"gln {gln} does not root in prefix {p}. The root must come "
                f"from the GLN's own digits.")
    return None


def g3_one_prefix_one_row(s, existing_here, holder_elsewhere):
    """A prefix belongs to one party row in production. This is NOT a
    de-duplication of companies — two party rows may carry the same NAME and
    that is a fact about the register. It refuses only when the same PREFIX is
    already held by a different party."""
    p = s["prefix"]
    if holder_elsewhere and holder_elsewhere["id"] != s["target_party_id"]:
        return ("prefix/held-elsewhere",
                f"prefix {p} is already on party {holder_elsewhere['id']} "
                f"({holder_elsewhere.get('legal_name')}). One prefix, one row. "
                f"Not resolved here — this is KJ's.")
    if existing_here and existing_here.get("prefix") and existing_here["prefix"] != p:
        return ("party/holds-other-prefix",
                f"party {s['target_party_id']} already holds prefix "
                f"{existing_here['prefix']}. A party may hold several prefixes, "
                f"but each is its own row — this promote would overwrite one.")
    return None


def g4_stage_ancestor(s, stage_party_exists):
    if not s.get("party_id"):
        return ("stage/no-party", "the staging row names no party_id")
    if not stage_party_exists:
        return ("stage/party-missing",
                f"staging party {s['party_id']} not found in the run database")
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
    """READ from the authority, never inferred. Absent means candidate,
    never root (GenSpecs s1.2.3)."""
    lt = (s.get("licence_type") or "").strip()
    if lt:
        return lt, (s.get("licence_type_source") or s.get("register") or "staging")
    return None, None


# ── preflight: refuse rather than assume a column exists ─────────────────────
NEED_PARTY = ["id", "prefix", "gln", "legal_name", "mo", "state", "source",
              "exception_reason", "verified_at", "last_updated",
              "licence_type", "licence_type_source", "url", "url_source",
              "stage_ancestor"]
NEED_STAGE = ["id", "party_id", "prefix", "root_method", "register", "n_devices"]


def columns(cur, table):
    cur.execute("""select column_name from information_schema.columns
                   where table_schema='public' and table_name=%s""", (table,))
    return {r[0] for r in cur.fetchall()}


def preflight(pcur, rcur, verbose):
    ok = True
    pc = columns(pcur, "party")
    missing = [c for c in NEED_PARTY if c not in pc]
    if missing:
        print(f"  PREFLIGHT FAIL  population.party is missing: {', '.join(missing)}")
        ok = False
    sc = columns(rcur, "company_prefix")
    ms = [c for c in NEED_STAGE if c not in sc]
    if ms:
        print(f"  PREFLIGHT FAIL  run.company_prefix is missing: {', '.join(ms)}")
        ok = False

    # what else exists that we should write, if it is there
    extras = {t: columns(pcur, t) for t in ("party_origin", "party_event")}
    for t, cols in extras.items():
        print(f"  {t:<14} {'present · ' + str(len(cols)) + ' columns' if cols else 'ABSENT — will not be written'}")

    # the constraints we must satisfy, read from the database rather than assumed
    pcur.execute("""select conname, pg_get_constraintdef(oid)
                    from pg_constraint
                    where conrelid='public.party'::regclass and contype in ('c','u')
                    order by conname""")
    cons = rows(pcur)
    print(f"  constraints on party: {len(cons)}")
    if verbose:
        for c in cons:
            print(f"      {c['conname']}  {c['pg_get_constraintdef'][:110]}")
    return ok, extras, cons


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-db", default="thingdaddy_run")
    ap.add_argument("--prod-db", default="thingdaddy_population")
    ap.add_argument("--prefix", help="promote one prefix. Omit to see the whole queue.")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--apply", action="store_true", help="write. Requires --i-am-kj.")
    ap.add_argument("--i-am-kj", action="store_true",
                    help="the founder gate. An agent cannot pass this.")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.apply and not a.i_am_kj:
        sys.exit("--apply requires --i-am-kj. An agent proposes; the answerable party ratifies.")

    mode = "APPLY" if a.apply else "DRY"
    print(f"\npromote_stage_to_production   {mode}   {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  {a.run_db}  ->  {a.prod_db}")
    print(f"  ONE PREFIX = ONE THINGSITE. This promotes a prefix, never a company.")
    print(f"  It does not merge party rows and it does not retire anything.\n")

    run, prod = connect(a.run_db), connect(a.prod_db)
    rcur, pcur = run.cursor(), prod.cursor()

    print("PREFLIGHT")
    ok, extras, cons = preflight(pcur, rcur, a.verbose)
    if not ok:
        print("\n  refusing to run against a schema that is missing what this tool writes.")
        sys.exit(20)
    print()

    # ── the queue ────────────────────────────────────────────────────────────
    sql = """select cp.id as stage_id, cp.party_id, cp.prefix, cp.root_method,
                    cp.register, cp.n_devices, cp.first_seen
             from company_prefix cp
             where cp.prefix is not null"""
    args = []
    if a.prefix:
        sql += " and cp.prefix = %s"
        args.append(a.prefix)
    sql += " order by cp.first_seen limit %s"
    args.append(a.limit)
    rcur.execute(sql, args)
    queue = rows(rcur)
    print(f"QUEUE  {len(queue)} staging prefix row(s)\n")
    if not queue:
        print("  nothing to promote. An empty queue is not a success; it is an empty queue.")
        sys.exit(0)

    scols = columns(rcur, "party")
    admitted, refused, unchanged = [], [], []

    for s in queue:
        # the staging party row, for the fields the authority recorded
        stage_party = None
        if "id" in scols:
            rcur.execute(f"select * from party where id=%s", (s["party_id"],))
            got = rows(rcur)
            stage_party = got[0] if got else None
        for k in ("gln", "legal_name", "mo", "licence_type", "licence_type_source",
                  "url", "url_source", "country", "city"):
            s[k] = (stage_party or {}).get(k)

        s["target_party_id"] = s["party_id"]

        # what production already holds
        pcur.execute("select * from party where id=%s", (s["party_id"],))
        here = (rows(pcur) or [None])[0]
        pcur.execute("select id, legal_name from party where prefix=%s", (s["prefix"],))
        elsewhere = (rows(pcur) or [None])[0]

        reason = (g1_length(s) or g2_gln_rooting(s)
                  or g3_one_prefix_one_row(s, here, elsewhere)
                  or g4_stage_ancestor(s, stage_party is not None))
        if reason:
            refused.append((s, reason))
            continue

        if here and here.get("prefix") == s["prefix"]:
            unchanged.append(s)          # idempotent: already promoted
            continue
        if not here:
            refused.append((s, ("party/not-in-production",
                f"party {s['party_id']} is not in production. This tool attaches a "
                f"prefix to a party that is already there; it does not create parties.")))
            continue
        admitted.append(s)

    # ── report ───────────────────────────────────────────────────────────────
    print("REFUSALS BY GATE          (the gate refusing is the product)")
    by_gate = {}
    for s, (code, msg) in refused:
        by_gate.setdefault(code.split("/")[0], []).append((s, code, msg))
    for gate in ("length", "gln", "prefix", "party", "stage"):
        n = len(by_gate.get(gate, []))
        print(f"  {gate:<10} {n}")
    print()
    for gate, items in by_gate.items():
        for s, code, msg in items[:12]:
            print(f"  REFUSED  {s['prefix']:<12} party {s['party_id']:<9} {code}")
            print(f"           {msg}")
    if refused:
        print()

    print(f"ADMITTED   {len(admitted)}")
    for s in admitted:
        state, why = grade_for(s)
        lt, lts = licence_for(s)
        print(f"  {s['prefix']:<12} party {s['party_id']:<9} -> {state:<10}"
              f" {s['root_method'] or 'root_method-not-recorded'}"
              f"  {s['n_devices'] or 0} devices")
        if why:
            print(f"               state is candidate: {why}")
        if not lt:
            print(f"               licence_type NOT READ — candidate, never root")
    print(f"UNCHANGED  {len(unchanged)}   (already promoted; this tool is idempotent)")
    print(f"REFUSED    {len(refused)}\n")

    if not a.apply:
        print("DRY RUN. Nothing was written. Add --apply --i-am-kj to write.")
        sys.exit(10 if refused else 0)

    # ── write, one transaction, and reconcile before commit ──────────────────
    n = 0
    try:
        for s in admitted:
            state, why = grade_for(s)
            lt, lts = licence_for(s)
            pcur.execute("""
                update party set
                  prefix              = %s,
                  gln                 = coalesce(%s, gln),
                  mo                  = coalesce(%s, mo),
                  licence_type        = coalesce(%s, licence_type),
                  licence_type_source = coalesce(%s, licence_type_source),
                  url                 = coalesce(%s, url),
                  url_source          = coalesce(%s, url_source),
                  state               = %s,
                  exception_reason    = %s,
                  verified_at         = case when %s = 'verified' then now() else verified_at end,
                  stage_ancestor      = %s,
                  last_updated        = now()
                where id = %s
            """, (s["prefix"], s.get("gln"), s.get("mo"), lt, lts,
                  s.get("url"), s.get("url_source"), state, why, state,
                  s["stage_id"], s["party_id"]))
            n += pcur.rowcount

            if extras.get("party_event"):
                cols = extras["party_event"]
                if {"party_id", "event_type"} <= cols:
                    detail = json.dumps({"prefix": s["prefix"], "state": state,
                                         "root_method": s.get("root_method"),
                                         "stage_id": s["stage_id"],
                                         "n_devices": s.get("n_devices")})
                    f = ["party_id", "event_type"]; v = [s["party_id"], "prefix_claimed"]
                    if "detail" in cols: f.append("detail"); v.append(detail)
                    if "source" in cols: f.append("source"); v.append("promote_stage_to_production")
                    if "actor"  in cols: f.append("actor");  v.append("KJ")
                    pcur.execute(f"insert into party_event ({','.join(f)}) "
                                 f"values ({','.join(['%s']*len(v))})", v)

        # reconciliation before commit — every count reconciles or we exit 1
        if n != len(admitted):
            prod.rollback()
            print(f"RECONCILIATION BREAK  admitted {len(admitted)} but {n} rows changed. "
                  f"Rolled back. No row is dropped silently.")
            sys.exit(30)

        pcur.execute("select count(*) from party where prefix is not null")
        rooted = pcur.fetchone()[0]
        prod.commit()
        print(f"COMMITTED  {n} row(s).  production now holds {rooted} rooted part(ies).")
        print("  Nothing was minted. The customer mints; we register and resolve.")
        sys.exit(10 if refused else 0)

    except Exception as e:
        prod.rollback()
        print(f"\nROLLED BACK — {type(e).__name__}: {e}")
        print("  Nothing was written. Read the error before changing a constraint:")
        print("  a gate refusing a write is the gate working.")
        sys.exit(30)


if __name__ == "__main__":
    main()
