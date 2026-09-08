# ThingDaddy — Platform Build-Out Plan (week of 2026-07-16)

## Decisions locked
- Build path: clean core — build the wireframe's screens FRESH in population/ui, each wired to the
  real population API. Build 44 is GUIDANCE ONLY — read to understand, build clean. Never wire/copy/ship.
  (Already-extracted catalog data, e.g. platform/data/allotrope_protocols.json, is usable as data.)
- Rhythm: repeating Core -> UI -> Populate cycle, per flow. All three, in order, cycling.
- Near-term gate: GA interview (working date 20 July) — GA-critical flows first.
- UI vocabulary: plain human labels (Location, Organization, Person/Agent), GS1 keys underneath; no "party" on screen (see CUSTOMER_VOCABULARY.md).
- Every release passes RELEASE-CHECK.md.

## Where we are
- Wired (real API): population/ui spine — land -> find -> claim -> manage + 5-pillar shell + Pillar-1
  basics + provenance. ~8 views over the live 81,928-row registry. (PR #4.)
- NOT wired: ~59 wireframe screens (design only) and Build 44's ~128 modules (guidance only).

## The cycle (definition of done per flow)
1. CORE  — API/engine/data model supports the flow (through the contract, gate intact, tests). If the
   flow needs data the registry can't model (drivers/workflows/cloud = not party rows), Core decides
   the model first — never fake it in the UI.
2. UI    — build the flow's screens fresh in population/ui, wired, styled to the wireframe, human vocabulary.
3. POPULATE — load/seed real data (loaders, seeds, entity resolution). Simulation labeled, never asserted.
4. PROVE + LAND — run live on the Mac, screenshot, RELEASE-CHECK, PR through the gate.

## Flow map (prioritized)
- Cycle 0 DONE: spine (find/claim/manage + pillars + provenance).
- Cycle 1 (GA hero): Registration heart — s01,s02 + p1-0..p1-6. GoDaddy find->claim->re-root + Pillar-1
  depth (authority check, role stamps, co-reference, one-machine-five-keys, classify, completeness gate,
  carrier profile). Core: role-stamp edges + completeness surfacing (carriers DEFERRED to Cycle 2).
- Cycle 2: AI Graph + store internals — p5-0..p5-7 + g*. EPCIS event surface; the asset/GIAI + carrier tier.
- Cycle 3: Drivers + Protocols — p2*, p3*. Biggest Core lift: catalog tier (not party rows).
- Cycle 4: Cloud/Edge + Billing + Exceptions — p4*, invoices/keys, x01,x02.

## Populate track (interleaved)
1. Loaders at scale (GDSN ~80k + GUDID) via /ingest (candidate only). Grow past 81,928.
2. Entity resolution / LEI bridge (TD-M-51) — Honeywell/cross-MO constellation (candidate_ip_TD-M-51...).
3. Discovery agents propose; only verified rows register (gate holds).

## This week (through GA 20 Jul)
Cycle 1 complete (GA hero, deep + real) + start Cycle 2 (graph views) + one populate push
(loader run + Honeywell entity-resolution spike). Honest: 59 screens is not one week.

## Cycle 1 . Core scope (building now)
1. Migration 004 — edge += asserter, valid_from, valid_to (nullable).
2. POST /party/:id/edge — role stamp + sameAs, candidate-only, event-stamped, tests.
3. GET /party/:id/completeness — state-aware base report, classification-hook stubbed, tests.
   NO carrier tier (Cycle 2). UI renders DZ-Lite carrier-profile read-only.
