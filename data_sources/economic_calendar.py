from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from config import Settings
from utils.time_utils import fa_datetime, now_in_timezone, parse_iso_to_timezone


IMPORTANT_KEYWORDS = [
    "CPI",
    "PCE",
    "Core",
    "Nonfarm",
    "Payroll",
    "Unemployment",
    "Initial Jobless",
    "FOMC",
    "Fed",
    "Retail Sales",
    "GDP",
    "ISM",
    "PMI",
    "Consumer Confidence",
    "Treasury",
]


class EconomicCalendarProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch_today_events(self) -> dict[str, Any]:
        errors: list[str] = []

        if self.settings.economic_calendar_api_key:
            try:
                return {
                    "items": self._fetch_fmp_calendar(),
                    "errors": [],
                    "source": "Financial Modeling Prep",
                }
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Financial Modeling Prep: {exc}")
        else:
            errors.append("ECONOMIC_CALENDAR_API_KEY تنظیم نشده است.")

        if self.settings.fred_api_key:
            try:
                return {
                    "items": self._fetch_fred_release_calendar(),
                    "errors": errors,
                    "source": "FRED - St. Louis Fed",
                }
            except Exception as exc:  # noqa: BLE001
                errors.append(f"FRED: {exc}")
        else:
            errors.append("FRED_API_KEY تنظیم نشده است.")

        return {"items": [], "errors": errors, "source": "Financial Modeling Prep / FRED"}

    def _fetch_fmp_calendar(self) -> list[dict[str, Any]]:
        today = now_in_timezone(self.settings.timezone).date().isoformat()
        url = "https://financialmodelingprep.com/stable/economic-calendar"
        response = self.session.get(
            url,
            params={
                "from": today,
                "to": today,
                "apikey": self.settings.economic_calendar_api_key,
            },
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("فرمت پاسخ تقویم اقتصادی قابل پردازش نیست.")

        filtered = []
        for event in payload:
            name = event.get("event") or event.get("title") or ""
            country = event.get("country") or ""
            impact = (event.get("impact") or event.get("importance") or "").lower()
            is_high = "high" in impact or "3" == str(event.get("importance", ""))
            is_relevant = country.upper() in {"US", "USA", "UNITED STATES"} or any(
                keyword.lower() in name.lower() for keyword in IMPORTANT_KEYWORDS
            )
            if not (is_high or is_relevant):
                continue

            event_dt = self._parse_event_datetime(event.get("date"))
            filtered.append(
                {
                    "event": name or "رویداد بدون نام",
                    "event_fa": self._persian_event_name(name),
                    "country": country or "نامشخص",
                    "time_tehran": fa_datetime(event_dt),
                    "forecast": event.get("estimate") or event.get("forecast") or "نامشخص",
                    "previous": event.get("previous") or "نامشخص",
                    "importance": event.get("impact") or event.get("importance") or "نامشخص",
                    "expected_impact": "وابسته به نتیجه",
                    "scenario": self._scenario_for_event(name),
                }
            )
        return filtered

    def _fetch_fred_release_calendar(self) -> list[dict[str, Any]]:
        today = now_in_timezone(self.settings.timezone).date().isoformat()
        url = "https://api.stlouisfed.org/fred/releases/dates"
        response = self.session.get(
            url,
            params={
                "api_key": self.settings.fred_api_key,
                "file_type": "json",
                "realtime_start": today,
                "realtime_end": today,
                "limit": 1000,
            },
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        releases = payload.get("release_dates") or []

        filtered = []
        for release in releases:
            name = release.get("release_name") or ""
            if not any(keyword.lower() in name.lower() for keyword in IMPORTANT_KEYWORDS):
                continue
            filtered.append(
                {
                    "event": name,
                    "event_fa": self._persian_event_name(name),
                    "country": "United States",
                    "time_tehran": "زمان دقیق در FRED ارائه نشده است.",
                    "forecast": "نامشخص",
                    "previous": "نامشخص",
                    "importance": "High/Relevant by mapping",
                    "expected_impact": "وابسته به نتیجه",
                    "scenario": self._scenario_for_event(name),
                    "source": "FRED - St. Louis Fed",
                }
            )
        return filtered

    def _parse_event_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return parse_iso_to_timezone(value, self.settings.timezone)

    @staticmethod
    def _scenario_for_event(name: str) -> str:
        lowered = name.lower()
        if any(term in lowered for term in ["cpi", "pce", "inflation", "core"]):
            return (
                "عدد بالاتر از انتظار معمولاً دلار و بازدهی را تقویت و طلا را تضعیف می‌کند؛ "
                "عدد پایین‌تر از انتظار معمولاً برای طلا حمایتی است."
            )
        if any(term in lowered for term in ["payroll", "jobs", "unemployment", "jobless"]):
            return (
                "بازار کار قوی‌تر از انتظار معمولاً فشار کاهشی روی طلا دارد؛ "
                "ضعف بازار کار می‌تواند انتظار کاهش نرخ بهره و تقاضای طلا را تقویت کند."
            )
        if any(term in lowered for term in ["fed", "fomc"]):
            return (
                "لحن انقباضی فدرال رزرو برای طلا منفی است؛ "
                "لحن متمایل به کاهش نرخ بهره برای طلا مثبت است."
            )
        return (
            "نتیجه قوی‌تر از انتظار می‌تواند دلار را تقویت کند؛ "
            "نتیجه ضعیف‌تر از انتظار معمولاً به نفع طلاست."
        )

    @staticmethod
    def _persian_event_name(name: str) -> str:
        lowered = name.lower()
        mapping = [
            ("cpi", "شاخص قیمت مصرف‌کننده آمریکا"),
            ("pce", "شاخص هزینه مصرف شخصی آمریکا"),
            ("nonfarm", "اشتغال غیرکشاورزی آمریکا"),
            ("payroll", "اشتغال غیرکشاورزی آمریکا"),
            ("unemployment", "نرخ بیکاری آمریکا"),
            ("jobless", "درخواست‌های بیمه بیکاری آمریکا"),
            ("fomc", "تصمیم یا صورت‌جلسه فدرال رزرو"),
            ("fed", "سخنرانی یا رویداد فدرال رزرو"),
            ("retail sales", "خرده‌فروشی آمریکا"),
            ("gdp", "تولید ناخالص داخلی"),
            ("ism", "شاخص ISM آمریکا"),
            ("pmi", "شاخص مدیران خرید"),
            ("consumer confidence", "اعتماد مصرف‌کننده آمریکا"),
            ("treasury", "حراج اوراق خزانه آمریکا"),
        ]
        for key, value in mapping:
            if key in lowered:
                return value
        return "رویداد اقتصادی مهم"
