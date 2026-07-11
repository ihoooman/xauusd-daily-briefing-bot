from __future__ import annotations

import unittest

from data_sources.polymarket_data import PolymarketProvider


class PolymarketSentimentTests(unittest.TestCase):
    def test_low_rate_cut_probability_is_not_bullish(self) -> None:
        self.assertEqual(
            PolymarketProvider._sentiment_for_gold("Fed rate cut this year", 0.20),
            "نزولی",
        )

    def test_high_rate_cut_probability_is_bullish(self) -> None:
        self.assertEqual(
            PolymarketProvider._sentiment_for_gold("Fed rate cut this year", 0.70),
            "صعودی",
        )

    def test_uncertain_probability_is_neutral(self) -> None:
        self.assertEqual(
            PolymarketProvider._sentiment_for_gold("Fed rate cut this year", 0.50),
            "خنثی",
        )


if __name__ == "__main__":
    unittest.main()
