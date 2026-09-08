"""
resolve.py — entity resolution and cross-MO unification.

  normalize()  : strip legal suffixes / punctuation for comparison
  block_key()  : cheap blocking key to avoid O(n^2) over millions of parties
  score()      : 0..1 similarity on normalized name + country agreement
  UnionFind    : merges a single legal entity's prefixes (across MOs) + its LEI
                 into one civilization profile (cluster)
"""
import re, difflib

_SUFFIXES = {
    "inc","incorporated","llc","ltd","limited","plc","corp","corporation","co","company",
    "gmbh","ag","sa","sas","spa","srl","bv","nv","oy","ab","as","kk","pte","pvt","private",
    "holdings","holding","group","international","intl","the","and","&",
}

def normalize(name):
    if not name:
        return ""
    s = name.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t and t not in _SUFFIXES]
    return " ".join(toks)

def block_key(norm_name, country=None):
    """First token + first letter of second token; keeps blocks small but recall high."""
    toks = norm_name.split()
    if not toks:
        return f"_{(country or '').upper()}"
    k = toks[0]
    if len(toks) > 1:
        k += "_" + toks[1][:1]
    return k

def score(name_a, country_a, name_b, country_b):
    na, nb = normalize(name_a), normalize(name_b)
    if not na or not nb:
        return 0.0
    sim = difflib.SequenceMatcher(None, na, nb).ratio()
    if country_a and country_b:
        if country_a.upper() == country_b.upper():
            sim = min(1.0, sim + 0.05)
        else:
            sim = max(0.0, sim - 0.10)
    return round(sim, 4)

class UnionFind:
    def __init__(self):
        self.parent = {}
    def add(self, x):
        self.parent.setdefault(x, x)
    def find(self, x):
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # deterministic: smaller key becomes root
            lo, hi = sorted((ra, rb))
            self.parent[hi] = lo
    def clusters(self):
        out = {}
        for x in list(self.parent):
            out.setdefault(self.find(x), []).append(x)
        return out
