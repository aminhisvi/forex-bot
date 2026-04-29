#!/usr/bin/env python3
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import time
import logging
import os
import sys
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

BOT_TOKEN = "8286666952:AAHiQb-p8Lkgg58CD6Huf5OerkdH4H_BzkI"
CHAT_ID   = "6097396379"

FETCH_INTERVAL_MIN  = 15
MORNING_BRIEF_HOUR  = 9
EVENING_RECAP_HOUR  = 23
NY_TZ = ZoneInfo("America/New_York")

CACHE_FILE = Path.home() / ".forex_bot_seen.json"

RSS_FEEDS = [
    {"name": "ForexLive", "url": "https://www.forexlive.com/feed/news"},
    {"name": "Investing.com", "url": "https://www.investing.com/rss/news.rss"},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
]

KEYWORD_RULES = [
    {"keywords": ["fed hike","rate hike","hawkish fed","fed raises","fomc hike","powell hawkish"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":1,"Gold":-1,"Oil":0,"BTC":-1,"NQ":-1,"ES":-1,"YM":-1},
     "importance":3,"tag":"🦅 HAWKISH FED"},
    {"keywords": ["fed cut","rate cut","dovish fed","fed eases","fomc cut","powell dovish","pivot"],
     "impacts": {"EUR/USD":1,"GBP/USD":1,"USD/JPY":-1,"Gold":1,"Oil":1,"BTC":1,"NQ":1,"ES":1,"YM":1},
     "importance":3,"tag":"🕊️ DOVISH FED"},
    {"keywords": ["fed pause","fed holds","fomc pause","rates unchanged"],
     "impacts": {"EUR/USD":0,"GBP/USD":0,"USD/JPY":0,"Gold":0,"Oil":0,"BTC":0,"NQ":0,"ES":0,"YM":0},
     "importance":2,"tag":"⏸️ FED PAUSE"},
    {"keywords": ["cpi higher","inflation rises","hot cpi","cpi beats","cpi above"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":1,"Gold":-1,"Oil":0,"BTC":-1,"NQ":-1,"ES":-1,"YM":-1},
     "importance":3,"tag":"🔥 HOT CPI"},
    {"keywords": ["cpi lower","inflation falls","cool cpi","cpi misses","disinflation"],
     "impacts": {"EUR/USD":1,"GBP/USD":1,"USD/JPY":-1,"Gold":1,"Oil":0,"BTC":1,"NQ":1,"ES":1,"YM":1},
     "importance":3,"tag":"❄️ COOL CPI"},
    {"keywords": ["nfp beats","strong jobs","jobs beat","payrolls beat","unemployment falls"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":1,"Gold":-1,"Oil":1,"BTC":-1,"NQ":-1,"ES":0,"YM":0},
     "importance":3,"tag":"💼 STRONG NFP"},
    {"keywords": ["nfp misses","weak jobs","jobs miss","unemployment rises","jobless claims rise"],
     "impacts": {"EUR/USD":1,"GBP/USD":1,"USD/JPY":-1,"Gold":1,"Oil":-1,"BTC":0,"NQ":1,"ES":0,"YM":0},
     "importance":3,"tag":"📉 WEAK NFP"},
    {"keywords": ["war escalates","military strike","invasion","missile attack","geopolitical tension","sanction"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":-1,"Gold":1,"Oil":1,"BTC":1,"NQ":-1,"ES":-1,"YM":-1},
     "importance":3,"tag":"⚔️ GEOPOLITICAL RISK"},
    {"keywords": ["ceasefire","peace deal","de-escalation","peace talks","war ends"],
     "impacts": {"EUR/USD":1,"GBP/USD":1,"USD/JPY":1,"Gold":-1,"Oil":-1,"BTC":-1,"NQ":1,"ES":1,"YM":1},
     "importance":3,"tag":"🕊️ DE-ESCALATION"},
    {"keywords": ["opec cut","opec+ cut","production cut","oil supply cut"],
     "impacts": {"EUR/USD":0,"GBP/USD":0,"USD/JPY":0,"Gold":1,"Oil":1,"BTC":0,"NQ":-1,"ES":-1,"YM":-1},
     "importance":2,"tag":"🛢️ OPEC CUT"},
    {"keywords": ["opec hike","production increase","oil supply hike","opec raises output"],
     "impacts": {"EUR/USD":0,"GBP/USD":0,"USD/JPY":0,"Gold":-1,"Oil":-1,"BTC":0,"NQ":1,"ES":1,"YM":1},
     "importance":2,"tag":"🛢️ OPEC HIKE"},
    {"keywords": ["btc etf approved","bitcoin etf approved","spot bitcoin etf","etf approval"],
     "impacts": {"EUR/USD":0,"GBP/USD":0,"USD/JPY":0,"Gold":0,"Oil":0,"BTC":1,"NQ":1,"ES":0,"YM":0},
     "importance":3,"tag":"₿ BTC ETF APPROVED"},
    {"keywords": ["btc etf rejected","bitcoin etf rejected","crypto ban","bitcoin ban","exchange hack"],
     "impacts": {"EUR/USD":0,"GBP/USD":0,"USD/JPY":0,"Gold":0,"Oil":0,"BTC":-1,"NQ":-1,"ES":0,"YM":0},
     "importance":3,"tag":"₿ CRYPTO BEARISH"},
    {"keywords": ["china stimulus","pboc cut","china eases","china gdp beat"],
     "impacts": {"EUR/USD":1,"GBP/USD":0,"USD/JPY":-1,"Gold":1,"Oil":1,"BTC":1,"NQ":1,"ES":1,"YM":1},
     "importance":2,"tag":"🇨🇳 CHINA STIMULUS"},
    {"keywords": ["china slowdown","china recession","china gdp miss"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":0,"Gold":-1,"Oil":-1,"BTC":-1,"NQ":-1,"ES":-1,"YM":-1},
     "importance":2,"tag":"🇨🇳 CHINA WEAK"},
    {"keywords": ["bank collapse","bank failure","banking crisis","credit crisis"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":-1,"Gold":1,"Oil":-1,"BTC":0,"NQ":-1,"ES":-1,"YM":-1},
     "importance":3,"tag":"🏦 BANKING CRISIS"},
    {"keywords": ["gdp beats","strong gdp","gdp growth beat","us economy strong"],
     "impacts": {"EUR/USD":-1,"GBP/USD":-1,"USD/JPY":1,"Gold":-1,"Oil":1,"BTC":0,"NQ":1,"ES":1,"YM":1},
     "importance":2,"tag":"📈 STRONG GDP"},
    {"keywords": ["gdp misses","weak gdp","recession fears","gdp contraction","us recession","stagflation"],
     "impacts": {"EUR/USD":1,"GBP/USD":0,"USD/JPY":-1,"Gold":1,"Oil":-1,"BTC":-1,"NQ":-1,"ES":-1,"YM":-1},
     "importance":3,"tag":"📉 WEAK GDP"},
]

ASSETS = ["EUR/USD","GBP/USD","USD/JPY","Gold","Oil","BTC","NQ","ES","YM"]

log_file = Path.home() / "forex_bot.log"
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("forex_bot")

def load_seen():
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            return set(data.get("seen", []))
        except:
            return set()
    return set()

def save_seen(seen):
    trimmed = list(seen)[-2000:]
    CACHE_FILE.write_text(json.dumps({"seen": trimmed}))

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":True}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            if not body.get("ok"):
                log.warning("Telegram error: %s", body)
    except Exception as e:
        log.error("Failed to send Telegram: %s", e)

def fetch_rss(feed):
    articles = []
    headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        req = urllib.request.Request(feed["url"], headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        ns = {"atom":"http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items:
            def txt(tag, default=""):
                el = item.find(tag) or item.find(f"atom:{tag}", ns)
                return (el.text or "").strip() if el is not None else default
            guid = txt("guid") or txt("id") or txt("link")
            title = txt("title")
            summary = txt("description") or txt("summary") or ""
            link = txt("link")
            if title and guid:
                articles.append({"id":f"{feed['name']}::{guid}","source":feed["name"],
                    "title":title,"summary":re.sub(r"<[^>]+>"," ",summary)[:400],"link":link})
    except Exception as e:
        log.warning("RSS error [%s]: %s", feed["name"], e)
    return articles

def analyse_article(article):
    text = (article["title"] + " " + article["summary"]).lower()
    return [rule for rule in KEYWORD_RULES if any(kw in text for kw in rule["keywords"])]

def signals_from_matches(matches):
    scores = {a:0 for a in ASSETS}
    for rule in matches:
        for asset, val in rule["impacts"].items():
            scores[asset] = scores.get(asset,0) + val
    return scores

def score_to_signal(score):
    if score >= 1: return "🟢 شراء"
    elif score <= -1: return "🔴 بيع"
    else: return "🟡 انتظار"

def format_alert(article, matches, scores):
    now_ny = datetime.now(NY_TZ).strftime("%H:%M ET")
    tags = " | ".join(r["tag"] for r in matches)
    importance = max(r["importance"] for r in matches)
    imp_str = "🔴🔴🔴 تأثير عالي" if importance==3 else "🟠🟠 تأثير متوسط"
    lines = [f"<b>⚡ ⚡ تنبيه إخباري — {imp_str}</b>",
             f"🕐 {now_ny}  |  📰 {article['source']}",
             f"<b>{article['title']}</b>",f"🏷️ {tags}","",
             "<b>📊 📊 إشارات السوق</b>"]
    for asset in ASSETS:
        lines.append(f"  {asset:<10} {score_to_signal(scores[asset])}")
    if article["link"]:
        lines.append(f"\n🔗 <a href=\"{article['link']}\">Read more</a>")
    return "\n".join(lines)

def format_morning_brief(articles):
    now_ny = datetime.now(NY_TZ).strftime("%A, %B %d, %Y")
    lines = [f"☀️ <b>☀️ الملخص الصباحي — {now_ny}</b>",""]
    all_matches = [m for a in articles for m in analyse_article(a)]
    if all_matches:
        scores = signals_from_matches(all_matches)
        lines.append("<b>📊 التوجه الليلي</b>")
        for asset in ASSETS:
            lines.append(f"  {asset:<10} {score_to_signal(scores[asset])}")
        lines.append(f"\n<b>📰 أهم الأخبار:</b>")
        for a in articles[:5]:
            lines.append(f"  • {a['title'][:90]}")
    else:
        lines.append("لا أخبار عالية التأثير overnight. Quiet session expected.")
    lines.append("\n💡 تداول بأمان. أدر مخاطرك. 🎯")
    return "\n".join(lines)

def format_evening_recap(articles, alert_count):
    now_ny = datetime.now(NY_TZ).strftime("%A, %B %d, %Y")
    lines = [f"🌙 <b>🌙 الملخص اليومي — {now_ny}</b>",
             f"تنبيهات اليوم: <b>{alert_count}</b>  |  المقالات: <b>{len(articles)}</b>",""]
    all_matches = [m for a in articles for m in analyse_article(a)]
    if all_matches:
        scores = signals_from_matches(all_matches)
        lines.append("<b>📊 DAILY BIAS</b>")
        for asset in ASSETS:
            lines.append(f"  {asset:<10} {score_to_signal(scores[asset])}")
    else:
        lines.append("لا أخبار عالية التأثير today.")
    lines.append("\n📅 نراك غداً. حافظ على انضباطك. 🧘")
    return "\n".join(lines)

class BotState:
    def __init__(self):
        self.seen = load_seen()
        self.lock = threading.Lock()
        self.today_articles = []
        self.today_alert_count = 0
        self.last_date = ""
        self.morning_brief_sent = False
        self.evening_recap_sent = False
    def reset_day(self, date_str):
        self.today_articles = []
        self.today_alert_count = 0
        self.morning_brief_sent = False
        self.evening_recap_sent = False
        self.last_date = date_str

state = BotState()

def poll_once():
    for feed in RSS_FEEDS:
        articles = fetch_rss(feed)
        log.info("Fetched %d from %s", len(articles), feed["name"])
        for art in المقالات:
            if art["id"] not in state.seen:
                with state.lock:
                    state.seen.add(art["id"])
                    state.today_articles.append(art)
                matches = analyse_article(art)
                if matches:
                    scores = signals_from_matches(matches)
                    send_telegram(format_alert(art, matches, scores))
                    log.info("Alert: %s", art["title"][:60])
                    with state.lock:
                        state.today_alert_count += 1
    save_seen(state.seen)

def check_scheduled():
    now_ny = datetime.now(NY_TZ)
    date_str = now_ny.strftime("%Y-%m-%d")
    hour = now_ny.hour
    if state.last_date and state.last_date != date_str:
        state.reset_day(date_str)
    elif not state.last_date:
        state.last_date = date_str
    if hour == MORNING_BRIEF_HOUR and not state.morning_brief_sent:
        send_telegram(format_morning_brief(list(state.today_articles)))
        state.morning_brief_sent = True
        log.info("☀️ الملخص الصباحي sent.")
    if hour == EVENING_RECAP_HOUR and not state.evening_recap_sent:
        send_telegram(format_evening_recap(list(state.today_articles), state.today_alert_count))
        state.evening_recap_sent = True
        log.info("Evening recap sent.")

def run_bot():
    log.info("البوت يعمل...")
    send_telegram("🤖 <b>🤖 بوت أخبار الفوركس يعمل الآن</b>\n📡 المصادر: ForexLive | Investing.com | CoinDesk")
    while True:
        try:
            check_scheduled()
            poll_once()
        except Exception as e:
            log.error("Error: %s", e, exc_info=True)
        time.sleep(FETCH_INTERVAL_MIN * 60)

if __name__ == "__main__":
    run_bot()
