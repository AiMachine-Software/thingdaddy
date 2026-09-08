#!/usr/bin/env python3
"""
render_harvest_site.py — turn a sitemap-harvest (structure + documents CSVs) into a RICH
ThingSite: five-pillar breakdown (DRILL-DOWN), site-map structure, documents library, and
a data-driven IDENTITY-ROOT badge (VERIFIED with provenance, or candidate).

Reads the two CSVs produced by sitemap_harvest.py and renders one self-contained HTML page.
Everything is CANDIDATE + sourced unless the prefix is in the verified-prefixes registry.
Structure mirrored, not cloned; no GDTI URN minted (prefix-is-root holds). Empty shown empty.

Verified-prefixes registry (JSON), auto-located at ../standards/verified_prefixes.json or
./verified_prefixes.json, or pass --verified-prefixes PATH. Keyed by bare domain, e.g.:
  {"diazyme.com": {"prefix":"0817089","company":"Diazyme Laboratories",
    "status":"verified","source":"GEPIR 2026-07-20","verified_by":"GEPIR","date":"2026-07-20"}}

Usage:
  python3 render_harvest_site.py --name "Thermo Fisher Scientific" --domain thermofisher.com \
     --accent E1251B --deep 6e0f08 --structure sitemap_structure.csv \
     --documents sitemap_documents.csv --out ThermoFisher_ThingSite.html
"""
from __future__ import annotations
import argparse, csv, html, hashlib, os, re, json
from collections import Counter, defaultdict

PILLARS = [("P1","Identity","the products & catalog identifiers (GTIN / PGLN / GLN)"),
           ("P2","SiLA Driver","instrument drivers & connectivity software"),
           ("P3","Workflow","protocols, methods, application notes (Allotrope)"),
           ("P4","Cloud & Edge","cloud platforms, IoT, data management"),
           ("P5","AI Graph","accessories, compatibility, selection tools — the relationships")]
SLOT_LABEL = {"PGLN":"Organization / sections","GLN":"Locations","GTIN":"Products",
              "GDTI":"Documents","GIAI":"Serialized assets","":"Unmapped (candidate)"}
DOC_ORDER = ["driver","manual","datasheet","sds","certificate","application-note","pdf"]
DOC_LABEL = {"driver":"Drivers","manual":"Manuals","datasheet":"Datasheets","sds":"Safety Data Sheets",
             "certificate":"Certificates","application-note":"Application notes","pdf":"Other PDFs"}
DRILL_CAP = 60   # max links shown per pillar (remainder counted, never silently dropped)

def esc(s): return html.escape(str(s if s is not None else ""))

def accent_for(name):
    h = int(hashlib.sha1(name.encode()).hexdigest(),16)
    return f"hsl({h%360},62%,42%)", f"hsl({h%360},64%,24%)"

def read_csv(path):
    if not path or not os.path.exists(path): return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def bare_domain(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://","",d).split("/")[0]
    return re.sub(r"^www\.","",d)

def url_label(u):
    p = re.sub(r"^https?://[^/]+/?","",u or "").rstrip("/")
    if not p: return u or ""
    segs = [s for s in p.split("/") if s]
    seg = segs[-1] if segs else p
    seg = re.sub(r"\.(html?|pdf|aspx?|php)$","",seg, flags=re.I)
    seg = re.sub(r"[?#].*$","",seg)
    seg = re.sub(r"[-_+]+"," ",seg).strip()
    return (seg[:90] or (segs[-1] if segs else u))

def load_verified(path_arg):
    candidates = []
    if path_arg: candidates.append(path_arg)
    here = os.path.dirname(os.path.abspath(__file__))
    candidates += [os.path.join(here, "..", "standards", "verified_prefixes.json"),
                   os.path.join(here, "verified_prefixes.json"),
                   os.path.join(here, "..", "verified_prefixes.json")]
    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c) as f: return json.load(f), c
            except Exception:
                pass
    return {}, ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--domain", default="")
    ap.add_argument("--accent"); ap.add_argument("--deep")
    ap.add_argument("--structure", default="sitemap_structure.csv")
    ap.add_argument("--documents", default="sitemap_documents.csv")
    ap.add_argument("--out", default="harvest_thingsite.html")
    ap.add_argument("--per-type", type=int, default=14, help="max documents shown per type")
    ap.add_argument("--verified-prefixes", default="", help="path to verified_prefixes.json")
    a = ap.parse_args()

    struct = read_csv(a.structure)
    docs = read_csv(a.documents)
    acc = "#"+a.accent if a.accent else accent_for(a.name)[0]
    deep = "#"+a.deep if a.deep else accent_for(a.name)[1]

    verified, vpath = load_verified(a.verified_prefixes)
    root = verified.get(bare_domain(a.domain)) if a.domain else None
    root_ok = bool(root and str(root.get("status","")).lower() == "verified")

    slot_counts = Counter(r.get("slot","") for r in struct)
    pill_counts = Counter()
    pill_urls = defaultdict(list)
    for r in struct:
        u = r.get("url","")
        for p in (r.get("pillars") or "").split("|"):
            if p:
                pill_counts[p]+=1
                if u: pill_urls[p].append(u)
    sect_counts = Counter(r.get("section","") for r in struct)
    doc_by_type = defaultdict(list)
    for d in docs:
        doc_by_type[d.get("doc_type","pdf")].append(d)

    # ---- pillar cards (now DRILL-DOWN <details>) ----
    total_struct = max(1,len(struct))
    pill_cards = ""
    for code,name,mean in PILLARS:
        n = pill_counts.get(code,0)
        pct = round(100*n/total_struct)
        urls = pill_urls.get(code, [])
        # de-dupe preserving order
        seen=set(); uniq=[]
        for u in urls:
            if u not in seen: seen.add(u); uniq.append(u)
        shown = uniq[:DRILL_CAP]
        lis = "".join(
            f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(url_label(u))}</a></li>'
            for u in shown)
        more = (f'<div class="muted">+{len(uniq)-DRILL_CAP:,} more (not shown; open the site map for all)</div>'
                if len(uniq)>DRILL_CAP else "")
        drill = (f'<div class="drill"><ul>{lis}</ul>{more}</div>' if shown else
                 '<div class="drill muted">No pages tagged to this pillar in this harvest.</div>')
        face = (f'<div class="pc">{code} · {esc(name)} <span class="exp">▸</span></div>'
                f'<div class="pn">{n:,}</div><div class="pm">{esc(mean)}</div>'
                f'<div class="bar"><span style="width:{min(100,pct)}%"></span></div>'
                f'<div class="ppct">{pct}% of pages · click to drill in</div>')
        pill_cards += (f'<details class="pill{" on" if n else ""}">'
                       f'<summary>{face}</summary>{drill}</details>')

    # ---- identity-root badge ----
    if root_ok:
        prov = " · ".join(x for x in [esc(root.get("source","")),
                                      ("first-party: "+esc(root.get("verified_by",""))) if root.get("verified_by") else "",
                                      esc(root.get("date",""))] if x)
        root_badge = (f'<div class="root ok"><span class="bdg">✓ IDENTITY ROOT VERIFIED</span>'
                      f'<span>GS1 Company Prefix <span class="pfx">{esc(root.get("prefix",""))}</span></span>'
                      f'<span class="prov">{prov}</span></div>')
    else:
        root_badge = ('<div class="root cand"><span class="bdg">◇ IDENTITY ROOT: CANDIDATE</span>'
                      '<span>GS1 company prefix not yet ratified — root the harvest and let the '
                      'answerable party confirm (R4).</span></div>')

    # ---- site-map (top sections + slot mix) ----
    slot_rows = "".join(
        f'<tr><td>{esc(SLOT_LABEL.get(k,k))}</td><td class="mono">{k or "—"}</td>'
        f'<td class="r">{v:,}</td></tr>'
        for k,v in slot_counts.most_common())
    sect_rows = "".join(
        f'<span class="chip">{esc(s or "home")}<b>{v:,}</b></span>'
        for s,v in sect_counts.most_common(18) if s)

    # ---- documents library ----
    doc_blocks = ""
    seen_types = [t for t in DOC_ORDER if t in doc_by_type] + [t for t in doc_by_type if t not in DOC_ORDER]
    for t in seen_types:
        items = doc_by_type[t]
        lis = "".join(
            f'<li><a href="{esc(d.get("url"))}" target="_blank" rel="noopener">{esc(d.get("title") or d.get("url"))}</a>'
            f'{" ".join(f"<span class=tag>"+esc(p)+"</span>" for p in (d.get("pillars") or "").split("|") if p)}</li>'
            for d in items[:a.per_type])
        more = f'<div class="muted">+{len(items)-a.per_type} more</div>' if len(items)>a.per_type else ""
        doc_blocks += (f'<div class="docgrp"><h3>{esc(DOC_LABEL.get(t,t.title()))} '
                       f'<span class="cnt">{len(items):,}</span></h3><ul>{lis}</ul>{more}</div>')
    total_docs = len(docs)

    if root_ok:
        status = (f'<div class="status ok"><b>Root VERIFIED · content candidate.</b> The GS1 company prefix '
                  f'<b>{esc(root.get("prefix",""))}</b> is ratified for {esc(a.name)} '
                  f'({esc(root.get("source","")) or "registry"}, first-party). The products, sections and documents '
                  f'below remain <b>candidate</b> — each is rooted and ratified on its own; a verified prefix does '
                  f'not auto-verify its children. Structure mirrored, not cloned; nothing minted.</div>')
    else:
        status = (f'<div class="status"><b>Candidate, sourced, unrooted.</b> Every product, section and document here '
                  f'is a <b>candidate</b> mirrored from {esc(a.domain or a.name)}&rsquo;s public site map — provenance '
                  f'is their own URL. No GS1 prefix is derived and no GDTI URN is minted (prefix-is-root holds); '
                  f'documents are candidate references until the company is rooted and the answerable party ratifies '
                  f'(R4). Structure is mirrored, not cloned; ambiguous pages were left unmapped, not force-fit.</div>')

    htmlpage = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(a.name)} · ThingSite</title>
<style>
:root{{--acc:{acc};--deep:{deep};--ink:#0e2a4a;--dim:#5a6b82;--line:#d6e0ee;--pnl:#f4f8fc;--cand:#b4700a;--ok:#137a4c}}
*{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff}}
.wrap{{max-width:1040px;margin:0 auto;padding:22px 26px 70px}}
header{{display:flex;align-items:center;gap:12px;padding:6px 0 14px;border-bottom:2px solid var(--acc);flex-wrap:wrap}}
.brand b{{color:var(--acc);letter-spacing:.5px}} .brand span{{color:#8397b0;font-weight:700}}
.hero{{background:linear-gradient(100deg,var(--deep),var(--acc) 66%);color:#fff;border-radius:14px;padding:22px 26px;margin:16px 0;box-shadow:0 4px 18px rgba(0,40,90,.16)}}
.hero .ey{{font-size:12px;font-weight:800;letter-spacing:1.5px;opacity:.85;margin-bottom:8px}}
.hero h1{{font-size:23px;font-weight:800;line-height:1.25;margin:0 0 10px}}
.hero p{{font-size:14px;line-height:1.6;max-width:860px;opacity:.96;margin:0}}
.root{{display:flex;align-items:center;gap:10px 14px;flex-wrap:wrap;margin:0 0 4px;padding:11px 15px;border-radius:10px;font-size:13px;border:1px solid}}
.root.ok{{background:#e8f6ee;border-color:#bfe6cd;color:var(--ok)}}
.root.cand{{background:#fbf7ef;border-color:#ecdcbc;color:var(--cand)}}
.root .bdg{{font-weight:800;letter-spacing:.4px}} .root .pfx{{font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:800}}
.root .prov{{color:var(--dim);font-size:12px}}
h2{{font-size:15px;letter-spacing:.5px;color:var(--dim);text-transform:uppercase;margin:28px 0 12px}}
.pills{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;align-items:start}}
.pill{{border:1px solid var(--line);border-radius:12px;padding:13px 15px;opacity:.5}}
.pill.on{{opacity:1;border-color:var(--acc)}}
.pill>summary{{list-style:none;cursor:pointer;outline:none}} .pill>summary::-webkit-details-marker{{display:none}}
.pill[open]{{box-shadow:0 4px 16px rgba(0,40,90,.10)}}
.pill .pc{{font-size:12px;font-weight:800;color:var(--acc)}} .pill .exp{{float:right;transition:transform .15s;color:var(--dim)}}
.pill[open] .exp{{transform:rotate(90deg)}}
.pill .pn{{font-size:26px;font-weight:800;margin:2px 0}}
.pill .pm{{font-size:12px;color:var(--dim);line-height:1.45;min-height:34px}}
.bar{{height:6px;background:#eef2f8;border-radius:6px;overflow:hidden;margin:8px 0 3px}} .bar span{{display:block;height:100%;background:var(--acc)}}
.ppct{{font-size:11px;color:var(--dim)}}
.drill{{margin-top:10px;border-top:1px dashed var(--line);padding-top:8px;max-height:340px;overflow:auto}}
.drill ul{{margin:0;padding-left:16px}} .drill li{{font-size:12px;line-height:1.5;margin:2px 0}}
.drill a{{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line);word-break:break-word}}
.drill a:hover{{border-color:var(--acc)}}
.cols{{display:grid;grid-template-columns:1fr 1.1fr;gap:16px}} @media(max-width:760px){{.cols{{grid-template-columns:1fr}}}}
.tbl{{width:100%;border-collapse:collapse}} .tbl td{{padding:6px 8px;border-bottom:1px solid var(--line);font-size:13px}} .tbl .r{{text-align:right;font-weight:700}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;color:var(--dim)}}
.chip{{display:inline-block;background:var(--pnl);border:1px solid var(--line);border-radius:20px;padding:3px 10px;margin:3px 4px 0 0;font-size:12px}} .chip b{{margin-left:6px;color:var(--acc)}}
.docgrp{{border:1px solid var(--line);border-radius:12px;padding:12px 15px;margin-bottom:12px;background:#fff}}
.docgrp h3{{margin:0 0 8px;font-size:15px}} .docgrp .cnt{{background:var(--acc);color:#fff;border-radius:20px;padding:1px 9px;font-size:12px;margin-left:6px}}
.docgrp ul{{margin:0;padding-left:18px}} .docgrp li{{font-size:13px;line-height:1.55;margin:3px 0}}
.docgrp a{{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}} .docgrp a:hover{{border-color:var(--acc)}}
.tag{{background:var(--pnl);color:var(--dim);border-radius:5px;padding:0 5px;font-size:10.5px;margin-left:5px}}
.muted{{color:var(--dim);font-size:12px;margin-top:5px}}
.status{{margin-top:24px;padding:12px 15px;border-left:4px solid var(--cand);background:#fbf7ef;border-radius:8px;font-size:13px;line-height:1.6}}
.status.ok{{border-left-color:var(--ok);background:#eef8f1}}
footer{{margin-top:28px;padding-top:14px;border-top:1px solid var(--line);color:#8397b0;font-size:12px}}
</style></head><body><div class="wrap">
<header><div class="brand"><b>{esc(a.name.upper())}</b> <span>ThingSite</span></div></header>
<div class="hero"><div class="ey">PHYSICAL AI · IoT · ONE IDENTITY SPINE</div>
<h1>The identity every machine reads.</h1>
<p>Projected from {esc(a.domain or a.name)}&rsquo;s own site map onto one identity spine — organized by the five
pillars, with {total_docs:,} helpful-content documents surfaced. The URN on the thing is the closed-hypothesis
ground truth a machine checks reality against; the same key a person browses as a page, a machine resolves as an
endpoint.</p></div>
{root_badge}

<h2>The five pillars — what their content feeds <span style="text-transform:none;font-weight:400">(click a card to drill in)</span></h2>
<div class="pills">{pill_cards}</div>

<h2>Site map — their structure, on our slots</h2>
<div class="cols">
  <table class="tbl">{slot_rows}</table>
  <div><div class="muted" style="margin-bottom:6px">Top sections (mirrored, not cloned):</div>{sect_rows}</div>
</div>

<h2>Documents · helpful content ({total_docs:,} candidate GDTI references)</h2>
{doc_blocks or '<div class="muted">No documents surfaced in this harvest.</div>'}

{status}
<footer>A ThingSite — the site map <b>is</b> the identity · projected from {esc(a.domain or a.name)} · powered by
ThingDaddy. Nothing fabricated; candidate shown as candidate.</footer>
</div></body></html>"""

    with open(a.out,"w") as f: f.write(htmlpage)
    print(f">> wrote {a.out}  ({len(htmlpage):,} bytes)")
    print(f"   root   : {'VERIFIED '+root.get('prefix','') if root_ok else 'candidate (unratified)'}"
          + (f"  [registry: {vpath}]" if vpath else "  [no verified-prefixes registry found]"))
    print(f"   pillars: " + ", ".join(f"{c}={pill_counts.get(c,0)}" for c,_,_ in PILLARS))
    print(f"   drill  : " + ", ".join(f"{c}={min(len(pill_urls.get(c,[])),DRILL_CAP)}/{len(pill_urls.get(c,[]))}" for c,_,_ in PILLARS))
    print(f"   docs   : {total_docs} across {len(doc_by_type)} types")

if __name__ == "__main__":
    main()
