"""Fail-closed checks for read-only Exness Demo capture and signal audit."""

import csv
import gzip
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from scripts.research.shadow_capture import capture, utc_time
from scripts.research.shadow_monitor import load_capture, record_signals


UTC = timezone.utc


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    COPY_TICKS_ALL = 0

    def __init__(self, start):
        self.start = start
        self.order_send_calls = 0
        self.account = SimpleNamespace(login=123, server="Exness-MT5Demo", trade_mode=0,
                                       currency="USD", margin_mode=2, balance=1000.0,
                                       equity=999.0)
        self.symbol = SimpleNamespace(name="XAUUSDm", trade_contract_size=100.0,
                                      volume_min=0.01, volume_step=0.01, volume_max=100.0,
                                      point=0.01, trade_tick_size=0.01,
                                      trade_tick_value=1.0)
        self.rows = np.array(
            [(int((start + timedelta(minutes=i)).timestamp() * 1000),
              4000.0 + i * 0.01, 4000.2 + i * 0.01, 6)
             for i in range(125)],
            dtype=[("time_msc", "i8"), ("bid", "f8"),
                   ("ask", "f8"), ("flags", "i4")],
        )

    def account_info(self):
        return self.account

    def symbol_info(self, symbol):
        return self.symbol if symbol == self.symbol.name else None

    def copy_ticks_range(self, symbol, start, end, flags):
        return self.rows

    def order_send(self, *args, **kwargs):
        self.order_send_calls += 1
        raise AssertionError("Shadow code must never submit an order")


class ShadowMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.start = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
        self.end = self.start + timedelta(hours=3)
        self.mt5 = FakeMT5(self.start)

    def make_capture(self, name="capture"):
        path = self.root / name
        capture(self.mt5, start=self.start, end=self.end, freeze_at=self.start,
                symbol="XAUUSDm", expected_login=123,
                expected_server="Exness-MT5Demo", output=path)
        return path

    def test_capture_and_signal_audit_seal_actual_quotes_without_orders(self):
        path = self.make_capture()
        manifest, ticks = load_capture(path)
        self.assertEqual(manifest["tick_count"], len(ticks))
        result = record_signals([path], self.root / "signals")
        self.assertEqual(result["tick_count"], 125)
        self.assertEqual(result["observed_m1_minutes"], 125)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(self.mt5.order_send_calls, 0)
        self.assertTrue((self.root / "signals" / "COMPLETE").is_file())
        with (self.root / "signals" / "signals.csv").open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), result["signal_count"])

    def test_wrong_demo_identity_rejected_before_fetch(self):
        self.mt5.account.trade_mode = 1
        with self.assertRaisesRegex(ValueError, "not Demo"):
            self.make_capture()
        self.assertFalse((self.root / "capture").exists())

    def test_bad_window_and_non_utc_rejected(self):
        with self.assertRaisesRegex(ValueError, "post-freeze"):
            capture(self.mt5, start=self.start, end=self.end,
                    freeze_at=self.start + timedelta(minutes=1),
                    symbol="XAUUSDm", expected_login=123,
                    expected_server="Exness", output=self.root / "bad")
        with self.assertRaisesRegex(ValueError, "UTC"):
            utc_time("2026-09-24T07:00:00+07:00")

    def test_crossed_quote_rejected_before_capture_completed(self):
        self.mt5.rows[1]["ask"] = self.mt5.rows[1]["bid"] - 0.01
        with self.assertRaisesRegex(ValueError, "crossed"):
            self.make_capture()
        self.assertFalse((self.root / "capture" / "COMPLETE").exists())

    def test_tamper_rejected_even_with_complete_marker(self):
        path = self.make_capture()
        with gzip.open(path / "ticks.csv.gz", "at") as handle:
            handle.write("fake\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            load_capture(path)

    def test_inconsistent_symbol_specification_rejected(self):
        first = self.make_capture("one")
        second = self.make_capture("two")
        manifest_path = second / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["symbol_specification"]["volume_min"] = 0.1
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "account/symbol/freeze mismatch"):
            record_signals([first, second], self.root / "signals")
        self.assertFalse((self.root / "signals").exists())


if __name__ == "__main__":
    unittest.main()
