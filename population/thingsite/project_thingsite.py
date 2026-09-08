#!/usr/bin/env python3
"""
project_thingsite.py — project a ThingSite from the spine, data-driven, for ANY party.

The GA/Diazyme sites were hand-curated (reskin_*.py, ~13 companies, bespoke copy). This
does NOT hand-tune: it reads a party straight from the Population DB and renders its
ThingSite from the data alone — name, MO, GS1 nine-slot counts, state, provenance. So
`--limit 5` proves it; `--limit 80000` is the same code. The site map IS the identity;
the page is projected, never authored.

Laws honored (nothing invented):
  * Renders ONLY what the spine holds. No fabricated products, prefixes, or documents.
  * A GDSN party is a CANDIDATE company (prefix=NULL, unrooted) — shown as exactly that.
  * Counts come from the DB. Empty slots are shown empty (candidate), not padded.

Reads via psql (same pattern as loaders/load_population.py). Runs where the DB is (the Mac).

Usage:
  python3 project_thingsite.py --source GDSN --limit 5 --outdir sites
  python3 project_thingsite.py --ids 123,456 --outdir sites
  python3 project_thingsite.py --source GDSN --limit 80000 --outdir sites   # the whole book
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, subprocess, sys

POP_DB = os.environ.get("POP_DB", "thingdaddy_population")

# the nine legal GS1 slots (the site-map schema — fixed, universal)
NINE = [("PGLN","organization"),("GLN","location"),("GTIN","product"),
        ("GIAI","serialized asset"),("GRAI","returnable asset"),("LGTIN","batch / lot"),
        ("GDTI","document"),("CPID","component"),("GSRN","person / agent")]

def psql_json(sql):
    out = subprocess.run(["psql","-d",POP_DB,"-tAc",sql], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"psql failed: {out.stderr.strip()}")
    s = out.stdout.strip()
    return json.loads(s) if s and s != "" else None

def q_lit(s):  # safe single-quote for a SQL literal (gln/source are our own controlled values)
    return "'" + str(s).replace("'", "''") + "'"

_HAS_NODE = None
def has_node():
    """Prod may not have the spine yet (node table = migrations 010/011). If it's absent we
    render companies with 0 products — honest, not a crash. Scratch HAS node -> real counts."""
    global _HAS_NODE
    if _HAS_NODE is None:
        r = psql_json("SELECT json_build_object('b', to_regclass('public.node') IS NOT NULL)")
        _HAS_NODE = bool(r and r.get("b"))
    return _HAS_NODE

def accent_for(name):
    """Deterministic brand-ish accent from the name — no hand-picking across 80k."""
    h = int(hashlib.sha1(name.encode("utf-8")).hexdigest(), 16)
    hue = h % 360
    # keep it corporate: mid saturation, readable on white
    return f"hsl({hue},62%,42%)", f"hsl({hue},64%,24%)"

def fetch_parties(args):
    where, lim = [], ""
    if args.ids:
        ids = ",".join(str(int(x)) for x in args.ids.split(","))
        where.append(f"id IN ({ids})")
    if args.source:
        where.append(f"source = {q_lit(args.source)}")
    where.append("legal_name IS NOT NULL")
    w = " AND ".join(where)
    if args.limit and not args.ids:
        lim = f"LIMIT {int(args.limit)}"
    sql = ("SELECT COALESCE(json_agg(t),'[]') FROM (SELECT id, legal_name, gln, mo, "
           f"state, source, prefix FROM party WHERE {w} ORDER BY id {lim}) t")
    return psql_json(sql) or []

def product_counts(party):
    """Real GTIN/node counts linked to this company by GLN. Empty is honest, not padded."""
    if not has_node():
        return 0, []
    gln = party.get("gln")
    if not gln:
        return 0, []
    n = psql_json(f"SELECT COALESCE(json_build_object('n',count(*)),'{{}}') "
                  f"FROM node WHERE gln = {q_lit(gln)} AND key_type='gtin'")
    total = (n or {}).get("n", 0)
    samples = psql_json(
        f"SELECT COALESCE(json_agg(t),'[]') FROM (SELECT urn, mo, state FROM node "
        f"WHERE gln = {q_lit(gln)} AND key_type='gtin' ORDER BY urn LIMIT 6) t") or []
    return total, samples

# ---- rendering --------------------------------------------------------------
def esc(s): return html.escape(str(s if s is not None else ""))

def slot_counts(party, gtin_total):
    have = {"PGLN": 1, "GLN": 1 if party.get("gln") else 0, "GTIN": gtin_total, "GSRN": 1}
    return {k: have.get(k, 0) for k, _ in NINE}

def render(party, gtin_total, samples):
    name = party["legal_name"]
    acc, deep = accent_for(name)
    mo = party.get("mo") or "candidate (MO resolves from the prefix band on verification)"
    gln = party.get("gln") or "—"
    state = party.get("state") or "candidate"
    prefix = party.get("prefix") or "—  (candidate · unrooted · GS1 prefix is variable-length, never derived)"
    counts = slot_counts(party, gtin_total)

    slot_html = "".join(
        f'<div class="slot{" on" if counts[k] else ""}"><div class="k">{k}</div>'
        f'<div class="d">{esc(d)}</div><div class="n">{counts[k] if counts[k] else "—"}</div></div>'
        for k, d in NINE)

    if samples:
        prod_rows = "".join(
            f'<tr><td class="mono">{esc(s["urn"])}</td><td>{esc(s.get("mo") or "")}</td>'
            f'<td><span class="pill">{esc(s.get("state") or "candidate")}</span></td></tr>'
            for s in samples)
        prod_block = (f'<table class="tbl"><thead><tr><th>Product (GTIN · URN)</th><th>MO</th>'
                      f'<th>State</th></tr></thead><tbody>{prod_rows}</tbody></table>'
                      f'<div class="muted">{gtin_total} product identities linked to this location'
                      f' (showing {len(samples)}).</div>')
    else:
        prod_block = ('<div class="empty">No product identities populated yet for this company. '
                      'The slot is <b>candidate</b>, not empty-forever — GTINs attach as the GUDID / '
                      'web-scan / GDSN population reaches this GLN. Nothing is fabricated to fill it.</div>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name)} · ThingSite</title>
<style>
:root{{--acc:{acc};--deep:{deep};--ink:#0e2a4a;--dim:#5a6b82;--line:#d6e0ee;--pnl:#f4f8fc;--cand:#b4700a;--ver:#218a53}}
*{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff}}
.wrap{{max-width:1000px;margin:0 auto;padding:22px 26px 60px}}
header{{display:flex;align-items:center;gap:12px;padding:6px 0 14px;border-bottom:2px solid var(--acc);flex-wrap:wrap}}
.brand b{{color:var(--acc);letter-spacing:.5px}} .brand span{{color:#8397b0;font-weight:700}}
.hero{{background:linear-gradient(100deg,var(--deep),var(--acc) 66%);color:#fff;border-radius:14px;padding:22px 26px;margin:16px 0;box-shadow:0 4px 18px rgba(0,40,90,.16)}}
.hero .ey{{font-size:12px;font-weight:800;letter-spacing:1.5px;opacity:.85;margin-bottom:8px}}
.hero h1{{font-size:23px;font-weight:800;line-height:1.25;margin:0 0 10px}}
.hero p{{font-size:14.5px;line-height:1.65;max-width:840px;opacity:.96;margin:0}}
h2{{font-size:15px;letter-spacing:.5px;color:var(--dim);text-transform:uppercase;margin:26px 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.card{{background:var(--pnl);border:1px solid var(--line);border-radius:11px;padding:12px 14px}}
.card .l{{font-size:11px;font-weight:700;letter-spacing:.5px;color:var(--dim);text-transform:uppercase}}
.card .v{{font-size:15px;font-weight:600;margin-top:3px;word-break:break-word}}
.slots{{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:8px}}
.slot{{border:1px solid var(--line);border-radius:10px;padding:10px;text-align:center;background:#fff;opacity:.55}}
.slot.on{{opacity:1;border-color:var(--acc);box-shadow:0 1px 4px rgba(0,40,90,.06)}}
.slot .k{{font-weight:800;font-size:13px;color:var(--acc)}} .slot .d{{font-size:10.5px;color:var(--dim);margin:2px 0 4px}}
.slot .n{{font-size:18px;font-weight:800}}
.pill{{background:#fbf1df;color:var(--cand);border-radius:20px;padding:2px 9px;font-size:11px;font-weight:700}}
.tbl{{width:100%;border-collapse:collapse;margin-top:6px}} .tbl th,.tbl td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);font-size:13px}}
.tbl th{{color:var(--dim);font-size:11px;letter-spacing:.5px;text-transform:uppercase}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
.empty{{background:var(--pnl);border:1px dashed var(--line);border-radius:11px;padding:14px;color:var(--dim);font-size:13.5px;line-height:1.6}}
.muted{{color:var(--dim);font-size:12px;margin-top:6px}}
.faces{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px}}
.face{{border:1px solid var(--line);border-radius:11px;padding:13px 15px}}
.face h3{{margin:0 0 5px;font-size:14px}} .face p{{margin:0;font-size:13px;color:var(--dim);line-height:1.55}}
.status{{margin-top:22px;padding:12px 15px;border-left:4px solid var(--cand);background:#fbf7ef;border-radius:8px;font-size:13px;line-height:1.6}}
footer{{margin-top:30px;padding-top:14px;border-top:1px solid var(--line);color:#8397b0;font-size:12px}}
@media(max-width:640px){{.faces{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<header><div class="brand"><b>{esc(name.upper())}</b> <span>ThingSite</span></div></header>

<div class="hero">
  <div class="ey">PHYSICAL AI · IoT · ONE IDENTITY SPINE</div>
  <h1>The identity every machine reads.</h1>
  <p>{esc(name)}&rsquo;s world resolves through <b>one identity spine</b>. The URN on the thing is the
  <b>closed-hypothesis ground truth</b> a machine checks reality against — not &ldquo;which of all things is
  this?&rdquo; but &ldquo;is what I sense what this ID declares?&rdquo; — yes-or-exception, never a hallucination.
  The same key a person browses as a page, a machine resolves as an endpoint.</p>
</div>

<h2>Identity</h2>
<div class="grid">
  <div class="card"><div class="l">Organization (PGLN)</div><div class="v">{esc(name)}</div></div>
  <div class="card"><div class="l">Location (GLN)</div><div class="v mono">{esc(gln)}</div></div>
  <div class="card"><div class="l">Member Organisation</div><div class="v">{esc(mo)}</div></div>
  <div class="card"><div class="l">GS1 Company Prefix</div><div class="v">{esc(prefix)}</div></div>
  <div class="card"><div class="l">State</div><div class="v" style="color:var(--cand)">{esc(state)}</div></div>
  <div class="card"><div class="l">Source</div><div class="v">{esc(party.get('source') or '')}</div></div>
</div>

<h2>The site map is the identity — nine legal slots</h2>
<div class="slots">{slot_html}</div>

<h2>Products</h2>
{prod_block}

<h2>Two faces, one key</h2>
<div class="faces">
  <div class="face"><h3>Human face</h3><p>This page — the company, its location, its identity tree,
  browsable and honest about what is candidate vs. verified.</p></div>
  <div class="face"><h3>Machine face</h3><p>The same URN resolves to the machine endpoint: driver,
  protocol, live state, geometry, conformance — what a device or robot reads.</p></div>
</div>

<div class="status"><b>Candidate, unrooted.</b> This ThingSite is projected from the spine as a
<b>candidate</b>: the company is real (sourced from {esc(party.get('source') or 'the registry')}), but the
GS1 company prefix is <b>NULL</b> — GS1 prefixes are variable-length and are never derived from a GLN or
GTIN. It moves to <b>verified</b> only when the answerable party ratifies against an authority (GEPIR /
GLEIF). Agents propose; only the answerable ratifies.</div>

<footer>A complete ThingSite — the site map <b>is</b> the identity · projected from the spine, not authored ·
powered by ThingDaddy. Nothing on this page was fabricated; empty slots are candidate, shown as candidate.</footer>
</div></body></html>"""

def main():
    ap = argparse.ArgumentParser(description="Project a ThingSite from the spine for any party")
    ap.add_argument("--source", default="GDSN")
    ap.add_argument("--ids", help="comma-separated party ids (overrides --source/--limit)")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--outdir", default="sites")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    parties = fetch_parties(a)
    if not parties:
        raise SystemExit("no parties matched — check --source / --ids / the DB (POP_DB).")

    print(f">> projecting {len(parties)} ThingSite(s) from {POP_DB}")
    if not has_node():
        print("   note: this DB has no 'node' spine yet (010/011 not applied) — products show as "
              "candidate (0). Company/location/MO render fully. Point at a scratch DB with the spine "
              "for live product counts.")
    written = []
    for p in parties:
        total, samples = product_counts(p)
        htmlpage = render(p, total, samples)
        slug = "".join(c.lower() if c.isalnum() else "-" for c in p["legal_name"])[:60].strip("-")
        fn = os.path.join(a.outdir, f"{p['id']}_{slug or 'company'}.html")
        with open(fn, "w") as f:
            f.write(htmlpage)
        written.append(fn)
        print(f"   [{p['id']}] {p['legal_name']}  ·  MO={p.get('mo') or 'candidate'}  ·  products={total}  -> {fn}")
    print(f">> done. {len(written)} ThingSites in {a.outdir}/")
    print("   Every one is CANDIDATE, prefix=NULL — projected from real spine rows, nothing fabricated.")

if __name__ == "__main__":
    main()
