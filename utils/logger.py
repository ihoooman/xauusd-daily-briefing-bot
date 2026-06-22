from __future__ import annotations

import logging
import re
from pathlib import Path


def setup_logger(name: str = "xauusd_bot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_dir = Path("output/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "bot.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def redact_sensitive(value: object) -> str:
    text = str(value)
    patterns = [
        (r"([?&](?:api_key|apikey|apiToken|token)=)[^&\s]+", r"\1<redacted>"),
        (r"(bot)\d+:[A-Za-z0-9_-]+(/)", r"\1<redacted>\2"),
        (r"(TELEGRAM_BOT_TOKEN=)[^\s]+", r"\1<redacted>"),
        (r"(TELEGRAM_CHAT_ID=)[^\s]+", r"\1<redacted>"),
        (r"(PRICE_API_KEY=)[^\s]+", r"\1<redacted>"),
        (r"(NEWS_API_KEY=)[^\s]+", r"\1<redacted>"),
        (r"(ECONOMIC_CALENDAR_API_KEY=)[^\s]+", r"\1<redacted>"),
        (r"(FRED_API_KEY=)[^\s]+", r"\1<redacted>"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
