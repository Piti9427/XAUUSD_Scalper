"""MT5 Wine entrypoint: isolated trial30 Demo shadow or explicit execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def clock_now():
    return datetime.now(timezone.utc)


def main(argv=None, *, mt5: Any = None) -> int:
    from scripts.trial30.runner import Trial30DemoRunner
    from scripts.smc.mt5_init import resolve_mt5_account_kwargs

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--config", type=Path, default=ROOT / "config/trial30-demo.json")
    parser.add_argument("--journal", type=Path, default=ROOT / "data/trial30-demo.sqlite3")
    parser.add_argument(
        "--cost-policy", type=Path, default=ROOT / "data/trial30-demo-cost-policy.json"
    )
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--max-cycles", type=int, default=0)
    args = parser.parse_args(argv)

    def emit(value):
        print(json.dumps(value, sort_keys=True, allow_nan=False), flush=True)

    expected = dict(
        snapshot="RESEARCH-D48-SELL-BE1R-20261001-T030",
        symbol="XAUUSDm",
        donchian=48,
        atr=14,
        side="SELL",
        volume=0.01,
        sl_atr=2.5,
        tp_atr=3.0,
        risk_cap=0.10,
        daily_loss_limit=0.20,
        protect_after_r=1.0,
        research_only=True,
        real_money="PROHIBITED",
        commission_unit="USD_per_lot_round_trip",
    )
    try:
        config = json.loads(args.config.read_text())
        if not isinstance(config, dict) or any(config.get(k) != v for k, v in expected.items()):
            raise ValueError("snapshot_config_mismatch")
    except (OSError, ValueError, TypeError):
        emit(dict(status="BLOCKED", reason="snapshot_config_mismatch"))
        return 2
    if args.execute and os.environ.get("MT5_ENABLE_DEMO_ORDER_SEND") != "1":
        emit(
            dict(
                status="BLOCKED", reason="explicit_demo_order_gate_required", order_api_called=False
            )
        )
        return 2
    if not 0.1 <= args.poll <= 10 or args.max_cycles < 0:
        emit(dict(status="BLOCKED", reason="invalid_poll_or_cycle_limit"))
        return 2
    credentials = resolve_mt5_account_kwargs()
    if not credentials:
        emit(dict(status="BLOCKED", reason="target_credentials_missing"))
        return 2
    try:
        policy = json.loads(args.cost_policy.read_text())
    except (OSError, ValueError):
        emit(dict(status="BLOCKED", reason="cost_policy_unreadable"))
        return 2
    if mt5 is None:
        import MetaTrader5 as broker_module

        mt5 = broker_module
    terminal = os.environ.get("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
    if not mt5.initialize(path=terminal, timeout=10000, **credentials):
        error = mt5.last_error()
        emit(
            dict(
                status="BLOCKED", reason="initialize_failed", error_code=error[0] if error else None
            )
        )
        return 1
    runner = None
    try:
        runner = Trial30DemoRunner(
            mt5=mt5,
            expected_login=credentials["login"],
            expected_server=credentials["server"],
            journal_path=args.journal,
            cost_policy=policy,
            execute=args.execute,
        )
        # No notifier enabled implicitly; durable broker-confirmed events remain in journal.
        count = 0
        prior = None
        heartbeat = time.monotonic()
        while True:
            now = clock_now()
            # Reload explicit cost attestation; stale/invalid policy still fails closed for entries.
            try:
                runner.policy = json.loads(args.cost_policy.read_text())
            except (OSError, ValueError):
                runner.policy = {}
            result = runner.cycle(now=now)
            key = json.dumps(
                {k: v for k, v in result.items() if k != "captured_utc"}, sort_keys=True
            )
            if key != prior or time.monotonic() - heartbeat >= 60:
                emit(result)
                prior = key
                heartbeat = time.monotonic()
            count += 1
            if not args.watch or (args.max_cycles and count >= args.max_cycles):
                return 1 if result["status"] in ("BLOCKED", "UNKNOWN", "REJECTED") else 0
            time.sleep(args.poll)
    except KeyboardInterrupt:
        emit(dict(status="STOPPED", reason="broker_sl_tp_remain_active"))
        return 0
    except Exception as exc:
        emit(dict(status="BLOCKED", reason=type(exc).__name__))
        return 1
    finally:
        if runner is not None:
            runner.close()
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
