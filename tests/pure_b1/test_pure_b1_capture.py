"""One bounded Exness M15/tick capture has immutable, linked provenance."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

from scripts.pure_b1.capture import capture_window


class PureB1CaptureTests(unittest.TestCase):
    def test_captures_m15_and_bid_ask_ticks_without_order_api(self):
        start = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=30)
        mt5 = Mock(
            TIMEFRAME_M15=15,
            TIMEFRAME_M1=1,
            COPY_TICKS_ALL=-1,
            ACCOUNT_TRADE_MODE_DEMO=0,
        )
        mt5.account_info.return_value = SimpleNamespace(
            login=123,
            server="Exness-Demo",
            trade_mode=0,
            margin_mode=2,
            currency="USD",
            balance=200.0,
            equity=200.0,
        )
        mt5.symbol_info.return_value = SimpleNamespace(
            name="XAUUSDm",
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_step=0.01,
            volume_max=100.0,
            point=0.001,
            trade_tick_size=0.001,
            trade_tick_value=0.001,
        )
        terminal_rates = [
            {
                "time": int((start + timedelta(minutes=15 * i)).timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.5,
                "tick_volume": 10,
            }
            for i in range(2)
        ]
        m1_rates = [
            {
                "time": int((start + timedelta(minutes=i)).timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.5,
                "tick_volume": 1,
            }
            for i in range(30)
        ]
        mt5.copy_rates_range.side_effect = lambda symbol, timeframe, begin, finish: (
            terminal_rates if timeframe == mt5.TIMEFRAME_M15 else m1_rates
        )
        mt5.symbol_info_tick.return_value = SimpleNamespace(
            bid=3000.0,
            ask=3000.2,
            time_msc=int((end - timedelta(seconds=5)).timestamp() * 1000),
        )
        ticks = np.array(
            [(int((start + timedelta(seconds=10)).timestamp() * 1000), 3000.0, 3000.2, 1)],
            dtype=[("time_msc", "i8"), ("bid", "f8"), ("ask", "f8"), ("flags", "i4")],
        )
        mt5.copy_ticks_range.return_value = ticks
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "capture"
            manifest = capture_window(
                mt5,
                start=start,
                end=end,
                freeze_at=start,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                output=output,
            )
            self.assertEqual(manifest["m15_bars"], 2)
            self.assertEqual(manifest["tick_count"], 1)
            self.assertEqual(manifest["late_entries"], 0)
            self.assertFalse(any(event.get("late_entry") for event in manifest["bar_events"]))
            self.assertTrue((output / "m15_bid.csv").exists())
            self.assertTrue((output / "m15_terminal.csv").exists())
            self.assertTrue((output / "m1_bid.csv").exists())
            self.assertTrue((output / "ticks" / "ticks.csv.gz").exists())
            self.assertEqual(
                json.loads((output / "manifest.json").read_text())["order_api_called"], False
            )
            with self.assertRaises(FileExistsError):
                capture_window(
                    mt5,
                    start=start,
                    end=end,
                    freeze_at=start,
                    symbol="XAUUSDm",
                    expected_login=123,
                    expected_server="Exness-Demo",
                    output=output,
                )
            mt5.copy_rates_range.reset_mock()
            mt5.account_info.return_value.login = 999
            with self.assertRaisesRegex(ValueError, "capture target Demo account changed"):
                capture_window(
                    mt5,
                    start=start,
                    end=end,
                    freeze_at=start,
                    symbol="XAUUSDm",
                    expected_login=123,
                    expected_server="Exness-Demo",
                    output=Path(tmp) / "wrong-account",
                )
            mt5.copy_rates_range.assert_not_called()
        mt5.order_send.assert_not_called()

    def test_incomplete_m1_is_recorded_and_does_not_enter(self):
        start = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=30)
        mt5 = Mock(
            TIMEFRAME_M15=15,
            TIMEFRAME_M1=1,
            COPY_TICKS_ALL=-1,
            ACCOUNT_TRADE_MODE_DEMO=0,
        )
        mt5.account_info.return_value = SimpleNamespace(
            login=123,
            server="Exness-Demo",
            trade_mode=0,
            margin_mode=2,
            currency="USD",
            balance=200.0,
            equity=200.0,
        )
        mt5.symbol_info.return_value = SimpleNamespace(
            name="XAUUSDm",
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_step=0.01,
            volume_max=100.0,
            point=0.001,
            trade_tick_size=0.001,
            trade_tick_value=0.001,
        )
        mt5.symbol_info_tick.return_value = SimpleNamespace(
            bid=3000.0,
            ask=3000.2,
            time_msc=int((start + timedelta(seconds=10)).timestamp() * 1000),
        )
        m1_rates = [
            {
                "time": int((start + timedelta(minutes=i)).timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.5,
                "tick_volume": 1,
            }
            for i in range(30)
            if i != 17
        ]
        terminal_rates = [
            {
                "time": int((start + timedelta(minutes=15 * i)).timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.5,
                "tick_volume": 10,
            }
            for i in range(2)
        ]
        mt5.copy_rates_range.side_effect = lambda symbol, timeframe, begin, finish: (
            terminal_rates if timeframe == mt5.TIMEFRAME_M15 else m1_rates
        )
        ticks = np.array(
            [(int((start + timedelta(seconds=10)).timestamp() * 1000), 3000.0, 3000.2, 1)],
            dtype=[("time_msc", "i8"), ("bid", "f8"), ("ask", "f8"), ("flags", "i4")],
        )
        mt5.copy_ticks_range.return_value = ticks
        with TemporaryDirectory() as tmp:
            manifest = capture_window(
                mt5,
                start=start,
                end=end,
                freeze_at=start,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                output=Path(tmp) / "capture",
            )
        gaps = [event for event in manifest["bar_events"] if event["type"] == "incomplete_m1_interval"]
        stale = [event for event in manifest["bar_events"] if event["type"] == "stale_quote"]
        self.assertEqual(manifest["m15_bars"], 1)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["cause"], "missing_minutes")
        self.assertFalse(gaps[0]["late_entry"])
        self.assertTrue(stale)
        self.assertFalse(stale[0]["late_entry"])
        self.assertEqual(manifest["late_entries"], 0)
        mt5.order_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
