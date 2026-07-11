from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from analysis.data_quality import assess_data_quality


class DataQualityTests(unittest.TestCase):
    def test_confirmed_complete_data_scores_high(self) -> None:
        now = datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        price = {"available": True, "validation": {"status": "confirmed"}}
        news = {
            "items": [
                {"source": "A", "published_sort": now},
                {"source": "B", "published_sort": now},
                {"source": "A", "published_sort": now},
            ]
        }
        technicals = {
            key: {"available": True, "last_candle_at": now}
            for key in ("1d", "4h", "1h")
        }
        result = assess_data_quality(
            now,
            price,
            news,
            {"items": [{}], "source": "Financial Modeling Prep"},
            {"items": [{}]},
            technicals,
        )
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["grade"], "بالا")

    def test_missing_data_lowers_quality(self) -> None:
        now = datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        result = assess_data_quality(
            now,
            {"available": False},
            {"items": []},
            {"items": [], "errors": ["failed"]},
            {"items": []},
            {},
        )
        self.assertLess(result["score"], 65)
        self.assertEqual(result["grade"], "پایین")


if __name__ == "__main__":
    unittest.main()
