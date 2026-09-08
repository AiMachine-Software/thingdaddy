-- ============================================================================
-- Migration 007 — carrier tier. Cycle 2 · Core.
--
-- A carrier hangs off the ASSET (the correct level — the Cycle-1 deferral made
-- real). A carrier is a GATED PROFILE, not a fabricated encoding:
--
--   * the ENGINE gates admissibility (e.g. RAIN-96 packs the variable part as a
--     number → numeric component only). The population API re-affirms this
--     through the ONE door (mint_cli) before a profile lands.
--   * the reference engine returns only the URN — it does NOT emit the encoded
--     RAIN-96 / GS1-128 / DL value. So `value` is NULL until Pom's authoritative
--     engine emits a real encoding. We NEVER hand-build a carrier value.
--   * verified-or-exception, mirrored: a carrier lands `candidate`; it may only
--     become `verified` when a real engine-emitted encoding is present
--     (carrier_gate_value_required — the same spirit as the party prefix gate).
--
-- MAP NOTE: the `value` column is the seam Pom's engine fills. Everything else —
-- admissibility, provenance, one-profile-per-carrier — the registry owns now.
--
-- Additive, idempotent. Apply: psql -v ON_ERROR_STOP=1 -d thingdaddy_population \
--   -f db/migrations/007_carrier_tier.sql
-- ============================================================================
CREATE TABLE IF NOT EXISTS carrier (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset_id     bigint      NOT NULL REFERENCES asset (id) ON DELETE CASCADE,
  carrier_type text        NOT NULL,               -- RAIN-96 | GS1-128 | DL (closed vocab).
  value        text,                               -- engine-emitted encoding. NULL until Pom's engine fills it (the seam).
  state        text        NOT NULL DEFAULT 'candidate',
  source       text        NOT NULL,
  first_seen   timestamptz NOT NULL DEFAULT now(),
  last_updated timestamptz NOT NULL DEFAULT now(),

  -- carrier_type is a closed vocabulary (the three declared carrier profiles).
  CONSTRAINT carrier_type_valid  CHECK (carrier_type IN ('RAIN-96', 'GS1-128', 'DL')),
  CONSTRAINT carrier_state_valid CHECK (state IN ('candidate', 'verified', 'exception')),

  -- ══ THE CARRIER GATE (mirrors the party prefix gate) ══
  -- No promotion on an empty encoding: a carrier may only be VERIFIED once a
  -- real engine-emitted value is present. Profiles sit `candidate` at value NULL.
  CONSTRAINT carrier_gate_value_required
    CHECK (state <> 'verified' OR value IS NOT NULL)
);

-- one profile per carrier type per asset (declare RAIN-96 once, DL once, …).
CREATE UNIQUE INDEX IF NOT EXISTS ux_carrier_asset_type ON carrier (asset_id, carrier_type);
CREATE INDEX IF NOT EXISTS ix_carrier_asset ON carrier (asset_id);
CREATE INDEX IF NOT EXISTS ix_carrier_state ON carrier (state);
