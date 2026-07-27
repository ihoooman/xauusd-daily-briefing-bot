from __future__ import annotations

import json
from typing import Any

import requests

from config import Settings


MARKET_TERMS = [
    "gold",
    "xau",
    "fed",
    "rate cut",
    "rate hike",
    "inflation",
    "cpi",
    "recession",
    "dollar",
    "dxy",
]


class PolymarketProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch_relevant_markets(self, limit: int = 6) -> dict[str, Any]:
        try:
            response = self.session.get(
                self.settings.polymarket_api_url,
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": 200,
                    "order": "volume24hr",
                    "ascending": "false",
                },
                timeout=self.settings.http_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            markets = payload if isinstance(payload, list) else payload.get("data", [])
            items = []
            for market in markets:
                title = market.get("question") or market.get("title") or market.get("slug") or ""
                description = market.get("description") or ""
                text = f"{title} {description}".lower()
                if not any(term in text for term in MARKET_TERMS):
                    continue
                items.append(self._normalize_market(market))
                if len(items) >= limit:
                    break
            return {"items": items, "errors": [], "source": "Polymarket Gamma API"}
        except Exception as exc:  # noqa: BLE001
            return {
                "items": [],
                "errors": [str(exc)],
                "source": "Polymarket Gamma API",
            }

    def _normalize_market(self, market: dict[str, Any]) -> dict[str, Any]:
        title = market.get("question") or market.get("title") or "بازار بدون عنوان"
        outcomes = self._jsonish(market.get("outcomes")) or []
        prices = self._jsonish(market.get("outcomePrices")) or []
        probability = "نامشخص"
        probability_value = None
        if outcomes and prices:
            try:
                pairs = list(zip(outcomes, prices, strict=False))
                yes_pair = next((pair for pair in pairs if str(pair[0]).lower() == "yes"), pairs[0])
                probability_value = float(yes_pair[1])
                probability = f"{probability_value * 100:.1f}%"
            except Exception:  # noqa: BLE001
                probability = "نامشخص"

        sentiment = self._sentiment_for_gold(title, probability_value)
        return {
            "title": title,
            "persian_title": self._persian_market_title(title),
            "probability": probability,
            "probability_value": probability_value,
            "interpretation": self._interpretation(title, probability),
            "sentiment": sentiment,
            "url": market.get("url") or market.get("slug"),
        }

    @staticmethod
    def _jsonish(value: Any) -> Any:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _sentiment_for_gold(title: str, probability: float | None) -> str:
        if probability is None or 0.45 <= probability <= 0.55:
            return "خنثی"

        lowered = title.lower()
        event_likely = probability > 0.55
        if any(
            term in lowered
            for term in ["no fed rate cuts", "no rate cuts", "zero rate cuts"]
        ):
            return "نزولی" if event_likely else "صعودی"
        if any(term in lowered for term in ["rate cut", "recession", "lower inflation"]):
            return "صعودی" if event_likely else "نزولی"
        if any(term in lowered for term in ["rate hike", "higher inflation", "strong dollar"]):
            return "نزولی" if event_likely else "صعودی"
        if "gold" in lowered or "xau" in lowered:
            if any(term in lowered for term in ["above", "over", "reach", "hit"]):
                return "صعودی" if event_likely else "نزولی"
            if any(term in lowered for term in ["below", "under"]):
                return "نزولی" if event_likely else "صعودی"
        return "خنثی"

    @staticmethod
    def _interpretation(title: str, probability: str) -> str:
        lowered = title.lower()
        if any(
            term in lowered
            for term in ["no fed rate cuts", "no rate cuts", "zero rate cuts"]
        ):
            return (
                f"بازار احتمال {probability} را برای عدم کاهش نرخ بهره نشان می‌دهد؛ "
                "احتمال بالاتر این سناریو معمولاً برای طلا فشارآور است."
            )
        if "rate cut" in lowered:
            return f"بازار احتمال {probability} را برای سناریوی کاهش نرخ بهره نشان می‌دهد؛ این موضوع معمولاً برای طلا حمایتی است."
        if "inflation" in lowered or "cpi" in lowered:
            return f"احتمال فعلی {probability} است و باید همراه با جهت تورم و واکنش دلار تفسیر شود."
        if "recession" in lowered:
            return f"احتمال فعلی {probability} است؛ افزایش ریسک رکود می‌تواند تقاضای دارایی امن را تقویت کند."
        if "dollar" in lowered or "dxy" in lowered:
            return f"احتمال فعلی {probability} است؛ دلار قوی‌تر معمولاً فشار کاهشی روی طلا دارد."
        return f"احتمال فعلی بازار {probability} است و اثر آن روی طلا قطعی نیست."

    @staticmethod
    def _persian_market_title(title: str) -> str:
        lowered = title.lower()
        topics = []
        if "gold" in lowered or "xau" in lowered:
            topics.append("قیمت طلا")
        if "fed" in lowered or "rate" in lowered:
            topics.append("نرخ بهره فدرال رزرو")
        if "inflation" in lowered or "cpi" in lowered:
            topics.append("تورم آمریکا")
        if "recession" in lowered:
            topics.append("رکود آمریکا")
        if "dollar" in lowered or "dxy" in lowered:
            topics.append("قدرت دلار آمریکا")
        topic_text = "، ".join(dict.fromkeys(topics or ["انتظارات کلان بازار"]))
        return f"بازار مرتبط با {topic_text}"
