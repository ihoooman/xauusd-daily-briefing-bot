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
    if (data_quality or {}).get("confidence_cap") == "پایین":
        confidence = "پایین"

    current_price = float(price["price"]) if price and price.get("available") else None
    support_details = _collect_level_details(technicals, "supports", current_price)
    resistance_details = _collect_level_details(technicals, "resistances", current_price)
    supports = [float(item["level"]) for item in support_details]
    resistances = [float(item["level"]) for item in resistance_details]
    invalidation = _invalidation_level(decision, supports, resistances)
    trigger_level = _trigger_level(decision, supports, resistances)
    trigger_detail = _trigger_detail(decision, support_details, resistance_details)
    trigger_met = _trigger_confirmed(decision, trigger_level, technicals)
    quality_usable = bool((data_quality or {}).get("usable_for_trade", False))
    trade_status = "ACTIVE / فعال" if trigger_met and quality_usable else "INACTIVE / غیرفعال"
    if (data_quality or {}).get("no_chase"):
        action_now = str(
            (data_quality or {}).get("entry_restriction")
            or "عدم ورود؛ تعقیب قیمت در پنجره خبر ممنوع است."
        )
    elif trade_status.startswith("ACTIVE"):
        action_now = f"ورود مطابق سوگیری {decision}"
    else:
        action_now = "عدم ورود"
    level_audit = _audit_levels_against_observed_range(
        price, support_details, resistance_details
    )

    main_reason = " ".join(reasons) or fundamentals.get(
        "main_reason", "داده کافی برای یک جهت قطعی وجود ندارد."
    )
    if abs(score) < 2:
        main_reason = (
            f"{main_reason} بازار قطعیت بالایی ندارد، اما خروجی طبق تنظیم دوگزینه‌ای "
            "فقط بین خرید و فروش انتخاب شده است."
        )
    blockers = list((data_quality or {}).get("blockers") or [])
    if blockers:
        main_reason = f"{main_reason} مانع فعال‌سازی: {'؛ '.join(blockers[:2])}"

    return {
        "bias": decision,
        "decision": decision,
        "trade_status": trade_status,
        "action_now": action_now,
        "entry_restriction": (data_quality or {}).get("entry_restriction"),
        "trigger_level": trigger_level,
        "trigger_detail": trigger_detail,
        "trigger_met": trigger_met,
        "trigger_evidence": _trigger_evidence(
            decision, trigger_level, trigger_detail, technicals
        ),
        "confidence": confidence,
        "main_reason": main_reason,
        "supports": supports,
        "resistances": resistances,
        "support_details": support_details,
        "resistance_details": resistance_details,
        "invalidation": invalidation,
        "bullish_scenario": _bullish_scenario(resistances, supports),
        "bearish_scenario": _bearish_scenario(supports, resistances),
        "risk_management": _risk_management(decision, supports, resistances),
        "score": score,
        "data_quality_score": quality_score,
        "level_audit": level_audit,
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
    return [
        float(item["level"])
        for item in _collect_level_details(technicals, key, current_price)
    ]


def _collect_level_details(
    technicals: dict[str, dict[str, Any]],
    key: str,
    current_price: float | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    details_key = "support_details" if key == "supports" else "resistance_details"
    for timeframe in ("1d", "4h", "1h"):
        item = technicals.get(timeframe, {})
        details = item.get(details_key) or []
        if details:
            for detail in details:
                normalized = dict(detail)
                normalized["value"] = round(float(detail["value"]), 2)
                normalized.setdefault("timeframe", timeframe)
                candidates.append(normalized)
            continue
        for level in item.get(key) or []:
            candidates.append(
                {
                    "value": round(float(level), 2),
                    "timeframe": timeframe,
                    "origin": "historical_pivot",
                    "origin_fa": "پیوت تاریخی؛ کندل منشأ در داده ورودی ثبت نشده است",
                }
            )

    candidates.sort(key=lambda item: float(item["value"]))
    if current_price is not None:
        if key == "supports":
            candidates = [
                item for item in candidates if float(item["value"]) < current_price
            ]
        else:
            candidates = [
                item for item in candidates if float(item["value"]) > current_price
            ]

    reference = current_price or (
        float(candidates[-1]["value"]) if candidates else 0
    )
    tolerance = reference * 0.001
    clusters = _cluster_level_details(candidates, tolerance)
    output = [
        {
            "level": round(
                sum(float(item["value"]) for item in cluster) / len(cluster), 2
            ),
            "kind": "حمایت" if key == "supports" else "مقاومت",
            "origin": "historical_pivot",
            "origin_fa": "خوشه پیوت‌های تاریخی از OHLC کندل‌های بسته‌شده",
            "contributors": cluster,
        }
        for cluster in clusters
    ]
    if key == "supports":
        return list(reversed(output))[:5]
    return output[:5]


def _cluster_level_details(
    candidates: list[dict[str, Any]],
    tolerance: float,
) -> list[list[dict[str, Any]]]:
    if not candidates:
        return []
    if tolerance <= 0:
        return [[item] for item in candidates]
    clusters: list[list[dict[str, Any]]] = [[candidates[0]]]
    for item in candidates[1:]:
        if float(item["value"]) - float(clusters[-1][-1]["value"]) <= tolerance:
            clusters[-1].append(item)
        else:
            clusters.append([item])
    return clusters


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
        return f"بسته‌شدن کندل تأییدی زیر سطح تحلیلی {supports[0]:.2f}"
    if decision.startswith("SHORT") and resistances:
        return f"بسته‌شدن کندل تأییدی بالای سطح تحلیلی {resistances[0]:.2f}"
    return "داده کافی برای تعیین سطح ابطال دقیق در دسترس نیست."


def _bullish_scenario(resistances: list[float], supports: list[float]) -> str:
    if resistances:
        return (
            f"فقط بسته‌شدن کندل یک‌ساعته بالای سطح تحلیلی {resistances[0]:.2f} "
            "می‌تواند مسیر رشد تا مقاومت‌های بعدی را فعال کند؛ لمس سطح کافی نیست."
        )
    if supports:
        return f"حفظ حمایت {supports[0]:.2f} و تشکیل کف بالاتر می‌تواند سناریوی خرید را معتبر کند."
    return "داده کافی برای سناریوی خرید دقیق در دسترس نیست."


def _bearish_scenario(supports: list[float], resistances: list[float]) -> str:
    if supports:
        return (
            f"فقط بسته‌شدن کندل یک‌ساعته زیر سطح تحلیلی {supports[0]:.2f} "
            "می‌تواند فشار فروش را تأیید کند؛ لمس سطح کافی نیست."
        )
    if resistances:
        return f"رد قیمت از محدوده {resistances[0]:.2f} می‌تواند سناریوی فروش کوتاه‌مدت بسازد."
    return "داده کافی برای سناریوی فروش دقیق در دسترس نیست."


def _risk_management(decision: str, supports: list[float], resistances: list[float]) -> str:
    if decision.startswith("LONG") and supports:
        return (
            f"برای خرید، فقط Close کندل بسته‌شده ۱ساعته زیر {supports[0]:.2f} "
            "نشانه تضعیف سناریو است."
        )
    if decision.startswith("SHORT") and resistances:
        return (
            f"برای فروش، فقط Close کندل بسته‌شده ۱ساعته بالای {resistances[0]:.2f} "
            "نشانه تضعیف سناریو است."
        )
    return "به‌دلیل کمبود سطوح معتبر، حجم معامله باید محافظه‌کارانه باشد."


def _trigger_level(
    decision: str,
    supports: list[float],
    resistances: list[float],
) -> float | None:
    if decision.startswith("LONG") and resistances:
        return resistances[0]
    if decision.startswith("SHORT") and supports:
        return supports[0]
    return None


def _trigger_confirmed(
    decision: str,
    trigger_level: float | None,
    technicals: dict[str, dict[str, Any]],
) -> bool:
    hourly = technicals.get("1h", {})
    if (
        trigger_level is None
        or not hourly.get("available")
        or not hourly.get("last_candle_closed")
        or hourly.get("last_close") is None
    ):
        return False
    close = float(hourly["last_close"])
    if decision.startswith("LONG"):
        return close > trigger_level
    if decision.startswith("SHORT"):
        return close < trigger_level
    return False


def _trigger_evidence(
    decision: str,
    trigger_level: float | None,
    trigger_detail: dict[str, Any] | None,
    technicals: dict[str, dict[str, Any]],
) -> str:
    hourly = technicals.get("1h", {})
    candle = hourly.get("last_closed_candle") or {}
    close = candle.get("close", hourly.get("last_close"))
    closed_at = candle.get(
        "close_at",
        hourly.get("last_candle_close_at", hourly.get("last_candle_at")),
    )
    if trigger_level is None or close is None or not hourly.get("last_candle_closed"):
        return "کندل بسته‌شده و سطح معتبر کافی برای تأیید شرط وجود ندارد."
    relation = "بالاتر از" if float(close) > trigger_level else "پایین‌تر یا مساوی"
    if decision.startswith("SHORT"):
        relation = "پایین‌تر از" if float(close) < trigger_level else "بالاتر یا مساوی"
    ohlc = ""
    if all(candle.get(field) is not None for field in ("open", "high", "low", "close")):
        ohlc = (
            f"؛ OHLC={float(candle['open']):.2f}/"
            f"{float(candle['high']):.2f}/{float(candle['low']):.2f}/"
            f"{float(candle['close']):.2f}"
        )
    origin = _trigger_origin_text(trigger_detail)
    return (
        f"Close آخرین کندل کاملاً بسته‌شده ۱ساعته در {closed_at} برابر "
        f"{float(close):.2f} است{ohlc} و {relation} Trigger {trigger_level:.2f} "
        f"قرار دارد. منشأ Trigger: {origin}."
    )


def _trigger_detail(
    decision: str,
    support_details: list[dict[str, Any]],
    resistance_details: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if decision.startswith("LONG") and resistance_details:
        return resistance_details[0]
    if decision.startswith("SHORT") and support_details:
        return support_details[0]
    return None


def _trigger_origin_text(detail: dict[str, Any] | None) -> str:
    if not detail:
        return "نامشخص"
    contributors = detail.get("contributors") or []
    if not contributors:
        return str(detail.get("origin_fa") or detail.get("origin") or "نامشخص")
    parts = []
    for item in contributors:
        timeframe = item.get("timeframe", "نامشخص")
        close_at = item.get("pivot_candle_close_at", "زمان نامشخص")
        parts.append(f"پیوت {timeframe} از کندل بسته‌شده در {close_at}")
    return "؛ ".join(parts)


def _audit_levels_against_observed_range(
    price: dict[str, Any] | None,
    supports: list[dict[str, Any]],
    resistances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    session_low = (price or {}).get("session_low")
    session_high = (price or {}).get("session_high")
    boundary_is_explicit = (price or {}).get("range_boundary_status") == "explicit"
    audited: list[dict[str, Any]] = []
    for kind, details in (("حمایت", supports), ("مقاومت", resistances)):
        for detail in details:
            level = float(detail["level"])
            observed = None
            if (
                boundary_is_explicit
                and session_low is not None
                and session_high is not None
            ):
                observed = float(session_low) <= level <= float(session_high)
            audited.append(
                {
                    "level": level,
                    "kind": kind,
                    "origin": detail.get("origin"),
                    "origin_fa": detail.get("origin_fa"),
                    "contributors": detail.get("contributors") or [],
                    "inside_observed_session_range": observed,
                }
            )
    return audited
