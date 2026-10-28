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

from scripts.demo_runtime.diagnostics import failure_record, fallback, public_reason


def clock_now():
    return datetime.now(timezone.utc)


def main(
    argv=None, *, mt5: Any = None, runner_class=None, name="trial30", expected_config=None,
    recover_initial_policy=False,
) -> int:
    from scripts.trial30.runner import Trial30DemoRunner
    from scripts.smc.mt5_init import resolve_mt5_account_kwargs
    from scripts.demo_runtime.boundary import poll_delay

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--config", type=Path, default=ROOT / f"config/{name}-demo.json")
    parser.add_argument("--journal", type=Path, default=ROOT / f"data/{name}-demo.sqlite3")
    parser.add_argument(
        "--cost-policy", type=Path, default=ROOT / "data/trial30-demo-cost-policy.json"
    )
    if name == "c22h4":
        parser.add_argument("--cache-output", type=Path)
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--initialize-timeout-ms", type=int, default=10000)
    args = parser.parse_args(argv)

    def emit(value):
        print(json.dumps(value, sort_keys=True, allow_nan=False), flush=True)

    def blocked(reason, stage, error=None, *, code=None):
        emit(dict(status="BLOCKED", reason=reason,
            failure=failure_record(error if error is not None else ValueError(reason),
                                   stage=stage, code=code or reason)))

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
    if expected_config is not None:
        expected = expected_config
    try:
        config = json.loads(args.config.read_text())
        if not isinstance(config, dict) or any(config.get(k) != v for k, v in expected.items()):
            raise ValueError("snapshot_config_mismatch")
    except (OSError, ValueError, TypeError) as exc:
        detail_code = ("config_read_failed" if isinstance(exc, OSError) else
                       "config_decode_failed" if isinstance(exc, json.JSONDecodeError) else
                       "snapshot_config_mismatch")
        blocked("snapshot_config_mismatch", "cli.config", exc, code=detail_code)
        return 2
    if args.execute and os.environ.get("MT5_ENABLE_DEMO_ORDER_SEND") != "1":
        emit(
            dict(
                status="BLOCKED", reason="explicit_demo_order_gate_required", order_api_called=False,
                failure=failure_record(ValueError("explicit_demo_order_gate_required"), stage="cli.authority"),
            )
        )
        return 2
    if not 0.1 <= args.poll <= 10 or args.max_cycles < 0:
        blocked("invalid_poll_or_cycle_limit", "cli.arguments")
        return 2
    if not 1000 <= args.initialize_timeout_ms <= 120000:
        blocked("invalid_initialize_timeout", "cli.arguments")
        return 2
    try:
        credentials = resolve_mt5_account_kwargs()
    except Exception as exc:
        blocked("target_credentials_invalid", "cli.credentials", exc)
        return 2
    if not credentials:
        blocked("target_credentials_missing", "cli.credentials")
        return 2
    initial_policy_error = None
    try:
        policy = json.loads(args.cost_policy.read_text())
    except (OSError, ValueError) as exc:
        if recover_initial_policy is not True:
            blocked("cost_policy_unreadable", "cli.policy_read", exc)
            return 2
        # Explicit coherent-generation consumers can recover an independently
        # validated sealed context. {} itself never becomes passing cost proof.
        policy = {}
        initial_policy_error = exc
    if mt5 is None:
        try:
            import MetaTrader5 as broker_module
            mt5 = broker_module
        except Exception as exc:
            blocked(public_reason(exc), "cli.sdk_import", exc, code="runtime_exception")
            return 1
    terminal = os.environ.get("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
    if args.execute and not os.environ.get("MT5_TERMINAL_PATH"):
        blocked("dedicated_terminal_path_required", "cli.terminal_path")
        return 2
    from scripts.demo_runtime.delivery import TelegramDelivery, HealthDelivery

    token, chat = os.environ.get("DEMO_TELEGRAM_TOKEN"), os.environ.get("DEMO_TELEGRAM_CHAT_ID")
    try:
        notify = TelegramDelivery(token, chat) if token and chat else None
        health_url = os.environ.get("DEMO_HEALTHCHECK_URL")
        health = HealthDelivery(health_url) if health_url else None
    except Exception as exc:
        blocked(public_reason(exc), "cli.delivery_init", exc, code="runtime_exception")
        return 1
    runner = None
    initialize_attempted = False
    exit_code = 1
    stage = "cli.runner_init"
    try:
        options = {"config": config} if name != "trial30" else {}
        runner = (runner_class or Trial30DemoRunner)(
            mt5=mt5,
            expected_login=credentials["login"],
            expected_server=credentials["server"],
            journal_path=args.journal,
            cost_policy=policy,
            execute=args.execute,
            notify=notify,
            health_notify=health,
            alert_notify=notify,
            account_guard_dir=ROOT / "data",
            **options,
        )
        initialize_attempted = True
        stage = "cli.initialize"
        if not mt5.initialize(path=terminal, timeout=args.initialize_timeout_ms, **credentials):
            error = mt5.last_error()
            emit(
                dict(
                    status="BLOCKED",
                    reason="initialize_failed",
                    error_code=error[0] if error and type(error[0]) is int else None,
                    failure=failure_record(ValueError("initialize_failed"), stage=stage),
                )
            )
        else:
            # Delivery requires explicit DEMO_* configuration; events persist during outages.
            count = 0
            prior = None
            heartbeat = time.monotonic()
            while True:
                reload_error = initial_policy_error if count == 0 else None
                stage = "cli.policy_reload"
                # Legacy invalid reload remains {}. An opted-in generation
                # consumer resolves one sealed context through its loader.
                # Owned management still runs with a separate IO explanation.
                try:
                    loaded_policy = json.loads(args.cost_policy.read_text())
                except (OSError, ValueError) as exc:
                    loaded_policy = {}
                    reload_error = exc
                now = clock_now()
                loader = getattr(runner, "reload_cost_policy", None)
                if callable(loader):
                    try:
                        loader(loaded_policy, now=now)
                    except Exception as exc:
                        # Configured coherent generations retain their prior
                        # context; the review adapter still blocks invalid entry.
                        reload_error = exc
                    if getattr(runner, "renewal_runtime", None) is not None:
                        now = clock_now()
                else:
                    runner.policy = loaded_policy
                stage = "cli.cycle"
                result = runner.cycle(now=now)
                if reload_error is not None:
                    runner.record_operational_failure(result, now=now,
                        stage="cli.policy_reload", error=reload_error, code="cost_policy_reload_failed")
                if name == "c22h4" and args.cache_output is not None:
                    stage = "cli.cache_export"
                    runner.export_cache(args.cache_output)
                key = json.dumps(
                    {k: v for k, v in result.items() if k != "captured_utc"}, sort_keys=True
                )
                if key != prior or time.monotonic() - heartbeat >= 60:
                    emit(result)
                    prior = key
                    heartbeat = time.monotonic()
                count += 1
                if not args.watch or (args.max_cycles and count >= args.max_cycles):
                    exit_code = 1 if result["status"] in ("BLOCKED", "UNKNOWN", "REJECTED") else 0
                    break
                stage = "cli.poll"
                time.sleep(poll_delay(args.poll, clock_now()))
    except KeyboardInterrupt:
        emit(dict(status="STOPPED", reason="broker_sl_tp_remain_active"))
        exit_code = 0
    except Exception as exc:
        blocked(public_reason(exc), stage, exc, code="runtime_exception")
        exit_code = 1
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception as exc:
                fallback(failure_record(exc, stage="cli.close", code="cli_cleanup_failed"))
                exit_code = exit_code or 1
        if initialize_attempted:
            try:
                mt5.shutdown()
            except Exception as exc:
                fallback(failure_record(exc, stage="cli.shutdown", code="cli_cleanup_failed"))
                exit_code = exit_code or 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
