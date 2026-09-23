"""Read-only, bounded Exness Demo real-tick capture for BotTradeGold research.

Run under the Python environment connected to the target MT5 terminal. This
module never submits an order. A capture is immutable and never qualifies a
strategy by itself.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utc_time(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be timezone-aware UTC")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _positive(value) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("invalid broker symbol specification")
    return number


def capture(mt5, *, start: datetime, end: datetime, freeze_at: datetime,
            symbol: str, expected_login: int, expected_server: str,
            output: Path) -> dict:
    """Capture one UTC day at most; caller owns MT5 initialize/shutdown."""
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0)
           for value in (start, end, freeze_at)):
        raise ValueError("capture times must be timezone-aware UTC")
    if start < freeze_at or not start < end or end - start > timedelta(days=1):
        raise ValueError("invalid post-freeze capture window")
    if output.exists():
        raise FileExistsError(output)
    account = mt5.account_info()
    if account is None or int(account.login) != expected_login:
        raise ValueError("target Demo account login mismatch")
    if str(account.server) != expected_server:
        raise ValueError("target Demo account server mismatch")
    if int(account.trade_mode) != int(getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)):
        raise ValueError("target account is not Demo")
    if str(account.currency) != "USD":
        raise ValueError("target account currency is not USD")
    if not all(math.isfinite(float(value)) and float(value) > 0
               for value in (account.balance, account.equity)):
        raise ValueError("invalid target account balance/equity")
    info = mt5.symbol_info(symbol)
    if info is None or str(info.name) != symbol or "XAUUSD" not in symbol:
        raise ValueError("target gold symbol mismatch")
    specification = {
        "contract_size": _positive(info.trade_contract_size),
        "volume_min": _positive(info.volume_min),
        "volume_step": _positive(info.volume_step),
        "volume_max": _positive(info.volume_max),
        "point": _positive(info.point),
        "trade_tick_size": _positive(info.trade_tick_size),
        "trade_tick_value": _positive(info.trade_tick_value),
    }
    if specification["volume_max"] < specification["volume_min"]:
        raise ValueError("invalid broker volume bounds")
    ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        raise ValueError("no broker real ticks returned")
    names = tuple(ticks.dtype.names or ())
    if not {"time_msc", "bid", "ask", "flags"}.issubset(names):
        raise ValueError("real ticks lack required Bid/Ask/time fields")
    times = [int(row["time_msc"]) for row in ticks]
    lo = int(start.timestamp() * 1000)
    hi = int(end.timestamp() * 1000)
    if any(time < lo or time > hi for time in times) or any(
        later < earlier for earlier, later in zip(times, times[1:])
    ):
        raise ValueError("out-of-window or unordered broker ticks")
    for row in ticks:
        bid, ask = float(row["bid"]), float(row["ask"])
        if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid:
            raise ValueError("invalid or crossed broker Bid/Ask tick")

    output.mkdir(parents=True)
    tick_file = output / "ticks.csv.gz"
    with gzip.open(tick_file, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(names)
        for row in ticks:
            writer.writerow([row[name].item() if hasattr(row[name], "item") else row[name]
                             for name in names])
    manifest = {
        "schema": "btg-shadow-ticks-v1",
        "status": "captured_research_only",
        "order_api_called": False,
        "source": "MetaTrader5.copy_ticks_range(COPY_TICKS_ALL)",
        "code_sha256": sha256(Path(__file__)),
        "freeze_at": freeze_at.isoformat(),
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "first_tick_msc": times[0],
        "last_tick_msc": times[-1],
        "tick_count": len(times),
        "fields": list(names),
        "tick_file": tick_file.name,
        "tick_sha256": sha256(tick_file),
        "account": {
            "login": expected_login,
            "server": str(account.server),
            "currency": str(account.currency),
            "trade_mode": int(account.trade_mode),
            "margin_mode": int(account.margin_mode),
            "balance": float(account.balance),
            "equity": float(account.equity),
        },
        "symbol": symbol,
        "symbol_specification": specification,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "COMPLETE").write_text("Captured real ticks; research only.\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=utc_time, required=True)
    parser.add_argument("--end", type=utc_time, required=True)
    parser.add_argument("--freeze-at", type=utc_time, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    login = os.environ.get("XAUUSD_MT5_LOGIN") or os.environ.get("MT5_LOGIN")
    password = os.environ.get("XAUUSD_MT5_PASSWORD") or os.environ.get("MT5_PASSWORD")
    server = os.environ.get("XAUUSD_MT5_SERVER") or os.environ.get("MT5_SERVER")
    if not login or not password or not server:
        parser.error("target MT5 Demo credentials are missing from environment")
    import MetaTrader5 as mt5

    terminal = os.environ.get("MT5_TERMINAL_PATH")
    kwargs = {"login": int(login), "password": password, "server": server}
    if terminal:
        kwargs["path"] = terminal
    if not mt5.initialize(**kwargs):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()[0]}")
    try:
        result = capture(
            mt5, start=args.start, end=args.end, freeze_at=args.freeze_at,
            symbol=args.symbol, expected_login=int(login),
            expected_server=server, output=args.output,
        )
    finally:
        mt5.shutdown()
    print(json.dumps({key: result[key] for key in
                      ("status", "symbol", "tick_count", "tick_sha256", "order_api_called")}))


if __name__ == "__main__":
    main()
