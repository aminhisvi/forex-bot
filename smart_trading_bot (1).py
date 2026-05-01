#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت أخبار التداول الاحترافي مع تحليل Claude AI
يرسل تقارير عند فتح سيشن لندن ونيويورك
يركز على: EUR/USD, GBP/USD, BTC
"""

import urllib.request
import urllib.error
import json
import time
import logging
import sys
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# ─────────────────────────────────────────────
#  CONFIG — ضع بياناتك هنا
# ─────────────────────────────────────────────
BOT_TOKEN      = "8286666952:AAHiQb-p8Lkgg58CD6Huf5OerkdH4H_BzkI"
CHAT_ID        = "6097396379"
ANTHROPIC_KEY  = "YOUR_ANTHROPIC_KEY"   # ← ضع API Key من Anthropic هنا عند الشحن

NY_TZ  = ZoneInfo("America/New_York")
MOR_TZ = ZoneInfo("Africa/Casablanca")

# أوقات التقارير بتوقيت نيويورك
LONDON_HOUR  = 4   # 9 صباحاً المغرب = 4 صباحاً نيويورك
NY_HOUR      = 9   # 2 مساءً المغرب = 9 صباحاً نيويورك

ASSETS = ["EUR/USD", "GBP/USD", "BTC"]

CACHE_FILE = Path.home() / ".smart_bot_seen.json"
LOG_FILE   = Path.home() / "smart_bot.log"

# ─────────────────────────────────────────────
#  RSS FEEDS
# ─────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "ForexLive",    "url": "https://www.forexlive.com/feed/news"},
    {"name": "Investing.com","url": "https://www.investing.com/rss/news.rss"},
    {"name": "CoinDesk",     "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Reuters FX",   "url": "https://feeds.reuters.com/reuters/businessNews"},
]

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("smart_bot")

# ─────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────
def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            if not body.get("ok"):
                log.warning("Telegram error: %s", body)
    except Exception as e:
        log.error("Telegram failed: %s", e)

# ─────────────────────────────────────────────
#  RSS FETCHER
# ─────────────────────────────────────────────
def fetch_rss(feed: dict) -> list:
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(feed["url"], headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items[:10]:
            def txt(tag, default=""):
                el = item.find(tag) or item.find(f"atom:{tag}", ns)
                return (el.text or "").strip() if el is not None else default
            title   = txt("title")
            summary = txt("description") or txt("summary") or ""
            link    = txt("link")
            if title:
                import re
                articles.append({
                    "source": feed["name"],
                    "title": title,
                    "summary": re.sub(r"<[^>]+>", " ", summary)[:300],
                    "link": link,
                })
    except Exception as e:
        log.warning("RSS error [%s]: %s", feed["name"], e)
    return articles

def fetch_all_news() -> list:
    all_articles = []
    for feed in RSS_FEEDS:
        all_articles.extend(fetch_rss(feed))
    return all_articles[:30]

# ─────────────────────────────────────────────
#  CLAUDE AI ANALYSIS
# ─────────────────────────────────────────────
def ask_claude(prompt: str) -> str:
    """استدعاء Claude AI للتحليل"""
    if ANTHROPIC_KEY == "YOUR_ANTHROPIC_KEY":
        return None  # لم يتم إضافة API Key بعد

    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps({
        "model": "claude-opus-4-5",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return body["content"][0]["text"]
    except Exception as e:
        log.error("Claude API error: %s", e)
        return None

def generate_session_report(session_name: str, news_list: list) -> str:
    """توليد تقرير السيشن باستخدام Claude AI"""

    # تحضير ملخص الأخبار
    news_text = "\n".join([
        f"- [{a['source']}] {a['title']}"
        for a in news_list[:15]
    ])

    now_mor = datetime.now(MOR_TZ).strftime("%A %d %B %Y — %H:%M")
    session_emoji = "🇬🇧" if "لندن" in session_name else "🇺🇸"

    prompt = f"""أنت محلل ماكرو احترافي متخصص في أسواق الفوركس والعملات الرقمية.

التاريخ والوقت: {now_mor} بتوقيت المغرب
السيشن: {session_name}
الأصول المطلوبة: EUR/USD, GBP/USD, BTC

آخر الأخبار المتاحة:
{news_text}

المطلوب منك: اكتب تقرير احترافي باللغة العربية يحتوي على:

1) 🗓 الأحداث الاقتصادية المهمة خلال 24-72 ساعة القادمة
   لكل حدث: الحدث، التوقيت، التوقع، السابق، لماذا مهم، تأثيره

2) 🌍 المخاطر الجيوسياسية غير المسعّرة بالكامل
   لكل خطر: الوضع، السيناريو، ردة فعل السوق إذا حدث

3) 🏦 توقعات البنوك المركزية (Fed, ECB, BoE)
   ماذا يتوقع السوق، النبرة (صقري/حمائمي)، التأثير على العملات

4) ⚠️ مخاطر خفية لا يراها معظم المتداولين

5) 📊 رأيي النهائي لكل أصل:
   لكل أصل (EUR/USD, GBP/USD, BTC):
   - التوجه: شراء 🟢 أو بيع 🔴 أو انتظار 🟡
   - رأيي: أتوقع أن هذا الخبر/الحدث سيكون [إيجابي/سلبي/محايد]
   - السبب: لأن... (شرح واضح ومفصل)
   - مستوى الثقة: عالي/متوسط/منخفض

اجعل الرأي شخصياً وواثقاً — قل "أتوقع" و"أرى" و"بناءً على..."
لا تكن محايداً — أعطِ رأياً واضحاً مع سبب قوي.
اكتب بأسلوب محترف لكن مفهوم."""

    response = ask_claude(prompt)

    if response:
        header = f"""{session_emoji} <b>تقرير سيشن {session_name}</b>
🕐 {now_mor}
━━━━━━━━━━━━━━━━━━━━━

"""
        footer = """
━━━━━━━━━━━━━━━━━━━━━
⚡ <i>هذا التحليل للمعلومات فقط — أدر مخاطرك دائماً</i>"""
        return header + response + footer
    else:
        return generate_fallback_report(session_name, news_list)

def generate_fallback_report(session_name: str, news_list: list) -> str:
    """تقرير احتياطي بدون AI"""
    now_mor = datetime.now(MOR_TZ).strftime("%A %d %B %Y — %H:%M")
    session_emoji = "🇬🇧" if "لندن" in session_name else "🇺🇸"

    top_news = "\n".join([
        f"  • {a['title'][:80]}"
        for a in news_list[:5]
    ]) if news_list else "  • لا توجد أخبار بارزة حالياً"

    return f"""{session_emoji} <b>تقرير سيشن {session_name}</b>
🕐 {now_mor}
━━━━━━━━━━━━━━━━━━━━━

📰 <b>أبرز الأخبار:</b>
{top_news}

📊 <b>إشارات السوق:</b>
  💶 EUR/USD   🟡 انتظار — ترقب البيانات
  💷 GBP/USD   🟡 انتظار — ترقب البيانات
  ₿  BTC       🟡 انتظار — لا محفز واضح

⚠️ <b>ملاحظة:</b> لتفعيل التحليل الاحترافي بالذكاء الاصطناعي، أضف Anthropic API Key في إعدادات البوت.

━━━━━━━━━━━━━━━━━━━━━
⚡ <i>أدر مخاطرك دائماً</i>"""

# ─────────────────────────────────────────────
#  BREAKING NEWS ALERTS
# ─────────────────────────────────────────────
BREAKING_KEYWORDS = [
    "fed", "fomc", "powell", "rate hike", "rate cut", "inflation", "cpi", "nfp",
    "payrolls", "gdp", "recession", "war", "attack", "sanctions", "opec",
    "bitcoin etf", "btc", "crypto ban", "bank collapse", "emergency",
    "breaking", "flash", "urgent", "ecb", "lagarde", "boe", "bailey"
]

def is_breaking(article: dict) -> bool:
    text = (article["title"] + " " + article["summary"]).lower()
    return any(kw in text for kw in BREAKING_KEYWORDS)

def generate_breaking_alert(article: dict, news_list: list) -> str:
    """توليد تنبيه خبر عاجل"""
    now_mor = datetime.now(MOR_TZ).strftime("%H:%M")

    prompt = f"""أنت محلل ماكرو احترافي.

خبر عاجل للتحليل:
العنوان: {article['title']}
المصدر: {article['source']}
التفاصيل: {article['summary']}

المطلوب: حلل هذا الخبر بـ 3-4 أسطر باللغة العربية:
1) ما هو تأثير هذا الخبر؟
2) رأيك: هل هو إيجابي أم سلبي على EUR/USD و GBP/USD و BTC؟
3) لماذا؟ (سبب واضح ومحدد)
4) التوصية: شراء/بيع/انتظار لكل أصل

كن مباشراً وواثقاً في رأيك."""

    analysis = ask_claude(prompt) if ANTHROPIC_KEY != "YOUR_ANTHROPIC_KEY" else None

    msg = f"""⚡ <b>خبر عاجل — {now_mor}</b>
📰 {article['source']}

<b>{article['title']}</b>

"""
    if analysis:
        msg += f"🤖 <b>تحليل فوري:</b>\n{analysis}\n"
    else:
        msg += "🟡 يتطلب تفعيل AI للتحليل الفوري\n"

    if article.get("link"):
        msg += f"\n🔗 <a href=\"{article['link']}\">اقرأ المزيد</a>"

    return msg

# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────
class BotState:
    def __init__(self):
        self.lock = threading.Lock()
        self.seen = self._load_seen()
        self.last_date = ""
        self.london_sent = False
        self.ny_sent = False

    def _load_seen(self) -> set:
        if CACHE_FILE.exists():
            try:
                return set(json.loads(CACHE_FILE.read_text()).get("seen", []))
            except:
                return set()
        return set()

    def save_seen(self):
        trimmed = list(self.seen)[-1000:]
        CACHE_FILE.write_text(json.dumps({"seen": trimmed}))

    def reset_day(self, date_str: str):
        self.london_sent = False
        self.ny_sent = False
        self.last_date = date_str
        log.info("يوم جديد: %s", date_str)

state = BotState()

# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
def check_scheduled(news_list: list):
    now_ny   = datetime.now(NY_TZ)
    date_str = now_ny.strftime("%Y-%m-%d")
    hour     = now_ny.hour

    if state.last_date and state.last_date != date_str:
        state.reset_day(date_str)
    elif not state.last_date:
        state.last_date = date_str

    # تقرير لندن
    if hour == LONDON_HOUR and not state.london_sent:
        log.info("إرسال تقرير لندن...")
        report = generate_session_report("لندن 🇬🇧", news_list)
        send_telegram(report)
        state.london_sent = True

    # تقرير نيويورك
    if hour == NY_HOUR and not state.ny_sent:
        log.info("إرسال تقرير نيويورك...")
        report = generate_session_report("نيويورك 🇺🇸", news_list)
        send_telegram(report)
        state.ny_sent = True

def check_breaking_news(news_list: list):
    for article in news_list:
        article_id = f"{article['source']}::{article['title'][:50]}"
        if article_id not in state.seen and is_breaking(article):
            with state.lock:
                state.seen.add(article_id)
            alert = generate_breaking_alert(article, news_list)
            send_telegram(alert)
            log.info("تنبيه عاجل: %s", article['title'][:60])
        elif article_id not in state.seen:
            with state.lock:
                state.seen.add(article_id)
    state.save_seen()

def run_bot():
    log.info("البوت يبدأ...")
    send_telegram(
        "🤖 <b>بوت التداول الاحترافي يعمل الآن</b>\n\n"
        "📊 الأصول: EUR/USD | GBP/USD | BTC\n"
        "🇬🇧 تقرير لندن: 9:00 ص بتوقيت المغرب\n"
        "🇺🇸 تقرير نيويورك: 2:00 م بتوقيت المغرب\n"
        "⚡ تنبيهات فورية: طوال اليوم\n\n"
        + ("✅ التحليل بالذكاء الاصطناعي مفعّل" if ANTHROPIC_KEY != "YOUR_ANTHROPIC_KEY"
           else "⚠️ أضف Anthropic API Key لتفعيل التحليل الاحترافي")
    )
    while True:
        try:
            news_list = fetch_all_news()
            check_scheduled(news_list)
            check_breaking_news(news_list)
        except Exception as e:
            log.error("خطأ: %s", e, exc_info=True)
        time.sleep(15 * 60)

if __name__ == "__main__":
    run_bot()
