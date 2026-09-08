-- ============================================================================
-- Migration 005 — asset tier (GIAI instances). Cycle 2 · Core scaffold.
--
-- "One machine" is an ASSET: a serialized instance (GIAI) rooted in a party's
-- prefix. Carriers and EPCIS events (later Cycle 2 pieces) hang off the ASSET,
-- not the party — the correct level (the Cycle-1 carrier deferral, made real).
--
-- LAWS (enforced at MINT by the engine, not re-checked here):
--   * the GIAI component is minted by the engine (R9 numeric, P32 no-alpha,
--     carrier-gate-safe) — NEVER hand-built. The `urn` column stores only what
--     the engine returned.
--   * verified-or-exception: an asset lands `candidate`; nothing mints verified.
--   * Caterpillar->Butterfly: `origin_asset_id` is the immutable custody link
--     (written once; the OEM identity never dies).
--
-- MAP NOTE: this table is the seam Pom's authoritative engine plugs into. The
-- API mints via a reference-engine shim (mint_cli.py) — a STAND-IN, clearly
-- flagged, that Pom replaces behind the same contract.
--
-- Additive, idempotent. Apply: psql -v ON_ERROR_STOP=1 -d thingdaddy_population \
--   -f db/migrations/005_asset_tier.sql
-- ============================================================================
CREATE TABLE IF NOT EXISTS asset (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  party_id        bigint      NOT NULL REFERENCES party (id) ON DELETE CASCADE,
  prefix          text        NOT NULL,               -- the root prefix the GIAI was minted under.
  giai_component  text        NOT NULL,               -- engine-minted, numeric (R9). No hand-built values.
  urn             text        NOT NULL,               -- exactly what the engine returned (urn:epc:id:giai:...).
  label           text,                               -- human label (e.g. "DZ-Lite c270").
  origin_asset_id bigint      REFERENCES asset (id),  -- Caterpillar->Butterfly custody link. Write once.
  state           text        NOT NULL DEFAULT 'candidate',
  source          text        NOT NULL,
  first_seen      timestamptz NOT NULL DEFAULT now(),
  last_updated    timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT asset_state_valid   CHECK (state IN ('candidate', 'verified', 'exception')),
  -- R9 mirror: the graph body component is digits only (alpha lives only in the
  -- legacy crosswalk, never here). The engine enforces this at mint; this is the
  -- database backstop, same spirit as party_prefix_digits_only.
  CONSTRAINT asset_component_numeric CHECK (giai_component ~ '^[0-9]+$'),
  CONSTRAINT asset_urn_unique UNIQUE (urn)
);

CREATE INDEX IF NOT EXISTS ix_asset_party  ON asset (party_id);
CREATE INDEX IF NOT EXISTS ix_asset_prefix ON asset (prefix);
CREATE INDEX IF NOT EXISTS ix_asset_origin ON asset (origin_asset_id);
CREATE INDEX IF NOT EXISTS ix_asset_state  ON asset (state);
