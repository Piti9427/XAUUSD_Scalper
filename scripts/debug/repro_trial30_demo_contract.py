"""Offline diagnostic: dedicated Demo detector reproduces trial30.

Synthetic completed UTC bars; no MT5, credentials, orders or notifications.
Exit 1 if the dedicated trial30 runtime detector drifts from the research signal.
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.research.breakout_logic import features
from scripts.strategy import pure_b1_bars, trial30_bars


def main():
    closes = [100.0 - i * 0.1 for i in range(48)] + [92.0]
    bars = pd.DataFrame(
        {
            "open": closes,
            "high": [v + 1 for v in closes],
            "low": [v - 1 for v in closes],
            "close": closes,
        },
        index=pd.date_range("2026-10-01", periods=49, freq="15min", tz="UTC"),
    )
    research = features(bars)
    runtime = trial30_bars(bars)
    expected = int(research.direction.iloc[-1])
    actual = int(runtime.direction.iloc[-1])
    assert expected == -1, "fixture must trigger trial30 SELL"
    print(
        json.dumps(
            {
                "snapshot": "RESEARCH-D48-SELL-BE1R-20261001-T030",
                "expected_trial30_direction": expected,
                "actual_trial30_direction": actual,
                "legacy_pure_b1_direction": int(pure_b1_bars(bars).direction.iloc[-1]),
                "status": "PASS" if actual == expected else "FAIL_DETECTOR_CONTRACT",
                "broker_tested": False,
                "order_api_called": False,
            }
        ),
        flush=True,
    )
    return 0 if actual == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
