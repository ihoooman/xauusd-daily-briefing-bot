from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    timezone: str = os.getenv("TIMEZONE", "Asia/Tehran")
    report_time: str = os.getenv("REPORT_TIME", "12:00")

    price_api_key: str | None = os.getenv("PRICE_API_KEY") or None
    news_api_key: str | None = os.getenv("NEWS_API_KEY") or None
    economic_calendar_api_key: str | None = (
        os.getenv("ECONOMIC_CALENDAR_API_KEY") or None
    )
    fred_api_key: str | None = os.getenv("FRED_API_KEY") or None
    polymarket_api_url: str = os.getenv(
        "POLYMARKET_API_URL", "https://gamma-api.polymarket.com/markets"
    )

    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID") or None

    report_dir: Path = BASE_DIR / "output" / "reports"

    http_timeout: int = int(os.getenv("HTTP_TIMEOUT", "20"))
    user_agent: str = os.getenv(
        "USER_AGENT",
        "xauusd-daily-briefing-bot/1.0 (+https://example.local)",
    )


settings = Settings()
