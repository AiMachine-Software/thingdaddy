# Restore the ThingDaddy DB locally

A `pg_dump` snapshot of the ThingDaddy database, so the platform service can be built
and proven against real rows locally — without touching production or the gate.

The dump file is shared privately (not in git — it is real data). Ask KJ for
`thingdaddy.dump` if you do not have it.

## Prerequisites
- PostgreSQL installed locally (`psql --version` should print a version).

## Restore (three commands)

    createdb thingdaddy_population
    pg_restore --no-owner --no-privileges -d thingdaddy_population ~/Downloads/thingdaddy.dump
    psql thingdaddy_population -c "select count(*) from node;"

The last line should print a row count in the tens of thousands — that confirms the
restore worked and you are looking at real rows.

If `pg_restore` prints a few "already exists" or ownership notices, that is normal for
`--no-owner --no-privileges`; the data still lands.

## What you now have
- The full schema and the real rows, keyed on the nine gated classes
  (`pgln, sgln, gtin, gdti, giai, gsrn, grai, sscc, cpi`).
- Diazyme rooted on the verified prefix `0817089`; General Atomics candidate (no prefix).

## Ground rules for building against it
- **This is a local snapshot for development.** It is not the shared live DB.
- **Do not commit the dump to git.** It is real data.
- **Build read routes first.** Point the platform service at this local DB and move read
  routes over one at a time.
- **Write routes go through the gate.** Two-writer-only is load-bearing — no second write
  path around the gate. We wire the shared connection and hand over write authority only
  after read routes are proven and gate ownership is settled.

## Refresh
When you need a newer snapshot, ask KJ to regenerate the dump; drop and recreate:

    dropdb thingdaddy_population
    createdb thingdaddy_population
    pg_restore --no-owner --no-privileges -d thingdaddy_population ~/Downloads/thingdaddy.dump
