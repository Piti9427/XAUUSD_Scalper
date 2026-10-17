import types
import unittest
from unittest.mock import patch


fake_mt5 = types.SimpleNamespace(
    TIMEFRAME_M1=1,
    TIMEFRAME_M5=5,
    TIMEFRAME_M15=15,
    TIMEFRAME_M30=30,
    TIMEFRAME_H1=60,
    TIMEFRAME_H4=240,
)

from scripts.mt5_connector import TIMEFRAMES, MT5Connector


class MT5ConnectorTests(unittest.TestCase):
    def setUp(self):
        # Scope this fake to the connector; other modules keep their own backend.
        backend = patch("scripts.mt5_connector.mt5", fake_mt5)
        backend.start()
        self.addCleanup(backend.stop)

    def test_timeframes_include_h4(self):
        self.assertEqual(TIMEFRAMES["H4"], fake_mt5.TIMEFRAME_H4)

    def test_get_candles_rejects_unknown_timeframe(self):
        connector = MT5Connector(login=1, password="x", server="demo")

        with self.assertRaisesRegex(ValueError, "Unsupported timeframe"):
            connector.get_candles("XAUUSD", "D1", 100)

    def test_get_spread_uses_ask_minus_bid(self):
        fake_mt5.symbol_info = lambda symbol: types.SimpleNamespace(
            ask=2650.125,
            bid=2650.025,
            spread=999,
        )
        connector = MT5Connector(login=1, password="x", server="demo")
        self.assertEqual(connector.get_spread("XAUUSD"), 0.1)


if __name__ == "__main__":
    unittest.main()
