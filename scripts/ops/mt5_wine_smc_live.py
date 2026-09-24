#!/usr/bin/env python3
"""Wine Demo live: detect → PLACE_LIMIT only → broker reconcile → quote two-tier.

Never uses Orchestrator OHLC fill. Never prints passwords. Demo + XAUUSDm only.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TRADE_MODE_DEMO = 0
MARGIN_HEDGE = 2


def _first_env(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True, default=str), flush=True)


def _repo_root() -> Path:
    env_root = _first_env("XAUUSD_REPO_ROOT")
    if env_root:
        return Path(env_root)
    raise RuntimeError("XAUUSD_REPO_ROOT is required")


def _foreign(mt5, symbol: str) -> list[dict]:
    positions = mt5.positions_get(symbol=symbol)
    orders = mt5.orders_get(symbol=symbol)
    if positions is None or orders is None:
        raise RuntimeError("broker_position_or_order_state_unavailable")
    rows = []
    for pos in positions:
        comment = str(getattr(pos, "comment", "") or "")
        if not comment.startswith("SMC_"):
            rows.append({"ticket": pos.ticket, "comment": comment[:31], "kind": "position"})
    for order in orders:
        comment = str(getattr(order, "comment", "") or "")
        if not comment.startswith("SMC_"):
            rows.append({"ticket": order.ticket, "comment": comment[:31], "kind": "order"})
    return rows


def main() -> int:
    login_raw = _first_env("XAUUSD_MT5_LOGIN", "MT5_LOGIN")
    password = _first_env("XAUUSD_MT5_PASSWORD", "MT5_PASSWORD")
    server = _first_env("XAUUSD_MT5_SERVER", "MT5_SERVER")
    path = _first_env("MT5_TERMINAL_PATH") or r"C:\Program Files\MetaTrader 5\terminal64.exe"
    once = _truthy("MT5_LIVE_ONCE")
    try:
        max_cycles = int(_first_env("MT5_LIVE_MAX_CYCLES") or "0")
    except ValueError:
        max_cycles = 0
    try:
        expected_login = int(login_raw) if login_raw else None
    except ValueError:
        expected_login = None
    if expected_login is None or not password or not server:
        _emit({"stage": "env_incomplete", "order_api_called": False})
        return 2
    if not _truthy("MT5_ENABLE_DEMO_ORDER_SEND"):
        _emit({"stage": "demo_order_send_not_enabled", "order_api_called": False})
        return 2

    repo = _repo_root()
    sys.path.insert(0, str(repo))
    os.chdir(str(repo))

    from scripts.smc.account_mode import verify_account_mode
    from scripts.smc.account_sync import apply_broker_capital
    from scripts.smc.broker_lifecycle import reconcile_broker_lifecycle
    from scripts.smc.broker_rates import classify_bar_clock, drop_forming_bars, rates_to_frame
    from scripts.smc.data_freshness import evaluate_new_risk_admission
    from scripts.smc.demo_live import admit_place_intents, two_tier_intents
    from scripts.smc.detection import evaluate_smc_setup, resolve_h1_ema_bias
    from scripts.smc.gold_v2_demo import GOLD_V2_DEMO
    from scripts.smc.liquidity import compute_liquidity_levels
    from scripts.smc.mt5_adapter import SMCExecutionAdapter
    from scripts.smc.news import NewsManager
    from scripts.smc.orchestrator import StrategyOrchestrator
    from scripts.smc.setup_identity import load_setup_registry
    from scripts.smc.types import AccountState
    from scripts.smc.warmup import H1_WARMUP_BARS, h1_warmup_ok

    symbol = str(GOLD_V2_DEMO["symbol"])
    adapter = SMCExecutionAdapter(
        symbol=symbol,
        dry_run=False,
        db_path=str(repo / "data" / "smc_trades.db"),
        terminal_path=path,
        login=expected_login,
        password=password,
        server=server,
    )
    import MetaTrader5 as mt5

    info = mt5.account_info()
    mode = verify_account_mode(account_info=info, require_hedging=True)
    if info is None or info.login != expected_login:
        _emit({"stage": "login_mismatch", "order_api_called": False})
        return 1
    if server.lower() not in str(info.server).lower():
        _emit({"stage": "server_mismatch", "order_api_called": False})
        return 1
    if info.trade_mode not in (TRADE_MODE_DEMO, 0):
        _emit({"stage": "demo_required", "order_api_called": False})
        return 1
    if not mode.ok:
        _emit(
            {"stage": "hedging_required", "reasons": list(mode.reasons), "order_api_called": False}
        )
        return 1
    if not mt5.symbol_select(symbol, True):
        _emit({"stage": "symbol_select_failed", "order_api_called": False})
        return 1

    registry = load_setup_registry(repo / "data" / "setup_registry.json")
    orch = StrategyOrchestrator(
        ttl_expire_bars=int(GOLD_V2_DEMO["ttl_expire_bars"]),
        max_sl_cap=float(GOLD_V2_DEMO["max_sl_cap"]),
        partial_tp_enabled=False,
        be_enabled=False,
        risk_pct=float(GOLD_V2_DEMO["risk_pct"]),
        setup_registry=registry,
    )
    news_mgr = NewsManager()
    news_cache = repo / "data" / "news_cache.json"
    last_processed = None
    cycle = 0
    _emit(
        {
            "stage": "live_start",
            "login": info.login,
            "server": info.server,
            "symbol": symbol,
            "balance": info.balance,
            "once": once,
        }
    )

    try:
        while True:
            cycle += 1
            now = datetime.now(timezone.utc)
            info = mt5.account_info()
            cycle_out: dict = {
                "cycle": cycle,
                "order_api_called": False,
                "probe": "smc_live",
                "symbol": symbol,
            }
            mode = verify_account_mode(account_info=info, require_hedging=True)
            if (
                info is None
                or info.login != expected_login
                or server.lower() not in str(info.server).lower()
                or info.trade_mode != TRADE_MODE_DEMO
                or not mode.ok
            ):
                cycle_out["stage"] = "target_demo_identity_lost"
                _emit(cycle_out)
                return 1
            try:
                foreign = _foreign(mt5, symbol)
            except RuntimeError:
                cycle_out["stage"] = "broker_state_unavailable"
                _emit(cycle_out)
                return 1
            cycle_out["foreign"] = foreign
            lifecycle = reconcile_broker_lifecycle(
                adapter,
                now=now,
                order_ttl_bars=int(GOLD_V2_DEMO["ttl_expire_bars"]),
                bar_minutes=int(GOLD_V2_DEMO["bar_minutes"]),
            )
            cycle_out["lifecycle"] = {
                "ttl": len(lifecycle.get("ttl_cancels") or []),
                "fills": len(lifecycle.get("broker_fills") or []),
                "closes": len(lifecycle.get("broker_closes") or []),
            }

            tick = mt5.symbol_info_tick(symbol)
            quotes = adapter.get_market_quotes() if hasattr(adapter, "get_market_quotes") else None
            bid = float(quotes["bid"]) if quotes else (float(tick.bid) if tick else None)
            ask = float(quotes["ask"]) if quotes else (float(tick.ask) if tick else None)
            scaled = []
            if bid is not None and ask is not None:
                for row in adapter.list_open_fills():
                    order_id = row["order_id"]
                    if adapter.has_lifecycle_event(order_id, "PARTIAL_CLOSE"):
                        continue
                    geom = adapter.get_fill_geometry(order_id) or {}
                    pos = adapter.get_matching_position(order_id)
                    lot = float(getattr(pos, "volume", 0) or geom.get("lot_size") or 0)
                    intents = two_tier_intents(
                        order_id=order_id,
                        lot_size=lot,
                        direction=str(geom.get("direction") or row.get("direction") or "BUY"),
                        entry=float(geom.get("entry_price") or 0),
                        sl=float(geom.get("sl_price") or 0),
                        bid=bid,
                        ask=ask,
                        already_scaled=False,
                        min_split_lot=float(GOLD_V2_DEMO["min_split_lot"]),
                        partial_ratio=float(GOLD_V2_DEMO["partial_tp_ratio"]),
                        be_buffer=float(GOLD_V2_DEMO["be_buffer"]),
                    )
                    if not intents:
                        continue
                    partial = intents[0]
                    cycle_out["order_api_called"] = True
                    part_res = adapter.execute_intent(partial)
                    if not part_res.success:
                        scaled.append({"order_id": order_id, "status": "partial_rejected"})
                        continue
                    be_res = adapter.execute_intent(intents[1])
                    scaled.append(
                        {
                            "order_id": order_id,
                            "status": "ok" if be_res.success else "be_rejected",
                        }
                    )
            cycle_out["two_tier"] = scaled

            m5_raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 500)
            h1_raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, int(H1_WARMUP_BARS))
            df_raw = rates_to_frame(m5_raw)
            df_m5 = (
                drop_forming_bars(
                    df_raw,
                    now=now,
                    bar_minutes=int(GOLD_V2_DEMO["bar_minutes"]),
                )
                if df_raw is not None
                else None
            )
            df_h1 = rates_to_frame(h1_raw)
            cycle_out["host_now"] = now.isoformat()
            if tick is not None:
                cycle_out["tick_time"] = datetime.fromtimestamp(
                    int(tick.time), tz=timezone.utc
                ).isoformat()
                cycle_out["tick_bid"] = float(tick.bid)
            if df_raw is not None and not df_raw.empty:
                cycle_out["raw_last_m5"] = df_raw["time"].iloc[-1].isoformat()
            if df_m5 is None or df_m5.empty:
                cycle_out["stage"] = "DATA_INSUFFICIENT_M5"
                _emit(cycle_out)
                if once or (max_cycles and cycle >= max_cycles):
                    return 1
                time.sleep(15)
                continue
            bar_time = df_m5["time"].iloc[-1].to_pydatetime()
            if bar_time.tzinfo is None:
                bar_time = bar_time.replace(tzinfo=timezone.utc)
            if tick is not None:
                tick_time = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
                clock = classify_bar_clock(
                    bar_open=bar_time,
                    tick_time=tick_time,
                    bar_minutes=int(GOLD_V2_DEMO["bar_minutes"]),
                )
            else:
                clock = "DATA_BAD_TIMEZONE"
            cycle_out["clock"] = clock
            cycle_out["bar_time"] = bar_time.isoformat()
            if clock != "ok":
                cycle_out["stage"] = clock
                _emit(cycle_out)
                if once or (max_cycles and cycle >= max_cycles):
                    return 1
                time.sleep(15)
                continue

            new_bar = last_processed is None or bar_time != last_processed
            last_processed = bar_time
            cycle_out["new_closed_bar"] = bool(new_bar)
            if new_bar and not foreign:
                news_events = news_mgr.fetch_forexfactory_calendar(cache_path=str(news_cache))
                schedule_known = bool(news_events)
                news_ok, news_reason = news_mgr.new_risk_allowed(
                    now, news_events, schedule_known=schedule_known, window_mins=30
                )
                h1_ready = df_h1 is not None and h1_warmup_ok(len(df_h1))
                snap = adapter.get_risk_snapshot()
                account = AccountState(
                    balance=float(getattr(info, "balance", 0) or 0),
                    equity=float(getattr(info, "equity", 0) or 0),
                )
                if snap is not None:
                    apply_broker_capital(
                        account, balance=snap.get("balance"), equity=snap.get("equity")
                    )
                admission = evaluate_new_risk_admission(
                    last_bar_time=bar_time,
                    now=now,
                    history_ready=True,
                    equity_known=snap is not None,
                    news_allowed=news_ok,
                    news_reason=news_reason,
                )
                cycle_out["admission"] = admission.reason
                cycle_out["h1_ready"] = h1_ready
                pending_bot = [
                    o.ticket
                    for o in (mt5.orders_get(symbol=symbol) or [])
                    if str(getattr(o, "comment", "") or "").startswith("SMC_")
                ]
                open_bot = [
                    p.ticket
                    for p in (mt5.positions_get(symbol=symbol) or [])
                    if str(getattr(p, "comment", "") or "").startswith("SMC_")
                ]
                cycle_out["bot_pending"] = pending_bot
                cycle_out["bot_positions"] = open_bot
                if admission.allowed and h1_ready and not pending_bot and not open_bot:
                    liquidity = compute_liquidity_levels(df_m5, bar_time.date())
                    h1_bias_dir, h1_bias_reason = resolve_h1_ema_bias(df_h1)
                    h1_bias_known = h1_bias_reason in ("ok", "h1_bias_flat")
                    spread = None
                    if bid is not None and ask is not None:
                        spread = ask - bid
                    decision = evaluate_smc_setup(
                        h1_candles=df_h1,
                        m5_candles=df_m5,
                        liquidity=liquidity,
                        current_time=bar_time,
                        current_spread=spread,
                        max_spread=float(GOLD_V2_DEMO["max_spread"]),
                        max_sl_cap=float(GOLD_V2_DEMO["max_sl_cap"]),
                        extended_killzones=bool(GOLD_V2_DEMO["extended_killzones"]),
                        tp_r=float(GOLD_V2_DEMO["tp_r"]),
                        min_body_ratio=float(GOLD_V2_DEMO["min_body_ratio"]),
                        max_sweep_pierce=float(GOLD_V2_DEMO["max_sweep_pierce"]),
                        sweep_lookback=int(GOLD_V2_DEMO["sweep_lookback"]),
                        max_sweep_to_mss_bars=int(GOLD_V2_DEMO["max_sweep_to_mss_bars"]),
                        max_mss_to_fvg_bars=int(GOLD_V2_DEMO["max_mss_to_fvg_bars"]),
                        require_choch=bool(GOLD_V2_DEMO["require_choch"]),
                    )
                    cycle_out["reject_reason"] = decision.reject_reason
                    if decision.accepted and decision.signal is not None:
                        last_bar = df_m5.iloc[-1].to_dict()
                        intents = orch.on_bar(
                            last_bar,
                            account,
                            setup_signal=decision.signal,
                            current_spread=spread,
                            max_spread=float(GOLD_V2_DEMO["max_spread"]),
                            h1_bias=h1_bias_dir,
                            h1_bias_known=h1_bias_known,
                        )
                        admit_reason, places = admit_place_intents(intents)
                        cycle_out["place_admit"] = admit_reason
                        if admit_reason == "ok":
                            for intent in places:
                                cycle_out["order_api_called"] = True
                                result = adapter.execute_intent(intent)
                                cycle_out["place"] = {
                                    "success": result.success,
                                    "message": result.message,
                                    "order_id": intent.order_id,
                                    "lot": intent.lot_size,
                                    "limit": intent.limit_price,
                                }
                                account.pending_order = None
            elif foreign:
                cycle_out["stage"] = "foreign_position_blocks"
            if "stage" not in cycle_out:
                cycle_out["stage"] = "cycle_ok"
            _emit(cycle_out)
            if once or (max_cycles and cycle >= max_cycles):
                return 0
            time.sleep(15)
    finally:
        adapter.close()
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
