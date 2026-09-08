# LESSON (canon) · Crash-test dummy #2 — the correction that installed the next defect

**5 September 2026. Status: SOLID once KJ ratifies §6. Book + phase-log canon.**
Companion to `lesson_crash_test_dummy_we_dont_cheat_2026-07-20.md`.

**The first crash-test dummy cost a day. This one cost seven weeks, reached a published
book, a live MQTT topic and an OPC-UA node — and it was planted by the fix for the
first one.**

---

# 1 · WHAT HAPPENED

**20 July.** The `0614141` ghost is evicted. `verified_prefixes.json` is rewritten to hold
only real, confirmed prefixes. It ends with **one entry**:

> `diazyme.com → 0817089` **(GEPIR-verified, 184 GUDID)**

**GEPIR WAS RETIRED ON 31 DECEMBER 2023 — nineteen months earlier.** No authority was
consulted. `0817089` is a *plausible parse* of the GLN `0817089020009`, and it was written
into the one file the population agent roots against, wearing an authority's name.

**That is the cardinal sin again, in the remedy for the cardinal sin.**

**22 July.** Two instruments are given identities **by hand**:

```
DZ-Lite c270        urn:epc:id:giai:0817089.1
DZ-Lite 3000 Plus   urn:epc:id:giai:0817089.2
"One changed digit per machine is the whole differentiator."
```

Not minted through the engine. Typed.

**5 September.** Verified by GS1, read by hand on gs1.org:

```
Search "Diazyme", United States → 2 results

081708902   GS1 Company Prefix · GLN 0817089020009 · GS1 US · updated 1 Jul 2026
081730202   GS1 Company Prefix · GLN 0817089020009 · GS1 US · updated 7 Jul 2026
```

**`0817089` is not a licence key. It does not appear. Both licences are NINE digits.**
And Diazyme holds a **second prefix nobody in the record had ever seen.**

The GS1 encoder, given a raw GIAI, puts the boundary in the same place:

```
(8004) 08170890245678  →  urn:epc:id:giai:081708902.45678
(8004) 0817302028765   →  urn:epc:id:giai:081730202.8765
```

**Three independent GS1 surfaces agree: the search, the licence record, the encoder.**

---

# 2 · WHY IT SURVIVED SEVEN WEEKS — the error validated itself

**This is the part worth reading twice.**

```
our hand-written GIAI      urn:epc:id:giai:0817089.2
rendered without the dot   081708902
the real licence key       081708902
```

**A wrong root plus a hand-written serial produced the right string.**

Every glance at `081708902` in the data looked *correct*, because it was — as a licence key.
It was simply not what we had made. **The two cheats did not compound; the second one
CONCEALED the first**, and it concealed it by accident, which is why nobody caught it.

**Had the engine minted those GIAIs, it would have checked the prefix and refused in July.**
A hand-written key skips the one check that would have caught a hand-taken root. **The two
cheats are one failure: nothing had to prove itself.**

---

# 3 · IT WAS RAISED, RULED, AND LEFT OPEN

**7 August.** The conflict surfaces during the Book 4 audit:

> **Ruling: the authority decides, we do not derive.** The GTIN digit-run `081708902` does
> NOT confirm a 9-digit GCP (partitions both ways). GEPIR/Book 4 evidence shows licence key
> `0817089`. So **`081708902` is on hold — not treated as verified — until Verified by GS1
> states the length by hand.**

And on the same day's open list:

> **Settle Diazyme's prefix in VBG** by hand (`0817089` vs `081708902`) — unblocks Book 4,
> the DB row, and the engine's GCP-length ruling in one lookup.

**The ruling was right. The lookup was never done.** It sat open for four weeks while
everything downstream kept building on the unsettled root.

**And the ruling's own evidence was already compromised** — "GEPIR/Book 4 evidence shows
`0817089`" cites a dead registry and a document that had itself inherited the error.
**Two mirrors of the same unverified value, read as two sources.**

---

# 4 · THE CASCADE

Everything rooted on a key the authority does not issue:

```
party.prefix · 252 nodes · the GLN parse
gdti:0817089.1.2                 the issued SiLA driver
gdti:0817089.2.1 … .2.6          all six AFO methods
cpi:0817089.100                  the CPID
giai:0817089.1 · .2 · .1000 · .1002
dz/giai/0817089.2/telemetry      a LIVE AWS MQTT topic
ns=2;s=giai:0817089.2            a LIVE OPC-UA NodeId
Book 4 — 41 uses, published
the SiLA XML · the AFO JSON · every screen built on 5 September
```

**And `081730202` — a second real licence — appears nowhere in the record.** Not in any
markdown, not in any SQL. We knew about neither of Diazyme's two prefixes.

---

# 5 · WHAT FOUND IT, AND WHY THAT MATTERS MORE THAN THE FIX

**A re-derivation harness that refused to trust its own implementation.**

`td_rederive.py` was built to repeat `gcp_cut` from recorded inputs and report
reproduced / refuted / cannot-repeat. Before judging anything it runs a **positive
control**: reproduce a value KJ read by hand.

```
POSITIVE CONTROL  00817089020658 → expected 0817089
                  got 081708902   (table entry "0817", gcpLength 9)
                  FAILED

REFUSED  This implementation cannot reproduce a value read by hand against
         Verified by GS1, so it has NO STANDING to call anything refuted.
         Nothing was judged.
```

**It declined to judge 12,047 claims — and in declining, walked back through a two-digit
error to the demo root.**

**A tool that had trusted itself would have called `081708902` refuted and moved on.**
The refusal was the finding. **Build the control before the experiment, and make failing it
fatal.**

**Also note what the GCP Length Table said all along: `0817 → 9`.** The arithmetic was
right and the recorded hand-read was wrong. The 7 August ruling — *the authority decides,
we do not derive* — is still correct as a rule; the failure was that **the thing recorded
as a hand-read had never been read from an authority at all.**

---

# 6 · THE RULES — additions to canon, for ratification

```
1  A CORRECTION CAN INSTALL THE NEXT DEFECT.
   The fix for crash-test dummy #1 wrote the root of #2 into the one file the
   population agent trusts. A remedy is a write, and every write is subject to
   every rule. AUDIT THE FIX AS HARD AS THE FAULT.

2  A SOURCE NAME IS A CLAIM AND MUST BE TRUE ON THE DAY IT IS WRITTEN.
   "GEPIR-verified" on 20 July 2026 named a registry retired 31 December 2023.
   Nobody could have consulted it. The label was the fabrication, not the value.

3  AN ERROR THAT VALIDATES ITSELF IS THE HARDEST CLASS.
   giai:0817089.2 rendered as 081708902 — the real licence key. Every glance
   confirmed it. Where a wrong value LOOKS right, only RE-DERIVATION finds it;
   inspection never will.

4  THE SEPARATOR MUST TRAVEL.
   A GIAI written without its dot is indistinguishable from a company prefix.
   Six such values were found on 5 September and read as containment findings.
   THE BOUNDARY IS NOT IN THE DIGITS — it must be carried, never inferred.

5  NO EPC KEY IS EVER HAND-WRITTEN.
   Generated by the engine, or admitted via admit() and marked admitted.
   THERE IS NO THIRD CATEGORY, and this failure used one. A hand-written key
   skips the only check that would catch a hand-taken root.

6  A CONTROL BEFORE AN EXPERIMENT, AND FAILING IT IS FATAL.
   A tool that cannot reproduce a known-good value has no standing to judge
   anything. Refusing to run IS a result.

7  AN OPEN RULING IS AN OPEN WOUND.
   "On hold until VBG states it by hand" was correct on 7 August and unactioned
   on 5 September. Everything downstream kept building. A ruling that names a
   required read is not settled until the read happens.
```

---

# 7 · THE REMEDY — and it must hit the source, not the mirror

**Rule 4 of the first crash-test dummy applies to its own successor.**

```
RE-ROOT      0817089 → 081708902, everywhere. 0817089 recorded as a
             SUPERSEDED READING, never deleted — it is cited in a published book.
RE-MINT      the GIAIs THROUGH THE ENGINE, not typed:
             urn:epc:id:giai:081708902.1 · .2
ADD          081730202 as Diazyme's second licence, candidate until its own read
RE-READ      the other eight recorded hand-reads against VBG. If this one was
             never read from an authority, the others need confirming too —
             Chromsystems 42503175 · Honeywell 0781410 + 0662498 · Thermo
             Asheville 081577302 + 081693402 · Thermo Madison 0850000184 +
             08600008927 · Thermo CDX Fremont 0884883
CAPTURE      the VBG screens go INTO THE REPO beside the transcriptions. A
             hand-read whose source image is not in the record is a claim citing
             a document the register does not hold.
```

**And the correction is cheap in the way it should be.** Nothing minted needs unwinding,
because **nothing here was properly minted.**

---

# 8 · WHY IT IS AN ASSET

**The first crash-test dummy proved verify-or-exception with a receipt. This one proves
something harder: that the discipline catches the discipline's own repairs.**

Seven weeks, a wrong root, a published book, a live MQTT topic — **found by a tool that
refused to trust itself, on a control it failed.** Nobody spotted it by reading, because
reading was exactly what could not find it.

**That is the argument for re-derivation over provenance sentences, made on ourselves, with
a date and a cost.** It belongs in the methodology book beside the first, and the pair say
the thing no competitor can say:

> **We are strictest with ourselves, we publish the receipts, and when the fix was the
> fault we published that too.**

---

*What are the chances the wrong root would render as the right licence key? It does not
matter. It happened, it survived seven weeks, and the only thing that found it was a
machine that would not take its own word for anything.*
