"""Foundation stories 39–40: separate research tape from USD 500 / shared-account replay."""

from __future__ import annotations

import unittest

from scripts.smc.replay_report import (
    EXECUTABLE_DEMO_BALANCE,
    ReplayKind,
    assert_not_conflated,
    build_replay_report,
)


class ReplayReportTests(unittest.TestCase):
    def test_theoretical_and_executable_are_distinct(self):
        theoretical = build_replay_report(
            kind=ReplayKind.THEORETICAL_TAPE,
            initial_balance=100_000.0,
            trade_count=50,
            net_profit=1200.0,
            win_rate=0.6,
        )
        executable = build_replay_report(
            kind=ReplayKind.EXECUTABLE_USD500,
            initial_balance=EXECUTABLE_DEMO_BALANCE,
            trade_count=12,
            net_profit=15.0,
            win_rate=0.5,
        )
        assert_not_conflated(theoretical=theoretical, executable=executable)
        self.assertIn("theoretical_tape_not_account_performance", theoretical.notes)
        self.assertIn("usd500_executable_not_theoretical_tape", executable.notes)
        self.assertIsNotNone(executable.affordability)
        self.assertAlmostEqual(executable.affordability.risk_budget, 2.5)

    def test_executable_flags_balance_mismatch(self):
        report = build_replay_report(
            kind=ReplayKind.EXECUTABLE_USD500,
            initial_balance=10_000.0,
            trade_count=3,
            net_profit=0.0,
            win_rate=0.0,
        )
        self.assertIn("executable_balance_mismatch", report.notes)

    def test_shared_account_without_events_cannot_claim_parity(self):
        report = build_replay_report(
            kind=ReplayKind.SHARED_ACCOUNT,
            initial_balance=500.0,
            trade_count=5,
            net_profit=-10.0,
            win_rate=0.2,
            external_account_events=None,
        )
        self.assertTrue(report.shared_account_parity_claimed)
        self.assertFalse(report.shared_account_parity_ok)
        self.assertIn("missing_external_account_events_no_parity", report.notes)

    def test_shared_account_with_events_allows_parity_flag(self):
        report = build_replay_report(
            kind=ReplayKind.SHARED_ACCOUNT,
            initial_balance=500.0,
            trade_count=5,
            net_profit=-10.0,
            win_rate=0.2,
            external_account_events=[{"type": "manual_loss", "pnl": -20.0}],
        )
        self.assertTrue(report.shared_account_parity_ok)
        self.assertIn("shared_account_events_present", report.notes)

    def test_assert_not_conflated_rejects_same_kind(self):
        a = build_replay_report(
            kind=ReplayKind.THEORETICAL_TAPE,
            initial_balance=1.0,
            trade_count=0,
            net_profit=0.0,
            win_rate=0.0,
        )
        with self.assertRaises(ValueError):
            assert_not_conflated(theoretical=a, executable=a)


if __name__ == "__main__":
    unittest.main()
