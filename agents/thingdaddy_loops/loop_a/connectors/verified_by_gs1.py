"""verified_by_gs1.py — authoritative confirmer of prefix + true length. Licensed MO path."""
import os, logging
from common.connector import BaseConnector
FIX = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures")
log = logging.getLogger("vbg")

class VerifiedByGS1Connector(BaseConnector):
    name = "verified_by_gs1"
    def __init__(self, store, cfg):
        super().__init__(store, cfg, FIX)
        self._table = {row["prefix"]: row for row in self._fixture("vbg.json")} if self.offline else {}

    def confirm(self, candidate_prefix):
        if candidate_prefix is None:
            return None
        if self.offline:
            return self._table.get(candidate_prefix)
        ep = (self.cfg.get("verified_by_gs1") or {}).get("data_hub_endpoint")
        if not ep:
            return None                      # no licensed access -> stays candidate
        try:
            payload = self._get_json(f"{ep}?prefix={candidate_prefix}")
            return payload or None
        except Exception as e:
            log.warning("VbG confirm failed for %s: %s", candidate_prefix, e)
            return None
