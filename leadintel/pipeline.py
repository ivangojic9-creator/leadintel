"""Pipeline: collect -> score/filter -> dedupe-insert -> notify. One run() per cron tick."""
import json
import logging
import os

from . import collectors, db, notify, scoring

log = logging.getLogger("leadintel.pipeline")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    with open(os.path.join(BASE, "config.json")) as f:
        cfg = json.load(f)
    # Secrets from environment override config (cloud/GitHub Actions safe).
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    cid = os.environ.get("TELEGRAM_CHAT_ID")
    if tok:
        cfg["telegram"]["bot_token"] = tok
    if cid:
        cfg["telegram"]["chat_id"] = cid
    if os.environ.get("LEADINTEL_LIVE") == "1":
        cfg["dry_run"] = False
    return cfg


def run():
    cfg = load_config()
    rules = cfg["scoring"]
    con = db.connect()
    stats = {"seen": 0, "filtered": 0, "duplicate": 0, "stored": 0, "notified": 0}

    for name, pcfg in cfg["platforms"].items():
        if not pcfg.get("enabled") or name not in collectors.REGISTRY:
            continue
        weight = pcfg.get("weight", 1.0)
        log.info("collecting: %s", name)
        try:
            found = list(collectors.REGISTRY[name](pcfg))
        except Exception:
            log.exception("collector %s crashed — continuing with others", name)
            continue
        log.info("  %s raw items", len(found))

        for lead in found:
            stats["seen"] += 1
            score, reasons, extracted = scoring.score_lead(
                lead, rules, weight, cfg["max_post_age_days"])
            if score is None:
                stats["filtered"] += 1
                continue
            lead.update(extracted)
            lead["score"] = score
            lead["tier"] = scoring.tier_for(score)

            row_id = db.insert_lead(con, lead)
            if row_id is None:
                stats["duplicate"] += 1
                continue
            stats["stored"] += 1
            log.info("  [%s %s] %s", lead["tier"], score, (lead.get("title") or "")[:70])

            if score >= cfg["notify_min_score"]:
                if notify.send(lead, reasons, cfg) and not cfg.get("dry_run"):
                    db.mark_notified(con, row_id)
                    stats["notified"] += 1

    log.info("run done: %s", stats)
    return stats
