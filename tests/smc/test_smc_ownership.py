import unittest

from scripts.smc.mt5_adapter import is_bot_owned_comment


class BotOwnershipCommentTests(unittest.TestCase):
    def test_symbol_only_never_counts_as_owned(self):
        self.assertFalse(is_bot_owned_comment(""))
        self.assertFalse(is_bot_owned_comment(None))
        self.assertFalse(is_bot_owned_comment("manual scalp"))
        self.assertFalse(is_bot_owned_comment("XAUUSD"))

    def test_smc_prefix_and_order_id_match(self):
        self.assertTrue(is_bot_owned_comment("SMC_abc"))
        self.assertTrue(is_bot_owned_comment("SMC_abc", "abc"))
        self.assertTrue(is_bot_owned_comment("SMC_Partial_abc", "abc"))
        self.assertFalse(is_bot_owned_comment("SMC_other", "abc"))


if __name__ == "__main__":
    unittest.main()
