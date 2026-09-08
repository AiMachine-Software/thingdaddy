# CLAUDE.md — ThingDaddy Platform (root contract)

**Claude Code reads this file at the start of every session. It is the single source of
truth for how ThingDaddy is built. Read it first, every time. Nothing below is optional.**
If a task conflicts with anything here, stop and surface it — the rules win.

Founder & CEO: Kevin J. Kail (KJ). Works primarily from iPhone in short directive bursts;
expects large, complete, structured outputs. Verify understanding before building — never assume.

---

## 0. The mission

**Everything connected to everything, on one In-Context Identity spine.**

**What ThingDaddy gives a thing: a Unique In-Context Digital ID.** *Unique* — guaranteed by rooting in a prefix (prefix-is-root; no prefix, no uniqueness). *In-context* — it carries the thing's rules (drivers), events (workflows), and relationships (graph); it means something in the graph, never in isolation. Never call it a "true identity" or "digital twin" — those import the wrong, isolated, passive notion. It is a unique, in-context, prefix-rooted digital ID.

ThingDaddy.com is the registrar of the physical world's namespace — the "GoDaddy of the
physical world." It gives every physical thing (machine, sensor, location, document, party,
agent) a verified, machine-readable identity rooted in a GS1 company prefix, then projects
that identity onto drivers, workflows, cloud/edge, a knowledge graph, and an AI/MCP layer.

We build the largest pre-built base of real prefixes, driver templates, and workflow
templates — with an easy flow and global deployability — so every entity, organic or
digital, can *claim* a true identity graph rather than build one from scratch.

**End mission: the largest Physical AI graph with In-Context IDs, by September 15.**

Test every build against three questions:
1. **Biggest base** — does it grow the base of real prefixes, drivers, workflows, edges?
2. **Easy flow** — does it move toward land → find your company → claim → manage (GoDaddy-simple)?
3. **Global deploy** — does it work everywhere, no walled dependency?

---

## 1. The canonical laws (NEVER violate — the rules ARE the product)

A graph of everything is only trustworthy if integrity is a property of the RULES, enforced
by construction, not of human diligence. These hold in code, in data, and in anything generated.

1. **Prefix is root.** Every identity roots in a GS1 company prefix — the prefix IS the
   namespace. No prefix, no namespace, no identity. Every entity — company, human, OR AI
   agent — needs one to participate. In-context IDs are the "senses"; data carriers trigger them.

2. **Caterpillar→Butterfly (custody transfer = identity transformation).** When an asset changes
   custody via PO + paid invoice, the new owner may assign a new identity in *their* namespace.
   The OEM identity never dies — preserve it as an immutable `originGIAI` link (written once,
   never overwritten). This is the provenance spine and warranty back-channel. Distinguished from
   GRAI association (rental/returnable = association only; both owners keep their IDs).

3. **One identity, many carriers.** A GS1 EPC URN can have many carriers at once (RAIN RFID,
   NFC/HF, 1D/2D barcode, GS1 Digital Link, firmware, cloud ARN, domain, human-readable). NEVER
   assume a single carrier is "the" trigger — write "via the appropriate data carrier" or list
   them. The EPC URI is the identity; carriers are how it's read. A GTIN on a box ≠ a GIAI on the
   serialized asset inside — two identity types, two events.

4. **Verified-or-exception (NEVER fabricate).** Every identity value is GEPIR/GDSN/GUDID-verified
   or written as an explicit NAMED exception. Candidate prefixes are first-class state. Nothing
   mints on a guess. DEMO-namespace identities are candidates until claimed; the claim is the
   verification moment.

5. **Standards-based, neutral.** Built on GS1 EPC URN — ratified, universally adopted, infinitely
   expandable, covers every thing type. Neutral by necessity: no walled vendor can be the
   universal graph. This is WHY the truth is derivable and pre-population is honest — computed
   from real sources, never invented.

**Simulation is labeled, never asserted.** When pre-populating edges at scale, every simulated
edge is `state=candidate`, `source=simulation`, `inferred=true`. Real evidence promotes it to
verified. The line between simulated and verified is never blurred.

---

## 2. The model (shared language — use these exact terms)

- **workspace = prefix = tenant = billing unit.** A user's workspace IS their prefix namespace.
- **Every GLN hosts a symphony.** A location's assets (GIAIs) are the players; their SiLA drivers
  are **The Rules** (what they may play); their Allotrope workflows are **The Events** (what they
  do, and when); their edges are the ensemble. A location's repertoire = what its assets' drivers
  and workflows allow.
- **A GSRN conductor — organic or digital — invokes the performance.** A human technician and an
  AI agent are the same kind of accountable, provenance-leaving node. The human–AI partnership,
  encoded.
- **Things friend things.** A data carrier read in the context of another triggers a friending
  event — an edge in the graph.
- **It all lands in the AI Graph**, provenanced forever — the substrate of an intelligent
  digital civilization.

### The 5 pillars (the workspace navigation, in order)
1. **In-Context IDs** — identities (prefix, GLNs, GIAIs, GSRNs)
2. **SiLA Drivers** — The Rules (what each asset may do)
3. **Allotrope Workflows** — The Events (what each asset does, when)
4. **Cloud Bindings** — map identities/drivers/workflows to GCP/Azure/AWS
5. **AI Graph** — everything connected: symphonies, friendings, provenance

---

## 3. The population service — THE CORE (current architecture)

The clean core built this cycle. Isolated: own DB (`thingdaddy_population`), own port (`8787`),
API boundary. Only VERIFIED data crosses to the platform. **The platform talks to it over HTTP —
it never reaches into the population database directly.**

Registry today: **81,928 real rows** (GDSN 80,993 + GUDID 928 + 7 verified seed). All real;
synthetic scale-test rows purged. Gate holds (0 verified-without-prefix).

### The population API
- `GET  /search?q=…&state=…&mo=…&source=…` — keyset search, max 20 (name / prefix / GLN)
- `GET  /record/:id` · `GET /record/prefix/:prefix`
- `POST /ingest` — batch upsert; ALWAYS lands candidate|exception, **never verified**
- `POST /gate/:id` — the SOLE promotion path to verified (defers to the DB CHECK constraint)
- `GET  /verified` — the platform's sole cross-boundary read
- `GET  /stats` · `GET /health`

**The gate is enforced in the database:** a CHECK constraint rejects `verified` without a
`prefix`. Do not bypass it. The gate is the point. Every write appends a `party_event` in the
same transaction (provenance). Re-ingest never downgrades a verified row.

The registration gate rule is universal: agents **propose**; only verified rows **register**.
Manual registration, Register Agent (TD-A-12), Population Agent (TD-A-05), and Demo Builder
(TD-A-30) all route through the gate. Never mint around it.

---

## 4. Verified prefixes — the ONLY real ones

GEPIR-confirmed. Everything else is a candidate until confirmed. (7 seed parties in the registry.)

| Company                         | Prefix     | GLN            | MO         |
|---------------------------------|------------|----------------|------------|
| Telular Corporation             | 0702054    | 0702054000004  | GS1 US     |
| Western Research 3000, Inc.     | 0899728002 | 0899728002003  | GS1 US     |
| Samsung Electronics Co., Ltd.   | 8806088    | 8801643000011  | GS1 Korea  |
| ASML Holding N.V.               | 8719011    | —              | GS1 NL     |
| Intel Corporation               | 0675900    | —              | GS1 US     |
| Micron Technology, Inc.         | 0805795    | —              | GS1 US     |
| Honeywell International Inc.     | 0662498    | —              | GS1 US     |

- DEMO prefixes use the form `0DEMO…` and MUST be flagged "candidate — pending Verified-by-GS1"
  everywhere they appear. The EPC URN *syntax* may be real; only the prefix digits are placeholders.
- Entity resolution: a GEPIR name search returns many namesakes (e.g. "Samsung" → hundreds of
  legal entities). Resolve the true operating entity via name signals + GS1 MO band + an LEI/GLEIF
  authority step. Never promote to VERIFIED without a confirmed prefix AND an authority match.

---

## 5. Repo layout

```
thingdaddy/
  apps/web/     the web app (React + Vite, one router):
                  src/platform/   the V4 platform (single file) — route /
                  src/thingsite/  the ThingSite flow S1-S6 (React port of td_screens_live) — route /thingsite
                  src/registry/   the population registry UI — route /registry
                  public/demo/    the legacy single-file HTML demos — route /demo
  apps/api/     the population API (Express over Postgres) — the registration seam
  population/   the registry data tier: schema, seed, loaders, fleet tooling — THE CORE
  agents/       the population fleet (loops feeding the API's /ingest)
  deploy/       Docker: one image = API + built web app, seeded Postgres
  docs/         mission, charter, blueprints, roadmap, setup playbook
  CLAUDE.md     this file — the contract
```

Build / run: `npm install` then `npm run dev` (web), `npm run dev:api` (API),
`npm run build` (static site into dist/). See README.md.

Note: **Build 44** (the prior ~37K-line unified React file) is a **source to HARVEST FROM**, not
a pattern to repeat. Build fresh on the clean population core; migrate Build 44's proven components
(EPC encoding, GS1 standards, drivers, workflows, graph) into the 5-pillar structure. Do not
create new monolith files.

---

## 6. The agent fleet (TD-A-00…32)

33 GSRN-identified agents across 9 families (F0 Orchestration/Identity, F1 Ingestion/Population,
F2 Verification/Governance, F3 Registration/Minting, F4 Relationship/Graph, F5 Drivers/Workflows,
F6 Cloud-Edge/Binding, F7 Physical-AI/MCP/Action, F8 Demo/Book/Public). Every agent carries a
GSRN passport (issued by TD-A-01) and is governed by verified-or-exception.

Two roles (map to the two API endpoints):
- **Discovery agents** (GUDID drop-folder, GTIN web-scan, GDSN, EDGAR/gov) → `POST /ingest` →
  land candidates. They FILL the registry.
- **Verification agents** (DUNS, LEI bridge, product-name cross-ref, GEPIR) → `POST /gate` →
  promote candidates. Verified requires CONVERGENCE of independent witnesses ending in GEPIR
  confirmation. Conflicts stay unresolved — never a guessed winner.

The loop-agent package lives in `agents/thingdaddy_loops/` (self-test passes; live connectivity
confirmed). Next: fix the GLEIF connector (302 redirect → `.json.zip` → stream-parse with ijson),
wire output to `POST /ingest`, then schedule via launchd. `[IP]` agents are candidate inventions
(passport pattern, populate–verify gate, illustrative-until-verified discovery).

---

## 7. Standing IP practice

Continuously scan all work for candidate patentable IP. When a novel mechanism, method, schema,
or workflow emerges, flag it, sketch the core claim, and map it to the TD-M master-family register
(new family vs. extension). Surface it proactively. Keystone open item: **TD-M-50** —
pre-populated graph & prefix-claim re-rooting (pre-populate under a DEMO prefix; company claims by
re-rooting onto their verified prefix; immutable origin links back to DEMO-staged origins).
Candidate: **TD-M-51** — LEI-to-prefix bridge (~3M LEIs vs. ~2M prefixes). Patent language is
invention-disclosure work product — never a filing or patentability claim.

---

## 8. How we build (Claude Code)

- **No blank pages.** Adapt a proven source to the mission: GoDaddy for the flow, Build 44 for
  proven components to harvest, the Charter for the rules. Reuse, don't reinvent.
- **Isolation over entanglement.** Services with API boundaries. No new 37K-line monoliths.
- **Prove before you commit.** Build → test against reality → commit. **One concern per commit.**
  Work on `feature/<name>` branches; merge to `main` via pull request.
  Until GitHub/team is set up, KJ works solo — commit directly to main; no feature branches/PRs
  yet. Switch to the branch+PR workflow when the team joins.
- **Show the plan before writing code** on anything non-trivial. Surface assumptions; never guess.
- **Test after edits.** Parse-check the platform; run the agent self-test; confirm the gate still
  holds back unverified rows before committing.
- **Never commit secrets.** `.env`, keys, `node_modules/`, and raw data feeds are git-ignored.
- **Never assume understanding — verify it.** If intent isn't clear, ask before building.

### The decision test
> Does this serve everything-connected-to-everything on one spine — growing the base, easing the
> flow, deployable globally — on rules that do not bend? If it fragments the spine or bends a
> rule, it does not belong.

---

## 9. Writing rules (all user-facing content)

- Anti-AI writing rules are standing: avoid banned words/phrases ("delve," "harness," "leverage,"
  "tapestry," "boasts," "in the realm of," "it's worth noting," "seamless," "not only… but also"
  scaffolding, em-dash throat-clearing). Write plainly and directly.
- Say **"legacy IDs,"** never "old IDs." Use exact EPC URN syntax always. Describe a GLN/prefix as
  "verified through GEPIR/GS1" only when it actually is. Real company names imply no endorsement.
- Document palette: darkened grays (#3A424E body captions) so light text stays readable.
- Never fabricate a GS1 prefix, an LEI, a citation, or an affiliation. If unknown, say so and mark
  it an exception.

---

## Do not
- Fabricate a prefix, GLN, edge, LEI, citation, or status. Unresolvable → candidate or named exception.
- Let the platform write to the population database directly (go through the API).
- Promote to `verified` outside the gate.
- Commit secrets, `.env`, `node_modules/`, or raw data feeds.
- Rebuild what Build 44 already proves — harvest it.

---

*We reached the summit first — the AI Graph, MCP, a real registry. Now we build back to the
trailhead, registration forward, with the mission in hand. Build honestly, on rules that hold,
toward the largest Physical AI graph with In-Context IDs, by September 15.*
