import unittest
from datetime import datetime, timezone

from scripts.smc.notification_policy import classify_exec_outcome, may_notify_execution
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
