"""
harness.py — checkpoint store, idempotent staging, daily caps, append-only writers.

Standing disciplines (ThingDaddy):
  * verified-or-exception on every record (status column, never fabricated)
  * idempotent staging keyed by (source, natural_key) — re-runs never re-resolve
  * SQLite checkpoint store with resumable cursors
  * hard daily caps as ceilings: clean stop + next-day resume
  * append-only outputs (non-destructive)
"""
import sqlite3, json, os, datetime, csv
from common.resolve import normalize, block_key, score

SCHEMA = """
CREATE TABLE IF NOT EXISTS party(
  party_id TEXT PRIMARY KEY, name TEXT, norm_name TEXT, country TEXT,
  lei TEXT, role TEXT DEFAULT 'unspecified', status TEXT, source TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ownership(
  child_lei TEXT, parent_lei TEXT, rel_type TEXT, source TEXT,
  PRIMARY KEY(child_lei, parent_lei, rel_type));
CREATE TABLE IF NOT EXISTS prefix(
  prefix TEXT, party_id TEXT, gs1_prefix TEXT, mo TEXT, length INTEGER,
  status TEXT, source TEXT, citation TEXT,
  PRIMARY KEY(prefix, party_id));
CREATE TABLE IF NOT EXISTS match_edge(
  lei TEXT, prefix TEXT, score REAL, tier TEXT, status TEXT, citation TEXT,
  PRIMARY KEY(lei, prefix));
CREATE TABLE IF NOT EXISTS cluster(member_key TEXT PRIMARY KEY, cluster_id TEXT);
CREATE TABLE IF NOT EXISTS needs_prefix(
  party_id TEXT PRIMARY KEY, name TEXT, country TEXT, signal TEXT,
  routed_mo TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS personality(
  party_id TEXT, gln TEXT, event_type TEXT, face TEXT,
  PRIMARY KEY(party_id, gln, event_type));
CREATE TABLE IF NOT EXISTS staging(
  source TEXT, natural_key TEXT, payload TEXT,
  PRIMARY KEY(source, natural_key));
CREATE TABLE IF NOT EXISTS cursor(source TEXT PRIMARY KEY, position TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS cap_usage(day TEXT, source TEXT, count INTEGER,
  PRIMARY KEY(day, source));
CREATE TABLE IF NOT EXISTS node(
  node_key TEXT PRIMARY KEY, label TEXT, node_type TEXT, country TEXT,
  status TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS edge(
  src_key TEXT, dst_key TEXT, edge_type TEXT, source TEXT,
  status TEXT, citation TEXT, observed TEXT,
  PRIMARY KEY(src_key, dst_key, edge_type, source));
"""

def today():
    return datetime.date.today().isoformat()

class CapReached(Exception):
    pass

class Store:
    def __init__(self, path):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ---- idempotent staging ----
    def stage(self, source, natural_key, payload):
        """Return True if newly staged, False if already seen (skip re-resolution)."""
        try:
            self.db.execute(
                "INSERT INTO staging(source,natural_key,payload) VALUES(?,?,?)",
                (source, str(natural_key), json.dumps(payload)))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    # ---- daily caps ----
    def cap_check(self, source, cap):
        d = today()
        row = self.db.execute(
            "SELECT count FROM cap_usage WHERE day=? AND source=?", (d, source)).fetchone()
        used = row["count"] if row else 0
        if used >= cap:
            raise CapReached(f"{source}: daily cap {cap} reached ({used}); clean stop, resume tomorrow")
        self.db.execute(
            "INSERT INTO cap_usage(day,source,count) VALUES(?,?,1) "
            "ON CONFLICT(day,source) DO UPDATE SET count=count+1", (d, source))
        self.db.commit()

    # ---- cursors ----
    def get_cursor(self, source):
        row = self.db.execute("SELECT position FROM cursor WHERE source=?", (source,)).fetchone()
        return row["position"] if row else None

    def set_cursor(self, source, position):
        self.db.execute(
            "INSERT INTO cursor(source,position,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(source) DO UPDATE SET position=excluded.position, updated_at=excluded.updated_at",
            (source, str(position), datetime.datetime.utcnow().isoformat()))
        self.db.commit()

    # ---- writers (upsert; status is the verified-or-exception stamp) ----
    def put_party(self, party_id, name, norm_name, country, lei, status, source, role="unspecified"):
        self.db.execute(
            "INSERT INTO party(party_id,name,norm_name,country,lei,role,status,source,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(party_id) DO UPDATE SET "
            "name=excluded.name,norm_name=excluded.norm_name,country=excluded.country,"
            "lei=excluded.lei,status=excluded.status,source=excluded.source",
            (party_id, name, norm_name, country, lei, role, status, source, today()))
        self.db.commit()

    def put_ownership(self, child, parent, rel, source):
        self.db.execute("INSERT OR IGNORE INTO ownership VALUES(?,?,?,?)", (child, parent, rel, source))
        self.db.commit()

    def put_prefix(self, prefix, party_id, gs1_prefix, mo, length, status, source, citation):
        self.db.execute(
            "INSERT INTO prefix(prefix,party_id,gs1_prefix,mo,length,status,source,citation) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(prefix,party_id) DO UPDATE SET "
            "gs1_prefix=excluded.gs1_prefix,mo=excluded.mo,length=excluded.length,"
            "status=excluded.status,source=excluded.source,citation=excluded.citation",
            (prefix, party_id, gs1_prefix, mo, length, status, source, citation))
        self.db.commit()

    def put_match(self, lei, prefix, score, tier, status, citation):
        self.db.execute(
            "INSERT INTO match_edge(lei,prefix,score,tier,status,citation) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(lei,prefix) DO UPDATE SET score=excluded.score,tier=excluded.tier,"
            "status=excluded.status,citation=excluded.citation",
            (lei, prefix, score, tier, status, citation))
        self.db.commit()

    def put_needs_prefix(self, party_id, name, country, signal, routed_mo, status):
        self.db.execute(
            "INSERT INTO needs_prefix(party_id,name,country,signal,routed_mo,status) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(party_id) DO UPDATE SET "
            "signal=excluded.signal,routed_mo=excluded.routed_mo,status=excluded.status",
            (party_id, name, country, signal, routed_mo, status))
        self.db.commit()

    def set_cluster(self, member_key, cluster_id):
        self.db.execute(
            "INSERT INTO cluster(member_key,cluster_id) VALUES(?,?) "
            "ON CONFLICT(member_key) DO UPDATE SET cluster_id=excluded.cluster_id",
            (member_key, cluster_id))
        self.db.commit()

    def put_node(self, node_key, label, node_type, country, status, source):
        self.db.execute(
            "INSERT INTO node(node_key,label,node_type,country,status,source) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(node_key) DO UPDATE SET "
            "label=excluded.label,node_type=excluded.node_type,country=excluded.country,"
            "status=CASE WHEN node.status='verified' THEN node.status ELSE excluded.status END",
            (node_key, label, node_type, country, status, source))
        self.db.commit()

    def put_edge(self, src_key, dst_key, edge_type, source, status, citation, observed):
        self.db.execute(
            "INSERT INTO edge(src_key,dst_key,edge_type,source,status,citation,observed) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(src_key,dst_key,edge_type,source) DO UPDATE SET "
            "status=excluded.status,citation=excluded.citation,observed=excluded.observed",
            (src_key, dst_key, edge_type, source, status, citation, observed))
        self.db.commit()

    def q(self, sql, args=()):
        return self.db.execute(sql, args).fetchall()

    def close(self):
        self.db.close()


    def cluster_of(self, party_id):
        r = self.db.execute("SELECT cluster_id FROM cluster WHERE member_key=?", (party_id,)).fetchone()
        return r["cluster_id"] if r else None

    def resolve_party(self, name, country, threshold=0.90):
        """Resolve a raw (name,country) to an existing profile.
        Returns (node_key, status): status 'resolved' with the party's cluster id
        (or party_id) when a strong match exists, else (None,'provisional')."""
        nn = normalize(name)
        bk = block_key(nn, country)
        rows = self.db.execute("SELECT party_id,name,country FROM party").fetchall()
        best=None; best_s=0.0
        for r in rows:
            s = score(name, country, r["name"], r["country"])
            if s > best_s:
                best, best_s = r, s
        if best and best_s >= threshold:
            key = self.cluster_of(best["party_id"]) or best["party_id"]
            return (key, "resolved")
        return (None, "provisional")


def append_csv(path, header, rows):
    """Append-only writer; writes header once."""
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)
