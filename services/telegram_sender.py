from __future__ import annotations

import requests

from config import Settings


def send_telegram_message(settings: Settings, text: str, parse_mode: str | None = "HTML") -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": _fit_one_message(text),
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    response = requests.post(url, json=payload, timeout=settings.http_timeout)
    response.raise_for_status()
    return True


def _fit_one_message(text: str, max_length: int = 3900) -> str:
    if len(text) <= max_length:
        return text

    suffix = "\n\n<b>ادامه:</b> گزارش کامل در فایل Markdown ذخیره شد."
    allowed = max_length - len(suffix)
    lines: list[str] = []
    total = 0
    for line in text.splitlines():
        next_total = total + len(line) + 1
        if next_total > allowed:
            break
        lines.append(line)
        total = next_total
    return "\n".join(lines).rstrip() + suffix
