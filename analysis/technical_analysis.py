from __future__ import annotations

from typing import Any

import pandas as pd


def analyze_all_timeframes(raw_data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        timeframe: analyze_timeframe(payload.get("data"), payload)
        for timeframe, payload in raw_data.items()
    }


def analyze_timeframe(df: pd.DataFrame | None, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("available") or df is None or df.empty or len(df) < 30:
        return {
            "available": False,
            "trend": "داده کافی برای تعیین دقیق این بخش در دسترس نیست.",
            "supports": [],
            "resistances": [],
            "rsi": "نامشخص",
            "moving_averages": "نامشخص",
            "macd": "نامشخص",
            "structure": "داده کافی برای تعیین دقیق این بخش در دسترس نیست.",
            "explanation": (
                "داده کافی برای تعیین دقیق این بخش در دسترس نیست. "
                f"منبع بررسی‌شده: {payload.get('source', 'نامشخص')}."
            ),
            "error": payload.get("error"),
        }

    working = df.copy()
    working["sma20"] = working["close"].rolling(20).mean()
    working["sma50"] = working["close"].rolling(50).mean()
    working["sma200"] = working["close"].rolling(200).mean()
    working["rsi"] = _rsi(working["close"])
    ema12 = working["close"].ewm(span=12, adjust=False).mean()
    ema26 = working["close"].ewm(span=26, adjust=False).mean()
    working["macd"] = ema12 - ema26
    working["macd_signal"] = working["macd"].ewm(span=9, adjust=False).mean()

    last = working.iloc[-1]
    trend = _trend_label(last, working)
    supports, resistances = _support_resistance(working)
    structure = _price_structure(working)

    ma_text = _moving_average_text(last)
    macd_text = _macd_text(last)
    rsi_value = "نامشخص" if pd.isna(last["rsi"]) else f"{last['rsi']:.1f}"

    explanation = (
        f"ساختار قیمت: {structure}. MACD: {macd_text}. "
        f"آخرین بسته‌شدن: {last['close']:.2f}. "
        f"منبع داده: {payload.get('source', 'نامشخص')}."
    )

    return {
        "available": True,
        "trend": trend,
        "supports": supports,
        "resistances": resistances,
        "rsi": rsi_value,
        "moving_averages": ma_text,
        "macd": macd_text,
        "structure": structure,
        "explanation": explanation,
        "last_close": float(last["close"]),
        "last_candle_at": working.index[-1].to_pydatetime(),
        "row_count": len(working),
    }


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _trend_label(last: pd.Series, df: pd.DataFrame) -> str:
    close = last["close"]
    sma20 = last.get("sma20")
    sma50 = last.get("sma50")
    if pd.notna(sma20) and pd.notna(sma50):
        if close > sma20 > sma50:
            return "صعودی"
        if close < sma20 < sma50:
            return "نزولی"

    recent = df["close"].tail(20)
    change_pct = (recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0] * 100
    if change_pct > 0.8:
        return "صعودی"
    if change_pct < -0.8:
        return "نزولی"
    return "رنج"


def _support_resistance(df: pd.DataFrame) -> tuple[list[float], list[float]]:
    recent = df.tail(120).copy()
    pivot_lows = []
    pivot_highs = []
    lows = recent["low"].tolist()
    highs = recent["high"].tolist()
    for idx in range(2, len(recent) - 2):
        if lows[idx] <= min(lows[idx - 2 : idx + 3]):
            pivot_lows.append(lows[idx])
        if highs[idx] >= max(highs[idx - 2 : idx + 3]):
            pivot_highs.append(highs[idx])

    close = float(recent["close"].iloc[-1])
    supports = sorted({round(level, 2) for level in pivot_lows if level < close}, reverse=True)[:3]
    resistances = sorted({round(level, 2) for level in pivot_highs if level > close})[:3]
    return supports, resistances


def _price_structure(df: pd.DataFrame) -> str:
    recent = df.tail(30)
    first_high = recent["high"].head(10).max()
    last_high = recent["high"].tail(10).max()
    first_low = recent["low"].head(10).min()
    last_low = recent["low"].tail(10).min()
    range_now = recent["high"].tail(10).max() - recent["low"].tail(10).min()
    range_before = recent["high"].head(10).max() - recent["low"].head(10).min()

    if last_high > first_high and last_low > first_low:
        return "سقف‌ها و کف‌های بالاتر"
    if last_high < first_high and last_low < first_low:
        return "سقف‌ها و کف‌های پایین‌تر"
    if range_before and range_now < range_before * 0.7:
        return "فشردگی رنج"
    if recent["close"].iloc[-1] > first_high:
        return "شکست رو به بالا"
    if recent["close"].iloc[-1] < first_low:
        return "شکست رو به پایین"
    return "رنج یا پولبک نامشخص"


def _moving_average_text(last: pd.Series) -> str:
    parts = []
    for name, label in (("sma20", "SMA20"), ("sma50", "SMA50"), ("sma200", "SMA200")):
        value = last.get(name)
        if pd.notna(value):
            parts.append(f"{label}: {value:.2f}")
    return "، ".join(parts) if parts else "نامشخص"


def _macd_text(last: pd.Series) -> str:
    macd = last.get("macd")
    signal = last.get("macd_signal")
    if pd.isna(macd) or pd.isna(signal):
        return "نامشخص"
    if macd > signal:
        return "مثبت"
    if macd < signal:
        return "منفی"
    return "خنثی"
