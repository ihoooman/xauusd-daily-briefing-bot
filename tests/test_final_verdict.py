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


if __name__ == "__main__":
    unittest.main()
