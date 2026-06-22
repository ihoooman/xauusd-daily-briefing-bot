from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from analysis.final_verdict import build_final_verdict
from analysis.fundamental_analysis import summarize_fundamentals
from analysis.technical_analysis import analyze_all_timeframes
from config import settings
from data_sources.economic_calendar import EconomicCalendarProvider
from data_sources.news_data import NewsDataProvider
from data_sources.polymarket_data import PolymarketProvider
from data_sources.price_data import PriceDataProvider
from data_sources.technical_data import TechnicalDataProvider
from services.telegram_sender import send_telegram_message
from utils.logger import redact_sensitive, setup_logger
from utils.time_utils import fa_datetime, now_in_timezone


logger = setup_logger()


def generate_daily_report(send_telegram: bool = True) -> Path:
    report_time = now_in_timezone(settings.timezone)
    logger.info("Generating XAU/USD report")

    price = PriceDataProvider(settings).fetch_current_price()
    if not price.get("available"):
        logger.error("Price fetch failed: %s", redact_sensitive(price.get("error")))

    news_payload = NewsDataProvider(settings).fetch_latest_news()
    for error in news_payload.get("errors", []):
        logger.warning("News source warning: %s", redact_sensitive(error))

    calendar_payload = EconomicCalendarProvider(settings).fetch_today_events()
    for error in calendar_payload.get("errors", []):
        logger.warning("Economic calendar warning: %s", redact_sensitive(error))

    prediction_payload = PolymarketProvider(settings).fetch_relevant_markets()
    for error in prediction_payload.get("errors", []):
        logger.warning("Prediction market warning: %s", redact_sensitive(error))

    technical_raw = TechnicalDataProvider(settings).fetch_all_timeframes()
    for timeframe, payload in technical_raw.items():
        if not payload.get("available"):
            logger.warning(
                "Technical data warning %s: %s",
                timeframe,
                redact_sensitive(payload.get("error")),
            )

    news_items = news_payload.get("items", [])
    calendar_items = calendar_payload.get("items", [])
    prediction_items = prediction_payload.get("items", [])
    technicals = analyze_all_timeframes(technical_raw)
    fundamentals = summarize_fundamentals(news_items)
    verdict = build_final_verdict(fundamentals, calendar_items, prediction_items, technicals)

    markdown = render_report(
        report_time=report_time,
        price=price,
        news_payload=news_payload,
        calendar_payload=calendar_payload,
        prediction_payload=prediction_payload,
        technicals=technicals,
        verdict=verdict,
    )

    settings.report_dir.mkdir(parents=True, exist_ok=True)
    report_path = settings.report_dir / f"xauusd-report-{report_time.date().isoformat()}.md"
    report_path.write_text(markdown, encoding="utf-8")
    logger.info("Report saved: %s", report_path)

    if send_telegram:
        try:
            telegram_text = render_telegram_report(
                report_time=report_time,
                price=price,
                news_payload=news_payload,
                calendar_payload=calendar_payload,
                prediction_payload=prediction_payload,
                technicals=technicals,
                verdict=verdict,
            )
            sent = send_telegram_message(settings, telegram_text, parse_mode="HTML")
            if sent:
                logger.info("Telegram report sent")
            else:
                logger.info("Telegram credentials not provided; skipped sending")
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram send failed: %s", redact_sensitive(exc))

    return report_path


def render_report(
    report_time: Any,
    price: dict[str, Any],
    news_payload: dict[str, Any],
    calendar_payload: dict[str, Any],
    prediction_payload: dict[str, Any],
    technicals: dict[str, dict[str, Any]],
    verdict: dict[str, Any],
) -> str:
    price_text = f"{price['price']:.2f}" if price.get("available") else "در دسترس نیست"
    price_source = price.get("source") or "نامشخص"

    lines = [
        "# گزارش روزانه طلا / XAUUSD",
        "",
        f"تاریخ: {report_time.date().isoformat()}",
        f"ساعت تولید گزارش: {fa_datetime(report_time)}",
        f"قیمت فعلی: {price_text}",
        f"منبع قیمت: {price_source}",
        f"زمان دریافت قیمت: {price.get('fetched_at') or 'نامشخص'}",
        "",
        "## ۱. خلاصه سریع بازار",
        "",
        f"* سوگیری کلی: {verdict['decision']}",
        f"* تصمیم بهتر امروز: {_decision_to_plain_fa(verdict['decision'])}",
        f"* مهم‌ترین عامل اثرگذار: {verdict['main_reason']}",
        f"* ریسک اصلی امروز: {_main_risk(calendar_payload, price)}",
        "",
        "## ۲. تحلیل اخبار فاندامنتال",
        "",
    ]
    lines.extend(_render_news(news_payload))
    lines.extend(["", "## ۳. تقویم اقتصادی امروز", ""])
    lines.extend(_render_calendar(calendar_payload))
    lines.extend(["", "## ۴. داده‌های پلی‌مارکت و انتظارات بازار", ""])
    lines.extend(_render_prediction_markets(prediction_payload))
    lines.extend(["", "## ۵. تحلیل تکنیکال", ""])
    lines.extend(_render_technicals(technicals))
    lines.extend(
        [
            "",
            "## ۶. جمع‌بندی نهایی و سناریو معاملاتی",
            "",
            f"* تصمیم نهایی: {verdict['decision']}",
            f"* میزان اطمینان: {verdict['confidence']}",
            f"* دلیل اصلی: {verdict['main_reason']}",
            f"* سناریوی خرید: {verdict['bullish_scenario']}",
            f"* سناریوی فروش: {verdict['bearish_scenario']}",
            f"* مدیریت ریسک: {verdict['risk_management']}",
            f"* سطح ابطال تحلیل: {verdict['invalidation']}",
            f"* حمایت‌های کلیدی: {_format_levels(verdict['supports'])}",
            f"* مقاومت‌های کلیدی: {_format_levels(verdict['resistances'])}",
            "",
            "## ۷. نکته ریسک",
            "",
            "«این گزارش صرفاً برای تحلیل و تصمیم‌سازی است و سیگنال قطعی خرید یا فروش محسوب نمی‌شود.»",
            "",
        ]
    )
    return "\n".join(lines)


def render_telegram_report(
    report_time: Any,
    price: dict[str, Any],
    news_payload: dict[str, Any],
    calendar_payload: dict[str, Any],
    prediction_payload: dict[str, Any],
    technicals: dict[str, dict[str, Any]],
    verdict: dict[str, Any],
) -> str:
    price_text = f"{price['price']:.2f}" if price.get("available") else "در دسترس نیست"
    supports = _format_levels(verdict.get("supports", [])[:3])
    resistances = _format_levels(verdict.get("resistances", [])[:3])
    news_lines = _telegram_news_lines(news_payload.get("items", [])[:3])
    calendar_lines = _telegram_calendar_lines(calendar_payload.get("items", [])[:3])
    prediction_lines = _telegram_prediction_lines(prediction_payload.get("items", [])[:2])

    lines = [
        "<b>گزارش روزانه طلا / XAUUSD</b>",
        f"تاریخ: {escape(report_time.date().isoformat())}",
        f"ساعت: {escape(fa_datetime(report_time))}",
        f"قیمت: <b>{escape(price_text)}</b>",
        f"منبع قیمت: {escape(price.get('source') or 'نامشخص')}",
        "",
        "<b>خلاصه بازار</b>",
        f"سوگیری: <b>{escape(verdict['decision'])}</b>",
        f"اطمینان: {escape(verdict['confidence'])}",
        f"حمایت‌ها: {escape(supports)}",
        f"مقاومت‌ها: {escape(resistances)}",
        f"ابطال: {escape(verdict['invalidation'])}",
        "",
        "<b>تکنیکال</b>",
        _telegram_technical_line("روزانه", technicals.get("1d", {})),
        _telegram_technical_line("۴ ساعته", technicals.get("4h", {})),
        _telegram_technical_line("۱ ساعته", technicals.get("1h", {})),
        "",
        "<b>اخبار مهم</b>",
        *news_lines,
        "",
        "<b>تقویم اقتصادی</b>",
        *calendar_lines,
        "",
        "<b>انتظارات بازار</b>",
        *prediction_lines,
        "",
        "<b>سناریو</b>",
        f"خرید: {escape(verdict['bullish_scenario'])}",
        f"فروش: {escape(verdict['bearish_scenario'])}",
        f"ریسک: {escape(verdict['risk_management'])}",
        "",
        "«این گزارش صرفاً برای تحلیل و تصمیم‌سازی است و سیگنال قطعی خرید یا فروش محسوب نمی‌شود.»",
    ]
    return "\n".join(lines)


def _telegram_technical_line(label: str, item: dict[str, Any]) -> str:
    trend = item.get("trend", "نامشخص")
    rsi = item.get("rsi", "نامشخص")
    supports = _format_levels((item.get("supports") or [])[:2])
    resistances = _format_levels((item.get("resistances") or [])[:2])
    return (
        f"{escape(label)}: روند {escape(str(trend))} | RSI {escape(str(rsi))} | "
        f"حمایت {escape(supports)} | مقاومت {escape(resistances)}"
    )


def _telegram_news_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["داده معتبر و مرتبطی دریافت نشد."]
    return [
        (
            f"• {escape(item.get('persian_title', 'خبر مرتبط با بازار طلا'))} | "
            f"{escape(item.get('impact', 'خنثی'))} | {escape(item.get('source', 'نامشخص'))}"
        )
        for item in items
    ]


def _telegram_calendar_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["رویداد بااهمیت قابل تأیید برای امروز دریافت نشد."]
    return [
        (
            f"• {escape(item.get('event_fa', item.get('event', 'نامشخص')))} | "
            f"{escape(item.get('time_tehran', 'نامشخص'))} | "
            f"{escape(item.get('expected_impact', 'وابسته به نتیجه'))}"
        )
        for item in items
    ]


def _telegram_prediction_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["بازار فعال و معناداری در پلی‌مارکت پیدا نشد."]
    return [
        (
            f"• {escape(item.get('persian_title', 'بازار مرتبط با انتظارات کلان'))} | "
            f"{escape(item.get('probability', 'نامشخص'))} | "
            f"{escape(item.get('sentiment', 'خنثی'))}"
        )
        for item in items
    ]


def _render_news(payload: dict[str, Any]) -> list[str]:
    items = payload.get("items", [])
    if not items:
        return [
            "* خبر: داده معتبر و مرتبطی دریافت نشد.",
            "* خلاصه: بخش اخبار فاندامنتال در این اجرا قابل به‌روزرسانی نبود.",
            "* اثر روی طلا: خنثی",
            f"* منبع: {payload.get('source', 'نامشخص')}",
            "* زمان انتشار: نامشخص",
        ]
    lines: list[str] = []
    for item in items:
        lines.extend(
            [
                f"* خبر: {item.get('persian_title', 'خبر مرتبط با بازار طلا')}",
                f"* خلاصه: {item.get('persian_summary', 'خلاصه فارسی در دسترس نیست.')}",
                f"* اثر روی طلا: {item.get('impact', 'خنثی')}؛ {item.get('why', '')}",
                f"* منبع: {item.get('source', 'نامشخص')}",
                f"* زمان انتشار: {item.get('published', 'نامشخص')}",
                "",
            ]
        )
    return lines


def _render_calendar(payload: dict[str, Any]) -> list[str]:
    items = payload.get("items", [])
    if not items:
        return [
            "* رویداد: رویداد بااهمیت قابل تأیید دریافت نشد.",
            "* کشور: نامشخص",
            "* ساعت به وقت تهران: نامشخص",
            "* پیش‌بینی: نامشخص",
            "* عدد قبلی: نامشخص",
            "* اثر احتمالی روی طلا: وابسته به نتیجه",
            "* سناریو: بخش تقویم اقتصادی در این اجرا قابل به‌روزرسانی نبود.",
        ]
    lines: list[str] = []
    for item in items:
        lines.extend(
            [
                f"* رویداد: {item.get('event_fa', item.get('event', 'نامشخص'))}",
                f"* کشور: {item.get('country', 'نامشخص')}",
                f"* ساعت به وقت تهران: {item.get('time_tehran', 'نامشخص')}",
                f"* پیش‌بینی: {item.get('forecast', 'نامشخص')}",
                f"* عدد قبلی: {item.get('previous', 'نامشخص')}",
                f"* اثر احتمالی روی طلا: {item.get('expected_impact', 'وابسته به نتیجه')}",
                f"* سناریو: {item.get('scenario', 'وابسته به نتیجه')}",
                "",
            ]
        )
    return lines


def _render_prediction_markets(payload: dict[str, Any]) -> list[str]:
    items = payload.get("items", [])
    if not items:
        return ["«بازار فعال و معناداری در پلی‌مارکت برای این بخش پیدا نشد.»"]
    lines: list[str] = []
    for item in items:
        lines.extend(
            [
                f"* بازار: {item.get('persian_title', 'بازار مرتبط با انتظارات کلان بازار')}",
                f"* احتمال فعلی: {item.get('probability', 'نامشخص')}",
                f"* برداشت تحلیلی: {item.get('interpretation', 'نامشخص')}",
                f"* اثر روی طلا: {item.get('sentiment', 'خنثی')}",
                "",
            ]
        )
    return lines


def _render_technicals(technicals: dict[str, dict[str, Any]]) -> list[str]:
    names = {"1d": "تایم‌فریم روزانه", "4h": "تایم‌فریم ۴ ساعته", "1h": "تایم‌فریم ۱ ساعته"}
    lines: list[str] = []
    for key in ("1d", "4h", "1h"):
        item = technicals.get(key, {})
        lines.extend(
            [
                names[key],
                "",
                f"* روند: {item.get('trend', 'داده کافی برای تعیین دقیق این بخش در دسترس نیست.')}",
                f"* حمایت‌ها: {_format_levels(item.get('supports', []))}",
                f"* مقاومت‌ها: {_format_levels(item.get('resistances', []))}",
                f"* RSI: {item.get('rsi', 'نامشخص')}",
                f"* میانگین‌های متحرک: {item.get('moving_averages', 'نامشخص')}",
                f"* توضیح: {item.get('explanation', 'داده کافی برای تعیین دقیق این بخش در دسترس نیست.')}",
                "",
            ]
        )
    return lines


def _format_levels(levels: list[float]) -> str:
    if not levels:
        return "داده کافی برای تعیین دقیق این بخش در دسترس نیست."
    return "، ".join(f"{level:.2f}" for level in levels)


def _decision_to_plain_fa(decision: str) -> str:
    if decision.startswith("LONG"):
        return "خرید فقط پس از تأیید شکست یا برگشت معتبر"
    if decision.startswith("SHORT"):
        return "فروش فقط پس از تأیید شکست حمایت یا رد مقاومت"
    return "خرید یا فروش طبق سوگیری غالب بازار"


def _main_risk(calendar_payload: dict[str, Any], price: dict[str, Any]) -> str:
    if calendar_payload.get("items"):
        return "نوسان ناشی از داده‌های اقتصادی و واکنش دلار آمریکا"
    if not price.get("available"):
        return "نبود قیمت لحظه‌ای معتبر در زمان تولید گزارش"
    return "تغییر ناگهانی انتظارات نرخ بهره یا بازدهی اوراق آمریکا"


if __name__ == "__main__":
    path = generate_daily_report(send_telegram=True)
    print(path)
