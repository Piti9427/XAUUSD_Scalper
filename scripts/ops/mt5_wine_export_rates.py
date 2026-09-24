#!/usr/bin/env python3
"""Read-only XAUUSDm M5/H1 export from Wine MT5. Never order_send. Never print passwords."""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


SYMBOL = "XAUUSDm"
HISTORY_START = datetime(2025, 8, 1, tzinfo=timezone.utc)


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


def _rates_to_rows(rates) -> list[dict]:
    if rates is None:
        return []
    rows = []
    for raw in rates:
        ts = datetime.fromtimestamp(int(raw["time"]), tz=timezone.utc)
        volume = 0
        try:
            volume = int(raw["tick_volume"])
        except Exception:
            try:
                volume = int(raw["real_volume"])
            except Exception:
                volume = 0
        rows.append(
            {
                "time": ts,
                "open": float(raw["open"]),
                "high": float(raw["high"]),
                "low": float(raw["low"]),
                "close": float(raw["close"]),
                "volume": int(volume or 0),
            }
        )
    rows.sort(key=lambda row: row["time"])
    return rows


def _classify_bar_clock(*, bar_open: datetime, tick_time: datetime, bar_minutes: int = 5) -> str:
    tick_floor = tick_time.replace(second=0, microsecond=0)
    remainder = tick_floor.minute % bar_minutes
    tick_floor = tick_floor - timedelta(minutes=remainder)
    expected = tick_floor - timedelta(minutes=bar_minutes)
    skew = abs((bar_open - expected).total_seconds())
    if skew > 180:
        return "DATA_BAD_TIMEZONE"
    return "ok"


def _write_ohlc_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["time", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "time": row["time"].isoformat(),
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
            )


def _copy_rates(mt5, symbol: str, timeframe, start: datetime, end: datetime, count: int):
    rates = mt5.copy_rates_range(symbol, timeframe, start, end)
    if rates is not None and len(rates) > 0:
        return rates, "copy_rates_range"
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is not None and len(rates) > 0:
        return rates, "copy_rates_from_pos"
    return None, None


def main() -> int:
    out: dict = {"order_api_called": False, "probe": "export_rates", "symbol": SYMBOL}
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

    repo = _repo_root()
    bar_minutes = 5
    h1_warmup_required = 1000

    import MetaTrader5 as mt5

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
        out["login"] = getattr(info, "login", None)
        out["server"] = getattr(info, "server", None)
        out["balance"] = getattr(info, "balance", None)
        out["equity"] = getattr(info, "equity", None)
        if info is None or info.login != expected_login:
            out["stage"] = "login_mismatch"
            return _emit(out, 1)
        if not mt5.symbol_select(SYMBOL, True):
            out["stage"] = "DATA_INSUFFICIENT_M5"
            out["detail"] = "symbol_select_failed"
            return _emit(out, 1)

        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=2)
        m5_raw, m5_method = _copy_rates(mt5, SYMBOL, mt5.TIMEFRAME_M5, HISTORY_START, end, 80000)
        h1_raw, h1_method = _copy_rates(mt5, SYMBOL, mt5.TIMEFRAME_H1, HISTORY_START, end, 12000)
        out["m5_method"] = m5_method
        out["h1_method"] = h1_method
        m5_rows = _rates_to_rows(m5_raw)
        h1_rows = _rates_to_rows(h1_raw)
        if not m5_rows:
            out["stage"] = "DATA_INSUFFICIENT_M5"
            return _emit(out, 1)
        if not h1_rows:
            out["stage"] = "DATA_INSUFFICIENT_H1"
            return _emit(out, 1)

        bar_delta = timedelta(minutes=bar_minutes)
        m5_rows = [row for row in m5_rows if row["time"] + bar_delta <= now]
        if not m5_rows:
            out["stage"] = "DATA_INSUFFICIENT_M5"
            out["detail"] = "all_bars_forming"
            return _emit(out, 1)

        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is None or not getattr(tick, "time", None):
            out["stage"] = "DATA_BAD_TIMEZONE"
            out["detail"] = "tick_missing"
            return _emit(out, 1)
        tick_time = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
        clock = _classify_bar_clock(
            bar_open=m5_rows[-1]["time"],
            tick_time=tick_time,
            bar_minutes=bar_minutes,
        )
        out["clock"] = clock
        out["last_m5"] = m5_rows[-1]["time"].isoformat()
        out["tick_time"] = tick_time.isoformat()
        out["m5_bars"] = len(m5_rows)
        out["h1_bars"] = len(h1_rows)
        out["m5_start"] = m5_rows[0]["time"].isoformat()
        out["m5_end"] = m5_rows[-1]["time"].isoformat()
        out["h1_warmup_ok"] = bool(len(h1_rows) >= h1_warmup_required)

        dest = repo / "data" / "exness-demo"
        dest.mkdir(parents=True, exist_ok=True)
        m5_path = dest / "XAUUSDm_M5.csv"
        h1_path = dest / "XAUUSDm_H1.csv"
        meta_path = dest / "export_meta.json"
        _write_ohlc_csv(m5_path, m5_rows)
        _write_ohlc_csv(h1_path, h1_rows)
        meta = dict(out)
        meta["m5_path"] = str(m5_path)
        meta["h1_path"] = str(h1_path)
        meta["h1_warmup_bars_required"] = h1_warmup_required
        meta_path.write_text(
            json.dumps(meta, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        out["m5_path"] = str(m5_path)
        out["h1_path"] = str(h1_path)
        if clock != "ok":
            out["stage"] = clock
            return _emit(out, 1)
        out["stage"] = "export_ok"
        return _emit(out, 0)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    sys.exit(main())
