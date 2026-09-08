#!/usr/bin/env python3
"""
render_p4_cloud_edge.py — render the Cloud & Edge (P4) layer for a ThingSite.

P4 = P1 + P2 + P3 deployed. This projects a company's identities onto the
CLOUD-AGNOSTIC binding  urn -> { aws:arn, azure:deviceId, edge:node }  and shows
the offline state model + the industrial OPC-UA edge path. AWS/Azure facts are
quoted from their own docs (reference_binding_and_cloud_edge_AWS_Azure).

DISCIPLINE (our rules — do not relax, sim-lane included):
  - IDs numeric; meaning lives in a bound LABEL, never inside the ID.
  - No fabricated prefix. Root shows VERIFIED only if identity_report carries a
    verified prefix; otherwise candidate. Item refs/serials stay candidate.
  - Cloud endpoints (ARN / deviceId / edge node) are SYNTHETIC projections,
    labelled source=synthetic — never a real assigned cloud resource.
  - Brand != registrant: we render the party as identity_report resolved it.

Offline, pure stdlib. Usage:
  python3 render_p4_cloud_edge.py --site sites/diazyme-laboratories
  python3 render_p4_cloud_edge.py --sites sites          # every site with a structure file
"""
import argparse, csv, json, os, sys, html

def esc(s): return html.escape(str(s if s is not None else ""))

def load_json(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}

def title_from_url(u):
    seg = (u or "").rstrip("/").split("/")[-1].replace(".html", "").replace("-", " ").strip()
    return (seg[:52] or "home")

def scan_struct(path):
    """Return (p4_urls, p1_gtin_urls) from a sitemap_structure.csv."""
    p4, p1 = [], []
    try:
        with open(path) as f:
            for row in csv.DictReader(f):
                pil = row.get("pillars") or ""
                if "P4" in pil: p4.append(row.get("url"))
                if "P1" in pil and (row.get("slot") == "GTIN"): p1.append(row.get("url"))
    except Exception:
        pass
    return p4, p1

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0e2a4a;background:#eef2f7;line-height:1.5}
.wrap{max-width:1000px;margin:0 auto;padding:26px 24px 60px}
header{border-bottom:3px solid #1f3a5f;padding-bottom:12px;margin-bottom:6px}
.eye{letter-spacing:.13em;text-transform:uppercase;font-size:11.5px;font-weight:700;color:#0a5e5d}
h1{font-size:23px;margin:5px 0 3px}
.sub{color:#5b6b78;font-size:14px}
.b{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:2px 8px;border-radius:20px;border:1px solid currentColor;vertical-align:middle}
.b.ok{color:#0a7d3c;background:#e4f6ea} .b.cand{color:#8a6d1f;background:#fbf3d9} .b.syn{color:#7a4ea8;background:#f0e9fa;border-color:#d6c4ec}
h2{font-size:15px;margin:26px 0 10px;color:#1f3a5f;display:flex;align-items:center;gap:8px}
h2 .n{display:inline-flex;width:22px;height:22px;border-radius:50%;background:#1f3a5f;color:#fff;font-size:12px;align-items:center;justify-content:center}
.card{background:#fff;border:1px solid #d8e1e8;border-radius:11px;padding:15px 16px;margin-bottom:12px}
.formula{background:#1f3a5f;color:#eaf1f8;border-radius:11px;padding:15px 18px;font-size:15px}
.formula b{color:#8fd7d3}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
.vx{font-family:-apple-system,sans-serif;font-size:10px;font-weight:700;color:#fff;background:#0a7d3c;border-radius:4px;padding:1px 5px}
.cx{font-family:-apple-system,sans-serif;font-size:9.5px;font-weight:700;text-transform:uppercase;color:#8a6d1f;background:#fbf3d9;border:1px solid #e8dca6;border-radius:5px;padding:0 5px}
table{width:100%;border-collapse:collapse;font-size:12.5px;background:#fff;border:1px solid #d8e1e8;border-radius:10px;overflow:hidden}
th{background:#1f3a5f;color:#fff;text-align:left;padding:8px 10px;font-size:11.5px}
td{padding:8px 10px;border-top:1px solid #e5ecf1;vertical-align:top}
td .mono{font-size:11px;color:#2a3b47}
.agn{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
@media(max-width:680px){.agn{grid-template-columns:1fr}}
.ep{border:1px solid #d8e1e8;border-radius:9px;padding:11px 12px;background:#fafcfe}
.ep h4{margin:0 0 4px;font-size:13px;color:#1f3a5f} .ep .mono{display:block;margin-top:5px;color:#42555f}
.src{font-size:11px;color:#5b6b78;margin-top:6px}
.note{font-size:12px;color:#5b6b78;margin-top:8px}
.pill{display:inline-block;background:#eef2f7;border:1px solid #d8e1e8;border-radius:6px;padding:1px 7px;font-size:11px;margin:2px 3px 0 0}
a{color:#0a5e5d}
footer{margin-top:30px;border-top:1px solid #d8e1e8;padding-top:12px;font-size:11.5px;color:#7a8791}
"""

def render_site(site_dir, sites_root):
    slug = os.path.basename(site_dir.rstrip("/"))
    pal = load_json(os.path.join(site_dir, "content_palette.json"))
    idr = load_json(os.path.join(site_dir, "identity_report.json"))
    struct = os.path.join(site_dir, "sitemap_structure.csv")
    if not os.path.exists(struct):
        return None
    company = pal.get("company") or slug
    domain = pal.get("domain") or ""
    pills = pal.get("pillars") or {}
    vp = (idr.get("verified_prefix") or {}).get("prefix")
    rooted = bool(idr.get("rooted"))
    p4_urls, p1_urls = scan_struct(struct)

    if vp and rooted:
        root_tok = f'<span class="vx">{esc(vp)}</span>'; root_badge = '<span class="b ok">verified root</span>'
    elif vp:
        root_tok = f'<span class="vx">{esc(vp)}</span>'; root_badge = '<span class="b ok">prefix on file</span>'
    else:
        root_tok = '<span class="cx">prefix candidate</span>'; root_badge = '<span class="b cand">candidate root</span>'

    rep_label = title_from_url(p1_urls[0]) if p1_urls else (company + " asset")
    # identity URN: numeric, meaning in label; item ref/serial candidate
    urn = f'urn:epc:id:sgtin:{root_tok}.<span class="cx">item ref</span>.<span class="cx">serial</span>'

    # cloud-agnostic endpoint projection (SYNTHETIC — placeholders, never real)
    aws = 'arn:aws:iot:&lt;region&gt;:&lt;account-id&gt;:thing/&lt;synthetic&gt;'
    azure = 'IoT Hub deviceId &lt;synthetic&gt;'
    edge = 'greengrass://&lt;node&gt;  /  iot-edge://&lt;module&gt;'

    # The AWS actual — real resource chain + ARN grammar (tenant values synthetic, never fabricated)
    aws_rows = [
        ("Thing (registry)", "arn:aws:iot:&lt;region&gt;:&lt;account-id&gt;:thing/&lt;thingName&gt;",
         "name is immutable — rename = delete+recreate = new identity (iot-dg p.447)"),
        ("Device Shadow (state)", "$aws/things/&lt;thingName&gt;/shadow",
         "desired / reported / delta — holds state connected or not (iot-device-shadows.html)"),
        ("Greengrass component (edge)", "arn:aws:greengrass:&lt;region&gt;:&lt;account-id&gt;:components:&lt;name&gt;",
         "edge runtime unit, runs locally, syncs to IoT Core (greengrass/v2)"),
        ("SiteWise asset (industrial)", "arn:aws:iotsitewise:&lt;region&gt;:&lt;account-id&gt;:asset/&lt;asset-id&gt;",
         "OPC-UA ingest via SiteWise Edge; up to 100 OPC UA servers per gateway (iot-sitewise)"),
    ]
    aws_actual = "".join(
        f'<tr><td><b>{esc(n)}</b></td><td><span class="mono">{arn}</span></td><td class="src" style="margin:0">{esc(note)}</td></tr>'
        for n, arn, note in aws_rows)

    body = f"""<div class="wrap">
<header>
  <div class="eye">ThingDaddy · Cloud &amp; Edge (P4)</div>
  <h1>{esc(company)} — Cloud &amp; Edge binding {root_badge}</h1>
  <div class="sub">{esc(domain)} &nbsp;·&nbsp; P4 = the identity + driver + workflow, deployed. Cloud-agnostic.</div>
</header>

<h2><span class="n">1</span> The binding — P1 + P2 + P3 = P4</h2>
<div class="formula">
  <b>P4 is not a fourth thing.</b> It is P1 (identity) + P2 (SiLA driver) + P3 (Allotrope method),
  <b>deployed</b> onto a cloud/edge runtime. Swap the runtime and P1+P2+P3 do not change — only the
  endpoint moves. The GS1 URN is the durable identity; each cloud's native ID is one endpoint beneath it.
</div>

<h2><span class="n">2</span> One resolution, every runtime <span class="b syn">synthetic projection</span></h2>
<div class="card">
  <div class="note" style="margin-top:0">Bound label: <b>{esc(rep_label)}</b> &nbsp;→&nbsp; identity (numeric, meaning in the label):</div>
  <div class="mono" style="margin:7px 0 12px">{urn}</div>
  <div class="agn">
    <div class="ep"><h4>AWS</h4><span class="mono">{aws}</span><div class="src">thing = name+attributes; the name is <b>immutable</b> (iot-dg p.447) — rename = delete+recreate = a new identity.</div></div>
    <div class="ep"><h4>Azure</h4><span class="mono">{azure}</span><div class="src">deviceId in the IoT Hub registry (SAS / X.509). Parallel to AWS; to be cited to learn.microsoft.com.</div></div>
    <div class="ep"><h4>Edge / on-prem</h4><span class="mono">{edge}</span><div class="src">Greengrass component / IoT Edge module running locally; talks to the cloud when connected.</div></div>
  </div>
  <div class="note"><b>Endpoints are synthetic placeholders</b> (source=synthetic) — a projection of the binding, never a real assigned cloud resource. The durable identity is the URN above; the cloud IDs are interchangeable plumbing beneath it.</div>
</div>

<h2><span class="n">3</span> State when disconnected — Shadow / Twin</h2>
<div class="card">
  AWS <b>Device Shadow</b> and Azure <b>Device Twin</b> hold state — <b>desired / reported / delta</b> —
  <i>whether the device is connected or not</i>; on reconnect the device syncs to it. That is where a
  warranty/return event or a run's status lives offline, bound to the identity above.
  <div class="src">Source: iot-device-shadows.html (AWS). Azure Device Twin parallel — to cite.</div>
</div>

<h2><span class="n">4</span> The industrial edge — OPC-UA / Kepware</h2>
<div class="card">
  On a plant floor: <b>Kepware (OPC-UA) → SiteWise Edge gateway (on Greengrass) → SiteWise cloud</b>;
  AWS documents <i>up to 100 OPC UA servers to a single gateway</i>. Azure parallel:
  <b>OPC Publisher → IoT Hub / IoT Operations</b>. Processing happens on-site before anything transmits.
  <div class="src">Source: iot-sitewise what-is-sitewise.html (AWS). Azure OPC Publisher — to cite.</div>
</div>

<h2><span class="n">5</span> The resolved binding — AWS actual</h2>
<div class="card">
  Resolving the identity in an AWS deployment terminates in <b>real AWS resources</b> — not the company's
  website. This is what the URN binds down to:
  <table style="margin-top:8px"><tr><th>AWS resource</th><th>ARN / handle</th><th>what it is (sourced)</th></tr>
  {aws_actual}</table>
  <div class="note">&lt;region&gt;, &lt;account-id&gt;, &lt;thingName&gt;, &lt;asset-id&gt; are
  <span class="b syn">synthetic placeholders</span> — we don't hold the customer's AWS account and never
  fabricate it. The ARN grammar and resource types are AWS's actual; the binding terminates in AWS while the
  durable identity stays the URN. (Azure parallel: IoT Hub device + Device Twin + IoT Edge module — to cite.
  The company's own web content lives in the ThingSite view, not here.)</div>
</div>

<footer>
  Cloud &amp; Edge (P4) layer · cloud-agnostic. Identity root {('VERIFIED ' + esc(vp)) if (vp and rooted) else 'candidate (no verified prefix — never guessed)'};
  item references, serials, and all cloud endpoints are candidate/synthetic and labelled as such. AWS facts quoted
  from docs.aws.amazon.com / iot-dg.pdf; Azure parallels marked to-cite. IDs numeric; meaning in bound labels.
</footer>
</div>"""

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(company)} · Cloud &amp; Edge (P4)</title><style>{CSS}</style></head>
<body>{body}</body></html>"""
    out = os.path.join(site_dir, slug + "_Cloud_Edge.html")
    with open(out, "w") as f:
        f.write(page)
    return out


def main():
    ap = argparse.ArgumentParser(description="Render the Cloud & Edge (P4) layer for ThingSites")
    ap.add_argument("--site", help="one site dir, e.g. sites/diazyme-laboratories")
    ap.add_argument("--sites", help="a sites root; render every site with a structure file")
    a = ap.parse_args()
    if a.site:
        o = render_site(a.site, os.path.dirname(a.site.rstrip("/")))
        print(">> cloud/edge ->", o if o else f"(skipped {a.site}: no structure file)")
    elif a.sites:
        n = 0
        for name in sorted(os.listdir(a.sites)):
            d = os.path.join(a.sites, name)
            if os.path.isdir(d) and os.path.exists(os.path.join(d, "sitemap_structure.csv")):
                o = render_site(d, a.sites)
                if o: n += 1; print("   ", o)
        print(f">> cloud/edge layer rendered for {n} site(s).")
    else:
        raise SystemExit("need --site or --sites")


if __name__ == "__main__":
    main()
