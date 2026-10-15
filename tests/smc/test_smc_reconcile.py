import unittest

from scripts.smc.reconcile import PendingExposure, reconcile_pending_exposure


class PendingReconcileTests(unittest.TestCase):
    def test_fill_during_cancel_keeps_exposure(self):
        decision = reconcile_pending_exposure(
            PendingExposure(
                order_id="o1",
                requested_volume=0.02,
                filled_volume=0.0,
                cancel_requested=True,
                broker_position_volume=0.02,
                broker_pending_volume=0.0,
            )
        )
        self.assertEqual(decision.status, "filled_during_cancel")
        self.assertEqual(decision.filled_volume, 0.02)
        self.assertEqual(decision.residual_pending_volume, 0.0)

    def test_partial_fill_keeps_residual_visible(self):
        decision = reconcile_pending_exposure(
            PendingExposure(
                order_id="o2",
                requested_volume=0.04,
                filled_volume=0.02,
                broker_pending_volume=0.02,
                broker_position_volume=0.02,
            )
        )
        self.assertEqual(decision.status, "partial_fill_with_residual")
        self.assertEqual(decision.residual_pending_volume, 0.02)

    def test_missing_broker_evidence_is_uncertain(self):
        decision = reconcile_pending_exposure(
            PendingExposure(order_id="o3", requested_volume=0.01, cancel_requested=True)
        )
        self.assertEqual(decision.status, "uncertain")


if __name__ == "__main__":
    unittest.main()
