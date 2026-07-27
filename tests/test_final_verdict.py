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


if __name__ == "__main__":
    unittest.main()
