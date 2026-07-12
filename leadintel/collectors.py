"""Collectors: each yields normalized lead dicts:
{platform, title, text, author, url, published_ts}
All read-only, public sources, polite pacing between requests."""
import html
import logging
import re
import time
import xml.etree.ElementTree as ET

from . import http

log = logging.getLogger("leadintel.collect")
ATOM = "{http://www.w3.org/2005/Atom}"


def _strip_html(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------------- Hacker News (Algolia API — official, no key) ----------------

def hackernews(cfg):
    for q in cfg.get("queries", []):
        url = ("https://hn.algolia.com/api/v1/search_by_date?query=%s"
               "&tags=(story,comment)&hitsPerPage=15" % http.quote(q))
        data = http.get_json(url)
        if not data:
            continue
        for h in data.get("hits", []):
            text = _strip_html(h.get("comment_text") or h.get("story_text") or "")
            title = h.get("title") or h.get("story_title") or text[:80]
            oid = h.get("objectID")
            yield {
                "platform": "Hacker News",
                "title": title,
                "text": text or title,
                "author": h.get("author"),
                "url": "https://news.ycombinator.com/item?id=%s" % oid,
                "published_ts": h.get("created_at_i"),
            }
        time.sleep(1)


# ---------------- Reddit via public search RSS (polite; OAuth upgrade opt-in) --

def _parse_atom(raw, platform):
    if not raw:
        return
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        log.warning("unparseable feed (%s)", platform)
        return
    for e in root.iter(ATOM + "entry"):
        title = (e.findtext(ATOM + "title") or "").strip()
        content = _strip_html(e.findtext(ATOM + "content") or "")
        link_el = e.find(ATOM + "link")
        link = link_el.get("href") if link_el is not None else None
        author = (e.findtext(ATOM + "author/" + ATOM + "name") or "").lstrip("/u/")
        published = e.findtext(ATOM + "published") or e.findtext(ATOM + "updated")
        ts = None
        if published:
            try:
                ts = int(time.mktime(time.strptime(published[:19], "%Y-%m-%dT%H:%M:%S")))
            except ValueError:
                pass
        if link:
            yield {"platform": platform, "title": title, "text": content or title,
                   "author": author, "url": link, "published_ts": ts}


def reddit_search(cfg):
    tw = cfg.get("time_window", "week")
    for q in cfg.get("queries", []):
        url = ("https://www.reddit.com/search.rss?q=%s&sort=new&t=%s&limit=25"
               % (http.quote(q), tw))
        for lead in _parse_atom(http.get(url), "Reddit") or []:
            yield lead
        time.sleep(3)  # polite: unauthenticated RSS is rate-limited


def reddit_subs(cfg):
    require_tag = cfg.get("require_hiring_tag", True)
    for sub in cfg.get("subreddits", []):
        url = "https://www.reddit.com/r/%s/new/.rss?limit=25" % sub
        for lead in _parse_atom(http.get(url), "Reddit r/%s" % sub) or []:
            if require_tag and "[for hire]" in lead["title"].lower():
                continue  # people offering, not buying
            yield lead
        time.sleep(3)


# ---------------- Generic RSS (Google Alerts etc.) ----------------------------

RSS_ITEM_FIELDS = {"title": "title", "link": "link", "description": "description",
                   "pubDate": "pubDate"}


def rss_feeds(cfg):
    for feed_url in cfg.get("feeds", []):
        raw = http.get(feed_url)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            log.warning("unparseable RSS: %s", feed_url[:80])
            continue
        # Atom (Google Alerts) or RSS2
        entries = list(root.iter(ATOM + "entry"))
        if entries:
            for lead in _parse_atom(raw, "Google Alerts") or []:
                yield lead
        else:
            for item in root.iter("item"):
                link = item.findtext("link")
                if not link:
                    continue
                ts = None
                pub = item.findtext("pubDate")
                if pub:
                    try:
                        ts = int(time.mktime(time.strptime(pub[:25].strip(), "%a, %d %b %Y %H:%M:%S")))
                    except ValueError:
                        pass
                yield {"platform": "RSS", "title": (item.findtext("title") or "").strip(),
                       "text": _strip_html(item.findtext("description") or ""),
                       "author": None, "url": link, "published_ts": ts}
        time.sleep(1)


# ---------------- Freelancer.com API (optional, free token) -------------------

def freelancer_api(cfg):
    token = cfg.get("oauth_token")
    if not token:
        return
    url = ("https://www.freelancer.com/api/projects/0.1/projects/active/"
           "?query=%s&limit=20&compact=true&full_description=true"
           % http.quote("website design OR shopify OR landing page"))
    data = http.get_json(url, headers={"freelancer-oauth-v1": token})
    if not data or data.get("status") != "success":
        return
    for p in data.get("result", {}).get("projects", []):
        budget = p.get("budget") or {}
        b = None
        if budget.get("minimum"):
            b = "$%s–%s" % (budget.get("minimum"), budget.get("maximum") or "?")
        yield {"platform": "Freelancer.com",
               "title": p.get("title", ""),
               "text": (p.get("description") or p.get("preview_description") or "")[:1500],
               "author": None,
               "url": "https://www.freelancer.com/projects/%s" % p.get("seo_url", p.get("id")),
               "published_ts": p.get("submitdate"), "budget": b}


REGISTRY = {
    "hackernews": hackernews,
    "reddit_search": reddit_search,
    "reddit_subs": reddit_subs,
    "rss_feeds": rss_feeds,
    "freelancer_api": freelancer_api,
}
