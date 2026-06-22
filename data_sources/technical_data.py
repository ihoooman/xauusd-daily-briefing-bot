from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from config import Settings
from utils.time_utils import utc_timestamp_to_timezone


class TechnicalDataProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch_all_timeframes(self) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for timeframe in ("1d", "4h", "1h"):
            try:
                output[timeframe] = {
                    "available": True,
                    "data": self.fetch_ohlc(timeframe),
                    "source": self._source_label(),
                }
            except Exception as exc:  # noqa: BLE001
                output[timeframe] = {
                    "available": False,
                    "data": pd.DataFrame(),
                    "source": self._source_label(),
                    "error": str(exc),
                }
        return output

    def _source_label(self) -> str:
        if self.settings.price_api_key:
            return "Twelve Data - XAU/USD"
        return "Yahoo Finance - GC=F COMEX gold futures OHLC proxy"

    def fetch_ohlc(self, timeframe: str) -> pd.DataFrame:
        if self.settings.price_api_key:
            if timeframe == "1d":
                return self._fetch_twelve_time_series(interval="1day")
            if timeframe == "1h":
                return self._fetch_twelve_time_series(interval="1h")
            if timeframe == "4h":
                hourly = self._fetch_twelve_time_series(interval="1h")
                if hourly.empty:
                    raise RuntimeError("داده یک‌ساعته برای ساخت تایم‌فریم ۴ ساعته موجود نیست.")
                return self._resample_4h(hourly)

        if timeframe == "1d":
            return self._fetch_yahoo_chart(range_value="1y", interval="1d")
        if timeframe == "1h":
            return self._fetch_yahoo_chart(range_value="60d", interval="1h")
        if timeframe == "4h":
            hourly = self._fetch_yahoo_chart(range_value="60d", interval="1h")
            if hourly.empty:
                raise RuntimeError("داده یک‌ساعته برای ساخت تایم‌فریم ۴ ساعته موجود نیست.")
            return self._resample_4h(hourly)
        raise ValueError(f"تایم‌فریم پشتیبانی نمی‌شود: {timeframe}")

    def _fetch_yahoo_chart(self, range_value: str, interval: str) -> pd.DataFrame:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        response = self.session.get(
            url,
            params={"range": range_value, "interval": interval},
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        error = payload.get("chart", {}).get("error")
        if error:
            raise RuntimeError(error)

        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
        if not timestamps:
            raise RuntimeError("کندل معتبر دریافت نشد.")

        rows = []
        for idx, timestamp in enumerate(timestamps):
            row = {
                "datetime": utc_timestamp_to_timezone(timestamp, self.settings.timezone),
                "open": quote.get("open", [None])[idx],
                "high": quote.get("high", [None])[idx],
                "low": quote.get("low", [None])[idx],
                "close": quote.get("close", [None])[idx],
                "volume": quote.get("volume", [0])[idx] or 0,
            }
            rows.append(row)

        df = pd.DataFrame(rows).dropna(subset=["open", "high", "low", "close"])
        if df.empty:
            raise RuntimeError("پس از پاک‌سازی، داده OHLC کافی باقی نماند.")
        df = df.set_index("datetime").sort_index()
        return df.astype(
            {"open": "float64", "high": "float64", "low": "float64", "close": "float64"}
        )

    def _fetch_twelve_time_series(self, interval: str) -> pd.DataFrame:
        url = "https://api.twelvedata.com/time_series"
        response = self.session.get(
            url,
            params={
                "symbol": "XAU/USD",
                "interval": interval,
                "outputsize": 500,
                "apikey": self.settings.price_api_key,
            },
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error":
            raise RuntimeError(payload.get("message", "خطای نامشخص Twelve Data"))

        values = payload.get("values") or []
        if not values:
            raise RuntimeError("داده کندلی XAU/USD از Twelve Data دریافت نشد.")

        rows = []
        for item in values:
            timestamp = pd.to_datetime(item["datetime"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize(self.settings.timezone)
            rows.append(
                {
                    "datetime": timestamp,
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item.get("volume") or 0),
                }
            )
        return pd.DataFrame(rows).set_index("datetime").sort_index()

    @staticmethod
    def _resample_4h(hourly: pd.DataFrame) -> pd.DataFrame:
        return (
            hourly.resample("4h")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(subset=["open", "high", "low", "close"])
        )
