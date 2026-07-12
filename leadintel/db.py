"""SQLite storage: leads table with dedupe (uid = sha1 of canonical URL)."""
import hashlib
import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "leads.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid TEXT UNIQUE NOT NULL,
  platform TEXT NOT NULL,
  title TEXT,
  text TEXT,
  author TEXT,
  url TEXT NOT NULL,
  published_ts INTEGER,
  found_ts INTEGER NOT NULL,
  budget TEXT,
  service TEXT,
  location TEXT,
  score INTEGER,
  tier TEXT,
  status TEXT DEFAULT 'new',      -- new | contacted | replied | call | closed | ignored
  notified INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_leads_tier ON leads(tier);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
"""


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def uid_for(url):
    canon = url.split("?")[0].rstrip("/").lower()
    return hashlib.sha1(canon.encode()).hexdigest()


def insert_lead(con, lead):
    """Insert if new. Returns row id or None if duplicate (URL or same title+author)."""
    t = (lead.get("title") or "").strip().lower()
    if t and con.execute(
            "SELECT 1 FROM leads WHERE lower(title)=? AND ifnull(author,'')=ifnull(?,'') LIMIT 1",
            (t, lead.get("author"))).fetchone():
        return None  # cross-post duplicate
    try:
        cur = con.execute(
            """INSERT INTO leads (uid, platform, title, text, author, url,
               published_ts, found_ts, budget, service, location, score, tier)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid_for(lead["url"]), lead["platform"], lead.get("title"),
             lead.get("text"), lead.get("author"), lead["url"],
             lead.get("published_ts"), int(time.time()), lead.get("budget"),
             lead.get("service"), lead.get("location"), lead["score"], lead["tier"]))
        con.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # duplicate


def mark_notified(con, row_id):
    con.execute("UPDATE leads SET notified=1 WHERE id=?", (row_id,))
    con.commit()


def set_status(con, row_id, status):
    con.execute("UPDATE leads SET status=? WHERE id=?", (status, row_id))
    con.commit()
    return con.total_changes


def list_leads(con, tier=None, limit=30):
    q = "SELECT id, tier, score, platform, status, title, url FROM leads"
    args = []
    if tier:
        q += " WHERE tier=?"
        args.append(tier)
    q += " ORDER BY score DESC, id DESC LIMIT ?"
    args.append(limit)
    return con.execute(q, args).fetchall()
