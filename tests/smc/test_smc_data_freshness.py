"""Foundation story 32: unknown/stale market/account/news blocks new risk."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from scripts.smc.data_freshness import (
    account_data_allows_new_risk,
    evaluate_new_risk_admission,
    market_data_allows_new_risk,
)


class DataFreshnessAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc)

    def test_missing_bar_blocks(self):
        ok, reason = market_data_allows_new_risk(last_bar_time=None, now=self.now)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_market_bar")

    def test_stale_bar_blocks(self):
        old = self.now - timedelta(minutes=20)
        ok, reason = market_data_allows_new_risk(last_bar_time=old, now=self.now)
        self.assertFalse(ok)
        self.assertIn("stale_market_bar_age_s", reason)

    def test_fresh_bar_allows(self):
        fresh = self.now - timedelta(minutes=2)
        ok, reason = market_data_allows_new_risk(last_bar_time=fresh, now=self.now)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_account_incomplete_blocks(self):
        ok, reason = account_data_allows_new_risk(history_ready=False, equity_known=True)
        self.assertFalse(ok)
        self.assertEqual(reason, "account_history_not_ready")
        ok2, reason2 = account_data_allows_new_risk(history_ready=True, equity_known=False)
        self.assertFalse(ok2)
        self.assertEqual(reason2, "account_equity_unknown")

    def test_combined_gate_orders_failures(self):
        report = evaluate_new_risk_admission(
            last_bar_time=None,
            now=self.now,
            history_ready=False,
            equity_known=False,
            news_allowed=False,
            news_reason="unknown_or_stale_news_schedule",
        )
        self.assertFalse(report.allowed)
        self.assertEqual(report.reason, "missing_market_bar")

        report2 = evaluate_new_risk_admission(
            last_bar_time=self.now - timedelta(minutes=1),
            now=self.now,
            history_ready=True,
            equity_known=True,
            news_allowed=False,
            news_reason="unknown_or_stale_news_schedule",
        )
        self.assertFalse(report2.allowed)
        self.assertEqual(report2.reason, "unknown_or_stale_news_schedule")

        report3 = evaluate_new_risk_admission(
            last_bar_time=self.now - timedelta(minutes=1),
            now=self.now,
            history_ready=True,
            equity_known=True,
            news_allowed=True,
        )
        self.assertTrue(report3.allowed)


if __name__ == "__main__":
    unittest.main()
