from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from analysis.data_quality import assess_data_quality


class DataQualityTests(unittest.TestCase):
    @staticmethod
    def _confirmed_price(now: datetime) -> dict:
        return {
            "available": True,
            "validation": {"status": "confirmed"},
            "session_open": 4100.0,
            "session_high": 4110.0,
            "session_low": 4090.0,
            "range_start": now.replace(hour=3, minute=30),
            "range_end": now,
            "range_boundary_status": "explicit",
            "range_comparison": {"status": "consistent"},
            "range_used_for_trade_activation": False,
        }

    def test_confirmed_complete_data_scores_high(self) -> None:
        now = datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        price = self._confirmed_price(now)
        news = {
            "items": [
                {"source": "A", "published_sort": now},
                {"source": "B", "published_sort": now},
                {"source": "A", "published_sort": now},
            ]
        }
        technicals = {
            key: {
                "available": True,
                "last_candle_at": now,
                "last_candle_closed": True,
                "consistency_warning": None,
            }
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
        self.assertTrue(result["usable_for_trade"])

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
        self.assertFalse(result["usable_for_trade"])

    def test_unconfirmed_candle_blocks_trading(self) -> None:
        now = datetime(2026, 7, 27, 18, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        technicals = {
            key: {
                "available": True,
                "last_candle_at": now,
                "last_candle_closed": key != "1h",
            }
            for key in ("1d", "4h", "1h")
        }
        result = assess_data_quality(
            now,
            self._confirmed_price(now),
            {"items": []},
            {"items": []},
            {"items": []},
            technicals,
        )
        self.assertFalse(result["usable_for_trade"])
        self.assertLessEqual(result["score"], 49)

    def test_timeframe_conflict_blocks_trade_and_caps_confidence(self) -> None:
        now = datetime(2026, 7, 27, 18, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        technicals = {
            "1d": {
                "available": True,
                "last_candle_at": now,
                "last_candle_closed": True,
                "trend": "صعودی",
            },
            "4h": {
                "available": True,
                "last_candle_at": now,
                "last_candle_closed": True,
                "trend": "نزولی",
            },
            "1h": {
                "available": True,
                "last_candle_at": now,
                "last_candle_closed": True,
                "trend": "نزولی",
            },
        }
        result = assess_data_quality(
            now,
            self._confirmed_price(now),
            {"items": []},
            {"items": []},
            {"items": []},
            technicals,
        )

        self.assertFalse(result["usable_for_trade"])
        self.assertEqual(result["confidence_cap"], "پایین")
        self.assertTrue(
            any("تناقض روند بین تایم‌فریم" in item for item in result["blockers"])
        )

    def test_session_range_mismatch_blocks_trade_activation(self) -> None:
        now = datetime(2026, 7, 28, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        price = self._confirmed_price(now)
        price["range_comparison"] = {"status": "mismatch"}
        technicals = {
            key: {
                "available": True,
                "last_candle_at": now,
                "last_candle_closed": True,
                "trend": "نزولی",
            }
            for key in ("1d", "4h", "1h")
        }

        result = assess_data_quality(
            now,
            price,
            {"items": []},
            {"items": []},
            {"items": []},
            technicals,
        )

        self.assertFalse(result["usable_for_trade"])
        self.assertTrue(
            any("ناسازگاری دامنه جلسه" in item for item in result["blockers"])
        )


if __name__ == "__main__":
    unittest.main()
