"""Offline counterexamples for commit a551b62; no broker or notifier calls."""

from dataclasses import replace
from pathlib import Path
import runpy
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.smc import detection  # noqa: E402 - repository bootstrap for direct execution


def capture_fixture(method):
    namespace = runpy.run_path(str(ROOT / "tests/smc/test_smc_detection.py"))
    case = namespace["TestSMCDetectionIntegration"](method)
    case.setUp()
    target_globals = getattr(case, method).__func__.__globals__
    calls = []

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return detection.detect_smc_setup(*args, **kwargs)

    with patch.dict(target_globals, detect_smc_setup=record):
        getattr(case, method)()
    return calls[0]


def main():
    parent = {}
    source = subprocess.check_output(
        ["git", "show", "a551b62^:scripts/smc/detection.py"],
        cwd=ROOT,
        text=True,
    )
    exec(compile(source, "parent_detection.py", "exec"), parent)
    old_detect = parent["detect_smc_setup"]
    reviewed = {}
    source = subprocess.check_output(
        ["git", "show", "a551b62:scripts/smc/detection.py"],
        cwd=ROOT,
        text=True,
    )
    exec(compile(source, "reviewed_detection.py", "exec"), reviewed)

    args, kwargs = capture_fixture("test_expansion_breakout_invalidates_stale_sweep")
    old_signal = old_detect(*args, **kwargs)
    assert old_signal is not None
    assert detection.detect_smc_setup(*args, **kwargs) is None
    print(f"VERIFIED original regression: parent SL={old_signal.sl_price}; working tree=None")

    args, kwargs = capture_fixture("test_valid_bullish_setup_during_london")
    changed = list(args)
    changed[2] = replace(args[2], pdl=2020.0)
    old_signal = old_detect(*changed, **kwargs)
    new_signal = detection.detect_smc_setup(*changed, **kwargs)
    assert old_signal is not None and old_signal.sweep_price == 2010.0
    assert reviewed["detect_smc_setup"](*changed, **kwargs) is None
    assert new_signal == old_signal
    print("VERIFIED cross-level fix: a551b62=None; working tree BUY entry=2014 SL=2008.2")

    def wick_only(candle, level, is_high_level=True, max_breakout_pierce=8.0):
        pierce = candle["high"] - level if is_high_level else level - candle["low"]
        return pierce > max_breakout_pierce

    with patch.object(detection, "is_expansion_breakout", side_effect=wick_only):
        capture_fixture("test_expansion_breakout_invalidates_stale_sweep")
        namespace = runpy.run_path(str(ROOT / "tests/smc/test_smc_detection.py"))
        case = namespace["TestSMCDetectionIntegration"]("test_breakout_branches_and_boundary")
        result = unittest.TestResult()
        case.run(result)
        assert len(result.failures) == 2 and not result.errors
    print(
        "VERIFIED mutation: legacy regression survives body-rule deletion; new BUY/SELL checks catch it"
    )


if __name__ == "__main__":
    main()
