from __future__ import annotations

from typing import Any


def build_final_verdict(
    fundamentals: dict[str, Any],
    calendar_items: list[dict[str, Any]],
    prediction_items: list[dict[str, Any]],
    technicals: dict[str, dict[str, Any]],
    price: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []

    if fundamentals.get("bias") == "صعودی":
        score += 1
        reasons.append("فاندامنتال‌ها متمایل به حمایت از طلا هستند.")
    elif fundamentals.get("bias") == "نزولی":
        score -= 1
        reasons.append("فاندامنتال‌ها متمایل به فشار روی طلا هستند.")

    prediction_score = 0
    for item in prediction_items:
        if item.get("sentiment") == "صعودی":
            prediction_score += 1
        elif item.get("sentiment") == "نزولی":
            prediction_score -= 1
    score += max(-2, min(2, prediction_score))

    for timeframe, weight in (("1d", 3), ("4h", 2), ("1h", 1)):
        trend = technicals.get(timeframe, {}).get("trend")
        if trend == "صعودی":
            score += weight
        elif trend == "نزولی":
            score -= weight

    if calendar_items:
        score = int(score * 0.8)
        reasons.append("وجود رویدادهای مهم اقتصادی، قطعیت سناریو را کاهش می‌دهد.")

    decision = _two_way_decision(score, fundamentals, technicals)

    confidence = "پایین"
    if abs(score) >= 6:
        confidence = "بالا"
    elif abs(score) >= 3:
        confidence = "متوسط"

    quality_score = int((data_quality or {}).get("score", 0))
    if quality_score < 65:
        confidence = "پایین"
    elif quality_score < 90 and confidence == "بالا":
        confidence = "متوسط"

    current_price = float(price["price"]) if price and price.get("available") else None
    supports = _collect_levels(technicals, "supports", current_price)
    resistances = _collect_levels(technicals, "resistances", current_price)
    invalidation = _invalidation_level(decision, supports, resistances)

    main_reason = " ".join(reasons) or fundamentals.get(
        "main_reason", "داده کافی برای یک جهت قطعی وجود ندارد."
    )
    if abs(score) < 2:
        main_reason = (
            f"{main_reason} بازار قطعیت بالایی ندارد، اما خروجی طبق تنظیم دوگزینه‌ای "
            "فقط بین خرید و فروش انتخاب شده است."
        )

    return {
        "decision": decision,
        "confidence": confidence,
        "main_reason": main_reason,
        "supports": supports,
        "resistances": resistances,
        "invalidation": invalidation,
        "bullish_scenario": _bullish_scenario(resistances, supports),
        "bearish_scenario": _bearish_scenario(supports, resistances),
        "risk_management": _risk_management(decision, supports, resistances),
        "score": score,
        "data_quality_score": quality_score,
    }


def _two_way_decision(
    score: int,
    fundamentals: dict[str, Any],
    technicals: dict[str, dict[str, Any]],
) -> str:
    if score > 0:
        return "LONG / خرید"
    if score < 0:
        return "SHORT / فروش"

    weighted = 0
    for timeframe, weight in (("1d", 2), ("4h", 2), ("1h", 1)):
        trend = technicals.get(timeframe, {}).get("trend")
        if trend == "صعودی":
            weighted += weight
        elif trend == "نزولی":
            weighted -= weight

    if weighted > 0:
        return "LONG / خرید"
    if weighted < 0:
        return "SHORT / فروش"
    if fundamentals.get("bias") == "نزولی":
        return "SHORT / فروش"
    return "LONG / خرید"


def _collect_levels(
    technicals: dict[str, dict[str, Any]], key: str, current_price: float | None = None
) -> list[float]:
    levels: list[float] = []
    for timeframe in ("1d", "4h", "1h"):
        levels.extend(technicals.get(timeframe, {}).get(key) or [])
    unique = sorted({round(float(level), 2) for level in levels})
    if current_price is not None:
        if key == "supports":
            unique = [level for level in unique if level < current_price]
        else:
            unique = [level for level in unique if level > current_price]
    tolerance = (current_price or (unique[-1] if unique else 0)) * 0.001
    unique = _cluster_nearby_levels(unique, tolerance)
    if key == "supports":
        return list(reversed(unique))[:5]
    return unique[:5]


def _cluster_nearby_levels(levels: list[float], tolerance: float) -> list[float]:
    if not levels or tolerance <= 0:
        return levels
    clusters: list[list[float]] = [[levels[0]]]
    for level in levels[1:]:
        if level - clusters[-1][-1] <= tolerance:
            clusters[-1].append(level)
        else:
            clusters.append([level])
    return [round(sum(cluster) / len(cluster), 2) for cluster in clusters]


def _invalidation_level(decision: str, supports: list[float], resistances: list[float]) -> str:
    if decision.startswith("LONG") and supports:
        return f"تثبیت زیر {supports[0]:.2f}"
    if decision.startswith("SHORT") and resistances:
        return f"تثبیت بالای {resistances[0]:.2f}"
    return "داده کافی برای تعیین سطح ابطال دقیق در دسترس نیست."


def _bullish_scenario(resistances: list[float], supports: list[float]) -> str:
    if resistances:
        return f"عبور و تثبیت بالای {resistances[0]:.2f} می‌تواند مسیر رشد تا مقاومت‌های بعدی را فعال کند."
    if supports:
        return f"حفظ حمایت {supports[0]:.2f} و تشکیل کف بالاتر می‌تواند سناریوی خرید را معتبر کند."
    return "داده کافی برای سناریوی خرید دقیق در دسترس نیست."


def _bearish_scenario(supports: list[float], resistances: list[float]) -> str:
    if supports:
        return f"شکست و تثبیت زیر {supports[0]:.2f} می‌تواند فشار فروش را تقویت کند."
    if resistances:
        return f"رد قیمت از محدوده {resistances[0]:.2f} می‌تواند سناریوی فروش کوتاه‌مدت بسازد."
    return "داده کافی برای سناریوی فروش دقیق در دسترس نیست."


def _risk_management(decision: str, supports: list[float], resistances: list[float]) -> str:
    if decision.startswith("LONG") and supports:
        return f"برای خرید، تثبیت زیر {supports[0]:.2f} نشانه تضعیف سناریو است."
    if decision.startswith("SHORT") and resistances:
        return f"برای فروش، تثبیت بالای {resistances[0]:.2f} نشانه تضعیف سناریو است."
    return "به‌دلیل کمبود سطوح معتبر، حجم معامله باید محافظه‌کارانه باشد."
