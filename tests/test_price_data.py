from __future__ import annotations

import unittest
from datetime import datetime, timezone

from data_sources.price_data import PriceDataProvider


class PriceValidationTests(unittest.TestCase):
    def test_close_spot_quotes_are_confirmed(self) -> None:
        result = PriceDataProvider._compare_spot_quotes(
            {"price": 4100.0},
            {"price": 4102.0, "source": "secondary"},
        )
        self.assertEqual(result["status"], "confirmed")

    def test_divergent_spot_quotes_are_rejected(self) -> None:
        result = PriceDataProvider._compare_spot_quotes(
            {"price": 4100.0},
            {"price": 4120.0, "source": "secondary"},
        )
        self.assertEqual(result["status"], "mismatch")

    def test_utc_day_range_uses_only_fully_closed_minute_bars(self) -> None:
        values = [
            {
                "datetime": "2026-07-28 00:00:00",
                "open": "4100",
                "high": "4102",
                "low": "4099",
                "close": "4101",
            },
            {
                "datetime": "2026-07-28 00:01:00",
                "open": "4101",
                "high": "4104",
                "low": "4100",
                "close": "4103",
            },
            {
                "datetime": "2026-07-28 00:02:00",
                "open": "4103",
                "high": "4200",
                "low": "4000",
                "close": "4102",
            },
        ]
        result = PriceDataProvider._aggregate_closed_utc_day_range(
            values,
            now_utc=datetime(2026, 7, 28, 0, 2, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(result["session_open"], 4100.0)
        self.assertEqual(result["session_high"], 4104.0)
        self.assertEqual(result["session_low"], 4099.0)
        self.assertEqual(result["range_bar_count"], 2)
        self.assertEqual(
            result["range_end"],
            datetime(2026, 7, 28, 0, 2, tzinfo=timezone.utc),
        )

    def test_inconsistent_quote_range_is_marked_as_mismatch(self) -> None:
        result = PriceDataProvider._compare_range_with_quote_fields(
            {
                "session_open": 4100.0,
                "session_high": 4110.0,
                "session_low": 4090.0,
            },
            quote_open=4050.0,
            quote_high=4110.0,
            quote_low=4020.0,
        )

        self.assertEqual(result["status"], "mismatch")


if __name__ == "__main__":
    unittest.main()
