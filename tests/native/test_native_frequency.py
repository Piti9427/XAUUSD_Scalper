"""Compile actual MQL5 decision core, not a separate strategy implementation."""

from pathlib import Path
import io
import json
import shutil
import subprocess
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.research.reward156_search import prepare_candidate
from scripts.research.reward156_tuning import closed_h4_ema

ROOT = Path(__file__).resolve().parents[2]


class NativeFrequencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("clang++") or shutil.which("g++")
        if compiler is None:
            raise unittest.SkipTest("native C++ compiler unavailable; MQL5 core not validated")
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.binaries = {}
        for name in ("frequency_host", "frequency_c22"):
            binary = Path(cls.folder.name) / name
            subprocess.run(
                [
                    compiler,
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(ROOT / "mql5"),
                    str(ROOT / "tests/native" / (name + ".cpp")),
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            cls.binaries[name] = binary

    def test_public_native_cases_pass_without_order_api(self):
        result = subprocess.run(
            [str(self.binaries["frequency_host"])],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        cases = [line for line in result.stdout.splitlines() if line.startswith("PASS ")]
        self.assertEqual(len(cases), 24)
        for name in (
            "test_warmup_cannot_reconstruct_session_eligibility",
            "test_unresolved_request_invalidates_terminal_report",
            "test_observed_month_scope_rejects_unobserved_zero_denominator",
        ):
            self.assertIn("PASS " + name, cases)
        self.assertNotIn("FAIL ", result.stdout)

    def test_c22_native_signals_indicators_and_macro_match_frozen_contract(self):
        rng = np.random.default_rng(7)
        close = 2700 + np.cumsum(rng.normal(0, 3, 5000))
        opening = np.r_[close[0], close[:-1]]
        bars = pd.DataFrame(
            dict(
                open=opening,
                high=np.maximum(opening, close) + 0.25,
                low=np.minimum(opening, close) - 0.25,
                close=close,
            ),
            index=pd.date_range("2024-09-01", periods=len(close), freq="15min", tz="UTC"),
        )
        contract = json.loads(
            (ROOT / "config/research-c22-qualified-b823f4aefe10fc72.json").read_text()
        )
        reference, _ = prepare_candidate(bars, contract)
        macro = closed_h4_ema(bars, 200)
        source = "".join(
            f"{int(stamp.timestamp())} {row.open:.17g} {row.high:.17g} {row.low:.17g} {row.close:.17g}\n"
            for stamp, row in bars.iterrows()
        )
        result = subprocess.run(
            [str(self.binaries["frequency_c22"])],
            input=source,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        native = np.loadtxt(io.StringIO(result.stdout))
        self.assertEqual(native.shape, (5000, 6))
        self.assertEqual(
            (int((reference.direction == 1).sum()), int((reference.direction == -1).sum())), (3, 93)
        )
        np.testing.assert_array_equal(native[:, 0], reference.direction)
        np.testing.assert_allclose(native[13:, 1], reference.atr.iloc[13:], atol=1e-10, rtol=1e-12)
        np.testing.assert_allclose(
            native[:, 3], bars.close.ewm(span=50, adjust=False).mean(), atol=1e-10
        )
        np.testing.assert_array_equal(native[:, 4].astype(bool), macro.notna())
        np.testing.assert_allclose(native[macro.notna(), 5], macro.dropna(), atol=1e-10)
        delta = bars.close.diff()
        gain = delta.clip(lower=0).rolling(7).mean()
        loss = (-delta.clip(upper=0)).rolling(7).mean()
        rsi = (100 - 100 / (1 + gain / loss)).mask((gain == 0) & (loss == 0), 50)
        np.testing.assert_allclose(native[7:, 2], rsi.iloc[7:], atol=1e-10)


if __name__ == "__main__":
    unittest.main()
