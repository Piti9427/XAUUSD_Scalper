"""Read the currently logged-in MT5 terminal and export closed bars; never trade."""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd


def inspect_terminal(mt5, symbol, start, end, output_dir):
    if not mt5.initialize():
        raise RuntimeError("MT5_INITIALIZE_FAILED")
    try:
        account = mt5.account_info()
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        positions, orders = mt5.positions_get(), mt5.orders_get()
        if account is None or info is None or tick is None or positions is None or orders is None:
            raise RuntimeError("MT5_READ_FAILED: account, symbol, tick, positions or orders unavailable")
        frames = {}
        for label, timeframe, minutes in (("M5", mt5.TIMEFRAME_M5, 5), ("H1", mt5.TIMEFRAME_H1, 60)):
            # Include H1 warmup and previous-day liquidity before the requested interval.
            rates = mt5.copy_rates_range(symbol, timeframe, start - timedelta(days=30), end)
            if rates is None or len(rates) == 0:
                raise RuntimeError(f"NO_HISTORY_{label}")
            frame = pd.DataFrame(rates)
            frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
            frame = frame[frame.time + pd.Timedelta(minutes=minutes) <= end]
            frame = frame.sort_values("time").reset_index(drop=True)
            if frame.empty or frame.time.duplicated().any():
                raise RuntimeError(f"INVALID_HISTORY_{label}")
            frames[label] = frame
        result = {
            "status": "READ_ONLY_SNAPSHOT", "live_ready": False,
            "captured_utc": datetime.now(timezone.utc).isoformat(),
            "account_fingerprint": sha256(f"{account.server}:{account.login}".encode()).hexdigest()[:16],
            "server": account.server, "trade_mode": account.trade_mode,
            "currency": account.currency, "balance": account.balance, "equity": account.equity,
            "symbol": symbol, "point": info.point, "digits": info.digits,
            "contract_size": info.trade_contract_size, "volume_min": info.volume_min,
            "volume_step": info.volume_step, "volume_max": info.volume_max,
            "bid": tick.bid, "ask": tick.ask, "spread_price": tick.ask - tick.bid,
            "tick_utc": datetime.fromtimestamp(tick.time, timezone.utc).isoformat(),
            "open_positions": len(positions), "pending_orders": len(orders),
            "requested_start": start.isoformat(), "requested_end": end.isoformat(),
            "history": {},
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        for label, frame in frames.items():
            path = output_dir / f"XAUUSD_{label}.csv"
            frame.to_csv(path, index=False)
            result["history"][label] = {
                "file": path.name, "sha256": sha256(path.read_bytes()).hexdigest(),
                "bars": len(frame), "first": frame.time.iloc[0].isoformat(),
                "last": frame.time.iloc[-1].isoformat(),
                "warmup_bars": int((frame.time < start).sum()),
                "requested_boundaries_covered": bool(frame.time.iloc[0] <= start and
                                                frame.time.iloc[-1] + pd.Timedelta(minutes=5 if label == "M5" else 60) >= end),
            }
        (output_dir / "snapshot.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        mt5.shutdown()


def utc_date(value):
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--start", type=utc_date, required=True, help="UTC YYYY-MM-DD")
    parser.add_argument("--end", type=utc_date, required=True, help="UTC exclusive YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.start >= args.end or args.end > datetime.now(timezone.utc):
        parser.error("Require start < end <= now")
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print(json.dumps({"status": "BLOCKED", "reason": "METATRADER5_UNAVAILABLE", "live_ready": False}))
        return 2
    try:
        print(json.dumps(inspect_terminal(mt5, args.symbol, args.start, args.end, args.output_dir), indent=2))
    except RuntimeError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "live_ready": False}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
