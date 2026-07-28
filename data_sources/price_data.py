from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        primary: dict[str, Any] | None = None

        if self.settings.price_api_key:
            try:
                primary = self._fetch_twelve_data_quote()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Twelve Data: {exc}")

        try:
            swissquote = self._fetch_swissquote_spot_price()
            if primary:
                primary["validation"] = self._compare_spot_quotes(primary, swissquote)
                primary["errors"] = errors
                return primary
            primary = swissquote
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Swissquote: {exc}")

        if primary:
            primary["validation"] = {
                "status": "unavailable",
                "message": "منبع مستقل دوم برای تطبیق قیمت در دسترس نبود.",
            }
            primary["errors"] = errors
            return primary

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

    @staticmethod
    def _compare_spot_quotes(
        primary: dict[str, Any], secondary: dict[str, Any]
    ) -> dict[str, Any]:
        primary_price = float(primary["price"])
        secondary_price = float(secondary["price"])
        divergence_pct = abs(primary_price - secondary_price) / primary_price * 100
        status = "confirmed" if divergence_pct <= 0.35 else "mismatch"
        return {
            "status": status,
            "secondary_source": secondary.get("source"),
            "secondary_price": secondary_price,
            "divergence_pct": round(divergence_pct, 3),
            "message": (
                "قیمت با منبع مستقل دوم تطبیق داده شد."
                if status == "confirmed"
                else "اختلاف قیمت دو منبع بیش از آستانه کنترل کیفیت است."
            ),
        }

    def _fetch_twelve_data_quote(self) -> dict[str, Any]:
        url = "https://api.twelvedata.com/quote"
        response = self.session.get(
            url,
            params={
                "symbol": "XAU/USD",
                "timezone": "UTC",
                "apikey": self.settings.price_api_key,
            },
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
        quote_session_open = _optional_float(payload.get("open"))
        quote_session_high = _optional_float(payload.get("high"))
        quote_session_low = _optional_float(payload.get("low"))
        result = {
            "available": True,
            "price": float(price),
            "fetched_at": fetched_at or "زمان اعلام‌شده توسط منبع موجود نیست",
            "retrieved_at": datetime.now(timezone.utc),
            "source": "Twelve Data",
            "quote_session_open": quote_session_open,
            "quote_session_high": quote_session_high,
            "quote_session_low": quote_session_low,
            "range_used_for_trade_activation": False,
            "raw": payload,
        }
        try:
            explicit_range = self._fetch_twelve_utc_day_range()
            result.update(explicit_range)
            result["range_comparison"] = self._compare_range_with_quote_fields(
                explicit_range,
                quote_session_open,
                quote_session_high,
                quote_session_low,
            )
        except Exception as exc:  # noqa: BLE001
            result.update(
                {
                    "session_open": None,
                    "session_high": None,
                    "session_low": None,
                    "range_source": "Twelve Data time_series 1min",
                    "range_timezone": "UTC",
                    "range_boundary_status": "unavailable",
                    "range_comparison": {
                        "status": "unavailable",
                        "message": (
                            "دامنه با مرز زمانی صریح دریافت نشد؛ فیلدهای Quote با "
                            "مرز نامعلوم جایگزین آن نشدند."
                        ),
                    },
                    "range_error": str(exc),
                }
            )
        return result

    def _fetch_twelve_utc_day_range(self) -> dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        session_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        response = self.session.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "XAU/USD",
                "interval": "1min",
                "start_date": session_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "outputsize": 2000,
                "order": "asc",
                "timezone": "UTC",
                "apikey": self.settings.price_api_key,
            },
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error":
            raise RuntimeError(payload.get("message", "خطای نامشخص Twelve Data"))
        return self._aggregate_closed_utc_day_range(
            payload.get("values") or [],
            now_utc=now_utc,
        )

    @staticmethod
    def _aggregate_closed_utc_day_range(
        values: list[dict[str, Any]],
        now_utc: datetime,
    ) -> dict[str, Any]:
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        else:
            now_utc = now_utc.astimezone(timezone.utc)
        session_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        rows: list[tuple[datetime, float, float, float, float]] = []
        for item in values:
            raw_timestamp = str(item.get("datetime") or "").strip()
            if not raw_timestamp:
                continue
            try:
                timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)
            close_at = timestamp + timedelta(minutes=1)
            if timestamp < session_start or close_at > now_utc:
                continue
            try:
                row = (
                    timestamp,
                    float(item["open"]),
                    float(item["high"]),
                    float(item["low"]),
                    float(item["close"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if (
                row[2] < row[3]
                or row[2] < max(row[1], row[4])
                or row[3] > min(row[1], row[4])
            ):
                continue
            rows.append(row)

        if not rows:
            raise RuntimeError(
                "کندل یک‌دقیقه‌ای کاملاً بسته‌شده برای دامنه روز UTC دریافت نشد."
            )
        rows.sort(key=lambda row: row[0])
        range_end = rows[-1][0] + timedelta(minutes=1)
        return {
            "session_open": rows[0][1],
            "session_high": max(row[2] for row in rows),
            "session_low": min(row[3] for row in rows),
            "session_last_closed_1m": rows[-1][4],
            "range_start": session_start,
            "range_end": range_end,
            "range_as_of": range_end,
            "range_source": (
                "Twelve Data time_series 1min - confirmed UTC calendar-day bars"
            ),
            "range_timezone": "UTC",
            "range_origin": "confirmed 1min candle OHLC aggregation",
            "range_boundary_status": "explicit",
            "range_definition": (
                "روز تقویمی UTC از 00:00:00 تا پایان آخرین کندل یک‌دقیقه‌ای "
                "کاملاً بسته‌شده"
            ),
            "range_used_for_trade_activation": False,
            "range_bar_count": len(rows),
        }

    @staticmethod
    def _compare_range_with_quote_fields(
        explicit_range: dict[str, Any],
        quote_open: float | None,
        quote_high: float | None,
        quote_low: float | None,
    ) -> dict[str, Any]:
        if quote_open is None or quote_high is None or quote_low is None:
            return {
                "status": "unavailable",
                "message": "فیلدهای دامنه Quote برای مقایسه کامل نبودند.",
            }
        observed = (
            float(explicit_range["session_open"]),
            float(explicit_range["session_high"]),
            float(explicit_range["session_low"]),
        )
        quote = (quote_open, quote_high, quote_low)
        max_diff = max(abs(left - right) for left, right in zip(observed, quote))
        tolerance = max(0.5, float(explicit_range["session_open"]) * 0.0005)
        status = "consistent" if max_diff <= tolerance else "mismatch"
        return {
            "status": status,
            "max_absolute_difference": round(max_diff, 4),
            "tolerance": round(tolerance, 4),
            "message": (
                "فیلدهای Quote با دامنه صریح روز UTC سازگارند."
                if status == "consistent"
                else (
                    "فیلدهای Quote با مرز اعلام‌نشده با دامنه صریح روز UTC "
                    "ناسازگارند و برای فعال‌سازی معامله استفاده نمی‌شوند."
                )
            ),
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
            "retrieved_at": datetime.now(timezone.utc),
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
            "retrieved_at": datetime.now(timezone.utc),
            "source": "Yahoo Finance - GC=F COMEX gold futures proxy",
            "raw": {"timestamp": last_timestamp},
        }


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
