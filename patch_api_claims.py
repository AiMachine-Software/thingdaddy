#!/usr/bin/env python3
"""
patch_api_claims.py — expose content_claim so the five pillars are real.

    python3 patch_api_claims.py            # DRY
    python3 patch_api_claims.py --apply

WHY
  The ThingSite screen renders five pillars as empty slots because NO ENDPOINT
  SERVES content_claim. 290,954 claims exist — Diazyme 14, Illumina 88, Thermo
  Asheville 70 and 15 — and none of them is reachable over HTTP.

  Rendering static slots was correct (never invent content) but it is not the
  fix. The fix is the endpoint.

ADDS
  GET /party/:id/claims          every claim, grouped by pillar, with grade,
                                 tx (where the source lives) and doc_key
  GET /prefix/:prefix/claims     the same, resolved from the prefix — because
                                 the prefix is the key and the screens should
                                 not have to know a party id

  Both GET. Nothing writes.

A NOTE ON WHAT TRAVELS
  tx is where the source lives. A claim without its tx is a number with no
  provenance, so tx travels whole and is never truncated server-side. The
  screen may shorten it for display; the API does not.
"""

import os
import sys

APPLY = "--apply" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("API_DIR") or os.path.join(HERE, "population", "api")
SERVER = os.path.join(API, "server.js")

MARK = "CLAIM READ ENDPOINTS"
ANCHOR = "// --- 404 fallthrough ---"

BLOCK = r'''
// ============================================================================
// CLAIM READ ENDPOINTS
//
// content_claim over HTTP, so the five pillars render what the register holds
// instead of five empty slots. Both routes are GET; nothing writes.
//
// tx is where the source lives and it travels WHOLE. A claim without its tx is
// a number with no provenance. The screen may shorten it; the API does not.
// ============================================================================

async function claimsForParty(partyId, limit) {
  const { rows } = await q(
    `SELECT id, pillar, section, display_order, nm, identifier, grade, tx, doc_key,
            first_seen, last_updated
       FROM content_claim
      WHERE party_id = $1
      ORDER BY pillar, display_order, id
      LIMIT $2`, [partyId, limit]);

  // Grouped by pillar for rendering; NULL grade is its own bucket and is never
  // folded into a grade. content_claim_grade_valid is a CHECK, and a CHECK
  // PASSES ON NULL — so an ungraded row is a real state that must be visible.
  const pillars = {};
  const counts  = {};
  let ungraded = 0;
  for (const r of rows) {
    (pillars[r.pillar] = pillars[r.pillar] || []).push(r);
    const g = r.grade == null ? '<<NULL>>' : r.grade;
    counts[r.pillar] = counts[r.pillar] || {};
    counts[r.pillar][g] = (counts[r.pillar][g] || 0) + 1;
    if (r.grade == null) ungraded++;
  }
  return { rows, pillars, counts, ungraded, total: rows.length };
}

// GET /party/:id/claims
app.get('/party/:id(\\d+)/claims', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 2000) : 500;

  const p = await q(`SELECT ${PARTY_COLS} FROM party WHERE id = $1`, [req.params.id]);
  if (p.rows.length === 0)
    return res.status(404).json({ error: `no party with id ${req.params.id}` });

  const c = await claimsForParty(req.params.id, limit);
  res.json({
    party: p.rows[0],
    ...c,
    limit,
    truncated: c.total === limit,
    note: c.total === 0
      ? 'This party holds no content claims. That is an empty register for this '
        + 'row, not a rendering failure — and an empty pillar is a declared gap.'
      : 'Every claim carries its grade and its tx. tx is where the source lives.',
  });
}));

// GET /prefix/:prefix/claims — the prefix is the key; a screen should not need
// to know a party id to read the record.
app.get('/prefix/:prefix(\\d+)/claims', h(async (req, res) => {
  const rawLimit = Number(req.query.limit);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 2000) : 500;

  const p = await q(`SELECT ${PARTY_COLS} FROM party WHERE prefix = $1`, [req.params.prefix]);
  if (p.rows.length === 0)
    return res.status(404).json({ error: `no party with prefix ${req.params.prefix}` });

  // ux_party_prefix makes this one row today. Under the 4 September ruling a
  // prefix may carry MANY claims from many sources, so the shape stays plural.
  const out = [];
  for (const row of p.rows) out.push({ party: row, ...(await claimsForParty(row.id, limit)) });

  res.json({
    prefix: req.params.prefix,
    holders: out.length,
    records: out,
    limit,
    note: 'One prefix, one ThingSite. Where more than one row holds a prefix, all '
        + 'are returned — duplicates are shown, never merged silently.',
  });
}));

'''


def die(msg):
    print(f"\n  REFUSED: {msg}\n")
    sys.exit(1)


def main():
    print()
    print(f"patch_api_claims   {'APPLY' if APPLY else 'DRY'}")
    print(f"  server: {SERVER}")
    print()

    if not os.path.isfile(SERVER):
        die(f"{SERVER} not found. Set API_DIR, or run from the repo root.")

    src = open(SERVER, encoding="utf-8").read()

    if MARK in src:
        print("  ALREADY PRESENT — not written twice.\n")
        return
    if ANCHOR not in src:
        die("cannot find the 404 fallthrough in server.js. The file moved — read it "
            "and re-cut this patch rather than guessing.")
    if "PARTY_COLS" not in src:
        die("PARTY_COLS is not defined in server.js. These routes select with it; "
            "re-cut against whatever the file actually uses.")

    print("  reads content_claim: id, pillar, section, display_order, nm,")
    print("                       identifier, grade, tx, doc_key, first_seen,")
    print("                       last_updated")
    print("  and party via PARTY_COLS (confirmed present)")
    print()
    print("  adds  GET /party/:id/claims")
    print("        GET /prefix/:prefix/claims")

    if not APPLY:
        print("\n  DRY RUN. Nothing written. Re-run with --apply.\n")
        return

    open(SERVER + ".bak2", "w", encoding="utf-8").write(src)
    open(SERVER, "w", encoding="utf-8").write(src.replace(ANCHOR, BLOCK.lstrip("\n") + ANCHOR, 1))
    print(f"\n  WROTE  {SERVER}   (backup at server.js.bak2)")
    print()
    print("  RESTART, THEN VERIFY:")
    print("    ./population/seed/demo_down.sh && ./population/seed/demo_up.sh >/dev/null 2>&1")
    print("    curl -s '127.0.0.1:8787/prefix/0817089/claims?limit=3' | head -c 700; echo")
    print("    curl -s '127.0.0.1:8787/party/4090847/claims?limit=2' | head -c 700")
    print()
    print("  Diazyme should return 14 claims. Illumina (4090847) should return 88.")
    print("  If either returns 0, the route is wrong — those counts are known-true.")
    print()


if __name__ == "__main__":
    main()
