#!/usr/bin/env python3
"""Read-only MT5 history dump for Demo Execution Path tickets.

Never calls order_send. Never prints passwords.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone


TICKETS = (4742640166, 4742656874, 4740603310)
GOLD = ("XAUUSDm", "XAUUSD247m", "XAUUSDz", "XAUUSD")


def _first_env(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _order_row(order) -> dict:
    return {
        "ticket": int(getattr(order, "ticket", 0) or 0),
        "symbol": getattr(order, "symbol", None),
        "type": int(getattr(order, "type", -1)),
        "state": int(getattr(order, "state", -1)),
        "volume_initial": getattr(order, "volume_initial", None),
        "price_open": getattr(order, "price_open", None),
        "comment": str(getattr(order, "comment", "") or "")[:31],
        "time_setup": getattr(order, "time_setup", None),
        "time_done": getattr(order, "time_done", None),
    }


def _deal_row(deal) -> dict:
    return {
        "ticket": int(getattr(deal, "ticket", 0) or 0),
        "order": int(getattr(deal, "order", 0) or 0),
        "symbol": getattr(deal, "symbol", None),
        "type": int(getattr(deal, "type", -1)),
        "entry": int(getattr(deal, "entry", -1)),
        "volume": getattr(deal, "volume", None),
        "price": getattr(deal, "price", None),
        "profit": getattr(deal, "profit", None),
        "comment": str(getattr(deal, "comment", "") or "")[:31],
        "time": getattr(deal, "time", None),
    }


def main() -> int:
    login_raw = _first_env("XAUUSD_MT5_LOGIN", "MT5_LOGIN")
    password = _first_env("XAUUSD_MT5_PASSWORD", "MT5_PASSWORD")
    server = _first_env("XAUUSD_MT5_SERVER", "MT5_SERVER")
    path = _first_env("MT5_TERMINAL_PATH") or r"C:\Program Files\MetaTrader 5\terminal64.exe"
    try:
        expected_login = int(login_raw) if login_raw else None
    except ValueError:
        expected_login = None
    out: dict = {
        "order_api_called": False,
        "probe": "history_dump",
        "tickets_requested": list(TICKETS),
    }
    if expected_login is None or not password or not server:
        out["stage"] = "env_incomplete"
        print(json.dumps(out, sort_keys=True, default=str))
        return 2

    import MetaTrader5 as mt5

    ok = bool(mt5.initialize(path=path, login=expected_login, password=password, server=server))
    err = mt5.last_error()
    out["initialize"] = ok
    out["error_code"] = err[0] if err else None
    out["error_message"] = err[1] if err and len(err) > 1 else None
    if not ok:
        out["stage"] = "initialize_failed"
        print(json.dumps(out, sort_keys=True, default=str))
        return 1

    try:
        info = mt5.account_info()
        out["login"] = getattr(info, "login", None)
        out["server"] = getattr(info, "server", None)
        out["balance"] = getattr(info, "balance", None)
        out["equity"] = getattr(info, "equity", None)
        if info is None or info.login != expected_login:
            out["stage"] = "login_mismatch"
            print(json.dumps(out, sort_keys=True, default=str))
            return 1

        gold = []
        for name in GOLD:
            si = mt5.symbol_info(name)
            gold.append(
                {
                    "name": name,
                    "present": si is not None,
                    "visible": bool(getattr(si, "visible", False)) if si is not None else False,
                    "trade_mode": getattr(si, "trade_mode", None) if si is not None else None,
                }
            )
        out["gold_symbols"] = gold

        out["open_positions"] = [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "volume": p.volume,
                "comment": str(p.comment or "")[:31],
            }
            for p in (mt5.positions_get() or [])
        ]
        out["open_orders"] = [_order_row(o) for o in (mt5.orders_get() or [])]

        by_ticket = {}
        for ticket in TICKETS:
            orders = mt5.history_orders_get(ticket=ticket)
            deals = mt5.history_deals_get(ticket=ticket)
            by_ticket[str(ticket)] = {
                "orders": [_order_row(o) for o in (orders or [])],
                "deals": [_deal_row(d) for d in (deals or [])],
            }
        out["by_ticket"] = by_ticket

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=2)
        all_orders = mt5.history_orders_get(start, now) or []
        all_deals = mt5.history_deals_get(start, now) or []
        smc_orders = [
            _order_row(o)
            for o in all_orders
            if str(getattr(o, "comment", "") or "").startswith("SMC_")
            or int(getattr(o, "ticket", 0) or 0) in TICKETS
        ]
        xauusdm_orders = [
            _order_row(o) for o in all_orders if str(getattr(o, "symbol", "") or "") == "XAUUSDm"
        ]
        out["history_window_hours"] = 48
        out["history_orders_count"] = len(all_orders)
        out["history_deals_count"] = len(all_deals)
        out["smc_or_probe_orders"] = smc_orders
        out["xauusdm_orders"] = xauusdm_orders
        out["deal_symbols"] = sorted(
            {str(getattr(d, "symbol", "") or "") for d in all_deals if getattr(d, "symbol", None)}
        )
        out["stage"] = "history_ok"
        print(json.dumps(out, sort_keys=True, default=str))
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
