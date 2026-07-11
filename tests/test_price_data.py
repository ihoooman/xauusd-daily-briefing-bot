from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
