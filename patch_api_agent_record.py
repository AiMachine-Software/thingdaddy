#!/usr/bin/env python3
"""
patch_api_agent_record.py — the AGENT-FIRST record.

    python3 patch_api_agent_record.py            # DRY
    python3 patch_api_agent_record.py --apply

WHY
  Ratified 2026-07-12: before any design decision, ask what the graph's
  consumer -- the AI agent -- needs here. And: an In-Context ID is only
  in-context if found+converted+inserted content travels with it; a bare
  number is only a candidate for context.

  Every read endpoint today is shaped for the screen:

    "identifier": "08476610 · 08478170 · 08478650 · 361052"
        four prefixes middot-joined for a human eye. An agent asking who
        holds 08478170 gets nothing -- it is a SUBSTRING, not a value.

    "tx": "verified · cut with gcp_cut from this company's own GUDID DIs,
           indicator stripped, GCP Length Table 2026-02-17 · 192,979 entries"
        the best provenance in the database, and it is PROSE. A human reads
        it. A machine cannot get the method, the table version or the date
        out of it.

    /record/prefix returns a PARTY object
        the human's shape. The prefix is the key; it should be the subject.

  We criticised SiLA this morning for holding a limit in a Description
  string. We were doing the same thing.

ADDS
  GET /agent/prefix/:prefix     the record, agent-first
  GET /agent/prefix/:prefix/ask what else can be asked about it

FIVE RULES THIS ENDPOINT KEEPS
  1  THE PREFIX IS THE SUBJECT. Party is a claim about it, not its parent.
  2  ONE VALUE PER FIELD. A display string carrying four values is split,
     and the split is FLAGGED -- it is a repair of our own defect.
  3  PROVENANCE IS STRUCTURE. The prose sentence is kept as `rendered`,
     never discarded and never the only form.
  4  THE GRADE TRAVELS ON THE VALUE, not on the record.
  5  GAPS ARE DECLARED. An agent must be able to see what we do NOT know
     without inferring it from an absence.
"""

import os
import sys

APPLY = "--apply" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("API_DIR") or os.path.join(HERE, "population", "api")
SERVER = os.path.join(API, "server.js")

MARK = "AGENT-FIRST RECORD"
ANCHOR = "// --- 404 fallthrough ---"

BLOCK = r'''
// ============================================================================
// AGENT-FIRST RECORD
//
// Ratified 2026-07-12: ask what the graph's consumer -- the agent -- needs.
// A bare number is only a CANDIDATE for context. This endpoint makes the
// context travel.
//
// THE PREFIX IS THE SUBJECT. Everything else is a dated, sourced, graded
// claim about it. The screen renders from this; this never renders for the
// screen.
// ============================================================================

// The five grades. party.state uses a three-value vocabulary; content_claim
// uses the five. ONE vocabulary reaches an agent.
const AG_GRADE = { verified: 'v', candidate: 'c', exception: 'e',
                   v: 'v', c: 'c', e: 'e', b: 'b', slot: 'slot' };
const agGrade = (s) => AG_GRADE[s] || 'slot';

// A display string carrying several values is SPLIT, and the split is
// declared. " · " is our own rendering join -- undoing it is a repair of our
// defect, not an interpretation of the source.
const AG_JOIN = /\s+·\s+/;
function agSplit(identifier) {
  if (identifier == null) return { values: [], split: false };
  const s = String(identifier);
  if (!AG_JOIN.test(s)) return { values: [s], split: false };
  return { values: s.split(AG_JOIN).map((x) => x.trim()).filter(Boolean), split: true };
}

// Provenance as STRUCTURE. What can be lifted from a column is lifted; what
// only exists in the prose stays in `rendered`. NOTHING IS PARSED OUT OF THE
// PROSE BY GUESSWORK -- a regex over a sentence is exactly the kind of
// derivation that invents a well-formed value.
function agProv(row, extra) {
  const p = {
    source: row.source || null,
    source_kind:
      row.source === 'GUDID' ? 'regulator-filing'
      : row.source === 'GDSN' ? 'pooled-feed'
      : row.source === 'EUDAMED' ? 'regulator-filing'
      : row.source === 'seed' ? 'seeded'
      : (row.source || '').startsWith('gepir') ? 'retired-registry'
      : 'unclassified',
    first_seen: row.first_seen || null,
    last_updated: row.last_updated || null,
    verified_at: row.verified_at || null,
    rendered: row.tx || null,
    rendered_is_prose: !!row.tx,
  };
  if (p.source_kind === 'retired-registry')
    p.note = 'GEPIR was retired 31 December 2023. This row is almost certainly '
           + 'a correct hand-read recorded under a name that no longer exists. '
           + 'Reported, not silently renamed.';
  if (p.source_kind === 'pooled-feed')
    p.note = 'A pooled feed is not a filing. Ruled 3 September 2026.';
  if (p.source_kind === 'seeded')
    p.note = 'A row whose source is "seed" was not attested by any authority.';
  return Object.assign(p, extra || {});
}

const agValue = (value, grade, prov) => ({ value, grade: agGrade(grade), provenance: prov });

// GET /agent/prefix/:prefix
app.get('/agent/prefix/:prefix(\\d+)', h(async (req, res) => {
  const pfx = req.params.prefix;

  const holders = await q(`SELECT ${PARTY_COLS} FROM party WHERE prefix = $1`, [pfx]);
  if (holders.rows.length === 0) {
    // An honest not-found is a real answer, and it says what WOULD resolve it.
    return res.status(404).json({
      subject: { prefix: pfx, resolves: false },
      grade: 'e',
      reason: 'no-holder-on-record',
      statement: 'The register holds no party rooted on this prefix. NEVER FABRICATED.',
      ask: { containment: `/agent/prefix/${pfx}/containment` },
    });
  }

  // ── the subject ─────────────────────────────────────────────────────────
  const subject = {
    prefix: pfx,
    length: pfx.length,
    length_method: 'arithmetic — char_length of the prefix, not a lookup',
    holders_on_record: holders.rows.length,
    holders_note: holders.rows.length > 1
      ? 'MORE THAN ONE ROW HOLDS THIS PREFIX. Both are returned. Duplicates are '
        + 'shown, never merged silently, and the registrar does not adjudicate '
        + 'which is right.'
      : null,
  };

  // ── claims, one value per field, grade on the value ─────────────────────
  const claims = { legal_name: [], gln: [], mo: [], duns: [], lei: [],
                   city: [], country: [], licence_type: [] };
  const gaps = [];

  for (const r of holders.rows) {
    const prov = agProv(r, { party_id: String(r.id) });
    const g = agGrade(r.state);
    const put = (k, v) => { if (v != null && v !== '') claims[k].push(agValue(v, g, prov)); };
    put('legal_name', r.legal_name);
    put('gln', r.gln);
    put('mo', r.mo);
    put('duns', r.duns);
    put('lei', r.lei);
    put('city', r.city);
    put('country', r.country);
    put('licence_type', r.licence_type);

    if (r.exception_reason)
      gaps.push({ field: 'state', why: r.exception_reason, party_id: String(r.id),
                  blocks: ['verified'] });
    if (!r.licence_type)
      gaps.push({ field: 'licence_type', why: 'not read', party_id: String(r.id),
                  blocks: ['verified'],
                  rule: 'licence_type absent => candidate, never root (4 Sep 2026)' });
    if (!r.mo)
      gaps.push({ field: 'mo', why: 'not read', party_id: String(r.id),
                  rule: 'mo is RECORDED from an authority or NULL. Deriving it from '
                      + 'the prefix digits is mo-band, forbidden since 18 Jul 2026.' });
  }

  // ── what is rooted here, one value per row, splits declared ─────────────
  const ids = holders.rows.map((r) => r.id);
  const cl = await q(
    `SELECT pillar, section, nm, identifier, grade, tx, doc_key, party_id
       FROM content_claim WHERE party_id = ANY($1::bigint[])
      ORDER BY pillar, display_order, id LIMIT 800`, [ids]);

  const attached = [];
  let splitCount = 0;
  for (const c of cl.rows) {
    const s = agSplit(c.identifier);
    if (s.split) splitCount++;
    for (const v of (s.values.length ? s.values : [null])) {
      attached.push({
        pillar: c.pillar, section: c.section, name: c.nm,
        value: v,
        grade: agGrade(c.grade),
        grade_is_null: c.grade == null,
        split_from_display: s.split,
        provenance: { rendered: c.tx || null, rendered_is_prose: !!c.tx,
                      doc_key: c.doc_key || null, party_id: String(c.party_id) },
      });
    }
    if (c.grade == null)
      gaps.push({ field: 'grade', why: 'this claim carries NO grade',
                  detail: 'content_claim_grade_valid is a CHECK, and a CHECK PASSES '
                        + 'ON NULL. The constraint reads as enforced and is not.',
                  claim: c.nm });
  }

  // ── findings in this namespace ──────────────────────────────────────────
  const inside = await q(
    `SELECT id, prefix, gln, legal_name, state, source FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1 ORDER BY length(prefix) LIMIT 50`, [pfx]);

  // ── the actor layer, which is entirely absent and says so ───────────────
  const actors = {
    grade: 'slot',
    gsrn: null, srin: null,
    statement: 'NO ACTOR IDENTITY IS HELD FOR THIS NAMESPACE. An enforced limit '
             + 'stops an unsafe VALUE; it cannot stop an unauthorised ACTOR. '
             + 'Without a GSRN there is no answer to "who performed this action", '
             + 'and without an SRIN no answer to "which revision of it".',
  };

  res.json({
    record: 'thingdaddy.agent.v1',
    generated_at: new Date().toISOString(),
    shaped_for: 'a consumer that has never seen the page',

    subject,
    claims,
    attached,
    keys_attached: attached.length,
    display_strings_split: splitCount,
    split_note: splitCount
      ? 'Some identifiers were stored as a single display string joining several '
        + 'values with " · ". They are split here and the split is flagged. THIS IS '
        + 'A REPAIR OF OUR OWN DEFECT: a value that can only be read by eye is not '
        + 'in context.'
      : null,

    findings: {
      containment: inside.rows.map((r) => ({
        prefix: r.prefix, holder: r.legal_name, gln: r.gln,
        source: r.source, grade: agGrade(r.state),
        relation: 'issued-inside',
        statement: 'This key sits inside the subject prefix. GS1 licences do not '
                 + 'nest, so only the licensee allocates there. A FACT, NOT A '
                 + 'VERDICT -- a bad cut, a mis-filing, a subsidiary, and misuse '
                 + 'all look identical here, and only the licensee knows which.',
      })),
    },

    capability: { grade: 'slot',
      statement: 'No capability surface is served from this API. SiLA Features and '
               + 'envelope bounds exist as files, not as records.' },
    actors,

    gaps,
    gap_policy: 'A DECLARED GAP IS STRONGER THAN A BLANK. Absence of evidence is a '
              + 'candidate, never an exception, never a guess. null is a refused key.',

    grades: { v: 'verified — an authority attested it',
              c: 'candidate — found, nothing has attested it',
              e: 'exception — looked at, could not resolve, named',
              b: 'built', slot: 'a declared gap' },
    grade_note: 'There is no grade for "we guessed", because nothing is guessed.',

    ask: {
      containment: `/agent/prefix/${pfx}/containment`,
      claims_full: holders.rows[0] ? `/prefix/${pfx}/claims` : null,
      human_page: `/record/prefix/${pfx}`,
      what_else: `/agent/prefix/${pfx}/ask`,
    },
  });
}));

// GET /agent/prefix/:prefix/ask — what can be asked, and what cannot.
// An agent should not have to discover our limits by hitting them.
app.get('/agent/prefix/:prefix(\\d+)/ask', h(async (req, res) => {
  const pfx = req.params.prefix;
  res.json({
    subject: { prefix: pfx },
    answerable: [
      { question: 'who holds this prefix, and on what evidence',
        at: `/agent/prefix/${pfx}`, grade_ceiling: 'v' },
      { question: 'what keys are rooted here',
        at: `/prefix/${pfx}/claims`, grade_ceiling: 'v' },
      { question: 'is anything filed inside this licence',
        at: `/containment/${pfx}`, grade_ceiling: 'v' },
      { question: 'how complete is this record',
        at: '/party/:id/completeness', grade_ceiling: 'v' },
    ],
    not_answerable: [
      { question: 'what may this instrument do',
        why: 'capability surfaces are files, not records. Not served.' },
      { question: 'what materials may it contact, and at what pH',
        why: 'ENVELOPE BOUNDS HAVE NOT BEEN HARVESTED. A user-guide bounds pass '
           + 'is owed. This is the axis a composition check cannot fire on today.' },
      { question: 'who may act on this, and in what role',
        why: 'no GSRN and no SRIN are held. There is no actor layer.' },
      { question: 'what is this thing worth, or should I buy it',
        why: 'not a question a registrar answers. We register and resolve.' },
    ],
    never_answerable: [
      { question: 'mint me an identifier',
        why: 'THE CUSTOMER MINTS. Nothing is ever minted by ThingDaddy.' },
      { question: 'which of two conflicting claims is correct',
        why: 'the registrar does not adjudicate. Both publish, dated and sourced, '
           + 'and the licensee answers.' },
    ],
  });
}));

// GET /agent/prefix/:prefix/containment — the finding, agent-shaped.
app.get('/agent/prefix/:prefix(\\d+)/containment', h(async (req, res) => {
  const pfx = req.params.prefix;
  const inside = await q(
    `SELECT id, prefix, gln, legal_name, state, source, first_seen FROM party
      WHERE prefix LIKE $1 || '%' AND prefix <> $1 ORDER BY length(prefix) LIMIT 200`, [pfx]);
  const outside = await q(
    `SELECT pp.id, pp.prefix, pp.legal_name, pp.state, pp.source FROM
       generate_series(4, greatest(length($1) - 1, 4)) n
       JOIN party pp ON pp.prefix = left($1, n) AND pp.prefix <> $1
      ORDER BY length(pp.prefix)`, [pfx]);
  res.json({
    subject: { prefix: pfx },
    method: 'string containment over digits. No name matching. No judgement.',
    inside: inside.rows.map((r) => ({ prefix: r.prefix, holder: r.legal_name,
      gln: r.gln, source: r.source, grade: agGrade(r.state), first_seen: r.first_seen })),
    outside: outside.rows.map((r) => ({ prefix: r.prefix, holder: r.legal_name,
      source: r.source, grade: agGrade(r.state) })),
    finding: (inside.rows.length || outside.rows.length) ? 'containment' : 'none',
    verdict: null,
    verdict_policy: 'THE REGISTER REPORTS THE CONTAINMENT AND NEVER THE CAUSE. '
                  + 'A bad cut by the registrar, a mis-filing, a subsidiary or channel '
                  + 'filing inside the parent licence, and genuine misuse are '
                  + 'indistinguishable here. Route the question to the licensee.',
  });
}));

'''


def die(msg):
    print(f"\n  REFUSED: {msg}\n")
    sys.exit(1)


def main():
    print()
    print(f"patch_api_agent_record   {'APPLY' if APPLY else 'DRY'}")
    print(f"  server: {SERVER}\n")

    if not os.path.isfile(SERVER):
        die(f"{SERVER} not found. Set API_DIR, or run from the repo root.")
    src = open(SERVER, encoding="utf-8").read()
    if MARK in src:
        print("  ALREADY PRESENT — not written twice.\n"); return
    if ANCHOR not in src:
        die("cannot find the 404 fallthrough in server.js. Read it and re-cut.")
    if "PARTY_COLS" not in src:
        die("PARTY_COLS is not defined in server.js. Re-cut against what it uses.")

    print("  adds  GET /agent/prefix/:prefix")
    print("        GET /agent/prefix/:prefix/ask")
    print("        GET /agent/prefix/:prefix/containment")
    print()
    print("  the prefix is the SUBJECT · one value per field · display strings")
    print("  split and flagged · provenance as structure with the prose kept as")
    print("  `rendered` · grade on every value · GAPS DECLARED")

    if not APPLY:
        print("\n  DRY RUN. Nothing written. Re-run with --apply.\n"); return

    open(SERVER + ".bak3", "w", encoding="utf-8").write(src)
    open(SERVER, "w", encoding="utf-8").write(src.replace(ANCHOR, BLOCK.lstrip("\n") + ANCHOR, 1))
    print(f"\n  WROTE  {SERVER}   (backup at server.js.bak3)\n")
    print("  RESTART, THEN READ IT AS AN AGENT WOULD:")
    print("    ./population/seed/demo_down.sh && ./population/seed/demo_up.sh >/dev/null 2>&1")
    print()
    print("    curl -s '127.0.0.1:8787/agent/prefix/0817089' | python3 -m json.tool | head -70")
    print("    curl -s '127.0.0.1:8787/agent/prefix/0817089/ask' | python3 -m json.tool")
    print("    curl -s '127.0.0.1:8787/agent/prefix/0000000' | python3 -m json.tool")
    print()
    print("  THE TEST: could something that has never seen the console answer")
    print("  'what is this, whose is it, what may it do, who may act on it'")
    print("  from that JSON alone — INCLUDING the parts we do not know?")
    print()


if __name__ == "__main__":
    main()
