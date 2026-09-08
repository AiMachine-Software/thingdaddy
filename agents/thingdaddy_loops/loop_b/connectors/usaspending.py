"""
usaspending.py — USASpending.gov federal awards (open API, no key).

Yields two edge kinds:
  contracts_with : recipient  -> awarding agency (buyer/seller)
  supplier_of    : subawardee -> prime recipient (supply relationship)

Production path:
  POST https://api.usaspending.gov/api/v2/search/spending_by_award/
  POST https://api.usaspending.gov/api/v2/subawards/
"""
import os, logging
from common.connector import BaseConnector
FIX = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures")
log = logging.getLogger("usaspending")

class UsaSpendingConnector(BaseConnector):
    name = "usaspending"
    def __init__(self, store, cfg):
        super().__init__(store, cfg, FIX)

    def iter_award_edges(self):
        data = self._fixture("usaspending.json") if self.offline else self._pull()
        for award in data:
            aid = award.get("award_id", "")
            if self.store.stage("usa_award", aid, award):
                yield {"kind": "contracts_with", "src": award["recipient"],
                       "src_country": award.get("recipient_country", "US"),
                       "dst": award["awarding_agency"], "dst_type": "agency",
                       "citation": f"USASpending award {aid}"}
            for sub in award.get("subawards", []):
                key = f"{sub['recipient']}->{award['recipient']}:{aid}"
                if self.store.stage("usa_subaward", key, sub):
                    yield {"kind": "supplier_of", "src": sub["recipient"],
                           "src_country": sub.get("country", "US"),
                           "dst": award["recipient"], "dst_type": "company",
                           "citation": f"USASpending subaward {aid}"}

    def _pull(self):
        base = "https://api.usaspending.gov/api/v2"
        flt = self.cfg.get("usaspending", {}).get("filters", {"time_period": [{"start_date": "2024-01-01", "end_date": "2025-12-31"}]})
        payload = {"filters": flt, "fields": ["Award ID", "Recipient Name", "Awarding Agency"],
                   "page": int(self.store.get_cursor("usaspending") or 1), "limit": 100}
        res = self._post_json(f"{base}/search/spending_by_award/", payload)
        out = []
        for r in res.get("results", []):
            out.append({"award_id": r.get("Award ID"), "recipient": r.get("Recipient Name"),
                        "recipient_country": "US", "awarding_agency": r.get("Awarding Agency"),
                        "subawards": []})
        self.store.set_cursor("usaspending", payload["page"] + 1)
        return out
