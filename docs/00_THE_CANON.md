# 00 · THE CANON — READ THIS FIRST, EVERY SESSION, BEFORE SPEAKING

*If you are answering a question about ThingDaddy and you have not read this file
in this session, stop and read it. Everything below was learned the hard way and
paid for once. Re-deriving any of it wastes KJ's time and is the single most
expensive failure in this project.*

---

## 0 · THE ONE RULE THAT PREVENTS THE REST

**Before you say a thing is missing, absent, unknown, or open — GREP THE
PROJECT.**

```
grep -rl "<term>" /mnt/project/*.md
```

It costs two seconds. Every day of this project has cost KJ a correction because
this step was skipped. Documented failures, all from raising as open something
already ruled:

```
the GSRN/SRIN model            ruled 13 Aug, raised as open 31 Aug
the CLIA / Allotrope absence   ruled 6 Aug, raised as open 31 Aug
"Diazyme P2 is empty"          a CLOSED rendering defect (R20)
the Diazyme GIAIs              ruled 28 Jul, superseded values quoted
the eight build steps          never written down, briefed 3× as if they were
Agilent's documents            fetched 13 Aug, called absent twice
the SHACL / config-not-code    an entire day, 19 Jul, re-derived from scratch
thesis
```

**The pattern is always the same: a plausible answer offered instead of a read.**
There is no mechanism that forces the read. This file is the mechanism, and it
only works if it is opened.

---

## 1 · THE MISSION

**2,000,000 GS1 prefixes by year end.**

The estate is the invitation. A company arrives at a ThingSite already built on
its own licence, finds its own manuals page-cited, and the claim moment is a
verification, not a creation.

**The device registers are the DEPTH lane. They are not the mission.** 479–835
identifiers per prefix — every medical register on earth is ~40–60k prefixes.
The mission lives in GDSN, MO directories, GLEIF deltas and the GS1 licence
conversation.

---

## 2 · THE YES/NO DISCRIMINATOR — run every idea through this

*From `claude_00_THE_THINGDADDY_YES_NO_DISCRIMINATOR.md`. Not a rule list — the
generator that produces yes/no on anything new.*

```
1 ROOTED               real authority, or honest candidate-until-ratified.
                       NO if it fabricates or claims authority it lacks.
2 HONEST ABOUT STATE   candidate vs verified never confused.
                       GS1 trust is BINARY — one fake public ID and it
                       is gone.
3 DETERMINED,          the key type follows what the thing IS (INV-4).
  NOT CHOSEN           NO if it is a claim you pick.
4 BUILDS ON            rides an adopted network and orchestrates across
                       them. NO if it replaces or competes with one.
5 NEUTRAL & SOVEREIGN  we hold the structure, not the data. An on-ramp TO
                       GS1. NO if it is a rival namespace or a data hoard.
```

**The discriminator is MAINTAINED by fearless feedback, not graduated from.**
If the correction loop stops, calibration drifts.

---

## 3 · THE LAWS — never re-litigate

```
LAW 0    PROVENANCE ABSOLUTE. Nothing enters the graph without traceable
         provenance. An identity without provenance is not an identity.
PREFIX   The GS1 prefix is the ROOT, not a qualifier. No prefix = exception,
IS ROOT  mint nothing.
THE      The customer mints, never ThingDaddy. Nothing ThingDaddy publishes
CUSTOMER is an assertion. Adoption is VERIFICATION, not creation.
MINTS
GENSPECS GenSpecs says what is PERMISSIBLE. ThingDaddy says what is
         ISSUABLE. Stricter, never looser.
NO ALPHA No letters in any ThingDaddy-GENERATED ID, ever. Numeric only.
         GENERATED != ADMITTED — a customer may admit their own legacy
         alphanumeric via admit().
CONTAINER Build the container — identity spine, slots, fleet, triggers —
BEFORE   BEFORE pouring content. Never pull a source until its container
CONTENT  exists, or it is water on the floor.
FIVE     v verified · c candidate · e exception · b built · slot.
GRADES   No collapse permitted. The grade travels with the row.
A SLOT   A declared gap is stronger than a wrong row rendered as held.
TRAVELS  Production carries 100,339 of them.
GEPIR    RETIRED 31 December 2023. Never cite it as a gate or lookup.
         The surface is Verified by GS1 -> Find company, HAND-READ ONLY.
MULTI IS Prefixes, urls, DUNS, GLNs, licences. NEVER PICK ONE. Which is
NORMAL   primary is the licensee's choice, not ours.
NULL IS  null = a refused key, never a guess. An empty string claims
A REFUSAL something the source did not say.
```

---

## 4 · THE FIVE PILLARS — from `ThingDaddy_Device_Record_Spec_1-2-3.md`

```
P1  IDs           GIAI instrument · GSRN+SRIN agent persona+version ·
                  SGTIN consumable · GDTI the manual · SGLN location
                  THREE PREFIX STATES: Verified · Unverified (real-basis,
                  DECLARED unverified) · Unresolved-candidate (skeleton,
                  prefix blank). Always generate the ID; the state governs
                  how it is declared.
P2  Drivers       the control-interface CLASS (serial/SCPI · REST/JSON ·
                  gRPC · Python SDK · proprietary · protocol) + a SiLA
                  Feature envelope, PAGE-CITED, referencing the P1 IDs.
                  "A fabricated driver is worse than none."
P3  Workflows     (a) DATA: output -> ASM measurement document / AFO
                  concepts, with P1 identities as PROVENANCE ANCHORS.
                  (b) METHOD: Sense->Understand->Decide->Act->Learn.
P4  Cloud/Edge    identity + driver as a PORTABLE EDGE ARTIFACT. Given the
                  In-Context ID, returns: GS1 identity · WoT/SiLA
                  capability · binding · authz · provenance destination.
                  CLOUD-NATIVE DEVICE IDS ARE GRAPH BINDINGS, NEVER
                  CANONICAL. The identity survives a runtime move.
P5  PhysAI/MCP    the testable tuple: agent GSRN + target GIAI + action +
                  authorization + transport + task lifecycle + provenance.
                  NO RESOLVED ID -> NO ACTION.
                  MCP EXTENSIONS, never core-MCP changes.
+ JOBS            demand cluster. CANDIDATE pending corpus join.
+ ENVIRONMENT     co-located instruments, consumables, software, carriers.
```

**Ten P5 conformance checks:** exact-target-identity · authorization-denial ·
replayed-request · transport-reconnect · long-running-task · task-cancellation ·
physical-event-callback · stale-target-context · wrong-location-target ·
provenance-write-failure.

---

## 5 · THE STANDARDS — grounded, with the numbers that reconcile

### The stack (KJ's own deck, bottom-up)
```
1 Base internet numbering        URN / URI — the addressing floor
2 NUMBERING STANDARDS (GS1)      the nine keys / In-Context ID
                                 <- THIS LAYER IS THINGDADDY
3 Science vocabulary             Allotrope AFO
4 Instrument drivers             SiLA
5 Network standards + workflows
```

### ALLOTROPE — three layers, three different numbers
```
AFO   the ONTOLOGY. ~5,000 terms/properties, BFO-aligned.
      af-e equipment 439 · af-p process 205 · af-r result 109 ·
      af-m material 73 · af-c common 34 · af-q quality 7
      2,449 concepts across 14 techniques (ELN case study, Sept 2017)
      PURL root http://purl.allotrope.org/voc/afo/
      LICENCE: CC-BY. Import cleared WITH ATTRIBUTION.
ADM   the SHACL SHAPES. 65 released models (April 2026 — the page
      COUNTS ITSELF; read the sentence, do not count the list).
      A shape constrains STRUCTURE, not analyte — which is why
      Diazyme conforms 17/17 while its analyte term does not exist.
ADF   the FILE. HDF5. Data Description + Data Cubes + Data Package.
      Byte-for-byte reversible.
MATURITY  Public / Candidate / Submission -> verified / candidate /
          pending. AFO's own gates, and they are ours.
```

**NEVER confuse the three numbers.** ~5,000 ontology terms, 2,449 case-study
concepts, 65 released SHACL models. They measure different things and collapsing
them has cost this project a correction more than once.

### SiLA 2 — the driver layer
```
SiLA Server (the instrument) -> Features -> Commands (with parameters)
                                          + Properties (readable state)
Transport: HTTP/2 + gRPC / protobuf
FDL: Feature Definition Language, XML
A DRIVER IS A DECLARATIVE FEATURE DEFINITION, NOT INTEGRATION CODE.
56 device types in the registry's closed vocabulary (some are product
names and duplicates — fewer real classes).
IN 11 OF 12 REGISTRY ENTRIES THE DRIVER AUTHOR IS NOT THE DEVICE MAKER.
```

### THE SYNTHESIS — config not code (19 July, the whole thesis)
> **Both standards are DECLARATIVE. An experiment modelled in Allotrope IS an
> RDF graph — equipment → process → material → result, typed nodes and typed
> edges. Each protocol is a subgraph; MERGE THEM ON SHARED ENTITIES and you have
> P5, from a real standard.**

```
instrument (GIAI) --has_driver--> SiLA Feature   (GDTI, P2)
                  --runs-------->  Allotrope RDF (GDTI, P3) --> result
                  --binds------->  cloud/edge               (P4)
```

**Onboarding an instrument is CONFIGURATION, not code.** Declare its Feature and
its method against its GS1 identity. This is INV-6.

**P5 is not built over the pillars. P5 is what P3 becomes when protocols merge
on shared identities.**

### WHERE A VOCABULARY RUNS OUT
```
no vendor SiLA Feature  -> AUTHOR one from the vendor's own catalog, bound
                           to a GDTI, CANDIDATE. Configuration, not vendor
                           code. SiLA decides whether it certifies.
no released AFO model   -> ground the STRUCTURE (af-p/af-e/af-r), represent
                           the analyte as a COMPANY EXTENSION via AFO's own
                           mechanism. CANDIDATE. NEVER mint a core AFO URI.
                           The customer proposes to the standards body.
```
**We do not author standards. We model a NEW USE CASE against an unchanged one,
mark it candidate, and the body that owns it decides.**

---

## 6 · MHS — the eighth vocabulary

MHS is the eighth pluggable vocabulary alongside SiLA, Allotrope, MCP, OPC-UA,
MTConnect, EDI, SAP IDoc. **Not a competitor. Not a bridge target.**

**Their own words name the gap:**
> *"much of this information has been stored in **paper manuals**... or as
> **tacit knowledge**"* — and their answer is a user typing tags or an agent
> interviewing them.

**We read the manual and cite the page.**

```
THEIRS   read/write primitives · discoverability · a reference file
         (measures, adjustables, safety limits) · MCP/CLI/code files
THE GAP  the reference file is OPERATOR-AUTHORED and it carries the
         SAFETY LIMITS. Under EU machinery rules from Jan 2027 that file
         performs a safety function.
WE ADD   WHICH UNIT (GIAI) · UNDER WHAT (GDTI+version) · ON WHICH LOT
         (LGTIN) · WHERE (SGLN) · WHOSE AUTHORITY (GSRN) · THAT IT RAN
         plus the vendor's DENIALS as first-class claims, and a GRADE
         and SOURCE per field.
```

**Five of those six have no programming interface** — a method, a lot, a place,
a relation and a past execution cannot be discovered on a network. Outside MHS's
scope by construction, not omission.

**Grounding it PROTECTS Anthropic.** They want adoption; the obstacle is
regulatory pushback; six regulators already require the identifier that closes
it — FDA, NMPA, EU, MHRA, ANVISA, PMDA.

**Posture: humility. "We support MHS and MCP using SiLA and Allotrope."** No
coverage claim, no conformance claim. We want to be publicly challenged — a
checkable claim that survives is credibility.

**No schema is published.** `github.com/modelhardwarestandard` is empty. What
survives any schema change: the identity, the page cites, the sha256s, the
grades, the denials.

---

## 7 · THE DEFECT FAMILIES — every one of these recurs

**A CHECK THAT CANNOT RETURN ITS OWN FAILURE.** Six instances in one day.
```
a CHECK passes on NULL — content_claim_grade_valid is decorative
ADD ... NOT VALID lands silently, skipping the rows that would alarm
grade(prefix, 0) -> 'shared' — zero is not more than one
test_gate C4 reconciled 0+0+0 on an empty ledger
pgrep on ps output matched its own command line — 4 false hits on a
  job that never existed
cu_*_not_verified named ONE source; every source added later escaped
```

**GREEN ON FAILURE — one channel for "it worked", none for "nothing happened".**
```
nightly    loop_daily: ten nights ok, zero productive rows
tool       harvest_510k filed junk as clearances_verified, stage ok
apply      psql -f exit 0 over a rolled-back statement
harvest    eudamed exit 0 on a truncated pull
```

**CONTAINMENT / SUBSTRING COLLISION.** Four in one day.
```
说明书 inside 操作说明书  -> an operating instruction became an IFU
api inside terapia       -> Italian product pages "rescued"
Medtronic / Medtronic Ireland · Aesculap under B. Braun
PCR must not match qPCR
```

**A FOLD THAT DESTROYS ITS INPUT MATCHES EVERYTHING.**
Every CJK and Cyrillic name folded to "" — 广州迪克医疗器械有限公司 matched
Ортотех ООД. **An empty fold is not a key and can never match.**
`name_fold.py`: `fold()` may return empty · `match_key()` never does ·
`same_name()` folds Latin, compares CJK exact.

**LINE-WRAP TRUNCATION — four faces, all silent, all plausible.**
non-breaking space · hyphen at a line break · multi-line spec values ·
unmarked continuation lines. **The page wraps, the read doesn't, and what
survives is still readable text.**

**ONE RULE IN MANY PLACES HOLDS IN WHICHEVER RAN LAST.** Six repairs, one
shape: `gcp_cut` · `name_fold` · `short_why` · the strip module · the rules
module · `afo_released_domains`. **One file, every caller imports it, none
carries a copy.**

**A DERIVATION THAT INVENTS A WELL-FORMED VALUE.**
```
@example.com -> example.com   NMPA derived doors: 33.3% open vs 86.2%
                              for regulator-published. The failures are
                              NXDOMAIN — the door was NEVER A DOOR.
gleif_full.csv carries an `mo` column GLEIF does not publish — a lookup
  from country. D43.
party.mo band-derived on 69,758 rows. D1.
```

**A TOOL MISATTRIBUTING ITS OWN FAILURE TO THE TARGET.**
```
curl http_code 0 recorded as a mechanism — 21% of refusals had none
a missing URL made the fetch fail and 16 rows were filed "blocked"
an unrendered JS shell classified as OPEN — 2 anchors vs 194 in Chrome
```

**COUNTING WITHOUT ASKING THE SOURCE.** The Allotrope page states its own
count — *"approximately 65 interoperable data models"* — and it was counted
instead of read. **A document that counts itself is a gift.**

---

## 8 · THE OPERATING RULES

```
CHAT -> AGREE -> COWORK -> CODE. Never build without explicit instruction.
PRESENT CHOICES, DO NOT MAKE THEM. "I have this information, here are the
  choices, here are the impacts, what do you want me to do?"
LOOK BEFORE ASSERTING. Structure from knowledge; CURRENT STATE FROM A
  SOURCE. Never carry the same confidence for both.
NEVER QUOTE AN UNVERIFIED NUMBER. Label it candidate.
CORRECTIONS ARE THE PRODUCT. One line, no groveling.
A FAILURE IS FIXED AND MOVED PAST. It does not stop the batch.
  Stop only for one thing: writing one company's content under another
  company's name.
ONE WRITER PER TABLE. One writer per file. One owner per append-target.
  git commit -- <paths>. Never -A, never `.`
NO WINDOW GUESSES A D-NUMBER. Entries go to the register owner.
NO AD-LIBBED COPY. Every word KJ's or a cited source, otherwise a slot.
HONEST UA. No proxy, no mirror, no cache reader, no UA spoof. A 403 is a
  named exception. NEVER RETRY A BLOCK WITH A NEW IDENTITY.
DEFERRED != HELD. A hold citing budget or rate-limit is the ABSENCE of a
  run wearing a verdict's clothes. N45.
UNKNOWN != NONE. A door that will not open cannot be asked what it holds.
NOT-YET-ATTEMPTED != ZERO. Keep them apart in every report.
```

---

## 9 · TERMS

```
"Legacy IDs"     not "old IDs"
"CPID"           the key. `cpi` is only the URN scheme — do not "fix" a
                 valid cpi: URN
NEVER            "true identity" · "digital twin"
```

---

## 10 · THE FILES THAT ARE ALREADY WRITTEN — read, do not re-derive

```
PLAN_CHECKLIST.md                     the Three-Database Operating Plan.
                                      §2 tools · §3 agents · §5.1 the four
                                      gates · §6 launch gates · §7 the
                                      fourteen days. THIS IS THE PLAN.
ThingDaddy_Device_Record_Spec_1-2-3   all five pillars + two worked
                                      exemplars, KingFisher Apex and
                                      QuantStudio 5, both page-cited
claude_00_THE_THINGDADDY_YES_NO_DISCRIMINATOR
claude_00_working_standard_kj          tell me how things really are
claude_00_RULE_clear_channel_communication
claude_VERIFIED_GS1_ROOTS_REGISTRY_2026-08-13   CHECK HERE BEFORE ASKING
                                                KJ FOR A PREFIX
claude_research_allotrope_sila_p5graph_config_not_code   the 19 Jul thesis
claude_ARCH_SiLA_Allotrope_stack_blueprint_and_AFO_2_1_2_grounding
claude_VOCAB_PACK_ALLOTROPE_AFO_ADM_ADF_grounded
claude_CORRECTION_AFO_2_1_2_domain_coverage_and_extension_repoint
claude_TARGET_sila_allotrope_instrument_makers   44 companies, sourced
claude_The_Story_of_GSRN_and_SRIN                the agent identity model
ThingDaddy_Prototype_vocabulary_packs.json       12 packs, ratified
claude_THINGDADDY_PHASE_LOG.md                   if a rule is SOLID it is
                                                 a passing test — do not
                                                 re-litigate
```

---

*Every line here was learned once and paid for once. The cost of re-deriving it
is KJ's time, and that is the most expensive thing in this project.*
