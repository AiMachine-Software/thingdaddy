# TAPE · 4 SEPTEMBER 2026, evening — the prefix is the base; party was ours

**Append to `THINGDADDY_PHASE_LOG.md`, above the 2026-09-04 morning entry.**
Numbering unresolved (25 August rows 17–21 still unratified). Numbers assigned
on paste.

---

# PART A · THE RULING

**KJ, 4 September, verbatim:**

> "a prefix is the primary key - we should never have had party leading
> anything. its a prefix at its core"

> "an agent does not care about company name only a human does .. a machine
> needs clean ID's in context to make fast clear decisions in this world a
> prefix is the base nothing else"

> "we have prefix — company then we try to find if there is a relationship
> later"

```
THE PREFIX IS THE BASE. An authority issued it. It is the primary key
and it leads. Nothing is upstream of it.

PARTY WAS OURS. It was minted by a name fold over GUDID labeler strings,
then made the PARENT of the authority's fact:
company_prefix.party_id bigint NOT NULL. A prefix row could not exist
without a party first. THE INFERENCE BECAME THE SPINE AND THE FACT
BECAME THE CHILD.

A NAME IS A CLAIM ABOUT A PREFIX, never a property of one. It carries a
source and a date. Two names on one prefix both publish. The registrar
does not adjudicate which is right.

THE FOLD SURVIVES AS AN ASSERTION, not a key. Zimmer's four prefixes
matching on name is a candidate association with its evidence recorded
— weighable, refutable, the client's to confirm.

ONLY CLEAN PREFIXES WITH ASSOCIATED DATA PROMOTE. A prefix with no
sourced claim is not promotable. It stays in stage.
```

**Composes with the machine-first law (ratified 2026-07-12)** — *before any
design decision, ask what the graph's consumer, the agent, needs here.* The
consumer needs a key an authority issued. The name is for the human reading the
page afterwards. **No new philosophy opened. GAS stays at 3.**

## A · 1 · Why this is the same defect the canon already names

The party id was minted by the **name fold** — the single most-corrected
operation in the project. Canon §7: *an empty fold is not a key and can never
match* · `Medtronic` inside `Medtronic Ireland` · 广州迪克医疗器械有限公司
matched Ортотех ООД. **We built the entity out of the least reliable operation
in the system, and made the authority's own key subordinate to it.**

And a table named `party` holding what are really prefixes is the D1 family: a
column named after an authority it was never read from.

---

# PART B · THE EVIDENCE TRAIL — how the data said it, five ways

Every one of these was filed as a defect, a backlog or an open item. They were
one fact arriving in five accents.

```
4,099 refusals   promote_harvest_to_stage · ONE PARTY, ONE ROW
                 (recorded 4 Sept morning — the same fight one layer up)
6,629 refusals   promote_stage_to_production · party/does-not-exist ·
                 84% of all refusals at full volume
1,232 refusals   prefix/held-elsewhere · a contest that only exists
                 because a prefix must hang off exactly one party
  312 silent     448 committed, rooted parties rose only 137.
  overwrites     party.prefix is SCALAR; the last row for a party wins.
                 Teleflex 0801904…0801926 — 18 claims, 1 surviving root.
53,996 rooted    "unexplained" — a question about the wrong entity
```

## B · 1 · ITEM 3 ANSWERED — the path was unrecordable, not unaccounted

**KJ, 4 September:** *"these 54000 are gdsn"*

```
thingdaddy_run.company_prefix    root_method NOT NULL when prefix is set
                                 (cp_prefix_needs_method), closed enum
                                 gcp-length-table · gepir · hand-read.
                                 mo-band CANNOT be written there.

thingdaddy_population.party      NO root_method COLUMN AT ALL.
                                 ERROR: column "root_method" does not exist
```

**54,133 rooted rows in production and not one records how it was rooted.** The
staging table makes a prefix-without-a-method impossible; production drops the
method on the way across. **The stricter database is upstream of the looser
one, which is backwards for a registrar.**

So *"which path rooted these, and did it pass gates"* is **unanswerable from
production by construction.** Not unknown — unrecordable. The column that would
answer it was never there.

**Corroborating:** production is 80,993 GDSN of 102,472 records; the five
`held-elsewhere` refusals (ASO LLC · Trividia · RANIR · Bausch & Lomb · Sams
Club) are all `source=GDSN` with `prefix_claimed = 0`. Five for five.

**Tonight's 449 are the sole exception**, and only because the tool wrote
`root_method` into `party_event.detail` as JSON. That is the entire rooting
audit trail in DB3 — **0.8% of the rooted estate.**

**This retires the mo-band worry for production:** it cannot be carrying a
forbidden method because it carries no method. D1's 69,758 band-derived values
are in `party.mo`, a different column and a separate defect.

**CONSEQUENCE FOR THE REBUILD: there is nothing to backfill.** The method only
exists in `thingdaddy_run.company_prefix`, which is exactly what §5.2 of the
spec rebuilds from. And per the 3 Sept ruling — **GDSN IS NOT ATTESTED; a
pooled feed is not a filing** — these roots re-enter later in the GDSN lane,
where "GDSN, pooled feed, not attested" becomes a claim with a source and a
date rather than an unmarked root.

**THE TELL WE MISSED ALL DAY.** The tool's own reconcile compared rows-changed
to rows-admitted: 448 UPDATEs, 448 admitted, clean. **It counted statements,
not distinct outcomes.** Canon §7's first family — a check that cannot return
its own failure. An external count caught it.

**NOTHING WAS LOST.** All 449 claims are intact in `party_event.detail` with
prefix, stage_id, root_method and timestamp. The ~312 overwritten prefixes come
back by replay, not repair. **The append-only record survived a schema that
could not hold what it recorded.**

---

# PART C · THE STRUCTURE — three tables, additive, no bandaid

```
prefix                THE REGISTRY. PK is the prefix itself.
  prefix       PK     GS1 bands are partitioned across MOs — globally
                      unique, no composite key needed
  length              arithmetic, not lookup
  mo                  RECORDED from an authority or NULL. NEVER derived
                      — deriving it is mo-band, forbidden 2026-07-18 (D1)
  state               v · c · e · b · slot
  root_method         closed enum: gcp-length-table · gepir · hand-read
  stage_ancestor      the staging row it came from
  first_seen · last_updated

  NO legal_name. The name is not a property of a prefix.

prefix_claim          THE MIRROR. Many rows per prefix, per attribute.
  prefix → prefix
  attribute           legal_name · url · address · licence_type ·
                      device_count · duns · lei
  value · source · source_date · grade · asserter

  0017276 carries ASO LLC (GDSN, dated) AND WAL-MART (GUDID labeler,
  2026-08-29). Both publish. The agent weighs. No contest to resolve.

prefix_association    THE RELATIONSHIP, FOUND LATER.
  prefix_a · prefix_b · relation · evidence · asserter · grade

  Teleflex's 18 licences link here as CANDIDATE assertions, never as a
  foreign key. Governed by correction #6 (P27, P28): sameAs is an
  evidence-backed assertion owned by a named asserter, and THE
  REGISTRAR NEVER ADJUDICATES IT. A foreign key is adjudication.
```

**THE PROMOTION GATE:**

```
prefix present · digits only · length 4-12, arithmetic
root_method in the closed enum
stage_ancestor present
AT LEAST ONE SOURCED CLAIM — a name with a source and a date
licence_type absent -> candidate, never verified
```

**Migration shape:** additive, rebuilt from stage (closer to source than
production, which is derived), never in place. New tables empty → rebuild → dry
run → cut `/record/prefix` → `party` read-only until the screens move, then
retires as a LEADS table for the ~48k unrooted rows (canon: *no prefix, no
ThingSite* — get-a-prefix on-ramp).

**UNRESOLVED, NOT PAPERED OVER.** `asset`, `content_claim`, `edge`, `node` key
on `party_id`. For a multi-prefix company **no evidence in the data says which
licence owns which asset.** Options: leave children company-scoped and surface
them through the association table, or re-key only where a single prefix makes
it unambiguous and slot the rest. **Volumes not yet measured. Do not guess.**

---

# PART D · WHAT WAS MEASURED TODAY

```
promote_stage_to_production   IDEMPOTENCY OBSERVED (was only specified):
                              2nd run ADMITTED 0 / UNCHANGED 1 / exit 0
                              grep prefix_promoted -> exit 1, no stale ref

FULL DRY RUN                  QUEUE 23,910 (25,704 rows − 1,794 NULL
                              prefix). NOT A CAP. Reconciles.
  length 0 · gln 5 · prefix 1,232 · party 6,629 · stage 0 = 7,866 ✓
  ADMITTED 16,043

APPLIED                       500-row batch: 448 committed, 52 refused,
                              exit 10. Rooted 53,996 -> 54,133 (+137).
                              THE GAP IS THE FINDING.

staging table                 25,704 rows · 17,049 parties · 20,446
                              distinct prefixes
  eudamed 3,390 rows / 2,420 parties   ← production holds 9
  gudid  16,805 rows / 10,640 parties  ← production holds 21,397
  nmpa    3,715 rows /  2,516 parties  ← production holds none

n_devices broadcast           964 of 2,953 multi-prefix parties carry an
                              IDENTICAL count on every prefix row (1,609
                              vary, 380 all-NULL). A party total written
                              onto a per-prefix column. Under the new
                              structure it is a PARTY-LEVEL CLAIM, not a
                              prefix attribute — correctly scoped, not
                              fixed.

227 .py in population/        the inventory estimate of ~120 is low.
stage_to_production.py        EXISTS, one letter from the tool we ran,
                              STILL UNREAD after six asks. Read before
                              writing anything — the assign_keys.py lesson.
```

**THE gln GATE IS NOT DECORATIVE.** It fired 5 times, all party 4148869: gln
`0685346000008` against prefixes `5700571`…`5700575`. Five sequential numbers
with prefix shape that cleared the length gate. **This is the single-issue-key
check owed since 25 August (Part 7 item 5), surfacing on its own.** The gate
caught it.

**THE stage GATE RETURNED 0 ACROSS 23,910 ROWS.** The queue is read *from*
staging, so every row has an ancestor by construction. **Candidate for
structurally-incapable-of-firing.** Register it.

**THE GATES STILL CANNOT REPORT CHECKED vs NEVER-FIRED.** Adding a CHECKED
column beside REFUSED is one line and is the difference between "the gates
cleared this queue" and "the gates were silent over it."

---

# PART E · CLAUDE'S CORRECTIONS THIS SESSION

```
1  left(prefix,3) IS NOT A BAND. It splits GS1 US into ten. Walmart's
   "16 bands" are ~5 MOs (US · 471 Taiwan · 489 HK · 693/694/697 China ·
   890 India). Xtant's "6" are 2 (US + 426 Germany). The proposed filter
   would have EXCLUDED legitimate US multi-licence companies —
   rebuilding the 1,934 exclusion that A5 removed.

2  "17 WRONG ROOTS" OVERSTATED. HARVEST_UNIFIED_SPEC §4.2 already rules:
   "The brand owner owns the prefix. Private label included — the
   labeler licensed the number." Walmart's US-band prefixes are
   plausibly its own. Only the 10 foreign-MO-band rows are suspect.
   The rule was in the project and was not read before alarming.

3  READ A PAGED SCREEN AS A COMPLETE RESULT. Walmart's 9 rows were 22;
   the missing "(N rows)" footer was the tell. Fix: psql -P pager=off.
   Then INFERRED which rows were admitted from a list never seen in
   full. Part 9's first pattern: inferring past a measurement.

4  "ONE LOADER FAILED" — WRONG. The missing party id range 4149773–
   4165372 spans three registers and five days. It is a WATERMARK:
   production's party table stopped taking loads while staging
   continued. Not a break. A boundary was read as a cause.

5  CALLED THE gln GATE DECORATIVE after it returned 0 on a queue of one.
   It caught the five-row single-issue-key case at volume.
```

---

# PART F · OPEN

```
1  stage_to_production.py — READ (this session). Its 30 Aug docstring
   already ruled: "prefix is NOT written: production has no
   company_prefix table, so a multi-licence company's prefixes travel
   inside its P1 claims where they are graded and sourced."
   promote_stage_to_production.py was built beside it and wrote the
   scalar anyway. A REGRESSION AGAINST A DECISION ALREADY MADE.
2  Which script mints party ids (the fold). SEVEN files write to party:
   move_4790 · nmpa_promote · promote_link_path_rewrite ·
   promote_stage_to_production · stage_to_production · td_pipeline ·
   w3_populate_all. At least two disagree about party.prefix.
   ONE WRITER PER TABLE is broken. The fold itself is still unread.
3  Child-table volumes on multi-prefix parties — decides whether the
   asset/claim re-keying problem is real or theoretical. NOT MEASURED.
4  The 25 August tape rows, still unratified: cap-as-success ·
   soft-404-as-absence · database-vs-filesystem scope · single-issue-key
   fold risk · read-the-engine-first. R4. **DATABASE-VS-FILESYSTEM
   SCOPE JUST PRODUCED A LIVE ERROR — see PART G.**
5  Replay the 449 claims into the new structure once it exists.
6  GDSN deprioritised (KJ, this session): "we loose nothing on gdsn
   today." Incumbent GDSN roots hold; GUDID rows refused as
   held-elsewhere wait and are picked up in the GDSN lane. Not a
   reversal of canon §1 — a sequencing call for G1.
7  THE SPEC NEEDS A PROVENANCE-BINDING PASS. GATE_PRODUCTION_CONTRACT
   §0 binds a claim to a task that named the document FIRST
   (claim_proposal.task_id NOT NULL; cite_doc_sha256 must equal
   harvest_task.doc_sha256). Its design target: "an agent cannot
   satisfy it accidentally · an agent cannot fail it silently."
   SPEC §2.2's source/asserter/derived_by are all SELF-REPORTED by the
   writer. Rewrite §2.2 and §4 against the contract before building.
   Only the first 80 lines of the contract have been read; §7's
   [NEEDS 030] list is unread.
```

---

# PART G · TWO REGISTER CORRECTIONS FOUND ON THE RECORD BRANCH

**`GATE_REGISTER.md` §1 (W6, 3 Sept) states `td_gs1_engine.py` does not
exist — "the most serious finding in the survey." IT IS A SCOPE ARTEFACT.**

```
~/thingdaddy-engine/reference/td_gs1_engine.py   44,842 bytes
~/thingdaddy-gh/reference/td_gs1_engine.py       44,842 bytes
sha256 bcc26210352fe34f1cfd43873c6a9cf2a2110c18f297b9219387375376eaaede
```

Short sha matches the 4 Sept handoff §3.1 exactly (27 PASS). **W6 searched
`~/thingdaddy` — the PLATFORM repo. The engine lives in the ENGINE repo.** Its
method line says it read "the source on disk"; the disk it read was one of two.
**This is `database-vs-filesystem scope`, one of the five unratified 25 August
rows, producing the most alarming line in the register.** Ratify it on that
basis. The register needs a one-line correction: the engine exists, the mint
guards are running.

**Second: Gate 2 is recorded two ways on the same day.**

```
GATE_REGISTER §1   "Gate 2 returns 5, required 0, and nothing promotes
                    to DB3 until it is zero"
HANDOFF §16.10     "Gate 2 RETURNS 0 across 11,986 companies. The 5 came
                    from the gate replaying .slice(0,12) against an
                    obsolete client. NOTHING BLOCKS DB3."
```

§16.10 is the later correction and explains the 5, so tonight's 448 did not
cross a hold — **but the register still states the hold is in force.** A
register saying "nothing promotes" while promotion runs is a discrepancy that
gets found at the wrong moment. Reconcile it.

**Also noted, and it is good news:** `party_gate_prefix_required` exists in
`thingdaddy_run` as well as `thingdaddy_population`, and **NOT VALID
constraints across all three databases: ZERO** — every one of the 254 was
validated against the rows already present.

**IP FLAG, CARRIED.** Write-time preservation of disagreement between
authority-issued keys with read-time reconciliation — the mirror as a
mechanism. Today's ruling sharpens it: the key is the authority's, the name is
a dated claim, and the disagreement is the deliverable. Adjacent to and
arguably the inverse of TD-M-51. Not in the IP log. **Route to Jane. Counsel
constitutes the register; no number assigned here.**

**GAS stays at 3.** One law ratified, five corrections logged, no new
philosophy opened.

---

*The data kept trying to educate us. Today it stopped being polite about it.*
