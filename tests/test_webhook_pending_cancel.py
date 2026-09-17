"""Unit tests for shared pending CANCEL_LIMIT helper."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.webhook.pending_cancel import cancel_unfilled_pending


def _runtime(adapter) -> SimpleNamespace:
    return SimpleNamespace(
        adapter=adapter,
        setup_registry=SimpleNamespace(mark_terminal=Mock()),
    )


class PendingCancelHelperTests(unittest.TestCase):
    def test_success_cancels_and_finishes(self):
        adapter = SimpleNamespace(
            execute_intent=Mock(
                return_value=SimpleNamespace(success=True, message="ok")
            ),
            log_lifecycle_event=Mock(),
            finish_setup=Mock(),
        )
        kept, row = asyncio.run(
            cancel_unfilled_pending(
                _runtime(adapter),
                order_id="P1",
                intent_reason="test",
                lifecycle_reason="life",
                terminal_reason="term",
                result_reason="why",
            )
        )
        self.assertFalse(kept)
        self.assertEqual(row["status"], "success")
        adapter.finish_setup.assert_called_once_with("P1")
        adapter.log_lifecycle_event.assert_called_once()

    def test_fill_during_cancel_releases_inbox(self):
        adapter = SimpleNamespace(
            execute_intent=Mock(
                return_value=SimpleNamespace(success=False, message="order not found")
            ),
            log_lifecycle_event=Mock(),
            finish_setup=Mock(),
        )
        rt = _runtime(adapter)
        kept, row = asyncio.run(
            cancel_unfilled_pending(
                rt,
                order_id="P2",
                intent_reason="test",
                lifecycle_reason="life",
                terminal_reason="term",
                result_reason="why",
            )
        )
        self.assertFalse(kept)
        self.assertEqual(row["status"], "rejected")
        adapter.finish_setup.assert_called_once_with("P2")
        rt.setup_registry.mark_terminal.assert_called_with("P2", "filled_during_cancel")

    def test_hard_reject_keeps_pending(self):
        adapter = SimpleNamespace(
            execute_intent=Mock(
                return_value=SimpleNamespace(success=False, message="broker busy")
            ),
            log_lifecycle_event=Mock(),
            finish_setup=Mock(),
        )
        kept, row = asyncio.run(
            cancel_unfilled_pending(
                _runtime(adapter),
                order_id="P3",
                intent_reason="test",
                lifecycle_reason="life",
                terminal_reason="term",
                result_reason="why",
            )
        )
        self.assertTrue(kept)
        self.assertEqual(row["status"], "rejected")
        adapter.finish_setup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
