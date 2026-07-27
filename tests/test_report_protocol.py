from __future__ import annotations

import unittest
from datetime import datetime, timezone

from main import render_report


class ReportProtocolTests(unittest.TestCase):
    def test_observed_evidence_precedes_derived_levels(self) -> None:
        candle_1h = {
            "open_at": "2026-07-27T13:00:00+00:00",
            "close_at": "2026-07-27T14:00:00+00:00",
            "open": 4090.0,
            "high": 4116.19,
            "low": 4066.50,
            "close": 4068.0,
            "source": "test-source",
        }
        candle_4h = {
            "open_at": "2026-07-27T08:00:00+00:00",
            "close_at": "2026-07-27T12:00:00+00:00",
            "open": 4100.0,
            "high": 4116.19,
            "low": 4070.0,
            "close": 4090.0,
            "source": "test-source",
        }
        technicals = {
            "1d": {"available": False},
            "4h": {
                "available": True,
                "trend": "نزولی",
                "last_candle_closed": True,
                "last_closed_candle": candle_4h,
                "support_details": [],
                "resistance_details": [],
            },
            "1h": {
                "available": True,
                "trend": "نزولی",
                "last_candle_closed": True,
                "last_closed_candle": candle_1h,
                "support_details": [
                    {
                        "value": 4050.0,
                        "timeframe": "1h",
                        "observed_field": "low",
                        "pivot_candle_close_at": "2026-07-25T10:00:00+00:00",
                    }
                ],
                "resistance_details": [],
            },
        }
        verdict = {
            "bias": "SHORT / فروش",
            "decision": "SHORT / فروش",
            "trade_status": "INACTIVE / غیرفعال",
            "action_now": "عدم ورود",
            "trigger_met": False,
            "trigger_evidence": "Close تأییدی شرط را محقق نکرده است.",
            "confidence": "پایین",
            "main_reason": "تناقض داده.",
            "bullish_scenario": "نامشخص",
            "bearish_scenario": "نامشخص",
            "risk_management": "عدم ورود",
            "invalidation": "نامشخص",
            "supports": [4050.0],
            "resistances": [],
            "level_audit": [
                {
                    "level": 4050.0,
                    "kind": "حمایت",
                    "contributors": [
                        {
                            "timeframe": "1h",
                            "pivot_candle_close_at": "2026-07-25T10:00:00+00:00",
                        }
                    ],
                    "inside_observed_session_range": False,
                }
            ],
        }
        report = render_report(
            report_time=datetime(2026, 7, 27, 18, 0, tzinfo=timezone.utc),
            price={
                "available": True,
                "price": 4068.0,
                "source": "test-source",
                "fetched_at": "2026-07-27T14:30:00+00:00",
                "session_open": 4100.0,
                "session_high": 4116.19,
                "session_low": 4066.50,
                "range_source": "test-source",
                "range_timezone": "UTC",
            },
            news_payload={"items": [], "source": "test"},
            calendar_payload={"items": []},
            prediction_payload={"items": []},
            technicals=technicals,
            verdict=verdict,
            data_quality={
                "score": 49,
                "grade": "پایین",
                "summary": "تناقض داده.",
            },
        )

        self.assertLess(
            report.index("دامنه مشاهده‌شده جلسه"),
            report.index("آخرین کندل کاملاً بسته‌شده ۱H"),
        )
        self.assertLess(
            report.index("آخرین کندل کاملاً بسته‌شده ۴H"),
            report.index("حمایت‌های مشتق‌شده"),
        )
        self.assertIn("* سوگیری کلی (Bias): SHORT / فروش", report)
        self.assertIn("* وضعیت معامله: INACTIVE / غیرفعال", report)
        self.assertIn("* اقدام فعلی (Action now): عدم ورود", report)
        self.assertIn("4050.00", report)
        self.assertIn("خارج از دامنه مشاهده‌شده و لمس آن تأیید نشده", report)


if __name__ == "__main__":
    unittest.main()
