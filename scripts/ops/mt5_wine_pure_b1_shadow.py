#!/usr/bin/env python3
"""Read-only Pure B1 broker capture or Shadow cycle under Wine Python.

Use scripts/ops/run_b1_d_wine.py --script scripts/ops/mt5_wine_pure_b1_shadow.py.
All configuration is environment based; no trade or notification API is called.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pure_b1.capture import capture_window
from scripts.pure_b1.shadow import shadow_cycle
from scripts.research.shadow_capture import utc_time


def _required(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    raise ValueError("required MT5 environment is missing")


def main() -> int:
    login = int(_required("XAUUSD_MT5_LOGIN", "MT5_LOGIN"))
    password = _required("XAUUSD_MT5_PASSWORD", "MT5_PASSWORD")
    server = _required("XAUUSD_MT5_SERVER", "MT5_SERVER")
    symbol = os.environ.get("PURE_B1_SYMBOL", "XAUUSDm")
    terminal = os.environ.get("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
    import MetaTrader5 as mt5

    if not mt5.initialize(path=terminal, login=login, password=password, server=server):
        error = mt5.last_error()
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "MT5_INITIALIZE_FAILED",
                    "error_code": error[0] if error else None,
                    "order_api_called": False,
                }
            )
        )
        return 2
    try:
        if os.environ.get("PURE_B1_CAPTURE_START_UTC"):
            start = utc_time(_required("PURE_B1_CAPTURE_START_UTC"))
            end = utc_time(_required("PURE_B1_CAPTURE_END_UTC"))
            freeze_at = utc_time(_required("PURE_B1_FREEZE_AT_UTC"))
            output = Path(_required("PURE_B1_CAPTURE_OUTPUT"))
            result = capture_window(
                mt5,
                start=start,
                end=end,
                freeze_at=freeze_at,
                symbol=symbol,
                expected_login=login,
                expected_server=server,
                output=output,
            )
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "symbol": symbol,
                        "m15_bars": result["m15_bars"],
                        "tick_count": result["tick_count"],
                        "order_api_called": False,
                    }
                )
            )
            return 0
        policy_path = os.environ.get("PURE_B1_COST_POLICY")
        policy = json.loads(Path(policy_path).read_text()) if policy_path else None
        log_path = Path(os.environ.get("PURE_B1_SHADOW_LOG", "data/pure_b1_shadow.jsonl"))
        state_path = Path(os.environ.get("PURE_B1_DAY_STATE", "data/pure_b1_day_state.json"))
        watch = os.environ.get("PURE_B1_SHADOW_WATCH") == "1"
        while True:
            now = datetime.now(timezone.utc)
            result = shadow_cycle(
                mt5,
                symbol=symbol,
                expected_login=login,
                expected_server=server,
                cost_policy=policy,
                now=now,
                log_path=log_path,
                state_path=state_path,
            )
            print(
                json.dumps(
                    {
                        "status": "SHADOW",
                        "bar_open_utc": result.get("bar_open_utc"),
                        "direction": result.get("direction"),
                        "admit": result["admit"],
                        "reason": result["reason"],
                        "order_api_called": False,
                    }
                ),
                flush=True,
            )
            if not watch:
                return 0
            time.sleep(5)
    except (ValueError, FileNotFoundError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "order_api_called": False}))
        return 1
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
