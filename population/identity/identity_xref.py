#!/usr/bin/env python3
"""
identity_xref.py — STAGE 5: root the harvest to a WHO.

The website agent produces UNROOTED content: candidate GTINs (source=WEB), documents, edges —
all provenanced to a company's own URLs, but not yet tied to an accountable party. This stage
cross-references that content against the identity authorities and PROPOSES a root. It never mints.

The rooting ladder (offline-first, authoritative, law-abiding):

  1. WHO by name — match the harvested company against our own `party` table (trigram on
     legal_name). Our party rows already carry authoritative, verified GS1 prefixes. A hit gives
     the real prefix / gln / lei / mo. This is the root.

  2. GTIN confirmation — for each candidate WEB GTIN, TEST (never derive) whether it belongs to
     the rooted party: does the party's known company prefix sit at the head of the GTIN's
     company-prefix region (indicator digit dropped)?  prefix-is-root, checked not guessed.
     * confirmed  — party prefix is a leading match  -> roots to the party (candidate->ratifiable)
     * band-only  — no party, but the MO band resolves -> the issuing Member Organisation is known
     * unrooted   — nothing authoritative said so     -> stays candidate, never guessed

  3. LEI fill (optional, --gleif) — resolve the party's legal entity to a GLEIF LEI when missing.
     One polite call. The LEI is the legal-entity anchor; provenance = GLEIF.

  4. GEPIR (optional, --gepir) — for a GTIN whose company is NOT in our party table, ask GEPIR
     who licenses it. Discovery only, candidate, provenance = GEPIR. Bounded + polite.

Laws honored: never fabricate a prefix/GLN/GTIN (absence -> candidate); prefix-is-root (only
tested against known prefixes, never derived); candidate-until-ratified (this stage proposes, R4
ratifies); registrar stricter than standard; every proposed root stamped with its authority.

Reads (from a website_agent outdir): page_gtins.csv  (urn,key_type,prefix,gln,mo,state,source)
Writes (to --outdir):
  identity_roots.csv   urn,gtin,company_prefix,mo,root_status,root_party_id,root_company,gln,lei,authority,note
  identity_report.json rollup: rooted / band-only / unrooted counts, the WHO, provenance

Usage:
  python3 identity_xref.py --gtins sites/thermo/page_gtins.csv \
      --company "Thermo Fisher Scientific" --outdir sites/thermo
  python3 identity_xref.py --gtins page_gtins.csv --company "Thermo Fisher Scientific" --gleif
  POP_DB=thingdaddy_population_test python3 identity_xref.py --gtins ... --company ...
"""
from __future__ import annotations
import argparse, csv, json, os, re, subprocess, sys, time
import urllib.request, urllib.parse, urllib.error

POP_DB = os.environ.get("POP_DB", "thingdaddy_population")
UA = "ThingDaddy-IdentityXref/0.1 (identity cross-reference; contact ops@thingdaddy.io)"

# --- GS1 MO band table (published GS1 prefix ranges — authoritative, NOT fabricated) --------
RANGES = [
    (1,19,"GS1 US"),(20,29,"Restricted (regional)"),(30,39,"GS1 US"),(40,49,"Restricted (company)"),
    (50,59,"GS1 US (reserved)"),(60,139,"GS1 US"),(200,299,"Restricted (regional)"),
    (300,379,"GS1 France"),(380,380,"GS1 Bulgaria"),(383,383,"GS1 Slovenija"),(385,385,"GS1 Croatia"),
    (387,387,"GS1 BIH"),(389,389,"GS1 Montenegro"),(400,440,"GS1 Germany"),(450,459,"GS1 Japan"),
    (460,469,"GS1 Russia"),(470,470,"GS1 Kyrgyzstan"),(471,471,"GS1 Chinese Taipei"),(474,474,"GS1 Estonia"),
    (475,475,"GS1 Latvia"),(476,476,"GS1 Azerbaijan"),(477,477,"GS1 Lithuania"),(478,478,"GS1 Uzbekistan"),
    (479,479,"GS1 Sri Lanka"),(480,480,"GS1 Philippines"),(481,481,"GS1 Belarus"),(482,482,"GS1 Ukraine"),
    (483,483,"GS1 Turkmenistan"),(484,484,"GS1 Moldova"),(485,485,"GS1 Armenia"),(486,486,"GS1 Georgia"),
    (487,487,"GS1 Kazakstan"),(488,488,"GS1 Tajikistan"),(489,489,"GS1 Hong Kong"),(490,499,"GS1 Japan"),
    (500,509,"GS1 UK"),(520,521,"GS1 Greece"),(528,528,"GS1 Lebanon"),(529,529,"GS1 Cyprus"),
    (530,530,"GS1 Albania"),(531,531,"GS1 Macedonia"),(535,535,"GS1 Malta"),(539,539,"GS1 Ireland"),
    (540,549,"GS1 Belgium & Luxembourg"),(560,560,"GS1 Portugal"),(569,569,"GS1 Iceland"),
    (570,579,"GS1 Denmark"),(590,590,"GS1 Poland"),(594,594,"GS1 Romania"),(599,599,"GS1 Hungary"),
    (600,601,"GS1 South Africa"),(603,603,"GS1 Ghana"),(604,604,"GS1 Senegal"),(607,607,"GS1 Oman"),
    (608,608,"GS1 Bahrain"),(609,609,"GS1 Mauritius"),(611,611,"GS1 Morocco"),(613,613,"GS1 Algeria"),
    (615,615,"GS1 Nigeria"),(616,616,"GS1 Kenya"),(617,617,"GS1 Cameroon"),(618,618,"GS1 Cote d'Ivoire"),
    (619,619,"GS1 Tunisia"),(620,620,"GS1 Tanzania"),(621,621,"GS1 Syria"),(622,622,"GS1 Egypt"),
    (624,624,"GS1 Libya"),(625,625,"GS1 Jordan"),(626,626,"GS1 Iran"),(627,627,"GS1 Kuwait"),
    (628,628,"GS1 Saudi Arabia"),(629,629,"GS1 Emirates"),(630,630,"GS1 Qatar"),(631,631,"GS1 Namibia"),
    (640,649,"GS1 Finland"),(680,681,"GS1 China"),(690,699,"GS1 China"),(700,709,"GS1 Norway"),
    (729,729,"GS1 Israel"),(730,739,"GS1 Sweden"),(740,740,"GS1 Guatemala"),(741,741,"GS1 El Salvador"),
    (742,742,"GS1 Honduras"),(743,743,"GS1 Nicaragua"),(744,744,"GS1 Costa Rica"),(745,745,"GS1 Panama"),
    (746,746,"GS1 Dominican Republic"),(750,750,"GS1 Mexico"),(754,755,"GS1 Canada"),(759,759,"GS1 Venezuela"),
    (760,769,"GS1 Switzerland"),(770,771,"GS1 Colombia"),(773,773,"GS1 Uruguay"),(775,775,"GS1 Peru"),
    (777,777,"GS1 Bolivia"),(778,779,"GS1 Argentina"),(780,780,"GS1 Chile"),(784,784,"GS1 Paraguay"),
    (786,786,"GS1 Ecuador"),(789,790,"GS1 Brasil"),(800,839,"GS1 Italy"),(840,849,"GS1 Spain"),
    (850,850,"GS1 Cuba"),(858,858,"GS1 Slovakia"),(859,859,"GS1 Czech"),(860,860,"GS1 Serbia"),
    (865,865,"GS1 Mongolia"),(867,867,"GS1 North Korea"),(868,869,"GS1 Turkiye"),(870,879,"GS1 Netherlands"),
    (880,881,"GS1 South Korea"),(883,883,"GS1 Myanmar"),(884,884,"GS1 Cambodia"),(885,885,"GS1 Thailand"),
    (888,888,"GS1 Singapore"),(890,890,"GS1 India"),(893,893,"GS1 Vietnam"),(896,896,"GS1 Pakistan"),
    (899,899,"GS1 Indonesia"),(900,919,"GS1 Austria"),(930,939,"GS1 Australia"),(940,949,"GS1 New Zealand"),
    (950,950,"GS1 Global Office"),(951,951,"GS1 Global Office (GM number)"),(952,952,"Demo/examples"),
    (955,955,"GS1 Malaysia"),(958,958,"GS1 Macau"),(960,969,"Global Office GTIN-8"),
    (977,977,"Serial publications (ISSN)"),(978,979,"Bookland (ISBN)"),(980,980,"Refund receipts"),
    (981,983,"GS1 coupon (common currency)"),(990,999,"GS1 coupon"),
]

def to_gtin14(d): return d.zfill(14)

def mo_for_gtin(gtin14):
    """MO band from the first 3 digits of the GS1 Company Prefix region (indicator dropped)."""
    body = gtin14[1:]                         # drop the indicator digit
    try: p3 = int(body[:3])
    except ValueError: return ""
    for lo, hi, name in RANGES:
        if lo <= p3 <= hi: return name
    return ""

def company_prefix_region(gtin14):
    """The GS1 Company Prefix REGION of a GTIN (indicator + check digit removed).
    We do NOT know where the company prefix ends (it's variable-length, never derived) — we only
    return the region a known prefix must be a leading substring of."""
    return gtin14[1:-1]

# --- our own registry (offline, authoritative) ------------------------------
def psql_json(sql):
    out = subprocess.run(["psql", "-d", POP_DB, "-tAc", sql], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"psql failed ({POP_DB}): {out.stderr.strip()}")
    s = (out.stdout or "").strip()
    return json.loads(s) if s else None

def lit(s): return "'" + str(s).replace("'", "''") + "'"

def find_party(company):
    """Best-matching party row for the harvested company name (trigram similarity)."""
    sql = (
        "SELECT COALESCE(json_agg(row), '[]') FROM ("
        "  SELECT id, legal_name, prefix, gln, lei, mo, state, source, "
        f"         similarity(legal_name, {lit(company)}) AS sim "
        "  FROM party "
        f"  WHERE legal_name % {lit(company)} OR legal_name ILIKE {lit('%'+company+'%')} "
        "  ORDER BY sim DESC NULLS LAST, (prefix IS NOT NULL) DESC "
        "  LIMIT 5"
        ") row"
    )
    try:
        return psql_json(sql) or []
    except SystemExit as e:
        print(f"   (registry lookup skipped: {e})", file=sys.stderr)
        return []

# --- GLEIF (optional, network) ----------------------------------------------
def _gleif_query(param, name, timeout):
    q = urllib.parse.urlencode({param: name, "page[size]": 1})
    url = "https://api.gleif.org/api/v1/lei-records?" + q
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    recs = d.get("data") or []
    if not recs: return None
    rec = recs[0]; ent = rec.get("attributes", {}).get("entity", {})
    return {"lei": rec.get("id"), "name": (ent.get("legalName") or {}).get("name"),
            "country": (ent.get("legalAddress") or {}).get("country"),
            "match": "exact" if param.endswith("legalName]") else "fulltext"}

_NAME_STOP = {"the", "inc", "llc", "ltd", "gmbh", "limited", "company", "co", "corp",
              "corporation", "ag", "sa", "bv", "nv", "plc", "group", "holdings", "and"}
def _name_tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower())
            if len(t) >= 3 and t not in _NAME_STOP}

def gleif_lei(name, timeout=25):
    """Exact legal-name first, then GLEIF fulltext — but a fulltext hit is accepted only if the
    returned name shares a real word with the query (else it's a confidently-wrong guess: reject)."""
    qtok = _name_tokens(name)
    for param in ("filter[entity.legalName]", "filter[fulltext]"):
        try:
            r = _gleif_query(param, name, timeout)
            if not (r and r.get("lei")): continue
            if r.get("match") == "exact":
                return r
            if qtok & _name_tokens(r.get("name")):     # fulltext must overlap the query name
                return r
            print(f"   [gleif] fulltext hit rejected (name mismatch): {r.get('name')!r} for {name!r}",
                  file=sys.stderr)
        except Exception as e:
            print(f"   [gleif:{param}] {name} -> {e}", file=sys.stderr)
    return None

# --- GEPIR (optional, network) — discovery for GTINs with no local party -----
def gepir_company(gtin14, timeout=25):
    # GEPIR public endpoints vary by region/version; kept behind --gepir and tolerant.
    url = "https://gepir.gs1.org/api/v1/products/" + urllib.parse.quote(gtin14)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        if isinstance(d, dict):
            comp = d.get("companyName") or d.get("partyName") or (d.get("company") or {}).get("name")
            pfx = d.get("companyPrefix") or d.get("gcp")
            if comp: return {"company": comp, "prefix": pfx}
        return None
    except Exception as e:
        print(f"   [gepir] {gtin14} -> {e}", file=sys.stderr); return None

def load_verified_prefix(domain, company, path_arg=""):
    """The verified GS1 prefix for a company, from verified_prefixes.json (keyed by domain,
    company-name fallback). This is first-party/GEPIR ground truth — it lets a harvested GTIN
    CONFIRM even when the registry party has no prefix. Returns the full entry or None."""
    cands = [path_arg] if path_arg else []
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [os.path.join(here, "..", "standards", "verified_prefixes.json"),
              os.path.join(here, "verified_prefixes.json"),
              os.path.join(here, "..", "verified_prefixes.json")]
    reg = {}
    for c in cands:
        if c and os.path.exists(c):
            try:
                with open(c) as f: reg = json.load(f); break
            except Exception: pass
    if not reg: return None
    d = re.sub(r"^www\.", "", re.sub(r"^https?://", "", (domain or "").strip().lower()).split("/")[0])
    e = reg.get(d)
    if not e and company:
        for v in reg.values():
            if str(v.get("company", "")).strip().lower() == company.strip().lower():
                e = v; break
    if e and str(e.get("status", "")).lower() == "verified" and e.get("prefix"):
        return e
    return None

def read_parties(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            nm = (r.get("name") or "").strip()
            if nm: rows.append(r)
    return rows

def root_parties(a):
    """Batch mode: root each roster entry via registry name-match (+ optional GLEIF LEI)."""
    parties = read_parties(a.parties)
    print(f">> identity xref · parties={len(parties)} · db={POP_DB}"
          + (" · +GLEIF" if a.gleif else ""))
    out_rows, roll = [], {"registry_match": 0, "registry_candidate": 0, "gleif_only": 0, "unrooted": 0}
    gleif_calls = 0
    for r in parties:
        name = r["name"].strip()
        matches = find_party(name)
        party = None
        for m in matches:                      # prefer a rooted (prefix-bearing) match
            if m.get("prefix"): party = m; break
        if party is None and matches: party = matches[0]

        prefix = (party or {}).get("prefix") or ""
        pid    = (party or {}).get("id") or ""
        mo     = (party or {}).get("mo") or ""
        lei    = (party or {}).get("lei") or ""
        lei_authority = "registry" if lei else ""
        sim    = round((party or {}).get("sim") or 0, 2)

        if party and prefix:
            status = "registry_match"; roll["registry_match"] += 1
        elif party:
            status = "registry_candidate"; roll["registry_candidate"] += 1
        else:
            status = "unrooted"; roll["unrooted"] += 1

        if a.gleif and not lei and gleif_calls < a.gleif_limit:
            gleif_calls += 1
            g = gleif_lei(name); time.sleep(a.sleep)
            if g and g.get("lei"):
                lei = g["lei"]; lei_authority = "GLEIF"
                if status == "unrooted":
                    status = "gleif_only"; roll["unrooted"] -= 1; roll["gleif_only"] += 1

        out_rows.append([name, r.get("domain", ""), r.get("role", ""), r.get("claim", ""),
                         status, pid, prefix, mo, lei, lei_authority, sim, r.get("source_url", "")])

    os.makedirs(a.outdir, exist_ok=True)
    roots_csv = os.path.join(a.outdir, "roster_roots.csv")
    with open(roots_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "domain", "role", "claim", "root_status", "registry_party_id",
                    "registry_prefix", "mo", "lei", "lei_authority", "name_sim", "source_url"])
        w.writerows(out_rows)
    report = {"parties": len(parties), "db": POP_DB, "rooting": roll,
              "note": ("Candidate roots only — nothing minted. registry_match = named party carries a "
                       "verified GS1 prefix; registry_candidate = in registry, no prefix yet; gleif_only = "
                       "legal entity anchored by LEI, prefix unknown; unrooted = candidate, nothing guessed. "
                       "Each vendor's domain seeds website_agent. R4 ratifies.")}
    with open(os.path.join(a.outdir, "roster_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    print(f">> roster roots: registry-match={roll['registry_match']} · registry-candidate={roll['registry_candidate']}"
          + (f" · gleif-only={roll['gleif_only']}" if a.gleif else "") + f" · unrooted={roll['unrooted']}")
    print(f"   -> {roots_csv}")
    print(f"   -> {os.path.join(a.outdir, 'roster_report.json')}")
    print(">> candidate roots. Rooted vendors' domains now seed website_agent --root. Nothing minted; R4 ratifies.")

def read_gtins(path):
    urns = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            u = r.get("urn") or ""
            m = re.search(r"(\d{14})$", u)
            if m: urns.append((u, m.group(1)))
    # de-dup keep order
    seen, out = set(), []
    for u, g in urns:
        if g not in seen: seen.add(g); out.append((u, g))
    return out

def main():
    ap = argparse.ArgumentParser(description="Stage 5 — root the harvest to a WHO (candidate; never minted).")
    ap.add_argument("--gtins", help="page_gtins.csv from the harvest (GTIN-rooting mode)")
    ap.add_argument("--company", help="the harvested company name (the WHO to root to)")
    ap.add_argument("--parties", help="roster_parties.csv — batch-root each entry (roster mode)")
    ap.add_argument("--gleif", action="store_true", help="fill LEI from GLEIF (network)")
    ap.add_argument("--gleif-limit", type=int, default=60, help="max GLEIF calls in --parties mode")
    ap.add_argument("--gepir", action="store_true", help="discover licensee for unrooted GTINs via GEPIR (network)")
    ap.add_argument("--gepir-limit", type=int, default=25, help="max GEPIR discovery calls")
    ap.add_argument("--domain", default="", help="the company's domain (keys the verified-prefix registry)")
    ap.add_argument("--sim-floor", type=float, default=0.5,
                    help="min name-similarity to assert a registry WHO (below = coincidence, not shown)")
    ap.add_argument("--verified-prefixes", default="", help="path to verified_prefixes.json")
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    # roster mode — batch-root a member list
    if a.parties:
        root_parties(a)
        return
    if not (a.gtins and a.company):
        raise SystemExit("pass --parties <roster.csv>  OR  --gtins <page_gtins.csv> --company <name>")

    gtins = read_gtins(a.gtins)
    print(f">> identity xref · company={a.company!r} · db={POP_DB} · candidate GTINs={len(gtins)}")

    # 1 · WHO by name (our own registry — authoritative, offline)
    matches = find_party(a.company)
    party = None
    for m in matches:                          # prefer a rooted (prefix-bearing) match
        if m.get("prefix"): party = m; break
    if party is None and matches: party = matches[0]
    best_sim = round((party or {}).get("sim") or 0, 2)
    if party and best_sim < a.sim_floor:
        print(f"   WHO: best registry match {party['legal_name']!r} (sim={best_sim}) is BELOW the "
              f"{a.sim_floor} floor — a name coincidence, not a party. Not asserting (candidate).")
        party = None
    elif party:
        print(f"   WHO: party#{party['id']} {party['legal_name']!r} · prefix={party.get('prefix') or '—'} "
              f"· mo={party.get('mo') or '—'} · state={party.get('state')} (sim={best_sim})")
    else:
        print("   WHO: no party match in registry — company is UNROOTED (candidate). Nothing guessed.")

    # verified prefix (first-party / GEPIR) — lets GTINs confirm even with no registry prefix
    vpx = load_verified_prefix(a.domain, a.company, a.verified_prefixes)
    verified_prefix = (vpx or {}).get("prefix") or ""
    if vpx:
        prov = " · ".join(x for x in [vpx.get("source", ""),
                          ("first-party: " + vpx.get("verified_by", "")) if vpx.get("verified_by") else "",
                          vpx.get("date", "")] if x)
        print(f"   VERIFIED PREFIX: {verified_prefix}  ({prov}) — GTINs carrying it CONFIRM.")

    # 3 · LEI fill (optional)
    lei = (party or {}).get("lei")
    lei_authority = "party" if lei else ""
    if a.gleif and not lei:
        g = gleif_lei((party or {}).get("legal_name") or a.company)
        if g and g.get("lei"):
            lei = g["lei"]; lei_authority = "GLEIF"
            print(f"   LEI: {lei}  ({g.get('name')}) — provenance GLEIF ({g.get('match')} match)")
        else:
            print("   LEI: no GLEIF match — legal entity remains unrooted (candidate).")

    party_prefix = (party or {}).get("prefix") or ""
    pfx = party_prefix or verified_prefix          # effective prefix for the leading-prefix confirm test
    pfx_via_verified = bool(verified_prefix and not party_prefix)
    pgln = (party or {}).get("gln") or ""

    # 2 · confirm each candidate GTIN against the KNOWN party prefix (tested, never derived)
    rows, roll = [], {"confirmed": 0, "band_only": 0, "unrooted": 0, "gepir_found": 0}
    gepir_calls = 0
    for urn, g14 in gtins:
        mo = mo_for_gtin(g14)
        region = company_prefix_region(g14)
        status, party_id, company, note, authority = "unrooted", "", "", "", ""
        if pfx and region.startswith(pfx):
            status = "confirmed"
            party_id = (party or {}).get("id", "")
            company = (party or {}).get("legal_name") or (vpx or {}).get("company") or a.company
            if pfx_via_verified:
                authority = f"verified-prefix({(vpx or {}).get('source','')})"
                note = f"verified prefix {pfx} leads GTIN company region (first-party)"
            else:
                authority = "registry(prefix-leading)"; note = f"party prefix {pfx} leads GTIN company region"
            roll["confirmed"] += 1
        elif mo:
            status = "band_only"; authority = "MO band"; note = f"issuing MO = {mo}; licensee unknown"
            roll["band_only"] += 1
        else:
            roll["unrooted"] += 1

        if status != "confirmed" and a.gepir and gepir_calls < a.gepir_limit:
            gepir_calls += 1
            gp = gepir_company(g14)
            time.sleep(a.sleep)
            if gp and gp.get("company"):
                company = gp["company"]; authority = "GEPIR"; roll["gepir_found"] += 1
                note = (note + " · " if note else "") + f"GEPIR licensee: {gp['company']}"

        rows.append([urn, g14, pfx if status == "confirmed" else "", mo, status,
                     party_id, company, pgln if status == "confirmed" else "",
                     lei if status == "confirmed" else "", authority, note])

    # write roots CSV
    roots_csv = os.path.join(a.outdir, "identity_roots.csv")
    with open(roots_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["urn", "gtin", "company_prefix", "mo", "root_status",
                    "root_party_id", "root_company", "gln", "lei", "authority", "note"])
        w.writerows(rows)

    report = {
        "company": a.company, "db": POP_DB, "candidate_gtins": len(gtins),
        "who": ({"party_id": party["id"], "legal_name": party["legal_name"],
                 "prefix": party.get("prefix"), "gln": party.get("gln"),
                 "mo": party.get("mo"), "state": party.get("state")} if party
                else ({"party_id": "", "legal_name": (vpx or {}).get("company") or a.company,
                       "prefix": verified_prefix, "gln": "", "mo": "",
                       "state": "verified-prefix"} if vpx else None)),
        "lei": lei, "lei_authority": lei_authority,
        "verified_prefix": ({"prefix": verified_prefix, "source": (vpx or {}).get("source"),
                             "verified_by": (vpx or {}).get("verified_by")} if vpx else None),
        "gtin_rooting": roll,
        "rooted": bool(pfx and roll["confirmed"] > 0),
        "note": ("Candidate proposals only — nothing minted. Confirmed GTINs root to the party by a "
                 "leading-prefix TEST against a known GS1 prefix (never derived). Band-only GTINs know "
                 "their issuing Member Organisation, not the licensee. Unrooted stays candidate. R4 ratifies."),
    }
    with open(os.path.join(a.outdir, "identity_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    print(f">> roots: confirmed={roll['confirmed']} · band-only={roll['band_only']} · unrooted={roll['unrooted']}"
          + (f" · gepir-found={roll['gepir_found']}" if a.gepir else ""))
    print(f"   -> {roots_csv}")
    print(f"   -> {os.path.join(a.outdir, 'identity_report.json')}")
    root_who = (party or {}).get("legal_name") or (vpx or {}).get("company") or a.company
    if report["rooted"]:
        via = f"verified prefix ({(vpx or {}).get('source','')})" if pfx_via_verified else "registry prefix"
        print(f">> ROOTED — {roll['confirmed']} GTIN(s) tie to {root_who} via {via} {pfx}. "
              "Candidate → ready for R4 ratification. Nothing minted.")
    else:
        print(">> STILL UNROOTED — no confirmed GTIN↔party tie. Candidate only; nothing guessed. "
              "Add the company's verified prefix (verified_prefixes.json) or enable --gepir/--gleif discovery.")

if __name__ == "__main__":
    main()
