# ThingDaddy — Engineering Standing Instructions (root CLAUDE.md)

Claude Code reads this file at the start of every session. It is the single
source of truth for how ThingDaddy is built. Nothing below is optional.

---

## 0. What ThingDaddy is

ThingDaddy.com is the "GoDaddy of the physical world" — a GS1 EPC URN
physical-identity registry platform. It gives every physical thing (machine,
sensor, location, document, party) a verified, machine-readable identity rooted
in a GS1 company prefix, then projects that identity onto cloud/edge, drivers,
workflows, a knowledge graph, and an AI/MCP layer.

Founder & CEO: Kevin J. Kail (KJ). Works primarily from iPhone in short
directive bursts; expects large, complete, structured outputs.

---

## 1. The four canonical laws (NEVER violate)

1. **Prefix is root.** Every identity roots in a GS1 company prefix. The prefix
   is the namespace. In-context IDs are the "senses"; data carriers trigger them.

2. **Caterpillar→Butterfly (custody transfer = identity transformation).** When
   an asset changes custody via PO + paid invoice, the new owner may assign a new
   identity in *their* namespace. The OEM identity never dies — preserve it as an
   immutable `originGIAI` link (written once, never overwritten). This is the
   provenance spine and the warranty back-channel. Distinguished from GRAI
   association (rental/returnable = association only, both owners keep their IDs).

3. **One identity, many carriers.** A GS1 EPC URN can have many carriers at once
   (RAIN RFID, NFC/HF, 1D/2D barcode, GS1 Digital Link, firmware, human-readable).
   NEVER assume a single carrier is "the" trigger. Write "via the appropriate data
   carrier" or list them. The EPC URI is the identity; carriers are how it's read.

4. **Verified-or-exception (NEVER fabricate).** Every identity value is
   GEPIR/GDSN/GUDID-verified or written as an explicit named exception. Candidate
   prefixes are first-class state. Nothing mints on a guess. DEMO-namespace
   identities are candidates until claimed; the claim is the verification moment.

---

## 2. The registration spine (the single gate)

- `addParty()` is the ONE gate for registration. No prefix → no registration →
  no mint. It rejects any party without a prefix and mints the identity set only
  when a prefix is confirmed.
- Manual registration, Register Agent (TD-A-12), Population Agent (TD-A-05), and
  Demo Builder (TD-A-30) all route through `addParty()`. Agents **propose**;
  only verified rows **register**. Never mint around the gate.

---

## 3. Verified prefixes — the ONLY real ones

These are GEPIR-confirmed from real screenshots. Everything else is a DEMO
candidate until confirmed.

| Company                         | Prefix     | GLN            | MO         |
|---------------------------------|------------|----------------|------------|
| Telular Corporation             | 0702054    | 0702054000004  | GS1 US     |
| Western Research 3000, Inc.     | 0899728002 | 0899728002003  | GS1 US     |
| Samsung Electronics Co., Ltd.   | 8806088    | 8801643000011  | GS1 Korea  |

- DEMO prefixes use the form `0DEMO…` and MUST be flagged
  "candidate — pending Verified-by-GS1" everywhere they appear.
- The GS1 EPC URN *syntax* may be real; only the prefix digits are placeholders.
- Entity resolution: a GEPIR name search returns many namesakes (e.g. "Samsung"
  → 305 legal entities). Resolve the true operating entity via name signals +
  GS1 MO band + an LEI/GLEIF authority step (TD-M-50/51). Never promote to
  VERIFIED without a confirmed prefix AND an authority match.

---

## 4. Repo layout

```
platform/  ThingDaddy_V4_Unified.jsx   — the V4 unified React platform (one file, Vite)
agents/    thingdaddy_agent_fleet.py   — base fleet: population→verify→register loops
           thingdaddy_agent_fleet_loopB.py — F4 relationship/graph + F5/F6 driver/binding
           td_live_connectors.py       — EDGAR/USASpending/SAM live connectors
           entity_resolution_agent.py  — generic namesake resolver (Samsung = worked example)
data/      loopB_seed_associations.json — graph export the platform's TD:GRAPH renders
docs/      deliverables (docx/pptx/xlsx)
```

See `platform/CLAUDE.md` and `agents/CLAUDE.md` for area-specific rules.

---

## 5. The agent fleet (TD-A-00…32)

33 GSRN-identified agents across 9 families (F0 Orchestration/Identity, F1
Ingestion/Population, F2 Verification/Governance, F3 Registration/Minting, F4
Relationship/Graph, F5 Drivers/Workflows, F6 Cloud-Edge/Binding, F7
Physical-AI/MCP/Action, F8 Demo/Book/Public). Every agent carries a GSRN
passport (issued by TD-A-01) and is governed by verified-or-exception.

- `[IP]` agents are candidate inventions: TD-A-15/18 → IP-C-10, TD-A-27 → IP-C-09,
  the passport pattern → IP-C-08, the populate–verify gate → IP-C-07.
- The Agent Builder Registry module (`agent_registry`) in the platform is the
  living index; live agents link to their running module.

---

## 6. Standing IP practice

Continuously scan all work for candidate patentable IP. When a novel mechanism,
method, schema, or workflow emerges, flag it, sketch the core claim, and map it
to the TD-M master-family register (new family vs. extension). Surface it
proactively. Keystone open item: **TD-M-50** — pre-populated graph & prefix-claim
re-rooting (pre-populate under a DEMO prefix, company claims by re-rooting onto
their verified prefix, immutable origin links back to DEMO-staged origins).
Patent language is invention-disclosure work product — never a filing or
patentability claim.

---

## 7. How to work in this repo (Claude Code)

- **Edit in place.** The platform is one ~37K-line file. Make surgical
  `str_replace` edits; do NOT regenerate the whole file.
- **Parse-check after platform edits:** `./platform/parse-check.sh` (Babel TSX
  parse). It must print `PARSE OK` before you commit.
- **Test agents after edits:** `python3 agents/thingdaddy_agent_fleet.py --status`
  and run the loop; confirm the gate still holds back unverified rows.
- **Never commit secrets.** SAM.gov needs a free key via `.env` (git-ignored).
- **Commit in small, described steps.** One concern per commit.

---

## 8. Writing rules (all user-facing content)

- Anti-AI writing rules are standing: avoid the banned words/phrases list
  (e.g. "delve", "tapestry", "boasts", "in the realm of", "it's worth noting",
  em-dash-heavy throat-clearing, "not only… but also" scaffolding). Write plainly
  and directly.
- Palette for documents: darkened grays (3A424E for doc body captions, #4B5563
  in demos) so light text stays readable.
- Never fabricate a GS1 prefix, an LEI, a citation, or an affiliation. If unknown,
  say so and mark it an exception.
