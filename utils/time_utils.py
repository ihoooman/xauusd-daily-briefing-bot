from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_in_timezone(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def utc_timestamp_to_timezone(timestamp: int | float, tz_name: str) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(ZoneInfo(tz_name))


def parse_iso_to_timezone(value: str | None, tz_name: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz_name))


def fa_datetime(dt: datetime | None) -> str:
    if dt is None:
        return "نامشخص"
    return dt.strftime("%Y-%m-%d %H:%M")
