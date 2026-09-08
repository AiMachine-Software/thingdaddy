# The dev seed

```
A DATED SNAPSHOT OF REAL PRODUCTION ROWS, FOR LOCAL DEVELOPMENT.

NOT fabricated. These are real GS1 prefixes with real GUDID provenance.
NOT authoritative. thingdaddy_population on the Mac mini is the record.
NOT a source of truth. Nothing here flows back.
NOT test data. Do not edit rows to make something render.

REGENERATE, NEVER EDIT. Cheap to remake, expensive to trust.
```

See `MANIFEST.txt` for the date and the row counts as taken.

## Bring it up

```
createdb thingdaddy_population
./seed_up.sh
cd ../api && npm install && npm start
```

Then open `population/fill/td_screens_live.html` in a browser.

The database is named `thingdaddy_population` so `api/.env` needs no change.
You will also need `INGEST_TOKEN` in `.env` if you touch a write endpoint —
though nothing in this seed exercises one.

## What is in it

| party_id | prefix | company | state | claims |
|---|---|---|---|---|
| 4090847 | 081627002 | Illumina, Inc. | **verified** | 88 |
| 4090838 | 081577302 | Thermo Fisher Scientific (Asheville) LLC | **verified** | 70 |
| 4090839 | 081693402 | Thermo Fisher Scientific (Asheville) LLC | **verified** | 15 |
| 4153997 | 0817089 | DIAZYME LABORATORIES, INC. | candidate | 14 |

Thermo Fisher Asheville holds two prefixes on two rows. That is
one-prefix-one-ThingSite, correct, carried as found.

## What is EMPTY, and why that is not a bug

```
node (for these parties)   0     92,678 nodes exist; none backfilled here
association               0
asset · edge · content_doc · party_origin   0
```

**This is production's current state, not a gap in the seed.** The same
endpoints return the same emptiness on the Mac mini today.

`/node/by-legacy/party/:id` returns 404 by design. From the API's own source:
*"404 when the spine hasn't been backfilled for this party (honest — the UI
shows 'not on the spine yet', never fakes a node)."*

So the graph and association screens show the empty state deliberately.

## Three more things that are correct, not broken

**`/stats` returns 4.** It counts the whole database and the database has four
parties.

**S1 shows "Over 11,000,000 identities".** A hardcoded string, not from
`/stats`. Flagged in PR #17 finding 3 and marked TODO on the Open list. It will
read eleven million over a four-row database. Unruled.

**`const RECORDS` still exists at line 285 of `td_screens_live.html`.** The file
is a hybrid — some screens call the API, some still read the fixture. Pointing
the remaining paths at the API is an open item.

## Endpoints this seed serves

```
/health · /stats · /search?q= · /verified
/record/:id · /record/prefix/:prefix
/party/:id/completeness
/party/:id/epcis · /party/:id/assets     served, empty
/node/by-legacy/party/:id                404, honest, by design
```

Write endpoints are not exercised. `/gate/:id` additionally needs
`population/verify/verify_cli.py`, which is not in git.

## Disposal

This seed dies when claims are re-keyed to prefix under the 4 September ruling.
Regenerate — do not migrate it, do not edit it, do not write tooling that
assumes its shape.
