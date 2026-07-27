from __future__ import annotations

import unittest
from datetime import datetime, timezone

import pandas as pd

from analysis.technical_analysis import analyze_timeframe
from data_sources.technical_data import TechnicalDataProvider


class ConfirmedCandleTests(unittest.TestCase):
    def test_open_hourly_candle_is_removed(self) -> None:
        index = pd.to_datetime(
            ["2026-07-27T13:00:00Z", "2026-07-27T14:00:00Z"],
            utc=True,
        )
        data = pd.DataFrame(
            {
                "open": [4100.0, 4090.0],
                "high": [4110.0, 4095.0],
                "low": [4085.0, 4066.5],
                "close": [4090.0, 4068.0],
                "volume": [0.0, 0.0],
            },
            index=index,
        )

        result = TechnicalDataProvider._drop_incomplete_bars(
            data,
            "1h",
            now_utc=datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result.index[-1], index[0])
        self.assertTrue(result.attrs["confirmed_candles_only"])

    def test_partial_four_hour_bucket_is_removed(self) -> None:
        index = pd.date_range(
            "2026-07-27T08:00:00Z",
            periods=7,
            freq="1h",
        )
        data = pd.DataFrame(
            {
                "open": range(7),
                "high": range(1, 8),
                "low": range(7),
                "close": range(1, 8),
                "volume": [0.0] * 7,
            },
            index=index,
        )

        result = TechnicalDataProvider._resample_4h(data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.index[0], pd.Timestamp("2026-07-27T08:00:00Z"))

    def test_analysis_records_exact_close_time_ohlc_and_level_origin(self) -> None:
        index = pd.date_range("2026-07-25T00:00:00Z", periods=60, freq="1h")
        closes = [100 + abs((idx % 10) - 5) for idx in range(60)]
        data = pd.DataFrame(
            {
                "open": [value - 0.25 for value in closes],
                "high": [value + 1.0 for value in closes],
                "low": [value - 1.0 for value in closes],
                "close": closes,
                "volume": [0.0] * 60,
            },
            index=index,
        )
        result = analyze_timeframe(
            data,
            {
                "available": True,
                "timeframe": "1h",
                "confirmed_candles_only": True,
                "source": "test-source",
                "source_timezone": "UTC",
            },
        )

        candle = result["last_closed_candle"]
        self.assertEqual(candle["open_at"], index[-1].to_pydatetime())
        self.assertEqual(
            candle["close_at"],
            (index[-1] + pd.Timedelta(hours=1)).to_pydatetime(),
        )
        self.assertEqual(candle["close"], float(closes[-1]))
        self.assertTrue(result["last_candle_closed"])
        self.assertTrue(result["support_details"])
        self.assertEqual(result["support_details"][0]["origin"], "historical_pivot")
        self.assertIn("pivot_candle_close_at", result["support_details"][0])


if __name__ == "__main__":
    unittest.main()
