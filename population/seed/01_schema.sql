--
-- PostgreSQL database dump
--

\restrict dm0sa9mTUbsUaR9vhtT9kQ5jgFy6KDI2oEkhOCNSfFYyBPuUYkjddxxgdydbUfX

-- Dumped from database version 16.14 (Homebrew)
-- Dumped by pg_dump version 16.14 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: epc_urn_valid(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.epc_urn_valid(u text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
DECLARE
  body text; scheme text; rest text; p text[];
  cp text; f2 text; f3 text;
BEGIN
  IF u IS NULL THEN RETURN true; END IF;                 -- NULL = not minted; allowed
  IF position('<' in u) > 0 THEN RETURN false; END IF;   -- placeholder is a proposal, never a valid URN
  IF left(u, 11) <> 'urn:epc:id:' THEN RETURN false; END IF;
  body := substr(u, 12);
  IF position(':' in body) = 0 THEN RETURN false; END IF;
  scheme := split_part(body, ':', 1);
  rest   := substr(body, length(scheme) + 2);
  p := string_to_array(rest, '.');

  IF scheme = 'gdti' THEN
    IF array_length(p,1) <> 3 THEN RETURN false; END IF;
    cp := p[1]; f2 := p[2]; f3 := p[3];
    IF cp !~ '^[0-9]+$' OR f2 !~ '^[0-9]+$' THEN RETURN false; END IF;
    IF length(cp) + length(f2) <> 12 THEN RETURN false; END IF;
    RETURN length(f3) BETWEEN 1 AND 17;

  ELSIF scheme = 'sgln' THEN
    IF array_length(p,1) NOT IN (2,3) THEN RETURN false; END IF;
    cp := p[1]; f2 := p[2];
    IF cp !~ '^[0-9]+$' OR f2 !~ '^[0-9]+$' THEN RETURN false; END IF;
    IF length(cp) + length(f2) <> 12 THEN RETURN false; END IF;
    IF array_length(p,1) = 3 THEN
      IF length(p[3]) < 1 OR length(p[3]) > 20 THEN RETURN false; END IF;
    END IF;
    RETURN true;

  ELSIF scheme = 'pgln' THEN
    IF array_length(p,1) <> 2 THEN RETURN false; END IF;
    cp := p[1]; f2 := p[2];
    IF cp !~ '^[0-9]+$' OR f2 !~ '^[0-9]+$' THEN RETURN false; END IF;
    RETURN length(cp) + length(f2) = 12;

  ELSIF scheme = 'gsrn' THEN
    IF array_length(p,1) <> 2 THEN RETURN false; END IF;
    cp := p[1]; f2 := p[2];
    IF cp !~ '^[0-9]+$' OR f2 !~ '^[0-9]+$' THEN RETURN false; END IF;
    RETURN length(cp) + length(f2) = 17;

  ELSIF scheme = 'giai' THEN
    IF array_length(p,1) <> 2 THEN RETURN false; END IF;
    cp := p[1]; f2 := p[2];
    IF cp !~ '^[0-9]+$' THEN RETURN false; END IF;
    RETURN length(f2) BETWEEN 1 AND 16;

  ELSIF scheme = 'sgtin' THEN
    IF array_length(p,1) <> 3 THEN RETURN false; END IF;
    cp := p[1]; f2 := p[2]; f3 := p[3];
    IF cp !~ '^[0-9]+$' OR f2 !~ '^[0-9]+$' THEN RETURN false; END IF;
    IF length(cp) + length(f2) <> 13 THEN RETURN false; END IF;
    RETURN length(f3) BETWEEN 1 AND 20;
  END IF;

  RETURN false;   -- unknown/unsupported epc scheme
END;
$_$;


--
-- Name: mint_asset(bigint, text, text, text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mint_asset(p_party_id bigint, p_prefix text, p_giai_component text, p_urn text, p_label text, p_source text, p_minted_by text, p_ruleset_version text DEFAULT NULL::text) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
DECLARE new_id bigint;
BEGIN
  IF p_minted_by IS NULL OR btrim(p_minted_by) = '' THEN
    RAISE EXCEPTION 'mint_asset: minted_by is required';
  END IF;
  IF p_urn IS NULL OR NOT epc_urn_valid(p_urn) THEN
    RAISE EXCEPTION 'mint_asset: % is not a well-formed EPC URN (migration 016 grammar gate)', p_urn;
  END IF;
  INSERT INTO asset (party_id, prefix, giai_component, urn, label, source,
                     minted_by, minted_at, ruleset_version)
  VALUES (p_party_id, p_prefix, p_giai_component, p_urn, p_label, p_source,
          p_minted_by, now(), p_ruleset_version)
  RETURNING id INTO new_id;
  RETURN new_id;
END $$;


--
-- Name: mint_node(text, text, text, text, text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mint_node(p_urn text, p_key_type text, p_kind text, p_label text, p_state text, p_source text, p_minted_by text, p_ruleset_version text DEFAULT NULL::text, p_prefix text DEFAULT NULL::text) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
DECLARE new_id bigint;
BEGIN
  IF p_urn IS NULL OR btrim(p_urn) = '' THEN
    RAISE EXCEPTION 'mint_node: a urn is required. To create a node WITHOUT an identity, INSERT directly — that path is open and needs no privilege.';
  END IF;
  IF p_minted_by IS NULL OR btrim(p_minted_by) = '' THEN
    RAISE EXCEPTION 'mint_node: minted_by is required. An identity with no account of where it came from is what this door exists to refuse.';
  END IF;
  IF NOT epc_urn_valid(p_urn) THEN
    RAISE EXCEPTION 'mint_node: % is not a well-formed EPC URN (migration 016 grammar gate)', p_urn;
  END IF;

  INSERT INTO node (urn, key_type, kind, label, state, source, prefix,
                    minted_by, minted_at, ruleset_version)
  VALUES (p_urn, p_key_type, p_kind, p_label, p_state, p_source, p_prefix,
          p_minted_by, now(), p_ruleset_version)
  RETURNING id INTO new_id;
  RETURN new_id;
END $$;


--
-- Name: party_origin_is_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.party_origin_is_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  RAISE EXCEPTION 'party_origin is append-only: % on id % is not permitted',
    TG_OP, COALESCE(OLD.id, NEW.id)
    USING ERRCODE = 'raise_exception';
END;
$$;


--
-- Name: party_search_tsv_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.party_search_tsv_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.search_tsv :=
      setweight(to_tsvector('simple', coalesce(NEW.legal_name, '')), 'A')
    || setweight(to_tsvector('simple', coalesce(NEW.city,       '')), 'C')
    || setweight(to_tsvector('simple', coalesce(NEW.country,    '')), 'C')
    || setweight(to_tsvector('simple', coalesce(NEW.mo,         '')), 'D');
  -- keep last_updated honest on every mutation.
  NEW.last_updated := now();
  RETURN NEW;
END;
$$;


--
-- Name: party_verified_prefix_immutable(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.party_verified_prefix_immutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.state = 'verified' AND OLD.prefix IS NOT NULL
     AND NEW.prefix IS DISTINCT FROM OLD.prefix THEN
    RAISE EXCEPTION 'verified prefix is immutable: party % prefix %->% not permitted',
      OLD.id, OLD.prefix, NEW.prefix
      USING ERRCODE = 'raise_exception';
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: remint_node(bigint, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.remint_node(p_node_id bigint, p_urn text, p_minted_by text, p_ruleset_version text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public'
    AS $$
BEGIN
  IF p_minted_by IS NULL OR btrim(p_minted_by) = '' THEN
    RAISE EXCEPTION 'remint_node: minted_by is required';
  END IF;
  IF NOT epc_urn_valid(p_urn) THEN
    RAISE EXCEPTION 'remint_node: % is not a well-formed EPC URN (migration 016 grammar gate)', p_urn;
  END IF;
  UPDATE node
     SET urn = p_urn, minted_by = p_minted_by, minted_at = now(),
         ruleset_version = COALESCE(p_ruleset_version, ruleset_version)
   WHERE id = p_node_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'remint_node: no node %', p_node_id;
  END IF;
END $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: asset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset (
    id bigint NOT NULL,
    party_id bigint NOT NULL,
    prefix text NOT NULL,
    giai_component text NOT NULL,
    urn text NOT NULL,
    label text,
    origin_asset_id bigint,
    state text DEFAULT 'candidate'::text NOT NULL,
    source text NOT NULL,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    minted_by text,
    minted_at timestamp with time zone,
    ruleset_version text,
    CONSTRAINT asset_component_numeric CHECK ((giai_component ~ '^[0-9]+$'::text)),
    CONSTRAINT asset_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text])))
);


--
-- Name: asset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.asset ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.asset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: association; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.association (
    id bigint NOT NULL,
    subject_node_id bigint NOT NULL,
    object_node_id bigint NOT NULL,
    rel text NOT NULL,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL,
    state text DEFAULT 'candidate'::text NOT NULL,
    inferred boolean DEFAULT false NOT NULL,
    source text NOT NULL,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    legacy jsonb,
    CONSTRAINT association_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text])))
);


--
-- Name: association_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.association ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.association_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: carrier; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.carrier (
    id bigint NOT NULL,
    asset_id bigint NOT NULL,
    carrier_type text NOT NULL,
    value text,
    state text DEFAULT 'candidate'::text NOT NULL,
    source text NOT NULL,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT carrier_gate_value_required CHECK (((state <> 'verified'::text) OR (value IS NOT NULL))),
    CONSTRAINT carrier_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text]))),
    CONSTRAINT carrier_type_valid CHECK ((carrier_type = ANY (ARRAY['RAIN-96'::text, 'GS1-128'::text, 'DL'::text])))
);


--
-- Name: carrier_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.carrier ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.carrier_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: content_claim; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_claim (
    id bigint NOT NULL,
    party_id bigint NOT NULL,
    pillar text NOT NULL,
    section text NOT NULL,
    display_order integer NOT NULL,
    nm text NOT NULL,
    identifier text,
    grade text,
    tx text,
    doc_key text,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT content_claim_exception_speaks CHECK (((grade <> 'e'::text) OR ((tx IS NOT NULL) AND (length(btrim(tx)) > 0)))),
    CONSTRAINT content_claim_grade_valid CHECK ((grade = ANY (ARRAY['v'::text, 'c'::text, 'e'::text, 'b'::text, 'slot'::text]))),
    CONSTRAINT content_claim_pillar_valid CHECK ((pillar = ANY (ARRAY['P1'::text, 'P2'::text, 'P3'::text, 'P4'::text, 'P5'::text]))),
    CONSTRAINT content_claim_slot_speaks CHECK (((grade <> 'slot'::text) OR ((tx IS NOT NULL) AND (length(btrim(tx)) > 0))))
);


--
-- Name: content_claim_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.content_claim ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.content_claim_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: content_doc; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_doc (
    party_id bigint NOT NULL,
    doc_key text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    url text
);


--
-- Name: edge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.edge (
    id bigint NOT NULL,
    subject_party_id bigint NOT NULL,
    rel text NOT NULL,
    object_label text NOT NULL,
    object_prefix text,
    object_party_id bigint,
    state text DEFAULT 'candidate'::text NOT NULL,
    source text NOT NULL,
    inferred boolean DEFAULT false NOT NULL,
    doc text,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    asserter text,
    valid_from timestamp with time zone,
    valid_to timestamp with time zone,
    CONSTRAINT edge_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text])))
);


--
-- Name: COLUMN edge.asserter; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.edge.asserter IS 'The accountable node that asserted this edge (a GSRN, or ''manual''). Distinct from source (the feed). NULL for legacy/loader rows.';


--
-- Name: COLUMN edge.valid_from; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.edge.valid_from IS 'Start of this assertion''s validity window. NULL = open start.';


--
-- Name: COLUMN edge.valid_to; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.edge.valid_to IS 'End of this assertion''s validity window. NULL = still valid / open-ended.';


--
-- Name: edge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.edge ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.edge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: legacy_id_crosswalk; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legacy_id_crosswalk (
    id bigint NOT NULL,
    party_id bigint,
    node_id bigint,
    id_type text NOT NULL,
    id_value text NOT NULL,
    match_method text DEFAULT 'name_exact_normalized'::text NOT NULL,
    match_confidence text NOT NULL,
    state text DEFAULT 'candidate'::text NOT NULL,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    source text NOT NULL,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    ratified_by text,
    ratified_at timestamp with time zone,
    CONSTRAINT legacy_id_crosswalk_confidence_valid CHECK ((match_confidence = ANY (ARRAY['HIGH'::text, 'LOW'::text, 'COLLISION'::text]))),
    CONSTRAINT legacy_id_crosswalk_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text]))),
    CONSTRAINT legacy_id_crosswalk_verified_needs_ratifier CHECK (((state <> 'verified'::text) OR (ratified_by IS NOT NULL)))
);


--
-- Name: legacy_id_crosswalk_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.legacy_id_crosswalk ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.legacy_id_crosswalk_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: node; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.node (
    id bigint NOT NULL,
    urn text,
    key_type text NOT NULL,
    kind text,
    prefix text,
    legal_name text,
    gln text,
    lei text,
    mo text,
    label text,
    standard text,
    state text DEFAULT 'candidate'::text NOT NULL,
    source text NOT NULL,
    exception_reason text,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    legacy jsonb,
    minted_by text,
    minted_at timestamp with time zone,
    ruleset_version text,
    CONSTRAINT node_gate_prefix CHECK (((state <> 'verified'::text) OR (prefix IS NOT NULL))),
    CONSTRAINT node_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text])))
);


--
-- Name: COLUMN node.minted_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.node.minted_by IS 'Who claimed the mint. Only mint_node()/remint_node() can set it, because only they can set urn.';


--
-- Name: node_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.node_event (
    id bigint NOT NULL,
    node_id bigint,
    association_id bigint,
    event_type text NOT NULL,
    from_state text,
    to_state text,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    source text NOT NULL,
    actor text,
    at timestamp with time zone DEFAULT now() NOT NULL,
    legacy jsonb,
    CONSTRAINT node_event_one_subject CHECK (((node_id IS NOT NULL) <> (association_id IS NOT NULL)))
);


--
-- Name: node_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.node_event ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.node_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: node_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.node ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.node_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: party; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.party (
    id bigint NOT NULL,
    prefix text,
    gln text,
    legal_name text NOT NULL,
    city text,
    country text,
    mo text,
    lei text,
    state text DEFAULT 'candidate'::text NOT NULL,
    source text NOT NULL,
    exception_reason text,
    verified_at timestamp with time zone,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL,
    search_tsv tsvector,
    duns text,
    is_demo boolean DEFAULT false NOT NULL,
    demo_urn text,
    licence_type text,
    licence_type_source text,
    url text,
    url_source text,
    stage_ancestor bigint,
    name_fold text,
    CONSTRAINT party_demo_not_verified CHECK (((NOT is_demo) OR (state <> 'verified'::text))),
    CONSTRAINT party_demo_urn_not_an_identity CHECK (((demo_urn IS NULL) OR ("left"(demo_urn, 11) <> 'urn:epc:id:'::text))),
    CONSTRAINT party_gate_prefix_required CHECK (((state <> 'verified'::text) OR (prefix IS NOT NULL))),
    CONSTRAINT party_needs_stage_ancestor CHECK ((stage_ancestor IS NOT NULL)),
    CONSTRAINT party_prefix_digits_only CHECK (((prefix IS NULL) OR (prefix ~ '^[0-9]+$'::text))),
    CONSTRAINT party_state_valid CHECK ((state = ANY (ARRAY['candidate'::text, 'verified'::text, 'exception'::text])))
);


--
-- Name: COLUMN party.duns; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.party.duns IS 'D&B DUNS cross-reference identifier (verification seed). Not a GS1 prefix.';


--
-- Name: COLUMN party.is_demo; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.party.is_demo IS 'DEMO structural marker: a pre-populated DEMO-staged candidate. Flipped false when the row is claimed/re-rooted. An is_demo row can never be verified (party_demo_not_verified).';


--
-- Name: COLUMN party.demo_urn; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.party.demo_urn IS 'A hosted PLACEHOLDER handle, never an identity. Constrained so an EPC id URN cannot be written here: this column exists so a provisional namespace cannot satisfy the verification gate, and an identity in it would defeat that.';


--
-- Name: party_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.party_event (
    id bigint NOT NULL,
    party_id bigint NOT NULL,
    event_type text NOT NULL,
    from_state text,
    to_state text,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    source text NOT NULL,
    actor text,
    at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT party_event_type_check CHECK ((event_type = ANY (ARRAY['candidate_staged'::text, 'updated'::text, 'verified'::text, 'exception'::text, 'prefix_claimed'::text, 'origin_linked'::text, 'claim_held'::text, 'asset_minted'::text, 'carrier_declared'::text, 'edge_asserted'::text])))
);


--
-- Name: party_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.party_event ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.party_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: party_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.party ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.party_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: party_origin; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.party_origin (
    id bigint NOT NULL,
    party_id bigint NOT NULL,
    origin_urn text,
    origin_prefix text,
    claimed_prefix text NOT NULL,
    authority jsonb DEFAULT '{}'::jsonb NOT NULL,
    actor text,
    at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT party_origin_urn_well_formed CHECK (((origin_urn IS NULL) OR ("left"(origin_urn, 11) <> 'urn:epc:id:'::text) OR public.epc_urn_valid(origin_urn)))
);


--
-- Name: TABLE party_origin; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.party_origin IS 'Append-only immutable origin ledger (Caterpillar->Butterfly / TD-M-50). One row per re-root, written once by POST /claim inside the promotion tx. Never updated or deleted (trg_party_origin_immutable). Model A: origin is a snapshot on the same party row, so there is no origin_party_id.';


--
-- Name: COLUMN party_origin.origin_urn; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.party_origin.origin_urn IS 'The identity a namespace was re-rooted FROM. Provenance, not a mint — so it is grammar-gated (016) rather than privilege-gated (017). Recording history is not minting; recording nonsense is still nonsense.';


--
-- Name: party_origin_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.party_origin ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.party_origin_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: v_epc_urn_violations; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_epc_urn_violations AS
 SELECT id,
    urn,
    key_type,
    label,
    state,
    source
   FROM public.node
  WHERE ((urn IS NOT NULL) AND ("left"(urn, 11) = 'urn:epc:id:'::text) AND (NOT public.epc_urn_valid(urn)));


--
-- Name: VIEW v_epc_urn_violations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_epc_urn_violations IS 'Rows predating migration 016. New writes cannot join them (the CHECK is live). When this view is empty: ALTER TABLE node VALIDATE CONSTRAINT node_urn_epc_valid;';


--
-- Name: v_unminted_identities; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_unminted_identities AS
 SELECT id,
    urn,
    key_type,
    label,
    source
   FROM public.node
  WHERE ((urn IS NOT NULL) AND ((minted_by IS NULL) OR (minted_at IS NULL)));


--
-- Name: VIEW v_unminted_identities; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_unminted_identities IS 'Identities with no mint provenance — all of them predate migration 017. New ones are impossible: only mint_node()/remint_node() can write node.urn, and both demand minted_by.';


--
-- Name: asset asset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_pkey PRIMARY KEY (id);


--
-- Name: asset asset_urn_has_provenance; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.asset
    ADD CONSTRAINT asset_urn_has_provenance CHECK (((urn IS NULL) OR ((minted_by IS NOT NULL) AND (minted_at IS NOT NULL)))) NOT VALID;


--
-- Name: asset asset_urn_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_urn_unique UNIQUE (urn);


--
-- Name: association association_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.association
    ADD CONSTRAINT association_pkey PRIMARY KEY (id);


--
-- Name: carrier carrier_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carrier
    ADD CONSTRAINT carrier_pkey PRIMARY KEY (id);


--
-- Name: content_claim content_claim_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_claim
    ADD CONSTRAINT content_claim_pkey PRIMARY KEY (id);


--
-- Name: content_claim content_claim_unique_row; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_claim
    ADD CONSTRAINT content_claim_unique_row UNIQUE (party_id, pillar, section, nm, identifier);


--
-- Name: content_doc content_doc_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_doc
    ADD CONSTRAINT content_doc_pkey PRIMARY KEY (party_id, doc_key);


--
-- Name: edge edge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.edge
    ADD CONSTRAINT edge_pkey PRIMARY KEY (id);


--
-- Name: legacy_id_crosswalk legacy_id_crosswalk_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_id_crosswalk
    ADD CONSTRAINT legacy_id_crosswalk_pkey PRIMARY KEY (id);


--
-- Name: node_event node_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node_event
    ADD CONSTRAINT node_event_pkey PRIMARY KEY (id);


--
-- Name: node node_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node
    ADD CONSTRAINT node_pkey PRIMARY KEY (id);


--
-- Name: node node_urn_epc_valid; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.node
    ADD CONSTRAINT node_urn_epc_valid CHECK (((urn IS NULL) OR ("left"(urn, 11) <> 'urn:epc:id:'::text) OR public.epc_urn_valid(urn))) NOT VALID;


--
-- Name: node node_urn_has_provenance; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.node
    ADD CONSTRAINT node_urn_has_provenance CHECK (((urn IS NULL) OR ((minted_by IS NOT NULL) AND (minted_at IS NOT NULL)))) NOT VALID;


--
-- Name: party_event party_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_event
    ADD CONSTRAINT party_event_pkey PRIMARY KEY (id);


--
-- Name: party_origin party_origin_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_origin
    ADD CONSTRAINT party_origin_pkey PRIMARY KEY (id);


--
-- Name: party party_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party
    ADD CONSTRAINT party_pkey PRIMARY KEY (id);


--
-- Name: party_origin ux_party_origin_party; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_origin
    ADD CONSTRAINT ux_party_origin_party UNIQUE (party_id);


--
-- Name: ix_asset_origin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_origin ON public.asset USING btree (origin_asset_id);


--
-- Name: ix_asset_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_party ON public.asset USING btree (party_id);


--
-- Name: ix_asset_prefix; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_prefix ON public.asset USING btree (prefix);


--
-- Name: ix_asset_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_state ON public.asset USING btree (state);


--
-- Name: ix_association_legacy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_association_legacy ON public.association USING gin (legacy);


--
-- Name: ix_association_object; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_association_object ON public.association USING btree (object_node_id);


--
-- Name: ix_association_rel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_association_rel ON public.association USING btree (rel);


--
-- Name: ix_association_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_association_subject ON public.association USING btree (subject_node_id);


--
-- Name: ix_carrier_asset; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_carrier_asset ON public.carrier USING btree (asset_id);


--
-- Name: ix_carrier_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_carrier_state ON public.carrier USING btree (state);


--
-- Name: ix_content_claim_grade; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_content_claim_grade ON public.content_claim USING btree (grade);


--
-- Name: ix_content_claim_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_content_claim_party ON public.content_claim USING btree (party_id, pillar, display_order);


--
-- Name: ix_edge_object; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_edge_object ON public.edge USING btree (object_party_id);


--
-- Name: ix_edge_rel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_edge_rel ON public.edge USING btree (rel);


--
-- Name: ix_edge_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_edge_state ON public.edge USING btree (state);


--
-- Name: ix_edge_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_edge_subject ON public.edge USING btree (subject_party_id);


--
-- Name: ix_edge_validity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_edge_validity ON public.edge USING btree (valid_from, valid_to);


--
-- Name: ix_legacy_id_crosswalk_id_value; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_legacy_id_crosswalk_id_value ON public.legacy_id_crosswalk USING btree (id_type, id_value);


--
-- Name: ix_node_event_assoc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_event_assoc ON public.node_event USING btree (association_id);


--
-- Name: ix_node_event_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_event_at ON public.node_event USING btree (at);


--
-- Name: ix_node_event_legacy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_event_legacy ON public.node_event USING gin (legacy);


--
-- Name: ix_node_event_node; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_event_node ON public.node_event USING btree (node_id);


--
-- Name: ix_node_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_event_type ON public.node_event USING btree (event_type);


--
-- Name: ix_node_key_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_key_type ON public.node USING btree (key_type);


--
-- Name: ix_node_legacy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_legacy ON public.node USING gin (legacy);


--
-- Name: ix_node_prefix; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_prefix ON public.node USING btree (prefix);


--
-- Name: ix_node_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_node_state ON public.node USING btree (state);


--
-- Name: ix_party_duns; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_duns ON public.party USING btree (duns) WHERE (duns IS NOT NULL);


--
-- Name: ix_party_event_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_event_at ON public.party_event USING btree (at);


--
-- Name: ix_party_event_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_event_party ON public.party_event USING btree (party_id);


--
-- Name: ix_party_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_event_type ON public.party_event USING btree (event_type);


--
-- Name: ix_party_gln; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_gln ON public.party USING btree (gln);


--
-- Name: ix_party_legal_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_legal_name_trgm ON public.party USING gin (legal_name public.gin_trgm_ops);


--
-- Name: ix_party_mo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_mo ON public.party USING btree (mo);


--
-- Name: ix_party_name_fold; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_name_fold ON public.party USING btree (name_fold) WHERE (name_fold IS NOT NULL);


--
-- Name: ix_party_origin_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_origin_party ON public.party_origin USING btree (party_id);


--
-- Name: ix_party_search_tsv; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_search_tsv ON public.party USING gin (search_tsv);


--
-- Name: ix_party_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_source ON public.party USING btree (source);


--
-- Name: ix_party_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_state ON public.party USING btree (state);


--
-- Name: ux_association; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_association ON public.association USING btree (subject_node_id, object_node_id, rel, source);


--
-- Name: ux_carrier_asset_type; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_carrier_asset_type ON public.carrier USING btree (asset_id, carrier_type);


--
-- Name: ux_edge_assertion; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_edge_assertion ON public.edge USING btree (subject_party_id, rel, object_label, source);


--
-- Name: ux_legacy_id_crosswalk; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_legacy_id_crosswalk ON public.legacy_id_crosswalk USING btree (party_id, id_type, id_value, source);


--
-- Name: ux_node_prefix; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_node_prefix ON public.node USING btree (prefix) WHERE ((prefix IS NOT NULL) AND (key_type = 'pgln'::text));


--
-- Name: ux_node_urn; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_node_urn ON public.node USING btree (urn) WHERE (urn IS NOT NULL);


--
-- Name: ux_party_prefix; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_party_prefix ON public.party USING btree (prefix) WHERE (prefix IS NOT NULL);


--
-- Name: party_origin trg_party_origin_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_party_origin_immutable BEFORE DELETE OR UPDATE ON public.party_origin FOR EACH ROW EXECUTE FUNCTION public.party_origin_is_append_only();


--
-- Name: party trg_party_search_tsv; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_party_search_tsv BEFORE INSERT OR UPDATE ON public.party FOR EACH ROW EXECUTE FUNCTION public.party_search_tsv_update();


--
-- Name: party trg_party_verified_prefix_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_party_verified_prefix_immutable BEFORE UPDATE ON public.party FOR EACH ROW EXECUTE FUNCTION public.party_verified_prefix_immutable();


--
-- Name: asset asset_origin_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_origin_asset_id_fkey FOREIGN KEY (origin_asset_id) REFERENCES public.asset(id);


--
-- Name: asset asset_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset
    ADD CONSTRAINT asset_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;


--
-- Name: association association_object_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.association
    ADD CONSTRAINT association_object_node_id_fkey FOREIGN KEY (object_node_id) REFERENCES public.node(id) ON DELETE CASCADE;


--
-- Name: association association_subject_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.association
    ADD CONSTRAINT association_subject_node_id_fkey FOREIGN KEY (subject_node_id) REFERENCES public.node(id) ON DELETE CASCADE;


--
-- Name: carrier carrier_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carrier
    ADD CONSTRAINT carrier_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.asset(id) ON DELETE CASCADE;


--
-- Name: content_claim content_claim_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_claim
    ADD CONSTRAINT content_claim_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;


--
-- Name: content_doc content_doc_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_doc
    ADD CONSTRAINT content_doc_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;


--
-- Name: edge edge_object_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.edge
    ADD CONSTRAINT edge_object_party_id_fkey FOREIGN KEY (object_party_id) REFERENCES public.party(id) ON DELETE SET NULL;


--
-- Name: edge edge_subject_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.edge
    ADD CONSTRAINT edge_subject_party_id_fkey FOREIGN KEY (subject_party_id) REFERENCES public.party(id) ON DELETE CASCADE;


--
-- Name: legacy_id_crosswalk legacy_id_crosswalk_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_id_crosswalk
    ADD CONSTRAINT legacy_id_crosswalk_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.node(id) ON DELETE SET NULL;


--
-- Name: legacy_id_crosswalk legacy_id_crosswalk_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_id_crosswalk
    ADD CONSTRAINT legacy_id_crosswalk_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;


--
-- Name: node_event node_event_association_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node_event
    ADD CONSTRAINT node_event_association_id_fkey FOREIGN KEY (association_id) REFERENCES public.association(id) ON DELETE CASCADE;


--
-- Name: node_event node_event_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.node_event
    ADD CONSTRAINT node_event_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.node(id) ON DELETE CASCADE;


--
-- Name: party_event party_event_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_event
    ADD CONSTRAINT party_event_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;


--
-- Name: party_origin party_origin_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_origin
    ADD CONSTRAINT party_origin_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict dm0sa9mTUbsUaR9vhtT9kQ5jgFy6KDI2oEkhOCNSfFYyBPuUYkjddxxgdydbUfX

