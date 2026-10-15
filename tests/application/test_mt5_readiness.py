from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from scripts.mt5_readiness import inspect_terminal
from scripts.run_backtest import load_csv


class TestMT5Readiness(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 3, 2, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=1)
        self.mt5 = Mock(TIMEFRAME_M5=5, TIMEFRAME_H1=60)
        self.mt5.initialize.return_value = True
        self.mt5.account_info.return_value = SimpleNamespace(
            login=123,
            server="Test-Demo",
            trade_mode=0,
            currency="USD",
            balance=2000.0,
            equity=2000.0,
        )
        self.mt5.symbol_info.return_value = SimpleNamespace(
            point=0.01,
            digits=2,
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_step=0.01,
            volume_max=100.0,
        )
        self.mt5.symbol_info_tick.return_value = SimpleNamespace(
            bid=2010.0, ask=2010.2, time=int(self.start.timestamp())
        )
        self.mt5.positions_get.return_value = ()
        self.mt5.orders_get.return_value = ()
        self.mt5.copy_rates_range.return_value = [
            {
                "time": int((self.start + timedelta(hours=i)).timestamp()),
                "open": 2000.0,
                "high": 2010.0,
                "low": 1990.0,
                "close": 2005.0,
                "tick_volume": 100,
                "spread": 20,
                "real_volume": 0,
            }
            for i in range(25)
        ]

    def test_export_is_read_only_closed_utc_and_loadable(self):
        with TemporaryDirectory() as tmp:
            result = inspect_terminal(self.mt5, "XAUUSD", self.start, self.end, Path(tmp))
            self.assertFalse(result["live_ready"])
            self.assertEqual(result["trade_mode"], 0)
            self.assertNotIn("login", result)
            h1 = load_csv(str(Path(tmp) / "XAUUSD_H1.csv"))
            self.assertEqual(len(h1), 24)
            self.assertEqual(str(h1.time.dt.tz), "UTC")
            self.assertLess(h1.time.max(), self.end)
        self.mt5.order_send.assert_not_called()
        self.mt5.login.assert_not_called()
        self.mt5.symbol_select.assert_not_called()
        self.mt5.shutdown.assert_called_once()

    def test_missing_broker_state_fails_without_export(self):
        self.mt5.positions_get.return_value = None
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "MT5_READ_FAILED"):
                inspect_terminal(self.mt5, "XAUUSD", self.start, self.end, Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.mt5.shutdown.assert_called_once()
        self.mt5.order_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
