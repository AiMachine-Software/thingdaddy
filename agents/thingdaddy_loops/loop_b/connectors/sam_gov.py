"""
sam_gov.py — SAM.gov Entity Management (UEI, legal name, parent). Requires an API key.

Yields parent_of edges (parent -> entity) and corroborates legal identity by UEI.
Production: https://api.sam.gov/entity-information/v3/entities?api_key=KEY&...
With no key configured, returns nothing (verified-or-exception: other sources still flow).
"""
import os, logging
from common.connector import BaseConnector
FIX = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures")
log = logging.getLogger("sam_gov")

class SamGovConnector(BaseConnector):
    name = "sam_gov"
    def __init__(self, store, cfg):
        super().__init__(store, cfg, FIX)

    def iter_parent_edges(self):
        data = self._fixture("sam.json") if self.offline else self._pull()
        for e in data:
            if not e.get("parent"):
                continue
            key = f"{e['parent']}->{e['entity']}:{e.get('uei','')}"
            if self.store.stage("sam_parent", key, e):
                yield {"parent": e["parent"], "parent_country": e.get("parent_country", "US"),
                       "entity": e["entity"], "entity_country": e.get("country", "US"),
                       "citation": f"SAM.gov UEI {e.get('uei','?')}"}

    def _pull(self):
        key = (self.cfg.get("sam_gov") or {}).get("api_key")
        if not key:
            log.info("SAM.gov: no api_key configured; skipping (edges from other sources still flow)")
            return []
        names = (self.cfg.get("sam_gov") or {}).get("watchlist", [])
        out = []
        for nm in names:
            url = (f"https://api.sam.gov/entity-information/v3/entities?api_key={key}"
                   f"&legalBusinessName={nm.replace(' ', '%20')}")
            res = self._get_json(url)
            for ent in res.get("entityData", []):
                core = ent.get("entityRegistration", {})
                parent = (ent.get("coreData", {}).get("entityHierarchyInformation", {})
                          .get("immediateParentEntity", {}) or {}).get("legalBusinessName")
                out.append({"entity": core.get("legalBusinessName"), "uei": core.get("ueiSAM"),
                            "parent": parent, "country": "US", "parent_country": "US"})
        return out
