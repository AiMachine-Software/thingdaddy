#!/usr/bin/env python3
"""
patch_api_tier1.py — add the four READ-ONLY endpoints the Tier 1 screens need.

    python3 patch_api_tier1.py            # DRY
    python3 patch_api_tier1.py --apply

WHY THESE FOUR
  Screens 8 (containment), 12 (exception register), 16 (estate view) and 11
  (the register at a glance) have no endpoint behind them today. Built without
  one they would be mockups, and nothing fake is ever public. These four make
  them real.

  Everything here is a GET. Nothing writes. Nothing minted.

WHAT IS ADDED
  GET /containment/:prefix   both directions for one prefix — what sits inside
                             it, and what it sits inside
  GET /containment           the estate-wide sweep, paged
  GET /exceptions            the 778 named exceptions, and the count by reason
  GET /estate                rows sharing a name fold — CANDIDATE association,
                             never asserted
  GET /claims/grades         the pillar x grade matrix over content_claim

THE CONTAINMENT RULE, stated once so it is not lost in the code
  A GS1 prefix that is a strict leading substring of another prefix is
  arithmetically impossible under the standard: licences do not nest. Every
  hit is one of four things and THE REGISTER MUST NEVER SAY WHICH —
      a bad cut by our own loader
      a mis-filing by them
      a subsidiary or channel filing inside the parent's licence
      genuine misuse
  We report the containment. The licensee reports the cause.
"""

import os
import re
import sys

APPLY = "--apply" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("API_DIR") or os.path.join(HERE, "population", "api")
SERVER = os.path.join(API, "server.js")

MARK = "TIER 1 READ-ONLY ENDPOINTS"
ANCHOR = "// --- 404 fallthrough ---"

BLOCK = r'''
// ============================================================================
// TIER 1 READ-ONLY ENDPOINTS
//
// Four GETs that give the Tier 1 screens real answers instead of mockups.
// Nothing here writes. Nothing here mints.
//
// THE CONTAINMENT RULE: a GS1 prefix that is a strict leading substring of
// another prefix is arithmetically impossible — licences do not nest. Every
// hit is a bad cut, a mis-filing, a subsidiary filing inside the parent's
// licence, or misuse. All four look identical. WE REPORT THE CONTAINMENT;
// THE LICENSEE REPORTS THE CAUSE.
// ============================================================================

// GET /containment/:prefix — both directions for one prefix.
//   inside : prefixes that START WITH this one — allocated in its namespace
//   outside: prefixes this one starts with — this row may sit inside another
app.get('/containment/:prefix(\\d+)', h(async (req, res) => {
  const p = req.params.prefix;

  const inside = await q(
    `SELECT id, prefix, gln, legal_name, state, source, mo, first_seen
       FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1
      ORDER BY length(prefix), prefix
      LIMIT 200`, [p]);

  // Bounded by construction: at most 8 probes against ux_party_prefix.
  const outside = await q(
    `SELECT pp.id, pp.prefix, pp.gln, pp.legal_name, pp.state, pp.source, pp.mo
       FROM generate_series(4, greatest(length($1) - 1, 4)) n
       JOIN party pp ON pp.prefix = left($1, n)
      ORDER BY length(pp.prefix)`, [p]);

  const self = await q(
    `SELECT id, prefix, gln, legal_name, state, source, mo FROM party WHERE prefix = $1`, [p]);

  res.json({
    prefix: p,
    holders: self.rows,                    // may be 0, 1 or more
    inside: inside.rows,
    outside: outside.rows,
    finding: (inside.rows.length || outside.rows.length) ? 'containment' : 'none',
    note: 'A containment is a FACT, not a verdict. A bad cut, a mis-filing, a '
        + 'subsidiary filing inside the parent licence, and misuse all look '
        + 'identical here. Only the licensee knows which.',
  });
}));

// GET /containment — the estate-wide sweep. Paged; never returns everything.
app.get('/containment', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 500) : 100;
  const rawOffset = Number(req.query.offset);
  const offset = Number.isFinite(rawOffset) && rawOffset > 0 ? rawOffset : 0;

  const { rows } = await q(
    `SELECT a.id   AS child_id,   a.prefix AS child,  a.legal_name AS child_name,
            a.source AS child_source, a.state AS child_state, a.gln AS child_gln,
            b.id   AS parent_id,  b.prefix AS parent, b.legal_name AS parent_name,
            b.source AS parent_source, b.state AS parent_state
       FROM party a
       JOIN LATERAL (
            SELECT p.id, p.prefix, p.legal_name, p.source, p.state
              FROM generate_series(4, greatest(length(a.prefix) - 1, 4)) n
              JOIN party p ON p.prefix = left(a.prefix, n)
             ORDER BY length(p.prefix)
             LIMIT 1
       ) b ON true
      WHERE a.prefix IS NOT NULL
      ORDER BY b.prefix, a.prefix
      LIMIT $1 OFFSET $2`, [limit, offset]);

  res.json({
    rows, count: rows.length, limit, offset,
    has_more: rows.length === limit,
    note: 'Containment is arithmetic over digits — no name matching, no '
        + 'judgement. The register reports it; the licensee explains it.',
  });
}));

// GET /exceptions — what we looked at and could not resolve, named.
// A declared gap is stronger than a blank. This is a trust exhibit.
app.get('/exceptions', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 500) : 100;
  const rawOffset = Number(req.query.offset);
  const offset = Number.isFinite(rawOffset) && rawOffset > 0 ? rawOffset : 0;
  const reason = typeof req.query.reason === 'string' && req.query.reason ? req.query.reason : null;

  const byReason = await q(
    `SELECT coalesce(exception_reason, '<<unnamed>>') AS reason, count(*)::int AS n
       FROM party
      WHERE state = 'exception'
      GROUP BY 1 ORDER BY n DESC`);

  const rows = reason
    ? await q(`SELECT id, prefix, gln, legal_name, state, source, mo, exception_reason, last_updated
                 FROM party WHERE state = 'exception' AND exception_reason = $1
                ORDER BY id LIMIT $2 OFFSET $3`, [reason, limit, offset])
    : await q(`SELECT id, prefix, gln, legal_name, state, source, mo, exception_reason, last_updated
                 FROM party WHERE state = 'exception'
                ORDER BY id LIMIT $1 OFFSET $2`, [limit, offset]);

  const total = byReason.rows.reduce((a, r) => a + r.n, 0);

  res.json({
    total,
    by_reason: byReason.rows,
    rows: rows.rows,
    count: rows.rows.length,
    limit, offset,
    has_more: rows.rows.length === limit,
    note: 'An exception is a thing we looked at and could not resolve, named. '
        + 'It is not a failure to hide — it is the reason the other grades mean '
        + 'anything.',
  });
}));

// GET /estate — party rows sharing a name fold.
//
// production's party.prefix is SCALAR under a unique index, so a company with
// four licences appears as FOUR ROWS. Grouping them is a CANDIDATE ASSERTION
// on name-fold evidence, never a claim that they are the same legal entity.
// The registrar does not adjudicate co-reference.
app.get('/estate', h(async (req, res) => {
  const fold = typeof req.query.fold === 'string' && req.query.fold ? req.query.fold : null;
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 200) : 50;

  if (fold) {
    const { rows } = await q(
      `SELECT id, prefix, gln, legal_name, state, source, mo, exception_reason
         FROM party WHERE name_fold = $1 ORDER BY (prefix IS NULL), prefix`, [fold]);
    return res.json({
      fold, rows, count: rows.length,
      rooted: rows.filter((r) => r.prefix).length,
      unrooted: rows.filter((r) => !r.prefix).length,
      grade: 'candidate',
      note: 'These rows share a name fold. That is EVIDENCE of one enterprise, '
          + 'not a ruling that they are one. Grade: candidate. The owner confirms.',
    });
  }

  const { rows } = await q(
    `SELECT name_fold,
            min(legal_name)                                  AS example_name,
            count(*)::int                                    AS rows,
            count(prefix)::int                               AS rooted,
            count(*) FILTER (WHERE prefix IS NULL)::int      AS unrooted,
            count(DISTINCT mo)::int                          AS mos
       FROM party
      WHERE name_fold IS NOT NULL
      GROUP BY name_fold
     HAVING count(prefix) > 1
      ORDER BY count(prefix) DESC, name_fold
      LIMIT $1`, [limit]);

  res.json({
    rows, count: rows.length, limit, grade: 'candidate',
    note: 'Multi-licence estates, grouped on name fold. Candidate evidence, '
        + 'never an assertion. A name fold is the least reliable operation in '
        + 'the system and is recorded here as such.',
  });
}));

// GET /claims/grades — the pillar x grade matrix. Feeds "the register at a
// glance". NULL is its own bucket and is never collapsed into a grade.
app.get('/claims/grades', h(async (_req, res) => {
  const { rows } = await q(
    `SELECT pillar, coalesce(grade, '<<NULL>>') AS grade, count(*)::int AS n
       FROM content_claim GROUP BY 1, 2 ORDER BY 1, 2`);

  const matrix = {};
  let total = 0, ungraded = 0;
  for (const r of rows) {
    matrix[r.pillar] = matrix[r.pillar] || {};
    matrix[r.pillar][r.grade] = r.n;
    total += r.n;
    if (r.grade === '<<NULL>>') ungraded += r.n;
  }

  res.json({
    total, ungraded, matrix,
    grades: ['v', 'c', 'e', 'b', 'slot'],
    note: ungraded > 0
      ? `${ungraded} claim(s) carry NO GRADE. content_claim_grade_valid is a `
        + 'CHECK, and a CHECK PASSES ON NULL — so the constraint reads as '
        + 'enforced and is not. Reported, not hidden.'
      : 'Every claim carries a grade.',
  });
}));

'''


def die(msg):
    print(f"\n  REFUSED: {msg}\n")
    sys.exit(1)


def main():
    print()
    print(f"patch_api_tier1   {'APPLY' if APPLY else 'DRY'}")
    print(f"  server: {SERVER}")
    print()

    if not os.path.isfile(SERVER):
        die(f"{SERVER} not found. Set API_DIR, or run from the repo root.")

    src = open(SERVER, encoding="utf-8").read()

    if MARK in src:
        print("  ALREADY PRESENT — not written twice.")
        print()
        return

    if ANCHOR not in src:
        die("cannot find the 404 fallthrough in server.js.\n"
            f"           Expected a line containing: {ANCHOR}\n"
            "           The file moved. Read it and re-cut this patch — do not guess.")

    # Report what each route needs, so a missing column fails HERE and not at
    # request time under a banner that says LIVE.
    needs = {
        "party": ["prefix", "legal_name", "state", "source", "mo", "gln",
                  "exception_reason", "name_fold", "last_updated"],
        "content_claim": ["pillar", "grade"],
    }
    print("  COLUMNS THESE ROUTES READ — verify against the live schema:")
    for t, cols in needs.items():
        print(f"    {t:16s} {', '.join(cols)}")
    print()
    print("    psql -d thingdaddy_population -c '\\d party' | grep name_fold")
    print()

    out = src.replace(ANCHOR, BLOCK.lstrip("\n") + ANCHOR, 1)
    print(f"  will insert {len(BLOCK.splitlines())} lines before the 404 fallthrough")
    print("  5 new GET routes: /containment/:prefix · /containment · /exceptions")
    print("                    · /estate · /claims/grades")

    if not APPLY:
        print()
        print("  DRY RUN. Nothing written. Re-run with --apply.")
        print()
        return

    open(SERVER + ".bak", "w", encoding="utf-8").write(src)
    open(SERVER, "w", encoding="utf-8").write(out)
    print()
    print(f"  WROTE  {SERVER}   (backup at server.js.bak)")
    print()
    print("  RESTART, THEN VERIFY EACH ROUTE — a port that answers is not a")
    print("  build that serves:")
    print()
    print("    ./population/seed/demo_down.sh")
    print("    ./population/seed/demo_up.sh")
    print()
    print("    curl -s '127.0.0.1:8787/claims/grades' | head -c 400; echo")
    print("    curl -s '127.0.0.1:8787/exceptions?limit=3' | head -c 500; echo")
    print("    curl -s '127.0.0.1:8787/estate?limit=5' | head -c 500; echo")
    print("    curl -s '127.0.0.1:8787/containment/0817089' | head -c 600; echo")
    print("    curl -s '127.0.0.1:8787/containment?limit=5' | head -c 600; echo")
    print()
    print("  /containment/0817089 SHOULD RETURN MedFare 081708901 as `inside`.")
    print("  If it does not, the route is wrong — that finding is known-true.")
    print()


if __name__ == "__main__":
    main()
