"""
net.py — shared production HTTP client.

Features: per-host rate limiting, exponential backoff with jitter, Retry-After
support, descriptive User-Agent (required by SEC EDGAR), optional API-key injection,
and JSON / text / POST-JSON helpers. Pure stdlib (urllib) so it runs on a stock
Mac mini Python with no extra dependencies.
"""
import time, json, random, urllib.request, urllib.error, urllib.parse, logging

log = logging.getLogger("net")

class HttpError(Exception):
    pass

class HttpClient:
    def __init__(self, user_agent="thingdaddy-loops/1.0", min_interval=0.15,
                 max_retries=5, backoff_base=0.8, timeout=60):
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._last = {}   # host -> last request monotonic time

    def _throttle(self, url):
        host = urllib.parse.urlparse(url).netloc
        last = self._last.get(host, 0.0)
        wait = self.min_interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def _request(self, url, data=None, headers=None, method=None):
        self._throttle(url)
        h = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if headers:
            h.update(headers)
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        last_err = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (429, 500, 502, 503, 504):
                    ra = e.headers.get("Retry-After")
                    delay = float(ra) if (ra and ra.isdigit()) else \
                        self.backoff_base * (2 ** attempt) + random.uniform(0, 0.4)
                    log.warning("HTTP %s on %s; retry %d/%d in %.1fs",
                                e.code, url, attempt + 1, self.max_retries, delay)
                    time.sleep(delay)
                    continue
                raise HttpError(f"{e.code} {url}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
                delay = self.backoff_base * (2 ** attempt) + random.uniform(0, 0.4)
                log.warning("net error on %s (%s); retry %d/%d in %.1fs",
                            url, e, attempt + 1, self.max_retries, delay)
                time.sleep(delay)
        raise HttpError(f"exhausted retries for {url}: {last_err}")

    def get_json(self, url, headers=None):
        return json.loads(self._request(url, headers=headers))

    def get_text(self, url, headers=None):
        return self._request(url, headers=headers)

    def post_json(self, url, payload, headers=None):
        return json.loads(self._request(url, data=payload, headers=headers, method="POST"))
