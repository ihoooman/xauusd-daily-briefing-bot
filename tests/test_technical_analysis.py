from __future__ import annotations

import unittest

import pandas as pd

from analysis.technical_analysis import analyze_timeframe


class TechnicalEvidenceLedgerTests(unittest.TestCase):
    def test_levels_and_closed_candle_keep_provenance(self) -> None:
        index = pd.date_range(
            "2026-07-24T00:00:00Z",
            periods=60,
            freq="1h",
        )
        close = pd.Series(
            [4060.0 + (idx % 8) * 2.0 for idx in range(60)],
            index=index,
        )
        data = pd.DataFrame(
            {
                "open": close - 1.0,
                "high": close + 3.0,
                "low": close - 3.0,
                "close": close,
                "volume": [0.0] * 60,
            },
            index=index,
        )

        result = analyze_timeframe(
            data,
            {
                "available": True,
                "source": "test",
                "timeframe": "1h",
                "confirmed_candles_only": True,
                "source_timezone": "UTC",
            },
        )

        self.assertEqual(
            result["last_closed_candle"]["origin"],
            "confirmed_candle_ohlc",
        )
        self.assertEqual(
            result["moving_average_details"][0]["origin"],
            "moving_average",
        )
        for level in result["support_details"] + result["resistance_details"]:
            self.assertEqual(level["origin"], "historical_pivot")


if __name__ == "__main__":
    unittest.main()
