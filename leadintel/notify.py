"""Telegram notifications in the exact requested format. dry_run logs instead."""
import logging
import time

from . import http

log = logging.getLogger("leadintel.notify")

TIER_EMOJI = {"Hot": "🔥", "Warm": "🌤", "Low": "❄️"}


def _fmt_time(ts):
    if not ts:
        return "unknown"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def opening_message(lead, template, portfolio_url):
    name = lead.get("author") or "there"
    service = (lead.get("service") or "your website").lower()
    return template.format(name=name, service_short=service, portfolio_url=portfolio_url)


def format_message(lead, reasons, cfg):
    summary = (lead.get("text") or lead.get("title") or "")[:280].strip()
    msg = (
        "%s NEW WEBSITE LEAD\n\n"
        "Platform: %s\n"
        "Lead score: %s/100 (%s)\n"
        "Published: %s\n"
        "Person/company: %s\n"
        "Service needed: %s\n"
        "Budget: %s\n"
        "Deadline: %s\n"
        "Location: %s\n\n"
        "Post summary:\n%s\n\n"
        "Why it is a good lead:\n%s\n\n"
        "Direct link:\n%s\n\n"
        "Suggested personalized opening message:\n%s"
    ) % (
        TIER_EMOJI.get(lead["tier"], "🔥"),
        lead["platform"],
        lead["score"], lead["tier"],
        _fmt_time(lead.get("published_ts")),
        lead.get("author") or "—",
        lead.get("service") or "—",
        lead.get("budget") or "—",
        lead.get("deadline") or "—",
        lead.get("location") or "—",
        summary,
        "; ".join(reasons) or "—",
        lead["url"],
        opening_message(lead, cfg["opening_message_template"], cfg["portfolio_url"]),
    )
    return msg


def send(lead, reasons, cfg):
    """Send to Telegram (or log in dry_run). Returns True on success."""
    msg = format_message(lead, reasons, cfg)
    if cfg.get("dry_run"):
        log.info("[DRY-RUN] would notify:\n%s\n%s", msg, "-" * 60)
        return True
    tg = cfg["telegram"]
    if "PASTE_" in tg.get("bot_token", "PASTE_"):
        log.error("Telegram not configured — set telegram.bot_token/chat_id in config.json")
        return False
    resp = http.post_json(
        "https://api.telegram.org/bot%s/sendMessage" % tg["bot_token"],
        {"chat_id": tg["chat_id"], "text": msg, "disable_web_page_preview": True})
    ok = bool(resp and resp.get("ok"))
    if not ok:
        log.error("telegram send failed: %s", resp)
    return ok


def test_telegram(cfg):
    tg = cfg["telegram"]
    resp = http.post_json(
        "https://api.telegram.org/bot%s/sendMessage" % tg["bot_token"],
        {"chat_id": tg["chat_id"], "text": "✅ LeadIntel connected. You'll get leads here."})
    return bool(resp and resp.get("ok"))
