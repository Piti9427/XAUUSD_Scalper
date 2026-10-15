"""Read-only target Demo historical capture; no order_send."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import MetaTrader5 as mt5


def main():
    output = Path(os.environ["XAUUSD_PROBE_OUTPUT"])
    output.mkdir(parents=True, exist_ok=False)
    login = int(os.environ["XAUUSD_MT5_LOGIN"])
    server = os.environ["XAUUSD_MT5_SERVER"]
    if not mt5.initialize(
        path=os.getenv("MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"),
        login=login,
        password=os.environ["XAUUSD_MT5_PASSWORD"],
        server=server,
        timeout=60000,
    ):
        raise RuntimeError(f"initialize failed {mt5.last_error()}")
    try:
        a = mt5.account_info()
        if not (
            a
            and a.login == login
            and a.server == server
            and a.trade_mode == 0
            and a.currency == "USD"
        ):
            raise RuntimeError("target Demo identity mismatch")
        s = mt5.symbol_info("XAUUSDm")
        if s is None:
            raise RuntimeError("target symbol missing")
        start = datetime.fromisoformat(
            os.environ.get("XAUUSD_CAPTURE_START", "2026-09-01T00:00:00+00:00")
        )
        end = datetime.fromisoformat(
            os.environ.get("XAUUSD_CAPTURE_END", "2026-09-26T00:00:00+00:00")
        )
        if (
            any(t.tzinfo is None or t.utcoffset() != timedelta(0) for t in (start, end))
            or not start < end
        ):
            raise ValueError("capture requires increasing aware UTC bounds")
        rates = mt5.copy_rates_range("XAUUSDm", mt5.TIMEFRAME_M1, start - timedelta(days=31), end)
        if rates is None or not len(rates):
            rates = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M1, 0, 80000)
        if rates is None or not len(rates):
            raise RuntimeError("M1 history missing")
        np.savez_compressed(output / "m1.npz", rates=rates)
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "target_demo_verified": True,
            "order_api_called": False,
            "server": server,
            "symbol": "XAUUSDm",
            "account": {
                k: getattr(a, k)
                for k in ("balance", "equity", "currency", "leverage", "margin_mode")
            },
            "symbol_spec": {
                k: getattr(s, k)
                for k in (
                    "trade_contract_size",
                    "trade_tick_size",
                    "trade_tick_value",
                    "volume_min",
                    "volume_step",
                    "volume_max",
                    "point",
                    "digits",
                    "trade_stops_level",
                    "swap_long",
                    "swap_short",
                    "swap_mode",
                    "swap_rollover3days",
                )
            },
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "m1_rows": len(rates),
            "days": [],
            "historical_costs_measured": False,
        }
        day = start
        while day < end:
            next_day = day + timedelta(days=1)
            ticks = mt5.copy_ticks_range(
                "XAUUSDm",
                day,
                next_day,
                mt5.COPY_TICKS_ALL,
            )
            if ticks is None:
                raise RuntimeError(f"ticks failed {day.date()} {mt5.last_error()}")
            start_ms = int(day.timestamp() * 1000)
            end_ms = int(next_day.timestamp() * 1000)
            # MT5 Python dates have second precision. Query through next UTC
            # midnight, then filter by time_msc to retain the final second.
            within_day = ticks[(ticks["time_msc"] >= start_ms) & (ticks["time_msc"] < end_ms)]
            valid = within_day[(within_day["bid"] > 0) & (within_day["ask"] >= within_day["bid"])]
            if len(valid) != len(within_day):
                raise RuntimeError("invalid/crossed quotes")
            path = output / f"{day:%Y-%m-%d}.npz"
            np.savez_compressed(
                path, time_msc=valid["time_msc"], bid=valid["bid"], ask=valid["ask"]
            )
            manifest["days"].append(
                {
                    "day": str(day.date()),
                    "ticks": len(valid),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
            print(json.dumps({"day": str(day.date()), "ticks": len(valid)}), flush=True)
            day = next_day
        manifest["m1_sha256"] = hashlib.sha256((output / "m1.npz").read_bytes()).hexdigest()
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (output / "COMPLETE").write_text("Read-only broker historical capture completed.\n")
        print(
            json.dumps(
                {"stage": "capture_complete", "ticks": sum(d["ticks"] for d in manifest["days"])}
            ),
            flush=True,
        )
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
