import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock, patch

from scripts.smc.mt5_adapter import SMCExecutionAdapter


class TestSetupInbox(unittest.TestCase):
    def test_claim_persists_across_restart_and_blocks_conflicting_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "trades.db")
            first = SMCExecutionAdapter(dry_run=True, db_path=db_path)
            payload = {"order_id": "A", "limit": 4050.0, "sl": 4045.0}
            try:
                receipt = first.claim_setup(payload)
                self.assertEqual(receipt["status"], "claimed")
            finally:
                first.close()

            second = SMCExecutionAdapter(dry_run=True, db_path=db_path)
            try:
                duplicate = second.claim_setup(payload)
                self.assertEqual(duplicate["status"], "duplicate")
                self.assertEqual(duplicate["receipt_id"], receipt["receipt_id"])
                changed = second.claim_setup({**payload, "sl": 4044.0})
                self.assertEqual(changed["status"], "conflict")
                busy = second.claim_setup({**payload, "order_id": "B"})
                self.assertEqual(busy["status"], "busy")
            finally:
                second.close()

    def test_two_workers_cannot_claim_different_setups_at_once(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "trades.db")
            adapters = [SMCExecutionAdapter(dry_run=True, db_path=db_path) for _ in range(2)]
            barrier = Barrier(2)

            def claim(index):
                barrier.wait()
                return adapters[index].claim_setup({"order_id": str(index)})["status"]

            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(claim, range(2)))
                self.assertCountEqual(outcomes, ["claimed", "busy"])
            finally:
                for adapter in adapters:
                    adapter.close()

    def test_live_mode_rejects_unwritable_persistent_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            parent_file = Path(directory) / "not-a-directory"
            parent_file.write_text("occupied")
            broker = Mock()
            broker.initialize.return_value = True
            with patch("scripts.smc.mt5_adapter.runtime.mt5", broker):
                with self.assertRaises(OSError):
                    SMCExecutionAdapter(
                        dry_run=False,
                        db_path=str(parent_file / "trades.db"),
                    )

    def test_live_mode_rejects_memory_only_journal(self):
        broker = Mock()
        broker.initialize.return_value = True
        with patch("scripts.smc.mt5_adapter.runtime.mt5", broker):
            with self.assertRaises(OSError):
                SMCExecutionAdapter(dry_run=False, db_path=":memory:")

    def test_setup_transition_to_accepted_saves_ticket(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "trades.db")
            adapter = SMCExecutionAdapter(dry_run=True, db_path=db_path)
            try:
                adapter.claim_setup({"order_id": "ORDER_1"})
                adapter.update_setup_status("ORDER_1", "accepted", ticket=98765)
                info = adapter.get_setup_status("ORDER_1")
                self.assertIsNotNone(info)
                self.assertEqual(info["status"], "accepted")
                self.assertEqual(info["ticket"], 98765)
            finally:
                adapter.close()

    def test_setup_rejection_releases_inbox_lock_for_next_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "trades.db")
            adapter = SMCExecutionAdapter(dry_run=True, db_path=db_path)
            try:
                claim_a = adapter.claim_setup({"order_id": "ORDER_A"})
                self.assertEqual(claim_a["status"], "claimed")
                adapter.update_setup_status("ORDER_A", "rejected")
                claim_b = adapter.claim_setup({"order_id": "ORDER_B"})
                self.assertEqual(claim_b["status"], "claimed")
            finally:
                adapter.close()

    def test_uncertain_setup_blocks_and_reconciles_against_broker(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "trades.db")
            broker = Mock()
            broker.initialize.return_value = True
            with patch("scripts.smc.mt5_adapter.runtime.mt5", broker):
                adapter = SMCExecutionAdapter(dry_run=False, db_path=db_path)
                try:
                    adapter.claim_setup({"order_id": "UNCERTAIN_1"})
                    adapter.update_setup_status("UNCERTAIN_1", "uncertain")

                    # While uncertain, next setup must be blocked
                    busy = adapter.claim_setup({"order_id": "ORDER_2"})
                    self.assertEqual(busy["status"], "busy")

                    # Reconcile Case A: Order found on broker
                    mock_order = SimpleNamespace(ticket=555444, comment="SMC_UNCERTAIN_1")
                    broker.orders_get.return_value = [mock_order]
                    broker.positions_get.return_value = []
                    outcome = adapter.reconcile_uncertain("UNCERTAIN_1")
                    self.assertEqual(outcome, "accepted")
                    info = adapter.get_setup_status("UNCERTAIN_1")
                    self.assertEqual(info["status"], "accepted")
                    self.assertEqual(info["ticket"], 555444)
                    adapter.finish_setup("UNCERTAIN_1")

                    # Reconcile Case B: Order cancelled/not on broker, exposure flat
                    claim_u2 = adapter.claim_setup({"order_id": "UNCERTAIN_2"})
                    self.assertEqual(claim_u2["status"], "claimed")
                    adapter.update_setup_status("UNCERTAIN_2", "uncertain")
                    broker.orders_get.return_value = []
                    broker.positions_get.return_value = []
                    broker.history_orders_get.return_value = []
                    outcome_b = adapter.reconcile_uncertain("UNCERTAIN_2")
                    self.assertEqual(outcome_b, "rejected")
                    info_b = adapter.get_setup_status("UNCERTAIN_2")
                    self.assertEqual(info_b["status"], "rejected")

                    # After rejection, next setup can be claimed
                    claim_next = adapter.claim_setup({"order_id": "ORDER_3"})
                    self.assertEqual(claim_next["status"], "claimed")
                finally:
                    adapter.close()
