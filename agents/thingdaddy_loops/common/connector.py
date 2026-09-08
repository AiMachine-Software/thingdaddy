"""
connector.py — shared connector base for both loops.

offline=True reads bundled fixtures (no network) and drives --selftest.
offline=False uses the shared HttpClient. Every live pull passes through the
store's daily cap (ceiling + resume) and idempotent staging upstream.
"""
import os, json, logging
from common.net import HttpClient

log = logging.getLogger("connector")

class BaseConnector:
    name = "base"

    def __init__(self, store, cfg, fixtures_dir):
        self.store = store
        self.cfg = cfg
        self.offline = cfg.get("offline", True)
        self.fixtures_dir = fixtures_dir
        self.cap = cfg.get("caps", {}).get(self.name, 10_000_000)
        net = cfg.get("net", {})
        self.client = HttpClient(
            user_agent=net.get("user_agent", "thingdaddy-loops/1.0"),
            min_interval=net.get("min_interval", 0.15),
            max_retries=net.get("max_retries", 5),
            timeout=net.get("timeout", 60),
        )

    def _fixture(self, fname):
        with open(os.path.join(self.fixtures_dir, fname)) as f:
            return json.load(f)

    def _get_json(self, url, headers=None):
        self.store.cap_check(self.name, self.cap)
        return self.client.get_json(url, headers=headers)

    def _post_json(self, url, payload, headers=None):
        self.store.cap_check(self.name, self.cap)
        return self.client.post_json(url, payload, headers=headers)

    def _get_text(self, url, headers=None):
        self.store.cap_check(self.name, self.cap)
        return self.client.get_text(url, headers=headers)
