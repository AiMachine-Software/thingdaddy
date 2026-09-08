"""gleif.py — GLEIF Global LEI Index (free, CC0). Spine of the profile graph."""
import os, logging
from common.connector import BaseConnector
from common.resolve import normalize
FIX = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures")
log = logging.getLogger("gleif")

class GleifConnector(BaseConnector):
    name = "gleif"
    def __init__(self, store, cfg):
        super().__init__(store, cfg, FIX)

    def iter_parties(self):
        data = self._fixture("gleif_lei.json") if self.offline else self._pull_level1()
        for rec in data:
            if self.store.stage("gleif_l1", rec["lei"], rec):
                yield rec["lei"], rec["name"], rec.get("country", "")

    def iter_ownership(self):
        data = self._fixture("gleif_rr.json") if self.offline else self._pull_level2()
        for rec in data:
            key = f"{rec['child']}->{rec['parent']}:{rec.get('rel','')}"
            if self.store.stage("gleif_l2", key, rec):
                yield rec["child"], rec["parent"], rec.get("rel", "consolidated_by")

    # --- production: GLEIF Golden Copy (Level 1 lei2, Level 2 rr). CC0. ---
    def _pull_level1(self):
        url = self.cfg["gleif"]["lei2_url"]
        cur = self.store.get_cursor("gleif_l1")
        if cur:
            url = self.cfg["gleif"].get("lei2_delta_url", url)
        payload = self._get_json(url)
        recs = payload.get("records", payload if isinstance(payload, list) else [])
        out = []
        for r in recs:
            ent = r.get("entity", r)
            ln = ent.get("legalName")
            name = ln.get("name") if isinstance(ln, dict) else ln
            addr = ent.get("legalAddress") or {}
            out.append({"lei": r.get("lei") or r.get("id"), "name": name,
                        "country": addr.get("country", "")})
        self.store.set_cursor("gleif_l1", payload.get("publishDate", "latest"))
        return out

    def _pull_level2(self):
        url = self.cfg["gleif"]["rr_url"]
        payload = self._get_json(url)
        recs = payload.get("records", payload if isinstance(payload, list) else [])
        out = []
        for r in recs:
            rr = r.get("relationship", r)
            sn, en = rr.get("startNode", {}), rr.get("endNode", {})
            out.append({"child": sn.get("id") if isinstance(sn, dict) else rr.get("child"),
                        "parent": en.get("id") if isinstance(en, dict) else rr.get("parent"),
                        "rel": rr.get("type", "consolidated_by")})
        return out
