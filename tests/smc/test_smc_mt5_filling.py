import unittest
from types import SimpleNamespace

from scripts.smc.mt5_filling import resolve_type_filling


class MT5FillingTests(unittest.TestCase):
    def setUp(self):
        self.mt5 = SimpleNamespace(
            SYMBOL_FILLING_FOK=1,
            SYMBOL_FILLING_IOC=2,
            ORDER_FILLING_FOK=0,
            ORDER_FILLING_IOC=1,
            ORDER_FILLING_RETURN=2,
        )

    def test_pending_uses_return(self):
        self.assertEqual(
            resolve_type_filling(3, for_pending=True, mt5_mod=self.mt5),
            2,
        )

    def test_market_prefers_ioc(self):
        self.assertEqual(
            resolve_type_filling(self.mt5.SYMBOL_FILLING_IOC, for_pending=False, mt5_mod=self.mt5),
            self.mt5.ORDER_FILLING_IOC,
        )

    def test_market_fok_when_no_ioc(self):
        self.assertEqual(
            resolve_type_filling(self.mt5.SYMBOL_FILLING_FOK, for_pending=False, mt5_mod=self.mt5),
            self.mt5.ORDER_FILLING_FOK,
        )

    def test_market_fallback_return(self):
        self.assertEqual(
            resolve_type_filling(0, for_pending=False, mt5_mod=self.mt5),
            self.mt5.ORDER_FILLING_RETURN,
        )


if __name__ == "__main__":
    unittest.main()
