"""Versioned B1/D reconstruction replay on broker M5 OHLC; never sends orders.

Historical Ask is unavailable in the legacy export. Every spread input is an
explicit scenario; output cannot qualify a strategy or establish account return.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .engine import Costs, metrics, simulate
from .strategies import registry, signals, wilder

VERSION = "b1-d-reconstruction-v1.0.0"


def load_broker_m5(path):
    raw = pd.read_csv(path)
    index = pd.to_datetime(raw.time, utc=True)
    if index.duplicated().any() or not index.is_monotonic_increasing:
        raise ValueError("duplicate or unordered broker bars")
    # UTC offset must be explicit in source; parsing naive values as UTC is forbidden.
    if not raw.time.str.contains(r"(?:Z|\+00:00)$", regex=True).all():
        raise ValueError("source timestamps must explicitly identify UTC")
    frame = raw[["open", "high", "low", "close"]].astype(float)
    frame.index = pd.DatetimeIndex(index)
    if not np.isfinite(frame.to_numpy()).all() or (frame <= 0).any().any():
        raise ValueError("invalid broker prices")
    if (
        (frame.high < frame[["open", "close"]].max(axis=1))
        | (frame.low > frame[["open", "close"]].min(axis=1))
    ).any():
        raise ValueError("invalid OHLC geometry")
    if not ((frame.index.minute % 5 == 0) & (frame.index.second == 0)).all():
        raise ValueError("M5 timestamps not aligned")
    return frame


def m15_features(m5):
    grouped = m5.resample("15min", label="left", closed="left")
    f = grouped.agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    f = f.loc[grouped.close.count() == 3].dropna()
    prior = f.close.shift()
    tr = pd.concat([f.high - f.low, (f.high - prior).abs(), (f.low - prior).abs()], axis=1).max(
        axis=1
    )
    f["atr"] = wilder(tr)
    delta = f.close.diff().fillna(0)
    gain, loss = wilder(delta.clip(lower=0)), wilder(-delta.clip(upper=0))
    f["rsi"] = 100 - 100 / (1 + gain / loss)
    f.loc[(loss == 0) & (gain > 0), "rsi"] = 100
    f.loc[(loss == 0) & (gain == 0), "rsi"] = 50
    f["body"] = (f.close - f.open).abs() / (f.high - f.low).replace(0, np.nan)
    f["fvg_up"], f["fvg_down"] = f.low - f.high.shift(2), f.low.shift(2) - f.high
    adjacent = f.index.to_series().diff(2).eq(pd.Timedelta(minutes=30))
    f.loc[~adjacent, ["fvg_up", "fvg_down"]] = np.nan
    # Handoff forbids an unvalidated regime router. Native risk, all regimes.
    f["regime"] = "all"
    return f


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/exness-demo/XAUUSDm_M5.csv"))
    parser.add_argument("--meta", type=Path, default=Path("data/exness-demo/export_meta.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spreads", type=float, nargs="+", default=[0.0, 0.3, 0.6, 1.0])
    args = parser.parse_args()
    if any(not np.isfinite(s) or s < 0 for s in args.spreads):
        parser.error("spreads must be finite and nonnegative")
    meta = json.loads(args.meta.read_text())
    if (
        meta.get("server") != "Exness-MT5Trial7"
        or meta.get("symbol") != "XAUUSDm"
        or meta.get("clock") != "ok"
    ):
        raise ValueError("broker export identity/clock mismatch")
    m5 = load_broker_m5(args.data)
    f = m15_features(m5)
    specs = [
        replace(s, name=name, reconstruction=True)
        for s, name in [
            (next(s for s in registry() if s.name == "B_Donchian30_RSI"), "B1_reconstructed"),
            (next(s for s in registry() if s.name == "D_ATR1.5_RSI_FVG"), "D_reconstructed"),
        ]
    ]
    final_output = args.output
    if final_output.exists():
        raise FileExistsError(final_output)
    args.output = final_output.with_name(final_output.name + ".partial")
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "version": VERSION,
        "environment": "BACKTEST",
        "provider": "Exness Demo legacy export",
        "execution": "M5 OHLC conservative stop-first; next exact M5 open; no tick path",
        "period": [str(m5.index.min()), str(m5.index.max())],
        "m5_bars": len(m5),
        "m15_bars": len(f),
        "strategies": [asdict(s) for s in specs],
        "regime_router": False,
        "spread_scenarios": args.spreads,
        "exposure": "fixed 1 oz; NOT broker lot/account-sized",
        "unmeasured": ["historical Ask", "commission", "swap", "slippage", "broker sizing/margin"],
        "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "meta_sha256": hashlib.sha256(args.meta.read_bytes()).hexdigest(),
        "code_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                Path(__file__),
                Path(__file__).with_name("strategies.py"),
                Path(__file__).with_name("engine.py"),
            ]
        },
        "production_ready": False,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rows = []
    for spread in args.spreads:
        quotes = m5.add_prefix("bid_").join((m5 + spread).add_prefix("ask_"))
        for spec in specs:
            sig = signals(f, spec)
            trades, dd = simulate(quotes, f, sig, spec, Costs(), native=True)
            trades.to_csv(args.output / f"{spec.name}_spread_{spread:g}.csv", index=False)
            rows.append(
                {
                    "strategy": spec.name,
                    "spread": spread,
                    "raw_signals": int(sig.direction.ne(0).sum()),
                    **metrics(trades, dd),
                }
            )
    result = pd.DataFrame(rows)
    result.to_csv(args.output / "summary.csv", index=False)
    for path in args.output.glob("*.csv"):
        if path.stat().st_size == 0:
            raise RuntimeError(f"FAILED_REPORT: empty {path}")
        columns = pd.read_csv(path, nrows=0).columns
        required = (
            {"strategy", "trades", "net"}
            if path.name == "summary.csv"
            else {"signal_time", "entry_time", "net", "r"}
        )
        if not required.issubset(columns):
            raise RuntimeError(f"FAILED_REPORT: schema {path}")
    (args.output / "COMPLETE").write_text(
        "Completed exploratory broker M5 proxy only; not real-tick or account validation.\n"
    )
    args.output.rename(final_output)
    print(
        result[["strategy", "spread", "trades", "net", "total_r", "pf", "max_equity_dd"]].to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
