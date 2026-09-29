"""Read-only Demo identity/account snapshot. Never submits or checks an order."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5


def main():
    login = int(os.environ["XAUUSD_MT5_LOGIN"])
    server = os.environ["XAUUSD_MT5_SERVER"]
    if not mt5.initialize(
        path=os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"),
        login=login,
        password=os.environ["XAUUSD_MT5_PASSWORD"],
        server=server,
        timeout=60000,
    ):
        raise RuntimeError("MT5 initialization failed")
    try:
        account = mt5.account_info()
        if (
            not account
            or account.login != login
            or account.server != server
            or account.trade_mode != 0
        ):
            raise RuntimeError("Requested Demo identity not verified")
        symbol = mt5.symbol_info("XAUUSDm")
        positions, orders = mt5.positions_get(), mt5.orders_get()
        if symbol is None or positions is None or orders is None:
            raise RuntimeError("Incomplete broker snapshot")
        result = {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "requested_identity_matches": True,
            "demo_verified": True,
            "account": {
                k: getattr(account, k)
                for k in (
                    "balance",
                    "equity",
                    "currency",
                    "leverage",
                    "margin_mode",
                    "margin_free",
                    "trade_allowed",
                    "trade_expert",
                )
            },
            "symbol": "XAUUSDm",
            "open_positions": len(positions),
            "pending_orders": len(orders),
            "symbol_spec": {
                k: getattr(symbol, k)
                for k in (
                    "volume_min",
                    "volume_step",
                    "trade_contract_size",
                    "trade_mode",
                    "trade_stops_level",
                )
            },
            "order_api_called": False,
        }
        Path(os.environ["XAUUSD_PROBE_OUTPUT"]).write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
