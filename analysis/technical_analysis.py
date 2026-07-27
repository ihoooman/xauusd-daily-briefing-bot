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
            "support_details": [],
            "resistance_details": [],
            "moving_average_details": [],
            "last_closed_candle": None,
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

    timeframe = str(payload.get("timeframe") or "نامشخص")
    last = working.iloc[-1]
    last_open_at = working.index[-1].to_pydatetime()
    last_close_at = _candle_close_at(last_open_at, timeframe)
    trend = _trend_label(last, working)
    supports, resistances, support_details, resistance_details = _support_resistance(
        working, timeframe
    )
    structure = _price_structure(working)
    consistency_warning = _trend_structure_warning(trend, structure)

    ma_text = _moving_average_text(last)
    ma_details = _moving_average_details(last, timeframe, last_close_at)
    macd_text = _macd_text(last)
    rsi_value = "نامشخص" if pd.isna(last["rsi"]) else f"{last['rsi']:.1f}"
    last_closed_candle = {
        "origin": "confirmed_candle_ohlc",
        "origin_fa": "OHLC کندل کاملاً بسته‌شده",
        "timeframe": timeframe,
        "open_at": last_open_at,
        "close_at": last_close_at,
        "open": float(last["open"]),
        "high": float(last["high"]),
        "low": float(last["low"]),
        "close": float(last["close"]),
        "source": payload.get("source", "نامشخص"),
        "source_timezone": payload.get("source_timezone", "UTC"),
    }

    explanation = (
        f"ساختار قیمت: {structure}. MACD: {macd_text}. "
        f"آخرین بسته‌شدن تأییدشده: {last['close']:.2f} در {last_close_at}. "
        "حمایت و مقاومت‌ها از پیوت کندل‌های بسته‌شده استخراج شده‌اند و "
        "به‌معنای لمس‌شدن آن‌ها در جلسه جاری نیستند. "
        f"منبع داده: {payload.get('source', 'نامشخص')}."
    )
    if consistency_warning:
        explanation += f" هشدار سازگاری: {consistency_warning}"

    return {
        "available": True,
        "trend": trend,
        "supports": supports,
        "resistances": resistances,
        "support_details": support_details,
        "resistance_details": resistance_details,
        "rsi": rsi_value,
        "moving_averages": ma_text,
        "moving_average_details": ma_details,
        "macd": macd_text,
        "structure": structure,
        "explanation": explanation,
        "last_close": float(last["close"]),
        "last_candle_at": last_close_at,
        "last_candle_open_at": last_open_at,
        "last_candle_close_at": last_close_at,
        "last_closed_candle": last_closed_candle,
        "last_candle_closed": bool(payload.get("confirmed_candles_only")),
        "source_timezone": payload.get("source_timezone", "نامشخص"),
        "level_origin": "پیوت تاییدشده از کندل‌های بسته‌شده تاریخی",
        "consistency_warning": consistency_warning,
        "analysis_window_low": float(working["low"].tail(120).min()),
        "analysis_window_high": float(working["high"].tail(120).max()),
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


def _support_resistance(
    df: pd.DataFrame,
    timeframe: str,
) -> tuple[list[float], list[float], list[dict[str, Any]], list[dict[str, Any]]]:
    recent = df.tail(120).copy()
    pivot_lows: list[tuple[float, Any]] = []
    pivot_highs: list[tuple[float, Any]] = []
    lows = recent["low"].tolist()
    highs = recent["high"].tolist()
    for idx in range(2, len(recent) - 2):
        if lows[idx] <= min(lows[idx - 2 : idx + 3]):
            pivot_lows.append((float(lows[idx]), recent.index[idx]))
        if highs[idx] >= max(highs[idx - 2 : idx + 3]):
            pivot_highs.append((float(highs[idx]), recent.index[idx]))

    close = float(recent["close"].iloc[-1])
    supports = sorted(
        {round(level, 2) for level, _ in pivot_lows if level < close}, reverse=True
    )[:3]
    resistances = sorted(
        {round(level, 2) for level, _ in pivot_highs if level > close}
    )[:3]
    support_details = _pivot_level_details(
        supports, pivot_lows, timeframe, "حمایت", "low"
    )
    resistance_details = _pivot_level_details(
        resistances, pivot_highs, timeframe, "مقاومت", "high"
    )
    return supports, resistances, support_details, resistance_details


def _pivot_level_details(
    selected: list[float],
    pivots: list[tuple[float, Any]],
    timeframe: str,
    kind: str,
    observed_field: str,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for level in selected:
        matches = [
            (value, timestamp)
            for value, timestamp in pivots
            if round(value, 2) == level
        ]
        if not matches:
            continue
        value, timestamp = matches[-1]
        open_at = timestamp.to_pydatetime()
        close_at = _candle_close_at(open_at, timeframe)
        details.append(
            {
                "value": round(float(value), 2),
                "kind": kind,
                "origin": "historical_pivot",
                "origin_fa": "پیوت تاریخی از OHLC کندل بسته‌شده",
                "timeframe": timeframe,
                "observed_field": observed_field,
                "pivot_candle_open_at": open_at,
                "pivot_candle_close_at": close_at,
            }
        )
    return details


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


def _moving_average_details(
    last: pd.Series,
    timeframe: str,
    as_of: Any,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for name, label, period in (
        ("sma20", "SMA20", 20),
        ("sma50", "SMA50", 50),
        ("sma200", "SMA200", 200),
    ):
        value = last.get(name)
        if pd.notna(value):
            details.append(
                {
                    "name": label,
                    "value": round(float(value), 2),
                    "period": period,
                    "timeframe": timeframe,
                    "origin": "moving_average",
                    "origin_fa": "میانگین متحرک از Close کندل‌های بسته‌شده",
                    "as_of": as_of,
                }
            )
    return details


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


def _trend_structure_warning(trend: str, structure: str) -> str | None:
    if trend == "صعودی" and structure == "سقف‌ها و کف‌های پایین‌تر":
        return "برچسب روند صعودی با ساختار سقف‌ها و کف‌های پایین‌تر متناقض است."
    if trend == "نزولی" and structure == "سقف‌ها و کف‌های بالاتر":
        return "برچسب روند نزولی با ساختار سقف‌ها و کف‌های بالاتر متناقض است."
    return None


def _candle_close_at(open_at: Any, timeframe: str) -> Any:
    durations = {
        "1h": pd.Timedelta(hours=1),
        "4h": pd.Timedelta(hours=4),
        "1d": pd.Timedelta(days=1),
    }
    duration = durations.get(timeframe)
    if duration is None:
        return open_at
    return (pd.Timestamp(open_at) + duration).to_pydatetime()
