"""Read-only Exness XAUUSDm history coverage probe; no trading calls."""

import json
import os
from datetime import datetime, timedelta, timezone
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
        raise RuntimeError("MT5 initialize failed")
    try:
        account = mt5.account_info()
        symbol = mt5.symbol_info("XAUUSDm")
        if (
            not account
            or account.login != login
            or account.server != server
            or account.trade_mode != 0
        ):
            raise RuntimeError("Requested Demo identity mismatch")
        if symbol is None:
            raise RuntimeError("XAUUSDm unavailable")
        start = datetime(2026, 3, 28, tzinfo=timezone.utc)
        end = datetime(2026, 9, 28, tzinfo=timezone.utc)
        current = start
        probes = []
        while current < end:
            stop = min(current + timedelta(days=7), end)
            ticks = mt5.copy_ticks_range(
                "XAUUSDm", current, stop - timedelta(milliseconds=1), mt5.COPY_TICKS_ALL
            )
            if ticks is None:
                raise RuntimeError(f"copy_ticks_range failed for {current.date()}")
            probes.append(
                {
                    "start_utc": current.isoformat(),
                    "end_exclusive_utc": stop.isoformat(),
                    "ticks": len(ticks),
                    "first_utc": datetime.fromtimestamp(
                        int(ticks[0]["time_msc"]) / 1000, timezone.utc
                    ).isoformat()
                    if len(ticks)
                    else None,
                    "last_utc": datetime.fromtimestamp(
                        int(ticks[-1]["time_msc"]) / 1000, timezone.utc
                    ).isoformat()
                    if len(ticks)
                    else None,
                }
            )
            print(json.dumps(probes[-1]), flush=True)
            current = stop
        result = {
            "account_identity_verified": True,
            "demo": True,
            "balance": account.balance,
            "equity": account.equity,
            "currency": account.currency,
            "symbol": "XAUUSDm",
            "volume_min": symbol.volume_min,
            "volume_step": symbol.volume_step,
            "trade_contract_size": symbol.trade_contract_size,
            "leverage": account.leverage,
            "margin_mode": account.margin_mode,
            "requested_start_utc": start.isoformat(),
            "requested_end_exclusive_utc": end.isoformat(),
            "probes": probes,
            "order_api_called": False,
        }
        Path(os.environ["XAUUSD_PROBE_OUTPUT"]).write_text(json.dumps(result, indent=2))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
