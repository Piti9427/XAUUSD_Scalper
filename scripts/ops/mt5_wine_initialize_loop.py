#!/usr/bin/env python3
"""Read-only MetaTrader5 initialize loop.

Exit 0 only when initialize() succeeds and account_info() matches the expected
Demo login. Never calls order_send / positions / history APIs. Never prints
passwords.
"""

from __future__ import annotations

import json
import os
import sys


TRADE_MODE_DEMO = 0


def _first_env(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def main() -> int:
    login_raw = _first_env("XAUUSD_MT5_LOGIN", "MT5_LOGIN")
    password = _first_env("XAUUSD_MT5_PASSWORD", "MT5_PASSWORD")
    server = _first_env("XAUUSD_MT5_SERVER", "MT5_SERVER")
    path = _first_env("MT5_TERMINAL_PATH") or r"C:\Program Files\MetaTrader 5\terminal64.exe"
    portable = _truthy("MT5_INITIALIZE_PORTABLE")
    omit_creds = _truthy("MT5_OMIT_CREDENTIALS")

    expected_login: int | None
    try:
        expected_login = int(login_raw) if login_raw else None
    except ValueError:
        expected_login = None

    creds_ok = expected_login is not None and bool(password) and bool(server)
    out: dict = {
        "account_present": False,
        "attached_login": None,
        "attached_server": None,
        "attached_trade_mode": None,
        "credentials_provided": bool(creds_ok and not omit_creds),
        "error_code": None,
        "error_message": None,
        "expected_login": expected_login,
        "expected_server": server,
        "import_ok": False,
        "initialize": False,
        "initialize_kwargs_keys": [],
        "login_match": False,
        "mt5_module_version": None,
        "omit_credentials": omit_creds,
        "order_api_called": False,
        "portable": portable,
        "target_demo_verified": False,
        "terminal_path_used": path,
    }

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print(json.dumps(out, sort_keys=True))
        return 2

    out["import_ok"] = True
    out["mt5_module_version"] = getattr(mt5, "__version__", None)

    kwargs: dict = {"path": path}
    if portable:
        kwargs["portable"] = True
    if creds_ok and not omit_creds:
        kwargs["login"] = expected_login
        kwargs["password"] = password
        kwargs["server"] = server
    out["initialize_kwargs_keys"] = sorted(k for k in kwargs if k != "password")

    ok = bool(mt5.initialize(**kwargs))
    err = mt5.last_error()
    out["initialize"] = ok
    if isinstance(err, (tuple, list)) and err:
        out["error_code"] = err[0]
        if len(err) > 1:
            out["error_message"] = err[1]

    if ok:
        info = mt5.account_info()
        out["account_present"] = info is not None
        if info is not None:
            attached_login = getattr(info, "login", None)
            trade_mode = getattr(info, "trade_mode", None)
            out["attached_login"] = attached_login
            out["attached_server"] = getattr(info, "server", None)
            out["attached_trade_mode"] = trade_mode
            out["login_match"] = attached_login == expected_login
            demo_const = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", TRADE_MODE_DEMO)
            out["target_demo_verified"] = bool(
                out["login_match"] and trade_mode in (demo_const, 0, "demo", "DEMO")
            )
        mt5.shutdown()

    print(json.dumps(out, sort_keys=True))
    if out["target_demo_verified"]:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
