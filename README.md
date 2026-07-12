# LeadIntel — Lead-Radar für WebRevive

Findet Leute, die **aktiv** nach Webdesign/Websites/Shopify suchen, bewertet sie 1–100
und schickt die guten sofort per Telegram. Kontaktiert **niemanden automatisch**.

**Kosten: 0 €/Monat.** Keine Dependencies (nur Python-Stdlib), SQLite, läuft lokal per launchd.

## Quellen (MVP, alle legal & offiziell)
| Quelle | Zugang | Status |
|---|---|---|
| Hacker News | Algolia-API (offiziell, keyfrei) | ✅ aktiv |
| Reddit-Suche | öffentliches Such-RSS, höflich gedrosselt | ✅ aktiv |
| r/forhire & Co | Subreddit-RSS, [For Hire]-Posts gefiltert | ✅ aktiv |
| Google Alerts | RSS-Zustellung (offiziell) | 🔧 Feeds eintragen |
| Freelancer.com | offizielle API, Gratis-Token | 🔧 optional |
| Reddit OAuth | Gratis-App, 100 req/min, robuster als RSS | 🔧 optionales Upgrade |
| X / LinkedIn / FB / Discord | teuer bzw. ToS-beschränkt | Phase 2 (siehe unten) |

## Setup (5 Minuten)
1. **Telegram-Bot:** In Telegram `@BotFather` anschreiben → `/newbot` → Namen vergeben
   → **Token** kopieren. Dann dem neuen Bot irgendeine Nachricht schicken und
   `https://api.telegram.org/bot<TOKEN>/getUpdates` im Browser öffnen → deine **chat.id** ablesen.
2. Token + chat_id in `config.json` unter `telegram` eintragen.
3. Test: `python3 run.py test-telegram` → ✅-Nachricht kommt an.
4. `"dry_run": false` setzen.
5. Dauerbetrieb: `sh install-launchd.sh` (alle 30 Min, überlebt Reboots).

**Google Alerts (empfohlen, 5 Min):** google.com/alerts → Alerts anlegen wie
„looking for a web designer", „need a new website for my business" → Zustellung: **RSS-Feed**
→ Feed-URLs in `config.json` unter `platforms.rss_feeds.feeds` einfügen.

## Bedienung
```
python3 run.py run              # ein Durchlauf (macht launchd automatisch)
python3 run.py list Hot         # heiße Leads anzeigen
python3 run.py mark 12 contacted# Status: contacted|replied|call|closed|ignored
python3 run.py export           # leads.csv für Excel/Sheets
```

## Wie das Scoring funktioniert (transparent, in config.json einstellbar)
Basis 30 · starke Kaufabsicht +25 · Hiring-Tag +20 · Budget genannt +15 · Urgency +10
· frisch (<24h) +10 · kein Web-Bezug −15 · Anbieter-Signale → rausgefiltert
· Spam-Signale → rausgefiltert · älter als 7 Tage → rausgefiltert.
**Hot ≥ 70 · Warm 45–69 · Low < 45.** Benachrichtigt wird ab `notify_min_score` (45).

Duplikate: SHA1 der URL ist UNIQUE in SQLite — jede Quelle kann denselben Post
beliebig oft liefern, du bekommst ihn genau einmal.

## Phase 2 (wenn das MVP Geld verdient)
- **X/Twitter:** API Basic $200/Mo — erst ab nachweisbarem ROI.
- **Reddit OAuth:** Gratis-App unter reddit.com/prefs/apps → `reddit_oauth` in config → zuverlässiger als RSS.
- **Discord:** eigenen Bot nur in Server einladen, deren Admins es erlauben (z. B. Freelance-Server mit #hiring-Channel).
- **Facebook-Gruppen:** API gibt Gruppen-Inhalte nur mit Gruppen-Admin-Rechten frei — realistisch: manuell.
- **LinkedIn:** kein legaler API-Zugang für Post-Suche — manuell über gespeicherte Suchen.
- **LLM-Scoring:** `scoring.py` hat einen klaren Contract — score_lead() kann 1:1 durch einen Claude-API-Call ersetzt werden, wenn Regel-Scoring nicht mehr reicht.

## Sicherheit
- Der Telegram-Token steht **nur** in `config.json` — Ordner nicht öffentlich teilen, nicht committen.
- Alle Quellen sind öffentlich & read-only, höfliches Pacing (sleep zwischen Requests, Backoff bei 429).
