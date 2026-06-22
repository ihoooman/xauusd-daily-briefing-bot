from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import requests

from config import Settings
from utils.time_utils import fa_datetime, parse_iso_to_timezone


NEWS_KEYWORDS = [
    "gold",
    "xau",
    "dollar",
    "treasury",
    "yield",
    "federal reserve",
    "fed",
    "inflation",
    "cpi",
    "pce",
    "jobs",
    "payrolls",
    "geopolitical",
    "central bank",
    "china",
    "india",
]

RSS_FEEDS = [
    ("FXStreet", "https://www.fxstreet.com/rss/news"),
    ("Kitco", "https://www.kitco.com/rss/news"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
]


class NewsDataProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch_latest_news(self, limit: int = 6) -> dict[str, Any]:
        errors: list[str] = []
        items: list[dict[str, Any]] = []

        if self.settings.news_api_key:
            try:
                items.extend(self._fetch_newsapi())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"NewsAPI: {exc}")

        for source, url in RSS_FEEDS:
            try:
                items.extend(self._fetch_rss(source, url))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source}: {exc}")

        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            key = item.get("url") or item["title"]
            deduped[key] = item

        sorted_items = sorted(
            deduped.values(),
            key=lambda item: item.get("published_sort") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        relevant = [item for item in sorted_items if self._is_relevant(item)]
        enriched = [self._enrich_item(item) for item in relevant[:limit]]
        return {"items": enriched, "errors": errors, "source": "NewsAPI/RSS"}

    def _fetch_newsapi(self) -> list[dict[str, Any]]:
        url = "https://newsapi.org/v2/everything"
        from_date = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        response = self.session.get(
            url,
            params={
                "q": "(gold OR XAUUSD OR Federal Reserve OR dollar OR Treasury yields OR inflation)",
                "from": from_date,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": self.settings.news_api_key,
            },
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ok":
            raise RuntimeError(payload.get("message", "خطای نامشخص NewsAPI"))

        items = []
        for article in payload.get("articles", []):
            dt = parse_iso_to_timezone(article.get("publishedAt"), self.settings.timezone)
            items.append(
                {
                    "title": article.get("title") or "بدون عنوان",
                    "summary_raw": article.get("description") or "",
                    "source": (article.get("source") or {}).get("name") or "NewsAPI",
                    "url": article.get("url"),
                    "published": fa_datetime(dt),
                    "published_sort": dt,
                }
            )
        return items

    def _fetch_rss(self, source: str, url: str) -> list[dict[str, Any]]:
        response = self.session.get(url, timeout=self.settings.http_timeout)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        items = []
        for entry in feed.entries[:30]:
            published = None
            if getattr(entry, "published_parsed", None):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif getattr(entry, "updated_parsed", None):
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            local_dt = published.astimezone(ZoneInfo(self.settings.timezone)) if published else None
            items.append(
                {
                    "title": getattr(entry, "title", "بدون عنوان"),
                    "summary_raw": getattr(entry, "summary", ""),
                    "source": source,
                    "url": getattr(entry, "link", None),
                    "published": fa_datetime(local_dt),
                    "published_sort": published,
                }
            )
        return items

    def _is_relevant(self, item: dict[str, Any]) -> bool:
        text = f"{item.get('title', '')} {item.get('summary_raw', '')}".lower()
        return any(keyword in text for keyword in NEWS_KEYWORDS)

    def _enrich_item(self, item: dict[str, Any]) -> dict[str, Any]:
        text = f"{item.get('title', '')} {item.get('summary_raw', '')}".lower()
        themes = []
        if any(word in text for word in ["fed", "federal reserve", "rate", "fomc"]):
            themes.append("سیاست پولی فدرال رزرو")
        if any(word in text for word in ["dollar", "dxy"]):
            themes.append("دلار آمریکا")
        if any(word in text for word in ["treasury", "yield", "bond"]):
            themes.append("بازدهی اوراق خزانه")
        if any(word in text for word in ["inflation", "cpi", "pce"]):
            themes.append("تورم آمریکا")
        if any(word in text for word in ["jobs", "payrolls", "unemployment"]):
            themes.append("بازار کار آمریکا")
        if any(word in text for word in ["geopolitical", "war", "risk"]):
            themes.append("ریسک ژئوپلیتیک")
        if any(word in text for word in ["gold", "xau"]):
            themes.append("طلا")

        impact = self._impact_label(text)
        topic = "، ".join(dict.fromkeys(themes)) or "عوامل کلان اثرگذار بر طلا"
        item["persian_title"] = f"خبر مرتبط با {topic}"
        item["persian_summary"] = (
            f"این خبر به {topic} اشاره دارد و برای ارزیابی جهت کوتاه‌مدت طلا مهم است."
        )
        item["impact"] = impact
        item["why"] = self._why_it_matters(topic, impact)
        return item

    @staticmethod
    def _impact_label(text: str) -> str:
        bullish_terms = ["dovish", "rate cut", "cuts", "weaker dollar", "lower yields", "risk-off"]
        bearish_terms = ["hawkish", "rate hike", "higher yields", "stronger dollar", "hot inflation"]
        if any(term in text for term in bullish_terms):
            return "افزایشی برای طلا"
        if any(term in text for term in bearish_terms):
            return "کاهشی برای طلا"
        return "خنثی"

    @staticmethod
    def _why_it_matters(topic: str, impact: str) -> str:
        if impact == "افزایشی برای طلا":
            return f"{topic} می‌تواند تقاضا برای دارایی امن یا انتظار کاهش نرخ بهره را تقویت کند."
        if impact == "کاهشی برای طلا":
            return f"{topic} می‌تواند دلار یا بازدهی واقعی را تقویت کند و فشار فروش روی طلا بسازد."
        return f"{topic} هنوز جهت روشن و قابل اتکایی برای طلا ایجاد نکرده است."
