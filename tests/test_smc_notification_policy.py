import unittest
from datetime import datetime, timezone

from scripts.smc.infra_verdict import classify_infra_evidence
from scripts.smc.notification_policy import (
    classify_exec_outcome,
    may_notify_close,
    may_notify_execution,
)
from scripts.smc.notifier import format_order_accepted_card, format_order_filled_card
from scripts.smc.types import Direction, Position


class NotificationPolicyTests(unittest.TestCase):
    def test_rejected_and_unknown_do_not_notify(self):
        self.assertFalse(may_notify_execution(success=False, status="REJECTED"))
        self.assertFalse(may_notify_execution(success=False, status="UNKNOWN"))
        self.assertFalse(may_notify_execution(success=True, status="UNKNOWN"))

    def test_ok_success_may_notify(self):
        self.assertTrue(may_notify_execution(success=True, status="OK"))
        self.assertTrue(may_notify_execution(success=True, status=None))

    def test_classify_unknown_as_uncertain(self):
        self.assertEqual(
            classify_exec_outcome(success=False, status="UNKNOWN"),
            "uncertain",
        )
        self.assertEqual(
            classify_exec_outcome(success=False, status="REJECTED"),
            "rejected",
        )
        self.assertEqual(
            classify_exec_outcome(success=True, status="OK"),
            "success",
        )

    def test_close_notify_requires_broker_evidence(self):
        self.assertFalse(may_notify_close(broker_close_success=False))
        self.assertTrue(may_notify_close(broker_close_success=True))
        self.assertTrue(
            may_notify_close(
                broker_close_success=False,
                already_flat_on_broker=True,
            )
        )

    def test_ohlc_invent_pnl_only_in_dry_run(self):
        from scripts.smc.notification_policy import (
            may_use_ohlc_invented_close_pnl,
            require_broker_cash_for_live_close,
        )

        self.assertTrue(may_use_ohlc_invented_close_pnl(dry_run=True))
        self.assertFalse(may_use_ohlc_invented_close_pnl(dry_run=False))
        self.assertTrue(require_broker_cash_for_live_close(dry_run=True, broker_pnl=None))
        self.assertFalse(require_broker_cash_for_live_close(dry_run=False, broker_pnl=None))
        self.assertTrue(require_broker_cash_for_live_close(dry_run=False, broker_pnl=-12.5))


class InfraVerdictTests(unittest.TestCase):
    def test_mac_off_mt5_is_inconclusive_not_strategy_fail(self):
        report = classify_infra_evidence(
            mt5_available=False,
            identity_ok=False,
        )
        self.assertEqual(report.verdict, "INCONCLUSIVE_INFRA")
        self.assertEqual(report.detail, "mt5_unavailable_on_host")

    def test_identity_fail_is_fail_infra(self):
        report = classify_infra_evidence(
            mt5_available=True,
            identity_ok=False,
        )
        self.assertEqual(report.verdict, "FAIL_INFRA")

    def test_soak_pass_is_pass_infra(self):
        report = classify_infra_evidence(
            mt5_available=True,
            identity_ok=True,
            soak_completed=True,
            soak_pass=True,
        )
        self.assertEqual(report.verdict, "PASS_INFRA")


class AcceptedVsFillCardTests(unittest.TestCase):
    def test_accepted_card_is_not_fill_card(self):
        accepted = format_order_accepted_card(
            direction=Direction.BUY,
            limit_price=2014.0,
            sl_price=2008.0,
            tp_price=2025.0,
            lot_size=0.01,
            order_id="ABC",
            ticket=99,
        )
        filled = format_order_filled_card(
            Position(
                direction=Direction.BUY,
                entry_price=2014.0,
                sl_price=2008.0,
                tp_price=2025.0,
                lot_size=0.01,
                open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
                initial_sl_distance=6.0,
            )
        )
        self.assertIn("ORDER ACCEPTED (PENDING)", accepted)
        self.assertIn("Not filled yet", accepted)
        self.assertIn("ORDER FILLED", filled)
        self.assertNotEqual(accepted, filled)


if __name__ == "__main__":
    unittest.main()
