import unittest
from datetime import datetime, timezone, timedelta
from scripts.smc.types import Direction, Position, OrderIntentType
from scripts.smc.news import NewsEvent, NewsManager


class TestSMCNewsManager(unittest.TestCase):
    def setUp(self):
        self.manager = NewsManager()
        self.nfp_time = datetime(2026, 3, 6, 13, 30, tzinfo=timezone.utc)
        self.events = [
            NewsEvent(
                time=self.nfp_time,
                currency="USD",
                impact="HIGH",
                name="Non-Farm Payrolls"
            )
        ]

    def test_news_blackout_window(self):
        # 10 minutes before NFP -> Blackout active!
        t_before = self.nfp_time - timedelta(minutes=10)
        is_blocked, name = self.manager.is_in_blackout(t_before, self.events, window_mins=30)
        self.assertTrue(is_blocked)
        self.assertEqual(name, "Non-Farm Payrolls")

        # 20 minutes after NFP -> Blackout active!
        t_after = self.nfp_time + timedelta(minutes=20)
        is_blocked, name = self.manager.is_in_blackout(t_after, self.events, window_mins=30)
        self.assertTrue(is_blocked)

        # 45 minutes before NFP -> Outside blackout window
        t_safe = self.nfp_time - timedelta(minutes=45)
        is_blocked, _ = self.manager.is_in_blackout(t_safe, self.events, window_mins=30)
        self.assertFalse(is_blocked)

    def test_foundation_blocks_unknown_news_and_blackout_without_forcing_exit(self):
        allowed, reason = self.manager.new_risk_allowed(
            self.nfp_time, None, schedule_known=False,
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "unknown_or_stale_news_schedule")

        blocked, reason = self.manager.new_risk_allowed(
            self.nfp_time - timedelta(minutes=10), self.events, schedule_known=True,
        )
        self.assertFalse(blocked)
        self.assertIn("news_blackout", reason)

        ok, reason = self.manager.new_risk_allowed(
            self.nfp_time - timedelta(minutes=45), self.events, schedule_known=True,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_pre_news_position_handling_lock_be(self):
        # Position open, currently at +1.2R profit, 14 min before NFP
        # Must return MOVE_SL_TO_BE
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0, # initial_sl = 5.0
            tp_price=2010.0,
            lot_size=0.10,
            open_time=self.nfp_time - timedelta(hours=1),
            initial_sl_distance=5.0
        )
        current_time = self.nfp_time - timedelta(minutes=14)
        current_price = 2006.0 # +6.0 profit / 5.0 initial_sl = +1.2R
        
        action = self.manager.evaluate_pre_news_position(
            current_time=current_time,
            events=self.events,
            position=pos,
            current_price=current_price,
            pre_window_mins=15
        )
        self.assertEqual(action, OrderIntentType.MOVE_SL_TO_BE)

    def test_pre_news_position_handling_close_market(self):
        # Position open, currently at +0.4R profit (< 1.0R), 10 min before NFP
        # Must return CLOSE_MARKET
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            lot_size=0.10,
            open_time=self.nfp_time - timedelta(hours=1),
            initial_sl_distance=5.0
        )
        current_time = self.nfp_time - timedelta(minutes=10)
        current_price = 2002.0 # +0.4R
        
        action = self.manager.evaluate_pre_news_position(
            current_time=current_time,
            events=self.events,
            position=pos,
            current_price=current_price,
            pre_window_mins=15
        )
        self.assertEqual(action, OrderIntentType.CLOSE_MARKET)


    def test_parse_forexfactory_json(self):
        # Sample raw JSON from ForexFactory
        sample_json = [
            {
                "title": "Non-Farm Employment Change",
                "country": "USD",
                "date": "2026-03-06T08:30:00-05:00", # 08:30 EST = 13:30 UTC
                "impact": "High",
                "forecast": "180K",
                "previous": "150K"
            },
            {
                "title": "EUR German Prelim CPI m/m",
                "country": "EUR",
                "date": "2026-03-06T08:00:00+01:00",
                "impact": "High",
                "forecast": "0.4%",
                "previous": "0.2%"
            }
        ]
        events = self.manager.parse_calendar_items(sample_json)
        self.assertEqual(len(events), 1) # Only USD High impact
        self.assertEqual(events[0].name, "Non-Farm Employment Change")
        self.assertEqual(events[0].currency, "USD")
        self.assertEqual(events[0].impact, "HIGH")
        # Assert UTC hour is 13:30: 08:30 - (-5) = 13:30 UTC
        self.assertEqual(events[0].time.hour, 13)
        self.assertEqual(events[0].time.minute, 30)
        self.assertEqual(events[0].time.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()

