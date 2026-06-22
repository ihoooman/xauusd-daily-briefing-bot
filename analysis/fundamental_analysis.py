from __future__ import annotations

from typing import Any


def summarize_fundamentals(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    score = 0
    reasons = []
    for item in news_items:
        impact = item.get("impact")
        if impact == "افزایشی برای طلا":
            score += 1
            reasons.append(item.get("why"))
        elif impact == "کاهشی برای طلا":
            score -= 1
            reasons.append(item.get("why"))

    if score > 1:
        bias = "صعودی"
    elif score < -1:
        bias = "نزولی"
    else:
        bias = "خنثی"

    return {
        "bias": bias,
        "score": score,
        "main_reason": next((reason for reason in reasons if reason), "خبر جهت‌دار کافی در دسترس نیست."),
    }
