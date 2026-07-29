from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

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


class _FedCalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._div_stack: list[set[str]] = []
        self._panel: dict[str, list[str]] | None = None
        self._column: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "div":
            return
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        self._div_stack.append(classes)
        if self._panel is None and "panel" in classes:
            self._panel = {"time": [], "content": [], "dates": []}
            return
        if self._panel is None:
            return
        if "col-xs-2" in classes:
            self._column = "time"
        elif "col-xs-7" in classes:
            self._column = "content"
        elif "col-xs-3" in classes:
            self._column = "dates"

    def handle_endtag(self, tag: str) -> None:
        if tag != "div" or not self._div_stack:
            return
        classes = self._div_stack.pop()
        if any(name in classes for name in ("col-xs-2", "col-xs-7", "col-xs-3")):
            self._column = None
        if self._panel is not None and "panel" in classes:
            row = {
                key: " ".join(" ".join(value).split())
                for key, value in self._panel.items()
            }
            if any(row.values()):
                self.rows.append(row)
            self._panel = None
            self._column = None

    def handle_data(self, data: str) -> None:
        if self._panel is not None and self._column and data.strip():
            self._panel[self._column].append(data.strip())


class EconomicCalendarProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def fetch_today_events(self) -> dict[str, Any]:
        errors: list[str] = []
        items: list[dict[str, Any]] = []
        sources: list[str] = []

        try:
            official_items = self._fetch_federal_reserve_calendar()
            items.extend(official_items)
            if official_items:
                sources.append("Federal Reserve Board - official calendar")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Federal Reserve Board: {exc}")

        fmp_items: list[dict[str, Any]] = []
        if self.settings.economic_calendar_api_key:
            try:
                fmp_items = self._fetch_fmp_calendar()
                items.extend(fmp_items)
                sources.append("Financial Modeling Prep")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Financial Modeling Prep: {exc}")
        else:
            errors.append("ECONOMIC_CALENDAR_API_KEY تنظیم نشده است.")

        if not fmp_items and self.settings.fred_api_key:
            try:
                fred_items = self._fetch_fred_release_calendar()
                items.extend(fred_items)
                if fred_items:
                    sources.append("FRED - St. Louis Fed")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"FRED: {exc}")
        elif not fmp_items:
            errors.append("FRED_API_KEY تنظیم نشده است.")

        return {
            "items": self._deduplicate_events(items),
            "errors": errors,
            "source": " + ".join(sources) or "Federal Reserve Board / FMP / FRED",
        }

    def _fetch_federal_reserve_calendar(self) -> list[dict[str, Any]]:
        today = now_in_timezone(self.settings.timezone).date()
        month_slug = today.strftime("%B").lower()
        url = (
            f"https://www.federalreserve.gov/newsevents/"
            f"{today.year}-{month_slug}.htm"
        )
        response = self.session.get(url, timeout=self.settings.http_timeout)
        response.raise_for_status()
        parser = _FedCalendarParser()
        parser.feed(response.text)

        events: list[dict[str, Any]] = []
        for row in parser.rows:
            release_days = {
                int(value)
                for value in row["dates"].replace(",", " ").split()
                if value.isdigit()
            }
            if today.day not in release_days:
                continue
            title = row["content"]
            if "FOMC Press Conference" in title:
                event_name = "FOMC Press Conference"
                event_fa = "نشست خبری پس از تصمیم FOMC"
            elif "FOMC Meeting" in title:
                event_name = "FOMC Meeting"
                event_fa = "تصمیم نرخ بهره فدرال رزرو"
            else:
                continue
            event_at = self._parse_fed_event_time(today, row["time"])
            if event_at is None:
                continue
            events.append(
                {
                    "event": event_name,
                    "event_fa": event_fa,
                    "country": "United States",
                    "time_tehran": fa_datetime(event_at),
                    "event_at": event_at,
                    "source_time": row["time"],
                    "source_timezone": "America/New_York",
                    "forecast": "نامشخص",
                    "previous": "نامشخص",
                    "importance": "High",
                    "expected_impact": "وابسته به نتیجه",
                    "scenario": self._scenario_for_event(event_name),
                    "source": url,
                    "risk_category": "fomc",
                }
            )
        return sorted(events, key=lambda item: item["event_at"])

    def _parse_fed_event_time(
        self,
        event_date: Any,
        source_time: str,
    ) -> datetime | None:
        normalized = source_time.replace(".", "").upper().strip()
        try:
            parsed_time = datetime.strptime(normalized, "%I:%M %p").time()
        except ValueError:
            return None
        event_at_et = datetime.combine(
            event_date,
            parsed_time,
            tzinfo=ZoneInfo("America/New_York"),
        )
        return event_at_et.astimezone(ZoneInfo(self.settings.timezone))

    @staticmethod
    def _deduplicate_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        has_official_fomc = any(
            item.get("risk_category") == "fomc"
            and str(item.get("source") or "").startswith(
                "https://www.federalreserve.gov/"
            )
            for item in items
        )
        output: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            event_name = str(item.get("event") or "")
            lowered = event_name.lower()
            if (
                not str(item.get("source") or "").startswith(
                    "https://www.federalreserve.gov/"
                )
                and has_official_fomc
                and ("fomc" in lowered or "interest rate decision" in lowered)
            ):
                continue
            key = (
                str(item.get("event_fa") or event_name),
                str(item.get("time_tehran") or "نامشخص"),
            )
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
        return output

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
                    "event_at": event_dt,
                    "forecast": event.get("estimate") or event.get("forecast") or "نامشخص",
                    "previous": event.get("previous") or "نامشخص",
                    "importance": event.get("impact") or event.get("importance") or "نامشخص",
                    "expected_impact": "وابسته به نتیجه",
                    "scenario": self._scenario_for_event(name),
                    "source": "Financial Modeling Prep",
                    "risk_category": (
                        "fomc"
                        if "fomc" in name.lower()
                        or "interest rate decision" in name.lower()
                        else "macro"
                    ),
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
