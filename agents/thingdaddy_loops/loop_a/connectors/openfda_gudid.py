"""
openfda_gudid.py — structured device records (openFDA / GUDID). No scraping.
Derives CANDIDATE prefixes from labeler + DI/GTIN (verified later by Verified by GS1).

Three intake paths, in priority order (production, offline=False):
  1. incoming_dir : drop weekly GUDID/AccessGUDID delta files (.json / .ndjson) into a
                    watch folder; the loop ingests and moves them to processed/.
  2. openFDA API  : https://api.fda.gov/device/udi.json  (cursor-resumable)
  3. fixtures     : bundled sample records (offline=True, used by --selftest)
Idempotent staging keyed by primary_di means re-feeding the same file is safe.
"""
import os, json, shutil, logging
from common.connector import BaseConnector
from common.mo_resolver import normalize_to_gtin13
FIX = os.path.join(os.path.dirname(__file__), "..", "data", "fixtures")
log = logging.getLogger("gudid")

class GudidConnector(BaseConnector):
    name = "gudid"
    def __init__(self, store, cfg):
        super().__init__(store, cfg, FIX)

    def iter_candidates(self):
        data = self._fixture("gudid.json") if self.offline else self._pull()
        glen = self.cfg.get("gcp_default_length", 7)
        for rec in data:
            key = rec.get("primary_di") or f"{rec.get('labeler')}|{rec.get('country')}"
            if not self.store.stage("gudid", key, rec):
                continue                              # already ingested -> skip (idempotent)
            di = rec.get("primary_di"); cand = gtin13 = None
            if di:
                gtin13 = normalize_to_gtin13(di)
                if gtin13 and len(gtin13) >= glen:
                    cand = gtin13[:glen]              # CANDIDATE company prefix (default length)
            yield {"labeler": rec.get("labeler"), "country": rec.get("country", ""),
                   "candidate_prefix": cand, "gtin13": gtin13}

    # ---- production intake ----
    def _pull(self):
        inc = (self.cfg.get("gudid") or {}).get("incoming_dir")
        if inc and os.path.isdir(inc):
            return self._read_incoming(inc)
        return self._pull_openfda()

    def _read_incoming(self, inc):
        processed = os.path.join(inc, "processed")
        os.makedirs(processed, exist_ok=True)
        out = []
        for fn in sorted(os.listdir(inc)):
            path = os.path.join(inc, fn)
            if not os.path.isfile(path) or not fn.lower().endswith((".json", ".ndjson")):
                continue
            try:
                rows = self._parse_gudid_file(path)
                out.extend(rows)
                shutil.move(path, os.path.join(processed, fn))
                log.info("GUDID feed: ingested %d records from %s", len(rows), fn)
            except Exception as e:
                log.warning("GUDID feed: %s failed (%s); left in place", fn, e)
        return out

    @staticmethod
    def _parse_gudid_file(path):
        text = open(path, encoding="utf-8", errors="replace").read().strip()
        if text.startswith("{"):
            obj = json.loads(text); rows = obj.get("results", obj.get("records", []))
        elif text.startswith("["):
            rows = json.loads(text)
        else:                                          # NDJSON (one record per line)
            rows = [json.loads(l) for l in text.splitlines() if l.strip()]
        recs = []
        for r in rows:
            labeler = r.get("labeler") or r.get("company_name") or r.get("companyName")
            di = r.get("primary_di") or r.get("primaryDi")
            if not di:
                ids = r.get("identifiers")
                if isinstance(ids, list) and ids:
                    di = (ids[0] or {}).get("id")
            recs.append({"labeler": labeler, "primary_di": di, "country": r.get("country", "")})
        return recs

    def _pull_openfda(self):
        url = self.cfg["gudid"]["udi_url"]; skip = int(self.store.get_cursor("gudid") or 0)
        payload = self._get_json(f"{url}&skip={skip}")
        out = []
        for r in payload.get("results", []):
            ids = r.get("identifiers") or [{}]
            out.append({"labeler": r.get("company_name"), "country": "",
                        "primary_di": (ids[0] or {}).get("id")})
        self.store.set_cursor("gudid", skip + len(out))
        return out
