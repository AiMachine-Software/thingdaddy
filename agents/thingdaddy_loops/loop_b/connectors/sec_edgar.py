"""
sec_edgar.py — SEC EDGAR Exhibit 21 (Subsidiaries of the Registrant).

Yields subsidiary_of edges (subsidiary -> registrant) from EX-21 exhibits filed
inside 10-K filings. Public, free. EDGAR requires a descriptive User-Agent with a
contact email and limits to ~10 req/s (handled by the shared HttpClient).

Production path:
  company_tickers : https://www.sec.gov/files/company_tickers.json      (name/ticker -> CIK)
  submissions     : https://data.sec.gov/submissions/CIK##########.json (find latest 10-K)
  filing index    : https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/index.json
  EX-21 document  : parsed for 'Subsidiary name / Jurisdiction' rows
"""
import os, re, logging
from common.connector import BaseConnector
FIX = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures")
log = logging.getLogger("sec_edgar")

class SecEdgarConnector(BaseConnector):
    name = "sec_edgar"
    def __init__(self, store, cfg):
        super().__init__(store, cfg, FIX)

    def iter_subsidiary_edges(self, seeds=None):
        data = self._fixture("edgar.json") if self.offline else self._pull(seeds or [])
        for filing in data:
            parent = filing["parent"]; pc = filing.get("parent_country", "US")
            accn = filing.get("accession", "")
            for sub in filing.get("subsidiaries", []):
                key = f"{sub['name']}<-{parent}:{accn}"
                if self.store.stage("edgar_sub", key, sub):
                    yield {"parent": parent, "parent_country": pc,
                           "sub": sub["name"], "sub_country": sub.get("country", ""),
                           "citation": f"EDGAR EX-21 {accn}"}

    def _pull(self, seeds):
        headers = {"User-Agent": self.cfg.get("net", {}).get("user_agent",
                   "ThingDaddy loops contact@thingdaddy.com")}
        tickers = self._get_json("https://www.sec.gov/files/company_tickers.json", headers=headers)
        by_name = {v["title"].upper(): str(v["cik_str"]).zfill(10) for v in tickers.values()}
        out = []
        for seed in seeds:
            cik = by_name.get(seed.upper())
            if not cik:
                continue
            sub = self._get_json(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=headers)
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", []); accns = recent.get("accessionNumber", [])
            accn = next((accns[i] for i, f in enumerate(forms) if f == "10-K"), None)
            if not accn:
                continue
            nod = accn.replace("-", "")
            idx = self._get_json(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{nod}/index.json", headers=headers)
            doc = next((it["name"] for it in idx.get("directory", {}).get("item", [])
                        if re.search(r"ex-?21", it["name"], re.I)), None)
            if not doc:
                continue
            html = self._get_text(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{nod}/{doc}", headers=headers)
            subs = self._parse_ex21(html)
            out.append({"parent": seed, "parent_country": "US", "accession": accn, "subsidiaries": subs})
        return out

    @staticmethod
    def _parse_ex21(html):
        text = re.sub(r"<[^>]+>", "\t", html)
        subs = []
        for line in text.splitlines():
            cells = [c.strip() for c in line.split("\t") if c.strip()]
            if len(cells) >= 2 and re.search(r"[A-Za-z]{3,}", cells[0]) \
               and not re.search(r"subsidiar|jurisdiction|exhibit", cells[0], re.I):
                subs.append({"name": cells[0], "country": cells[1]})
        return subs
