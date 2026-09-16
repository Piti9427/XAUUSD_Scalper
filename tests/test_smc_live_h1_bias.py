"""Tests for live H1 bias resolve on MT5 adapter (Gate C clock path)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from scripts.smc.mt5_adapter import SMCExecutionAdapter


class TestResolveLiveH1Bias(unittest.TestCase):
    def test_dry_run_returns_unknown(self):
        adapter = SMCExecutionAdapter(dry_run=True, db_path=":memory:")
        try:
            bias, known = adapter.resolve_live_h1_bias()
            self.assertIsNone(bias)
            self.assertFalse(known)
        finally:
            adapter.close()

    def test_insufficient_bars_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = Mock()
            broker.TIMEFRAME_H1 = 60
            # Only 50 bars — below EMA200 warmup.
            broker.copy_rates_from_pos = Mock(
                return_value=np.array(
                    [(i, 1.0, 1.0, 1.0, 2000.0 + i * 0.01, 0, 0, 0) for i in range(50)],
                    dtype=[
                        ("time", "i8"),
                        ("open", "f8"),
                        ("high", "f8"),
                        ("low", "f8"),
                        ("close", "f8"),
                        ("tick_volume", "i8"),
                        ("spread", "i4"),
                        ("real_volume", "i8"),
                    ],
                )
            )
            with patch("scripts.smc.mt5_adapter.runtime.mt5", broker):
                with patch(
                    "scripts.smc.mt5_adapter.adapter.mt5_init.initialize_mt5",
                    return_value=Mock(ok=True, path_used=None, last_error=None, detail="ok"),
                ):
                    adapter = SMCExecutionAdapter(
                        dry_run=False,
                        db_path=str(Path(directory) / "t.db"),
                        terminal_path="C:\\MT5\\terminal64.exe",
                    )
                    try:
                        bias, known = adapter.resolve_live_h1_bias()
                        self.assertIsNone(bias)
                        self.assertFalse(known)
                    finally:
                        adapter.close()

    def test_directional_bias_known(self):
        with tempfile.TemporaryDirectory() as directory:
            closes = [1900.0] * 200 + [2100.0]  # last close above EMA → BUY
            broker = Mock()
            broker.TIMEFRAME_H1 = 60
            broker.copy_rates_from_pos = Mock(
                return_value=np.array(
                    [
                        (i, c, c, c, c, 0, 0, 0)
                        for i, c in enumerate(closes)
                    ],
                    dtype=[
                        ("time", "i8"),
                        ("open", "f8"),
                        ("high", "f8"),
                        ("low", "f8"),
                        ("close", "f8"),
                        ("tick_volume", "i8"),
                        ("spread", "i4"),
                        ("real_volume", "i8"),
                    ],
                )
            )
            with patch("scripts.smc.mt5_adapter.runtime.mt5", broker):
                with patch(
                    "scripts.smc.mt5_adapter.adapter.mt5_init.initialize_mt5",
                    return_value=Mock(ok=True, path_used=None, last_error=None, detail="ok"),
                ):
                    adapter = SMCExecutionAdapter(
                        dry_run=False,
                        db_path=str(Path(directory) / "t.db"),
                        terminal_path="C:\\MT5\\terminal64.exe",
                    )
                    try:
                        bias, known = adapter.resolve_live_h1_bias()
                        self.assertTrue(known)
                        self.assertEqual(bias, "BUY")
                    finally:
                        adapter.close()


if __name__ == "__main__":
    unittest.main()
