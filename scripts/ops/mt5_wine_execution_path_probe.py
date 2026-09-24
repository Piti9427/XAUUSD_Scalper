#!/usr/bin/env python3
"""Demo Execution Path Probe: Orchestrator PLACE_LIMIT far from market, then CANCEL.

Loads credentials from env only. Never prints passwords. Aborts before order_send
on identity / hedging / foreign-position / sizing / geometry failure.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


TRADE_MODE_DEMO = 0
MARGIN_HEDGE = 2
GOLD_CANDIDATES = ("XAUUSDm", "XAUUSD247m", "XAUUSDz", "XAUUSD")
OFFSET_FROM_BID = 80.0
SL_DISTANCE = 2.00
TP_R = 2.5
RISK_PCT = 0.005


def _first_env(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, sort_keys=True, default=str))
    return code


def _repo_root() -> Path:
    env_root = _first_env("XAUUSD_REPO_ROOT")
    if env_root:
        return Path(env_root)
    raise RuntimeError("XAUUSD_REPO_ROOT is required")


def main() -> int:
    out: dict = {
        "order_api_called": False,
        "place_ticket": None,
        "cancel_ok": False,
        "probe": "execution_path",
    }
    login_raw = _first_env("XAUUSD_MT5_LOGIN", "MT5_LOGIN")
    password = _first_env("XAUUSD_MT5_PASSWORD", "MT5_PASSWORD")
    server = _first_env("XAUUSD_MT5_SERVER", "MT5_SERVER")
    path = _first_env("MT5_TERMINAL_PATH") or r"C:\Program Files\MetaTrader 5\terminal64.exe"
    try:
        expected_login = int(login_raw) if login_raw else None
    except ValueError:
        expected_login = None
    if expected_login is None or not password or not server:
        out["stage"] = "env_incomplete"
        return _emit(out, 2)
    if os.environ.get("MT5_ENABLE_DEMO_ORDER_SEND", "").strip() != "1":
        out["stage"] = "demo_order_send_not_enabled"
        return _emit(out, 2)

    repo = _repo_root()
    sys.path.insert(0, str(repo))
    try:
        from scripts.smc.account_mode import verify_account_mode
        from scripts.smc.mt5_filling import resolve_type_filling
        from scripts.smc.orchestrator import StrategyOrchestrator
        from scripts.smc.stops_geometry import pending_stops_geometry_allows
        from scripts.smc.types import AccountState, Direction, OrderIntentType, SetupSignal
    except Exception as exc:
        out["stage"] = "import_repo_failed"
        out["detail"] = type(exc).__name__
        return _emit(out, 2)

    try:
        import MetaTrader5 as mt5
    except ImportError:
        out["stage"] = "mt5_import_missing"
        return _emit(out, 2)

    ok = bool(mt5.initialize(path=path, login=expected_login, password=password, server=server))
    err = mt5.last_error()
    out["initialize"] = ok
    out["error_code"] = err[0] if err else None
    out["error_message"] = err[1] if err and len(err) > 1 else None
    if not ok:
        out["stage"] = "initialize_failed"
        return _emit(out, 1)

    try:
        info = mt5.account_info()
        mode = verify_account_mode(account_info=info, require_hedging=True)
        out["login"] = getattr(info, "login", None)
        out["server"] = getattr(info, "server", None)
        out["trade_mode"] = getattr(info, "trade_mode", None)
        out["margin_mode"] = getattr(info, "margin_mode", None)
        out["currency"] = getattr(info, "currency", None)
        out["account_mode_ok"] = mode.ok
        out["account_mode_reasons"] = list(mode.reasons)
        if info is None or info.login != expected_login:
            out["stage"] = "login_mismatch"
            return _emit(out, 1)
        if server.lower() not in str(info.server).lower():
            out["stage"] = "server_mismatch"
            return _emit(out, 1)
        if info.trade_mode not in (TRADE_MODE_DEMO, 0):
            out["stage"] = "demo_required"
            return _emit(out, 1)
        if not mode.ok:
            out["stage"] = "hedging_required"
            return _emit(out, 1)

        requested = _first_env("MT5_PROBE_SYMBOL")
        symbol = None
        for cand in ((requested,) if requested else ()) + GOLD_CANDIDATES:
            if not cand:
                continue
            si = mt5.symbol_info(cand)
            if si is not None:
                symbol = cand
                break
        out["symbol"] = symbol
        if symbol is None:
            out["stage"] = "gold_symbol_missing"
            return _emit(out, 1)
        if not mt5.symbol_select(symbol, True):
            out["stage"] = "symbol_select_failed"
            return _emit(out, 1)
        si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if si is None or tick is None:
            out["stage"] = "symbol_tick_missing"
            return _emit(out, 1)

        positions = mt5.positions_get(symbol=symbol)
        orders = mt5.orders_get(symbol=symbol)
        if positions is None or orders is None:
            out["stage"] = "broker_state_unavailable"
            return _emit(out, 1)
        foreign = []
        for pos in positions:
            comment = str(getattr(pos, "comment", "") or "")
            if not comment.startswith("SMC_"):
                foreign.append({"ticket": pos.ticket, "comment": comment[:31]})
        for order in orders:
            comment = str(getattr(order, "comment", "") or "")
            if not comment.startswith("SMC_"):
                foreign.append({"ticket": order.ticket, "kind": "order", "comment": comment[:31]})
        out["foreign"] = foreign
        if foreign:
            out["stage"] = "foreign_position_blocks"
            return _emit(out, 1)

        bid = float(tick.bid)
        ask = float(tick.ask)
        point = float(si.point)
        stops_raw = getattr(si, "trade_stops_level", None)
        if stops_raw is None:
            out["stage"] = "stops_level_missing"
            return _emit(out, 1)
        stops_level = float(stops_raw)
        contract_size = float(si.trade_contract_size)
        min_lot = float(si.volume_min)
        lot_step = float(si.volume_step)
        entry = round(bid - OFFSET_FROM_BID, 2)
        sl = round(entry - SL_DISTANCE, 2)
        tp = round(entry + SL_DISTANCE * TP_R, 2)
        geom_ok, geom_reason = pending_stops_geometry_allows(
            entry_price=entry,
            sl_price=sl,
            tp_price=tp,
            point=point,
            stops_level=stops_level,
        )
        out["contract_size"] = contract_size
        out["volume_min"] = min_lot
        out["lot_step"] = lot_step
        out["geometry"] = geom_reason
        out["prices"] = {"bid": bid, "ask": ask, "entry": entry, "sl": sl, "tp": tp}
        if not geom_ok:
            out["stage"] = "geometry_blocked"
            return _emit(out, 1)

        now = datetime.now(timezone.utc)
        setup_id = f"ep{now:%m%d%H%M%S}"
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=entry,
            sweep_wick=sl,
            mss_price=entry,
            entry_price=entry,
            sl_price=sl,
            tp_price=tp,
            sl_distance=SL_DISTANCE,
            risk_r=TP_R,
            fvg_high=entry,
            fvg_low=entry,
            reason="ADR-0029 execution-path probe: far BUY_LIMIT then cancel",
            timestamp=now,
            setup_id=setup_id,
        )
        account = AccountState(balance=float(info.balance), equity=float(info.equity))
        orch = StrategyOrchestrator(risk_pct=RISK_PCT)
        bar = {"time": now, "open": bid, "high": bid, "low": bid, "close": bid}
        intents = orch.on_bar(
            bar,
            account,
            setup_signal=signal,
            current_spread=ask - bid,
            h1_bias=Direction.BUY,
            h1_bias_known=True,
        )
        place = next((i for i in intents if i.intent_type == OrderIntentType.PLACE_LIMIT), None)
        out["orchestrator_intents"] = [i.intent_type.value for i in intents]
        out["setup_id"] = setup_id
        if place is None or not place.lot_size:
            out["stage"] = "orchestrator_rejected"
            return _emit(out, 1)
        out["lot_size"] = place.lot_size

        filling = resolve_type_filling(int(si.filling_mode), for_pending=True, mt5_mod=mt5)
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(place.lot_size),
            "type": mt5.ORDER_TYPE_BUY_LIMIT,
            "price": float(place.limit_price),
            "sl": float(place.sl_price),
            "tp": float(place.tp_price),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
            "comment": f"SMC_{setup_id}"[:31],
        }
        out["order_api_called"] = True
        result = mt5.order_send(request)
        if result is None:
            out["stage"] = "place_unknown"
            out["place_retcode"] = None
            return _emit(out, 1)
        out["place_retcode"] = int(result.retcode)
        out["place_comment"] = str(result.comment)
        out["place_ticket"] = int(result.order) if result.order else None
        placed = result.retcode in (
            mt5.TRADE_RETCODE_DONE,
            getattr(mt5, "TRADE_RETCODE_PLACED", -1),
        )
        if not placed:
            out["stage"] = "place_rejected"
            return _emit(out, 1)

        positions = mt5.positions_get(symbol=symbol) or []
        if positions:
            out["stage"] = "unexpected_fill"
            out["positions"] = [p.ticket for p in positions]
            return _emit(out, 1)

        ticket = int(result.order)
        leave = os.environ.get("MT5_PROBE_LEAVE_PENDING", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        out["leave_pending"] = leave
        if leave:
            leftover = mt5.orders_get(symbol=symbol) or []
            out["leftover_orders"] = [o.ticket for o in leftover]
            out["stage"] = "probe_placed"
            return _emit(out, 0)

        cancel = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if cancel is None:
            out["stage"] = "cancel_unknown"
            return _emit(out, 1)
        out["cancel_retcode"] = int(cancel.retcode)
        out["cancel_comment"] = str(cancel.comment)
        out["cancel_ok"] = cancel.retcode == mt5.TRADE_RETCODE_DONE
        leftover = mt5.orders_get(symbol=symbol) or []
        out["leftover_orders"] = [o.ticket for o in leftover]
        if not out["cancel_ok"] or leftover:
            out["stage"] = "cancel_failed"
            return _emit(out, 1)
        out["stage"] = "probe_ok"
        return _emit(out, 0)
    except Exception as exc:
        out["stage"] = "probe_exception"
        out["detail"] = type(exc).__name__
        return _emit(out, 1)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
