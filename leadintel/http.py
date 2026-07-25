"""HTTP helper: polite UA, timeouts, retries with backoff. Stdlib only."""
import json
import time
import urllib.request
import urllib.parse
import logging

UA = "LeadIntel/1.0 (personal lead monitor; contact: ivangojic9@gmail.com)"
log = logging.getLogger("leadintel.http")

# Circuit breaker: Domains, die uns rate-limiten (429), werden nach 2 Treffern
# fuer den Rest des Laufs uebersprungen. Auf GitHub-Runnern drosselt v.a. Reddit
# hart und dauerhaft - weiter zu retryen kostet nur Minuten, bringt aber nichts.
_429_strikes = {}
_DEAD_AFTER = 2


def get(url, retries=3, timeout=20, headers=None):
    """GET with retries. Returns bytes or None (never raises)."""
    netloc = urllib.parse.urlsplit(url).netloc
    if _429_strikes.get(netloc, 0) >= _DEAD_AFTER:
        log.info("skip %s (rate-limited domain, circuit open)", url[:90])
        return None
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _429_strikes.pop(netloc, None)
                return resp.read()
        except Exception as e:
            code = getattr(e, "code", None)
            log.warning("GET %s failed (attempt %d/%d, %s)", url[:90], attempt, retries, code or e)
            if code == 429:
                # kein Retry bei Rate-Limit: Strike zaehlen und sofort weiter
                _429_strikes[netloc] = _429_strikes.get(netloc, 0) + 1
                return None
            if attempt < retries:
                time.sleep(2 ** attempt)
    log.error("GET gave up: %s", url[:120])
    return None


def get_json(url, **kw):
    raw = get(url, **kw)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8", "ignore"))
    except ValueError:
        log.error("invalid JSON from %s", url[:120])
        return None


def post_json(url, payload, timeout=20):
    """POST JSON (used for Telegram). Returns parsed response or None."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"User-Agent": UA, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception as e:
        log.error("POST %s failed: %s", url[:90], e)
        return None


def quote(s):
    return urllib.parse.quote(s)
