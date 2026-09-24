import unittest
from types import SimpleNamespace

from scripts.smc.halt_actions import bot_owned_order_ids, plan_halt_flatten_intents
from scripts.smc.types import OrderIntentType


class HaltFlattenTests(unittest.TestCase):
    def test_plan_requests_cancel_then_close_for_bot_ids_only(self):
        intents = plan_halt_flatten_intents(
            pending_order_ids=["SETUP_A", ""],
            open_position_ids=["SETUP_B"],
            reason="drawdown_halt",
        )
        self.assertEqual(
            [i.intent_type for i in intents],
            [OrderIntentType.CANCEL_LIMIT, OrderIntentType.CLOSE_MARKET],
        )
        self.assertEqual([i.order_id for i in intents], ["SETUP_A", "SETUP_B"])
        self.assertTrue(all("drawdown_halt" in i.reason for i in intents))

    def test_bot_owned_filter_ignores_manual_comments(self):
        exposure = [
            SimpleNamespace(comment="SMC_BOT1"),
            SimpleNamespace(comment="MANUAL_X"),
            SimpleNamespace(comment="SMC_BOT2"),
        ]
        self.assertEqual(bot_owned_order_ids(exposure), ["BOT1", "BOT2"])


if __name__ == "__main__":
    unittest.main()
