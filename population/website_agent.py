#!/usr/bin/env python3
"""
website_agent.py — the ThingSite content engine. Orchestrates the built stages into one
resumable run: a company in -> the full content palette + ThingSite + P5 graph out.

Stages (each skipped if its output exists, unless --force):
  1 sitemap harvest   -> sitemap_structure.csv, sitemap_documents.csv   (structure + pillars + docs)
  2 page read         -> page_documents.csv, page_gtins.csv, page_edges.csv  (real PDFs, GTINs, edges)
  M mine PDFs  (--mine) -> doc_attribution/identifiers/settings.csv, mined_gtins.csv (labeled GTINs)
  3 render ThingSite  -> <slug>_ThingSite.html
  4 render P5 graph   -> <slug>_P5_Graph.html
  5 identity xref (--root) -> identity_roots.csv (roots page + mined GTINs to a WHO)

Everything CANDIDATE + sourced; nothing minted; config not code. --mine reads INSIDE the PDFs (the
clean GTIN source); --root cross-references identity (registry + GLEIF/GEPIR) to root it to a WHO.

Usage:
  python3 website_agent.py --domain thermofisher.com --name "Thermo Fisher Scientific" --accent E1251B --deep 6e0f08
  python3 website_agent.py --domain thermofisher.com --name "Thermo Fisher Scientific" --mine --root --gleif
"""
from __future__ import annotations
import argparse, csv, json, os, subprocess, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))          # .../population
SITEMAP   = os.path.join(HERE, "sitemap", "sitemap_harvest.py")
RENDER    = os.path.join(HERE, "sitemap", "render_harvest_site.py")
PAGES     = os.path.join(HERE, "pagereader", "page_reader.py")
GRAPH     = os.path.join(HERE, "standards", "render_p5_graph.py")
MINEDGRAPH= os.path.join(HERE, "standards", "render_mined_graph.py")
BINDINGS  = os.path.join(HERE, "standards", "binding_sets.py")
STANDARDS = os.path.join(HERE, "standards")
IDENTITY  = os.path.join(HERE, "identity", "identity_xref.py")
DOCMINE   = os.path.join(HERE, "docmine", "docmine.py")

def slugify(s): return ("".join(c.lower() if c.isalnum() else "-" for c in s)[:50].strip("-")) or "company"
def have(p): return os.path.exists(p) and os.path.getsize(p) > 0
def count_rows(p):
    if not have(p): return 0
    with open(p, newline="") as f: return max(0, sum(1 for _ in f) - 1)

def build_mined_gtins(docids, out_csv):
    """labeled + check-valid GTINs from docmine -> spine rows (the clean GTIN source)."""
    seen, rows = set(), []
    if have(docids):
        with open(docids, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("id_kind") == "gtin" and (r.get("gtin_if_valid") or ""):
                    g = r["gtin_if_valid"]
                    if g not in seen:
                        seen.add(g); rows.append(["urn:epc:id:gtin:" + g, "gtin", "", "", "", "candidate", "WEB-DOC"])
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["urn", "key_type", "prefix", "gln", "mo", "state", "source"]); w.writerows(rows)
    return len(rows)

def merge_gtins(paths, out_csv):
    """union GTIN spine CSVs, dedup by urn (labeled doc GTINs first — they win the source stamp)."""
    seen, rows = set(), []
    for p in paths:
        if not have(p): continue
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                u = r.get("urn")
                if u and u not in seen:
                    seen.add(u); rows.append([u, r.get("key_type", "gtin"), r.get("prefix", ""),
                                              r.get("gln", ""), r.get("mo", ""), r.get("state", "candidate"),
                                              r.get("source", "WEB")])
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["urn", "key_type", "prefix", "gln", "mo", "state", "source"]); w.writerows(rows)
    return len(rows)

def run(cmd, label):
    print("   $ " + " ".join(cmd))
    rc = subprocess.run(cmd).returncode
    if rc != 0: print(f"   !! stage '{label}' exited {rc}", file=sys.stderr)
    return rc == 0

def main():
    ap = argparse.ArgumentParser(description="ThingSite content engine — orchestrate the harvest stages")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--accent", default=""); ap.add_argument("--deep", default="")
    ap.add_argument("--limit", type=int, default=4000, help="max sitemap urls")
    ap.add_argument("--pages-limit", type=int, default=80, help="max pages to read")
    ap.add_argument("--max-sitemaps", type=int, default=1)
    ap.add_argument("--outdir", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--fast", action="store_true",
                    help="skeleton build: sitemap -> ThingSite + P5 graph only (skip page-read/binding/mine) — fast, for fleet scale")
    ap.add_argument("--mine", action="store_true",
                    help="stage M: mine inside manual/protocol PDFs (docmine) — labeled GTINs + attribution + settings")
    ap.add_argument("--mine-limit", type=int, default=40, help="max PDFs to mine")
    ap.add_argument("--mine-doc-type", default="", help="restrict mining to a doc_type (default: all)")
    ap.add_argument("--root", action="store_true",
                    help="run stage 5 identity cross-reference (root the harvest to a WHO via the registry)")
    ap.add_argument("--gleif", action="store_true", help="stage 5: fill LEI from GLEIF")
    ap.add_argument("--gepir", action="store_true", help="stage 5: discover licensees via GEPIR")
    a = ap.parse_args()

    slug = slugify(a.name)
    out = a.outdir or os.path.join(HERE, "sites", slug)
    os.makedirs(out, exist_ok=True)
    print(f">> website agent · {a.name} ({a.domain})  ->  {out}")

    struct = os.path.join(out, "sitemap_structure.csv")
    docs   = os.path.join(out, "sitemap_documents.csv")
    site   = os.path.join(out, f"{slug}_ThingSite.html")
    graph  = os.path.join(out, f"{slug}_P5_Graph.html")
    pdfs   = os.path.join(out, "page_documents.csv")
    gtins  = os.path.join(out, "page_gtins.csv")
    docids = os.path.join(out, "doc_identifiers.csv")
    mined  = os.path.join(out, "mined_gtins.csv")
    allg   = os.path.join(out, "all_gtins.csv")
    minedgraph = os.path.join(out, f"{slug}_Mined_Graph.html")
    roots  = os.path.join(out, "identity_roots.csv")

    # 1 · sitemap harvest
    if a.force or not have(struct):
        print(">> [1/4] sitemap harvest")
        run(["python3", SITEMAP, "--domain", a.domain, "--limit", str(a.limit),
             "--max-sitemaps", str(a.max_sitemaps), "--outdir", out], "sitemap")
    else: print(">> [1/4] sitemap harvest — cached")

    # 2 · page read (real PDFs + GTINs + edges) — skipped in --fast skeleton mode
    if a.fast:
        print(">> [2/4] page read — skipped (--fast)")
    elif a.force or not have(pdfs):
        print(">> [2/4] page read")
        if have(docs):
            run(["python3", PAGES, "--docs", docs, "--limit", str(a.pages_limit), "--outdir", out], "pages")
        else:
            print("   (no documents to read — skipping)")
    else: print(">> [2/4] page read — cached")

    # M · document-content mining (docmine) — opt-in; downloads the PDFs and reads inside them
    if a.mine:
        if a.force or not have(docids):
            print(">> [M] document-content mining (inside the PDFs)")
            if have(pdfs):
                cmd = ["python3", DOCMINE, "--docs", pdfs, "--limit", str(a.mine_limit), "--outdir", out]
                if a.mine_doc_type: cmd += ["--doc-type", a.mine_doc_type]
                run(cmd, "docmine")
            else:
                print("   (no page_documents.csv to mine — skipping)")
        else: print(">> [M] document-content mining — cached")
        n_mined = build_mined_gtins(docids, mined)   # labeled valid GTINs -> spine rows
        print(f"   mined labeled GTINs -> spine: {n_mined}  ({mined})")
        # render the REAL protocol graph from what was mined (the miner's notes on the staff)
        if a.force or not have(minedgraph):
            if have(os.path.join(out, "doc_settings.csv")) or have(docids):
                run(["python3", MINEDGRAPH, "--mined-dir", out, "--name", a.name, "--out", minedgraph], "mined-graph")

    # 2.5 · binding sets (real published edges -> candidate binding/substitution sets) — cheap, no network
    pedges  = os.path.join(out, "page_edges.csv")
    bindcsv = os.path.join(out, "binding_sets.csv")
    if have(pedges) and (a.force or not have(bindcsv)):
        print(">> [2.5] binding sets (driver · protocol · substitution slot)")
        run(["python3", BINDINGS, "--edges", pedges, "--name", a.name, "--outdir", out], "bindings")

    # 3 · render ThingSite
    if a.force or not have(site):
        print(">> [3/4] render ThingSite")
        cmd = ["python3", RENDER, "--name", a.name, "--domain", a.domain,
               "--structure", struct, "--documents", docs, "--out", site]
        if a.accent: cmd += ["--accent", a.accent]
        if a.deep:   cmd += ["--deep", a.deep]
        run(cmd, "render")
    else: print(">> [3/4] render ThingSite — cached")

    # 4 · render P5 graph
    if a.force or not have(graph):
        print(">> [4/4] render P5 graph")
        run(["python3", GRAPH, "--standards", STANDARDS,
             "--instrument", f"{a.name} instrument (GTIN · candidate)", "--out", graph], "graph")
    else: print(">> [4/4] render P5 graph — cached")

    # 5 · identity cross-reference (root the harvest to a WHO) — opt-in; needs the DB
    if a.root:
        # root the union of page-scraped GTINs + mined labeled GTINs (mined win the source stamp)
        root_input = gtins
        if a.mine and have(mined):
            merge_gtins([mined, gtins], allg); root_input = allg
        if a.force or not have(roots):
            print(">> [5] identity cross-reference (root to a WHO)")
            if have(root_input):
                cmd = ["python3", IDENTITY, "--gtins", root_input, "--company", a.name,
                       "--domain", a.domain, "--outdir", out]
                if a.gleif: cmd.append("--gleif")
                if a.gepir: cmd.append("--gepir")
                run(cmd, "identity")
            else:
                print("   (no candidate GTINs to root — skipping)")
        else: print(">> [5] identity cross-reference — cached")

    # content palette summary (the valuable-content metric)
    pillars = Counter()
    if have(struct):
        with open(struct, newline="") as f:
            for r in csv.DictReader(f):
                for p in (r.get("pillars") or "").split("|"):
                    if p: pillars[p] += 1
    # rooting outcome (stage 5), if it ran
    ident = None
    ipath = os.path.join(out, "identity_report.json")
    if have(ipath):
        try:
            with open(ipath) as f: ident = json.load(f)
        except Exception: ident = None
    rooted = bool(ident and ident.get("rooted"))

    mined_stats = ({"labeled_gtins": count_rows(mined),
                    "attribution": count_rows(os.path.join(out, "doc_attribution.csv")),
                    "identifiers": count_rows(docids),
                    "settings": count_rows(os.path.join(out, "doc_settings.csv"))}
                   if a.mine else None)

    palette = {
        "company": a.name, "domain": a.domain, "outdir": out,
        "sitemap_urls": count_rows(struct), "documents_sitemap": count_rows(docs),
        "documents_files": count_rows(pdfs), "gtins": count_rows(gtins),
        "mined": mined_stats,
        "edges": count_rows(os.path.join(out, "page_edges.csv")),
        "binding_sets": count_rows(bindcsv), "pillars": dict(pillars),
        "thingsite": site if have(site) else None, "graph": graph if have(graph) else None,
        "rooted": rooted,
        "identity": ({"who": ident.get("who"), "lei": ident.get("lei"),
                      "gtin_rooting": ident.get("gtin_rooting")} if ident else None),
        "note": ("ROOTED to a WHO (candidate → R4 ratifies)" if rooted else
                 "candidate + sourced; UNROOTED — run with --root to cross-reference identity (prefix/GLN/GTIN/LEI)"),
    }
    with open(os.path.join(out, "content_palette.json"), "w") as f: json.dump(palette, f, indent=2)

    print(">> content palette")
    print(f"   urls={palette['sitemap_urls']} · docs(sitemap)={palette['documents_sitemap']} · "
          f"files(pdf)={palette['documents_files']} · gtins={palette['gtins']} · edges={palette['edges']}")
    if pillars: print("   pillars: " + ", ".join(f"{k}={v}" for k, v in sorted(pillars.items())))
    if mined_stats:
        print(f"   mined(pdf): labeled-gtins={mined_stats['labeled_gtins']} · attribution={mined_stats['attribution']} · "
              f"identifiers={mined_stats['identifiers']} · settings={mined_stats['settings']}")
    print(f"   -> ThingSite : {site}")
    print(f"   -> P5 graph  : {graph}")
    print(f"   -> palette   : {os.path.join(out,'content_palette.json')}")
    if ident:
        r = ident.get("gtin_rooting", {})
        who = (ident.get("who") or {}).get("legal_name")
        if rooted:
            print(f">> ROOTED — {r.get('confirmed',0)} GTIN(s) tie to {who}. Candidate → R4 ratifies. Nothing minted.")
        else:
            print(f">> STILL UNROOTED — no confirmed GTIN↔party tie (confirmed={r.get('confirmed',0)}, "
                  f"band-only={r.get('band_only',0)}, unrooted={r.get('unrooted',0)}). Candidate; nothing guessed.")
    else:
        print(">> UNROOTED — content is candidate. Run again with --root to cross-reference identity (registry + GLEIF/GEPIR).")

if __name__ == "__main__":
    main()
