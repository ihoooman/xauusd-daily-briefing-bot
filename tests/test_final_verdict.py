from __future__ import annotations

import unittest

from analysis.final_verdict import build_final_verdict


class FinalVerdictTests(unittest.TestCase):
    def test_low_quality_caps_confidence_and_filters_levels(self) -> None:
        technicals = {
            "1d": {"trend": "صعودی", "supports": [99, 101], "resistances": [102]},
            "4h": {"trend": "صعودی", "supports": [98], "resistances": [103]},
            "1h": {"trend": "صعودی", "supports": [97], "resistances": [104]},
        }
        result = build_final_verdict(
            {"bias": "صعودی"},
            [],
            [],
            technicals,
            price={"available": True, "price": 100},
            data_quality={"score": 50},
        )
        self.assertEqual(result["decision"], "LONG / خرید")
        self.assertEqual(result["confidence"], "پایین")
        self.assertEqual(result["trade_status"], "INACTIVE / غیرفعال")
        self.assertNotIn(101, result["supports"])

    def test_nearby_levels_are_clustered(self) -> None:
        technicals = {
            "1d": {"trend": "نزولی", "supports": [99.0], "resistances": [101.0]},
            "4h": {"trend": "نزولی", "supports": [99.05], "resistances": [101.05]},
            "1h": {"trend": "نزولی", "supports": [98.0], "resistances": [102.0]},
        }
        result = build_final_verdict(
            {"bias": "خنثی"},
            [],
            [],
            technicals,
            price={"available": True, "price": 100},
            data_quality={"score": 90},
        )
        self.assertEqual(result["supports"], [99.03, 98.0])
        self.assertEqual(result["resistances"], [101.03, 102.0])

    def test_derived_level_outside_session_is_not_claimed_as_observed(self) -> None:
        technicals = {
            "1d": {
                "trend": "نزولی",
                "supports": [4050.0],
                "resistances": [4116.0],
            },
            "4h": {
                "trend": "نزولی",
                "supports": [4052.0],
                "resistances": [4109.0],
            },
            "1h": {
                "available": True,
                "trend": "نزولی",
                "supports": [4050.0],
                "resistances": [4086.0],
                "last_close": 4066.86,
                "last_candle_closed": True,
                "last_candle_at": "2026-07-27T14:00:00Z",
            },
        }
        result = build_final_verdict(
            {"bias": "نزولی"},
            [],
            [],
            technicals,
            price={
                "available": True,
                "price": 4066.86,
                "session_low": 4066.50,
                "session_high": 4116.19,
                "range_boundary_status": "explicit",
            },
            data_quality={"score": 95, "usable_for_trade": True},
        )
        self.assertEqual(result["decision"], "SHORT / فروش")
        self.assertFalse(result["trigger_met"])
        self.assertEqual(result["trade_status"], "INACTIVE / غیرفعال")
        support_audit = [
            item for item in result["level_audit"] if item["kind"] == "حمایت"
        ]
        self.assertTrue(support_audit)
        self.assertTrue(
            all(item["inside_observed_session_range"] is False for item in support_audit)
        )

    def test_trade_activates_only_on_confirmed_hourly_close(self) -> None:
        candle = {
            "open_at": "2026-07-27T13:00:00+00:00",
            "close_at": "2026-07-27T14:00:00+00:00",
            "open": 100.0,
            "high": 103.0,
            "low": 99.5,
            "close": 102.5,
            "source": "test-source",
        }
        technicals = {
            "1d": {"trend": "صعودی", "supports": [98.0], "resistances": [102.0]},
            "4h": {"trend": "صعودی", "supports": [99.0], "resistances": [102.0]},
            "1h": {
                "available": True,
                "trend": "صعودی",
                "supports": [99.5],
                "resistances": [102.0],
                "last_close": 102.5,
                "last_candle_closed": True,
                "last_candle_close_at": candle["close_at"],
                "last_closed_candle": candle,
            },
        }
        result = build_final_verdict(
            {"bias": "صعودی"},
            [],
            [],
            technicals,
            price={"available": True, "price": 100.0},
            data_quality={"score": 95, "usable_for_trade": True},
        )

        self.assertEqual(result["bias"], "LONG / خرید")
        self.assertTrue(result["trigger_met"])
        self.assertEqual(result["trade_status"], "ACTIVE / فعال")
        self.assertIn("ورود مطابق سوگیری", result["action_now"])
        self.assertIn("2026-07-27T14:00:00+00:00", result["trigger_evidence"])
        self.assertIn("OHLC=100.00/103.00/99.50/102.50", result["trigger_evidence"])

    def test_confirmed_close_stays_inactive_when_quality_has_conflict(self) -> None:
        technicals = {
            "1d": {"trend": "صعودی", "supports": [98.0], "resistances": [102.0]},
            "4h": {"trend": "نزولی", "supports": [99.0], "resistances": [102.0]},
            "1h": {
                "available": True,
                "trend": "صعودی",
                "supports": [99.5],
                "resistances": [102.0],
                "last_close": 102.5,
                "last_candle_closed": True,
                "last_candle_close_at": "2026-07-27T14:00:00+00:00",
            },
        }
        result = build_final_verdict(
            {"bias": "صعودی"},
            [],
            [],
            technicals,
            price={"available": True, "price": 100.0},
            data_quality={
                "score": 49,
                "usable_for_trade": False,
                "confidence_cap": "پایین",
                "blockers": ["تناقض روند بین تایم‌فریم‌های اصلی وجود دارد."],
            },
        )

        self.assertTrue(result["trigger_met"])
        self.assertEqual(result["trade_status"], "INACTIVE / غیرفعال")
        self.assertEqual(result["action_now"], "عدم ورود")
        self.assertEqual(result["confidence"], "پایین")

    def test_fomc_no_chase_overrides_confirmed_trigger(self) -> None:
        technicals = {
            "1d": {"trend": "صعودی", "supports": [98.0], "resistances": [102.0]},
            "4h": {"trend": "صعودی", "supports": [99.0], "resistances": [102.0]},
            "1h": {
                "available": True,
                "trend": "صعودی",
                "supports": [99.5],
                "resistances": [102.0],
                "last_close": 103.0,
                "last_candle_closed": True,
            },
        }
        restriction = (
            "عدم ورود و ممنوعیت تعقیب قیمت تا حداقل 2026-07-29 23:30 تهران."
        )

        result = build_final_verdict(
            {"bias": "صعودی"},
            [],
            [],
            technicals,
            price={"available": True, "price": 100.0},
            data_quality={
                "score": 49,
                "usable_for_trade": False,
                "confidence_cap": "پایین",
                "blockers": ["ریسک فعال FOMC اجازه ورود نمی‌دهد."],
                "no_chase": True,
                "entry_restriction": restriction,
            },
        )

        self.assertTrue(result["trigger_met"])
        self.assertEqual(result["trade_status"], "INACTIVE / غیرفعال")
        self.assertEqual(result["action_now"], restriction)


if __name__ == "__main__":
    unittest.main()
