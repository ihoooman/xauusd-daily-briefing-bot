from __future__ import annotations

from typing import Any

import requests

from config import Settings
from utils.time_utils import fa_datetime, utc_timestamp_to_timezone


class PriceDataProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch_current_price(self) -> dict[str, Any]:
        errors: list[str] = []

        if self.settings.price_api_key:
            try:
                return self._fetch_twelve_data_quote()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Twelve Data: {exc}")

        try:
            return self._fetch_swissquote_spot_price()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Swissquote: {exc}")

        try:
            return self._fetch_yahoo_gold_futures_price()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Yahoo Finance GC=F: {exc}")

        return {
            "available": False,
            "price": None,
            "fetched_at": None,
            "source": "نامشخص",
            "error": "؛ ".join(errors) or "منبع قیمت در دسترس نیست.",
        }

    def _fetch_twelve_data_quote(self) -> dict[str, Any]:
        url = "https://api.twelvedata.com/quote"
        response = self.session.get(
            url,
            params={"symbol": "XAU/USD", "apikey": self.settings.price_api_key},
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error":
            raise RuntimeError(payload.get("message", "خطای نامشخص Twelve Data"))

        price = payload.get("close") or payload.get("previous_close")
        if price is None:
            raise RuntimeError("قیمت در پاسخ API وجود ندارد.")

        fetched_at = payload.get("datetime")
        return {
            "available": True,
            "price": float(price),
            "fetched_at": fetched_at or "زمان اعلام‌شده توسط منبع موجود نیست",
            "source": "Twelve Data",
            "raw": payload,
        }

    def _fetch_swissquote_spot_price(self) -> dict[str, Any]:
        url = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
        response = self.session.get(url, timeout=self.settings.http_timeout)
        response.raise_for_status()
        payload = response.json()
        if not payload:
            raise RuntimeError("پاسخ Swissquote خالی است.")

        quote = payload[0]
        prices = quote.get("spreadProfilePrices") or []
        if not prices:
            raise RuntimeError("قیمت bid/ask در پاسخ Swissquote وجود ندارد.")

        best = prices[0]
        bid = float(best["bid"])
        ask = float(best["ask"])
        midpoint = (bid + ask) / 2
        timestamp_ms = quote.get("ts")
        fetched_at = "زمان اعلام‌شده توسط منبع موجود نیست"
        if timestamp_ms:
            fetched_at = fa_datetime(
                utc_timestamp_to_timezone(timestamp_ms / 1000, self.settings.timezone)
            )

        return {
            "available": True,
            "price": midpoint,
            "bid": bid,
            "ask": ask,
            "fetched_at": fetched_at,
            "source": "Swissquote public quotes - XAU/USD spot midpoint",
            "raw": {"timestamp_ms": timestamp_ms},
        }

    def _fetch_yahoo_gold_futures_price(self) -> dict[str, Any]:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        response = self.session.get(
            url,
            params={"range": "1d", "interval": "1m"},
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []

        last_price = None
        last_timestamp = None
        for timestamp, close in zip(reversed(timestamps), reversed(closes), strict=False):
            if close is not None:
                last_price = float(close)
                last_timestamp = timestamp
                break

        if last_price is None or last_timestamp is None:
            raise RuntimeError("قیمت معتبر در پاسخ Yahoo Finance وجود ندارد.")

        fetched_at = utc_timestamp_to_timezone(last_timestamp, self.settings.timezone)
        return {
            "available": True,
            "price": last_price,
            "fetched_at": fa_datetime(fetched_at),
            "source": "Yahoo Finance - GC=F COMEX gold futures proxy",
            "raw": {"timestamp": last_timestamp},
        }
