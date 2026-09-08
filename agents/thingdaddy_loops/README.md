# ThingDaddy Loops — Civilization Profiles + Relationship Graph

Two production agent loops that build the digital-civilization graph and keep it current,
sharing one hardened core and one SQLite graph so relationship edges attach directly to
unified company profiles.

- **Loop A — Civilization Profiles.** Matches a GS1 company prefix to each member, unifies
  one legal entity across many GS1 Member Organizations into a single profile, and flags
  companies that need a prefix (routed to the correct MO).
- **Loop B — Relationship Graph.** Adds supplier / customer / custody / subsidiary edges from
  public-disclosure sources, each endpoint resolved to a Loop A profile — turning the profile
  registry into the connected physical graph.

Runnable engine behind the *Registration and Role* chapter and the *LEI-to-Prefix Bridge* in
**Building a Digital Civilization Mosaic**.

## Quick start (Mac mini)

```bash
./setup_macmini.sh          # venv + deps + offline self-test (no network)
# edit config.yaml: net.user_agent (contact email for SEC), sam_gov.api_key (optional)
make run-all                # Loop A then Loop B, live -> ./out
make install-launchd        # schedule daily always-on runs (02:30)
```

Prove the logic offline anytime, with no network and no keys:

```bash
python3 tests/selftest.py
```

## Sources

| Loop | Source | Access | Gives |
|------|--------|--------|-------|
| A | GLEIF Global LEI Index (Golden Copy + API) | free, CC0 | ~3M+ entities; who-is-who + who-owns-whom (the spine) |
| A | openFDA / GUDID | free, no key | structured device records -> candidate prefixes |
| A | Verified by GS1 | licensed MO / Data Hub | confirms prefix + true length (candidate -> verified) |
| B | SEC EDGAR Exhibit 21 | free (User-Agent w/ email) | subsidiary_of edges |
| B | USASpending.gov | free, no key | contracts_with (recipient->agency), supplier_of (sub->prime) |
| B | SAM.gov Entity Mgmt | free api key | parent_of edges + UEI corroboration |

## Standing disciplines (encoded, not optional)

- **Prefix is root** — no prefix, no namespace, no identity; MO resolved from the GS1 Prefix.
- **Verified-or-exception** — every record and edge is `verified` (authoritative source resolves
  both ends), `candidate` (derived / one endpoint provisional — never auto-promoted), or
  `exception` (held open, never fabricated). Verify gates are deterministic Python, not model calls.
- **Candidate prefix is a first-class state** — a GTIN-derived prefix stays candidate until
  Verified by GS1 confirms the true length (Caterpillar -> Butterfly promotion).
- **No raw scraping** — structured, authoritative sources only.
- **Idempotent staging** keyed by `(source, natural_key)` — re-runs never re-resolve.
- **Daily caps as ceilings** — clean stop + resumable cursors. **Append-only** outputs.

## Outputs (`./out`)

`civilization_profiles.csv` · `cross_mo_links.csv` · `needs_prefix_queue.csv`
`graph_nodes.csv` · `graph_edges.csv` · `graph.json` (nodes + edges for visualization)

## Architecture

```
common/     harness (shared SQLite: party, prefix, cluster, needs_prefix, node, edge;
            staging, caps, resumable cursors, append-only writers, resolve_party)
            net (retry/backoff/rate-limit HTTP client) · logging (rotating) ·
            verify (verify_prefix, verify_match, verify_edge) · resolve (fuzzy + union-find) ·
            mo_resolver (GS1 Prefix -> MO) · data/ (gs1_prefix_ranges.csv, gs1_mo_directory.csv)
loop_a/     run.py + connectors/ (gleif, openfda_gudid, verified_by_gs1) + data/fixtures
loop_b/     run.py + connectors/ (sec_edgar, usaspending, sam_gov) + data/fixtures
run_all.py  full pipeline (A then B) on the shared graph
launchd/    com.thingdaddy.loops.plist (daily)  ·  install_launchd.sh  ·  setup_macmini.sh
tests/      selftest.py (both loops, offline)
```

> The GS1 prefix range table is a seed of the well-known allocations. Replace
> `common/data/gs1_prefix_ranges.csv` with the full official list from
> `gs1.org/standards/id-keys/company-prefix` for complete coverage of all 110+ MOs.

## Scaling the initial GLEIF load

The whole LEI population is a large Golden Copy file. For the first build, download the
concatenated/Golden Copy file and stream it (install the optional `ijson`); thereafter use the
delta files (8h / 24h / 7d / 31d) for incremental updates. Cursors resume a capped run.

## IP capture

- **LEI-to-Prefix Bridge** (extends TD-M-50 / TD-M-51): confidence-tiered, verified-or-exception
  mapping of the LEI population to the GS1 prefix population, with a needs-prefix invitation queue
  routed by MO. GS1 prefix is absent from GLEIF's certified-mapping set — the novelty anchor.
- **Cross-MO party unification** via GS1-Prefix-range MO resolution + LEI ownership tree.
- **Disclosure-sourced edge attachment**: resolving public-filing relationship endpoints to
  prefix-rooted profiles, with provisional-node handling under a deterministic edge verify gate.
