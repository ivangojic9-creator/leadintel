"""Deterministic lead scoring & filtering. Transparent rules > black box:
every score is explainable, tune via config.json 'scoring' section.
Upgrade path: swap score_lead() for an LLM call, keep the same contract."""
import re
import time

BUDGET_RE = re.compile(r"(?:[$€£]\s?\d[\d,.]{2,}|budget[^.\n]{0,40})", re.I)
SERVICE_MAP = [
    (re.compile(r"shopify|woocommerce|e-?commerce|online (store|shop)", re.I), "Shopify / eCommerce"),
    (re.compile(r"landing ?page", re.I), "Landing Page"),
    (re.compile(r"redesign|revamp|rebuild|refresh", re.I), "Website Redesign"),
    (re.compile(r"conversion|cro\b", re.I), "CRO"),
    (re.compile(r"web ?site|web ?design|web ?developer|homepage", re.I), "Website"),
]
LOCATION_RE = re.compile(r"\b(?:in|from|based in)\s+([A-Z][a-zA-Z]+(?:,?\s[A-Z]{2})?)\b")


def _contains_any(text, phrases):
    return [p for p in phrases if p in text]


def score_lead(lead, rules, platform_weight, max_age_days):
    """Returns (score 0-100 or None-if-filtered, reasons list, extracted dict)."""
    blob = ((lead.get("title") or "") + " " + (lead.get("text") or "")).lower()
    reasons = []

    # ---- hard filters -------------------------------------------------
    if _contains_any(blob, rules["spam_signals"]):
        return None, ["spam signal"], {}
    offering = _contains_any(blob, rules["offering_signals"])
    strong = _contains_any(blob, rules["strong_intent"])
    if offering and not strong:
        return None, ["service provider, not buyer: %s" % offering[0]], {}

    age_days = None
    if lead.get("published_ts"):
        age_days = (time.time() - lead["published_ts"]) / 86400
        if age_days > max_age_days:
            return None, ["too old (%.0fd)" % age_days], {}

    # ---- scoring -------------------------------------------------------
    score = 30
    if strong:
        score += 25
        reasons.append("strong intent: '%s'" % strong[0])
    medium = _contains_any(blob, rules["medium_intent"])
    if medium and not strong:
        score += 15
        reasons.append("medium intent: '%s'" % medium[0])
    if not strong and not medium:
        score -= 20
        reasons.append("no clear intent phrase")
    if _contains_any(blob, rules["hiring_tags"]):
        score += 20
        reasons.append("explicit hiring tag")
    if offering:
        score -= 30
        reasons.append("mixed offering signals")

    extracted = {}
    m = BUDGET_RE.search(lead.get("text") or "")
    if m:
        extracted["budget"] = m.group(0).strip()[:60]
        score += 15
        reasons.append("budget mentioned")
    if _contains_any(blob, rules["urgency"]):
        score += 10
        reasons.append("urgency")
    if "?" in (lead.get("title") or ""):
        score += 5

    if age_days is not None:
        if age_days < 1:
            score += 10
            reasons.append("fresh (<24h)")
        elif age_days < 3:
            score += 5

    for rx, label in SERVICE_MAP:
        if rx.search(blob):
            extracted["service"] = label
            break
    else:
        score -= 15
        reasons.append("no web-service keyword")

    loc = LOCATION_RE.search(lead.get("text") or "")
    if loc:
        extracted["location"] = loc.group(1)

    score = int(max(1, min(100, score * platform_weight)))
    return score, reasons, extracted


def tier_for(score):
    if score >= 70:
        return "Hot"
    if score >= 45:
        return "Warm"
    return "Low"
