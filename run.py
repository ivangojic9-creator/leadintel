#!/usr/bin/env python3
"""LeadIntel CLI.

  python3 run.py run                 collect + score + notify (one tick)
  python3 run.py list [Hot|Warm|Low] show stored leads
  python3 run.py mark <id> <status>  status: contacted|replied|call|closed|ignored
  python3 run.py export              leads.csv next to leads.db
  python3 run.py test-telegram       send a test message
"""
import csv
import logging
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(os.path.join(BASE, "leadintel.log"))])

from leadintel import db, notify, pipeline  # noqa: E402


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        pipeline.run()

    elif cmd == "list":
        tier = sys.argv[2] if len(sys.argv) > 2 else None
        con = db.connect()
        rows = db.list_leads(con, tier)
        if not rows:
            print("no leads stored yet")
        for r in rows:
            print("#%-4s %-4s %-3s %-14s %-10s %s\n      %s" % (
                r["id"], r["tier"], r["score"], r["platform"][:14],
                r["status"], (r["title"] or "")[:70], r["url"]))

    elif cmd == "mark" and len(sys.argv) >= 4:
        con = db.connect()
        if db.set_status(con, int(sys.argv[2]), sys.argv[3]):
            print("lead #%s -> %s" % (sys.argv[2], sys.argv[3]))
        else:
            print("no lead with id", sys.argv[2])

    elif cmd == "export":
        con = db.connect()
        rows = con.execute("SELECT * FROM leads ORDER BY score DESC").fetchall()
        out = os.path.join(BASE, "leads.csv")
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if rows:
                w.writerow(rows[0].keys())
                w.writerows([tuple(r) for r in rows])
        print("exported %d leads -> %s" % (len(rows), out))

    elif cmd == "test-telegram":
        cfg = pipeline.load_config()
        print("ok" if notify.test_telegram(cfg) else "FAILED — check token/chat_id")

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
