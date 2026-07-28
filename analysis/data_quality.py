from __future__ import annotations

from datetime import datetime
from typing import Any


def assess_data_quality(
    report_time: datetime,
    price: dict[str, Any],
    news_payload: dict[str, Any],
    calendar_payload: dict[str, Any],
    prediction_payload: dict[str, Any],
    technicals: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    score = 0
    warnings: list[str] = []
    blockers: list[str] = []

    if price.get("available"):
        score += 35
        validation = price.get("validation") or {}
        if validation.get("status") == "confirmed":
            score += 10
        elif validation.get("status") == "mismatch":
            warnings.append("قیمت دو منبع مستقل هم‌خوانی کافی ندارد.")
            blockers.append("اختلاف قیمت منابع از آستانه مجاز بیشتر است.")
        else:
            score += 4
            warnings.append("قیمت با منبع مستقل دوم تأیید نشد.")
    else:
        warnings.append("قیمت زنده در دسترس نیست.")
        blockers.append("قیمت زنده معتبر برای تصمیم معاملاتی وجود ندارد.")

    range_fields = (
        "session_open",
        "session_high",
        "session_low",
        "range_start",
        "range_end",
    )
    if price.get("range_boundary_status") != "explicit" or any(
        price.get(field) is None for field in range_fields
    ):
        warnings.append("دامنه جلسه با مرز زمانی صریح و قابل ممیزی در دسترس نیست.")
        blockers.append("دامنه جلسه بدون مرز زمانی معتبر برای معامله قابل استفاده نیست.")
    range_comparison = price.get("range_comparison") or {}
    if range_comparison.get("status") == "mismatch":
        warnings.append(
            "دامنه روز UTC با فیلدهای Quote دارای مرزبندی نامعلوم ناسازگار است."
        )
        blockers.append("ناسازگاری دامنه جلسه میان داده‌های منبع وجود دارد.")
    elif range_comparison.get("status") == "unavailable":
        warnings.append("دامنه جلسه با فیلدهای Quote به‌طور کامل تطبیق داده نشد.")

    for timeframe, points in (("1d", 10), ("4h", 10), ("1h", 10)):
        item = technicals.get(timeframe, {})
        if not item.get("available"):
            warnings.append(f"داده تکنیکال {timeframe} ناقص است.")
            blockers.append(f"داده تکنیکال {timeframe} برای تصمیم معاملاتی کافی نیست.")
            continue
        if not item.get("last_candle_closed"):
            blockers.append(f"بسته‌بودن آخرین کندل {timeframe} تأیید نشده است.")
            continue
        if _is_fresh(report_time, item.get("last_candle_at"), timeframe):
            score += points
        else:
            score += points // 2
            warnings.append(f"آخرین کندل {timeframe} قدیمی‌تر از حد انتظار است.")
        if item.get("consistency_warning"):
            score = max(score - 8, 0)
            warnings.append(str(item["consistency_warning"]))
            blockers.append(
                f"تناقض روند و ساختار در تایم‌فریم {timeframe} وجود دارد."
            )

    directional_trends = {
        item.get("trend")
        for item in technicals.values()
        if item.get("trend") in {"صعودی", "نزولی"}
    }
    if len(directional_trends) > 1:
        score = max(score - 10, 0)
        warnings.append("روند تایم‌فریم‌های اصلی هم‌جهت نیست.")
        blockers.append("تناقض روند بین تایم‌فریم‌های اصلی وجود دارد.")

    news_items = news_payload.get("items") or []
    fresh_news = [
        item
        for item in news_items
        if _hours_old(report_time, item.get("published_sort")) <= 48
    ]
    source_count = len({item.get("source") for item in fresh_news if item.get("source")})
    if len(fresh_news) >= 3 and source_count >= 2:
        score += 15
    elif fresh_news:
        score += 8
        warnings.append("پوشش اخبار تازه یا تنوع منابع محدود است.")
    else:
        warnings.append("خبر تازه و قابل زمان‌سنجی کافی دریافت نشد.")

    if calendar_payload.get("items"):
        score += 5 if calendar_payload.get("source") == "Financial Modeling Prep" else 3
    elif calendar_payload.get("errors"):
        warnings.append("تقویم اقتصادی امروز کامل تأیید نشد.")

    if prediction_payload.get("items"):
        score += 5

    score = min(score, 100)
    if blockers:
        score = min(score, 49)
    if score >= 90:
        grade = "بالا"
    elif score >= 65:
        grade = "متوسط"
    else:
        grade = "پایین"

    return {
        "score": score,
        "grade": grade,
        "warnings": warnings,
        "blockers": blockers,
        "usable_for_trade": not blockers,
        "confidence_cap": "پایین" if blockers else None,
        "summary": (
            "؛ ".join(
                item.rstrip(".؟!") for item in (blockers + warnings)[:3]
            )
            + "."
            if blockers or warnings
            else "منابع اصلی تازه و سازگار هستند."
        ),
    }


def _is_fresh(report_time: datetime, value: Any, timeframe: str) -> bool:
    weekend = report_time.weekday() >= 5
    thresholds = {"1h": 30 if weekend else 3, "4h": 36 if weekend else 8, "1d": 96}
    return _hours_old(report_time, value) <= thresholds[timeframe]


def _hours_old(report_time: datetime, value: Any) -> float:
    if not isinstance(value, datetime):
        return float("inf")
    candidate = value
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=report_time.tzinfo)
    return max((report_time - candidate.astimezone(report_time.tzinfo)).total_seconds() / 3600, 0)
