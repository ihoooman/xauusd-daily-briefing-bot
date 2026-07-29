from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from config import Settings
from data_sources.economic_calendar import EconomicCalendarProvider


FED_HTML = """
<div class="panel panel-unstyled">
  <div class="panel-body"><div class="row">
    <div class="col-xs-2"><p>2:30 p.m.</p></div>
    <div class="col-xs-7"><p>FOMC Press Conference</p></div>
    <div class="col-xs-3"><p>29</p></div>
  </div></div>
</div>
<div class="panel border panel-unstyled">
  <div class="panel-body"><div class="row">
    <div class="col-xs-2"><p>2:00 p.m.</p></div>
    <div class="col-xs-7">
      <p>FOMC Meeting</p><p>Two-day meeting, July 28 - 29</p>
    </div>
    <div class="col-xs-3"><p>29</p></div>
  </div></div>
</div>
"""


class EconomicCalendarTests(unittest.TestCase):
    def test_official_fomc_times_are_converted_to_tehran(self) -> None:
        provider = EconomicCalendarProvider(Settings(timezone="Asia/Tehran"))
        response = Mock()
        response.text = FED_HTML
        response.raise_for_status.return_value = None
        provider.session.get = Mock(return_value=response)
        now = datetime(2026, 7, 29, 13, 0, tzinfo=ZoneInfo("Asia/Tehran"))

        with patch(
            "data_sources.economic_calendar.now_in_timezone",
            return_value=now,
        ):
            events = provider._fetch_federal_reserve_calendar()

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event"], "FOMC Meeting")
        self.assertEqual(events[0]["time_tehran"], "2026-07-29 21:30")
        self.assertEqual(events[1]["event"], "FOMC Press Conference")
        self.assertEqual(events[1]["time_tehran"], "2026-07-29 22:00")
        self.assertTrue(all(item["risk_category"] == "fomc" for item in events))


if __name__ == "__main__":
    unittest.main()
