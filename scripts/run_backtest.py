#!/usr/bin/env python3
"""
Backtest runner script.
Adapts available M15/H1 CSV data for the SMC backtester.
Uses M15 as a diagnostic proxy when M5 is unavailable; it is not M5-equivalent.

Usage:
    python3 -m scripts.run_backtest
    python3 scripts/run_backtest.py
"""

import csv
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from scripts.smc.backtester import SMCBacktester, format_backtest_summary


def load_csv(filepath: str) -> pd.DataFrame:
    """
    Loads plain MT5 exports (time,open,high,low,close,...) or Yahoo multi-header CSV:
    Row 0: Price,Close,High,Low,Open,Volume  (column names)
    Row 1: Ticker,GC=F,...                    (ticker symbols)
    Data rows have Datetime as index.
    """
    with open(filepath, newline="", encoding="utf-8-sig") as handle:
        columns = next(csv.reader(handle))
    if "time" in columns:
        df = pd.read_csv(filepath)
    else:
        df = pd.read_csv(filepath, header=[0, 1], index_col=0)
        df.columns = [col[0] for col in df.columns]
        df = df.reset_index()
    # Rename to lowercase
    rename_map = {}
    for col in df.columns:
        if col in ("Price", "Datetime") or col == df.columns[0]:
            rename_map[col] = "time"
        else:
            rename_map[col] = col.lower()
    df = df.rename(columns=rename_map)

    df["time"] = pd.to_datetime(df["time"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run XAUUSD SMC Backtest")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with Exness Demo profile ($2,254.16 balance, 30pt spread)",
    )
    parser.add_argument(
        "--small",
        action="store_true",
        help="Run with small-account profile ($100 balance, ADR-020 gate)",
    )
    parser.add_argument("--balance", type=float, default=None, help="Initial account balance")
    parser.add_argument(
        "--risk", type=float, default=None, help="Risk percentage per trade (e.g. 0.01)"
    )
    parser.add_argument(
        "--spread", type=float, default=0.30, help="Spread buffer in dollars (default 0.30)"
    )
    parser.add_argument("--m5", dest="m5_path", default=None, help="M5 CSV path (UTC time,OHLC)")
    parser.add_argument("--h1", dest="h1_path", default=None, help="H1 CSV path")
    parser.add_argument(
        "--window", choices=["development", "holdout", "out_of_range"], default=None
    )
    parser.add_argument("--source-label", default=None)
    parser.add_argument(
        "--proxy", action="store_true", help="Mark feed as proxy (cannot claim EVALUABLE)"
    )
    parser.add_argument("--gold-v2", action="store_true", help="Force GOLD_V2_DEMO risk/TP profile")

    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    from scripts.smc.gold_v2_demo import GOLD_V2_DEMO, count_split_eligible, slice_m5_window

    default_m5 = os.path.join(data_dir, "XAUUSD_M5.csv")
    default_m15 = os.path.join(data_dir, "XAUUSD_M15.csv")
    default_h1 = os.path.join(data_dir, "XAUUSD_H1.csv")
    m5_path = args.m5_path
    h1_path = args.h1_path or default_h1

    if not os.path.exists(h1_path):
        print(f"ERROR: H1 CSV not found: {h1_path}")
        sys.exit(1)

    df_h1 = load_csv(h1_path)
    print(f"H1 data: {len(df_h1)} bars, {df_h1['time'].iloc[0]} to {df_h1['time'].iloc[-1]}")

    is_proxy = bool(args.proxy)
    source_label = args.source_label
    if m5_path:
        if not os.path.exists(m5_path):
            print(f"ERROR: M5 CSV not found: {m5_path}")
            sys.exit(1)
        df_m5 = load_csv(m5_path)
        print(f"M5 data: {len(df_m5)} bars, {df_m5['time'].iloc[0]} to {df_m5['time'].iloc[-1]}")
    elif os.path.exists(default_m5):
        df_m5 = load_csv(default_m5)
        print(f"M5 data: {len(df_m5)} bars")
    elif os.path.exists(default_m15):
        df_m5 = load_csv(default_m15)
        is_proxy = True
        source_label = source_label or "m15_proxy"
        print(
            f"M15 data (used as M5 proxy): {len(df_m5)} bars, {df_m5['time'].iloc[0]} to {df_m5['time'].iloc[-1]}"
        )
        print(
            "DIAGNOSTIC ONLY: M15 proxy, unchanged bar-count windows; not a broker M5 readiness test."
        )

    else:
        print("ERROR: No M5 or M15 data found in data/")
        sys.exit(1)

    if args.window:
        df_m5 = slice_m5_window(df_m5, args.window)
        print(f"Window {args.window}: {len(df_m5)} M5 bars")
        if df_m5.empty:
            print(f"DATA_INSUFFICIENT: no M5 bars in window {args.window}")
            sys.exit(3)

    m5_start = df_m5["time"].iloc[0]
    m5_end = df_m5["time"].iloc[-1]
    h1_before = df_h1[df_h1["time"] < m5_start]
    if len(h1_before) < 200:
        print(
            f"WARNING: Only {len(h1_before)} H1 bars before M5 start. EMA200 may be inaccurate early on."
        )

    print(f"\nDate range: {m5_start.date()} to {m5_end.date()}")
    print(f"Calendar span: {(m5_end - m5_start).days} days\n")

    use_gold = bool(args.gold_v2 or args.m5_path)
    if args.demo and not use_gold:
        balance = args.balance or 2254.16
        risk_pct = args.risk or 0.01
        profile_name = f"EXNESS DEMO PROFILE (${balance:,.2f}, Risk: {risk_pct * 100:.1f}%, Spread: ${args.spread:.2f})"
    elif args.small and not use_gold:
        balance = args.balance or 100.0
        risk_pct = args.risk or 0.01
        profile_name = f"SMALL-ACCOUNT $100 PROFILE (ADR-020 Gate, Risk: {risk_pct * 100:.1f}%, Spread: ${args.spread:.2f})"
    elif use_gold:
        balance = args.balance or 10000.0
        risk_pct = args.risk if args.risk is not None else GOLD_V2_DEMO["risk_pct"]
        profile_name = (
            f"GOLD_V2_DEMO (${balance:,.2f}, Risk: {risk_pct * 100:.1f}%, "
            f"Spread: ${GOLD_V2_DEMO['spread_buffer']:.2f}, window={args.window or 'unlabeled'})"
        )

    else:
        balance = args.balance or 10000.0
        risk_pct = args.risk or 0.005
        profile_name = f"STANDARD BACKTEST (${balance:,.2f}, Risk: {risk_pct * 100:.1f}%, Spread: ${args.spread:.2f})"

    print("=" * 60)
    print(f"RUN: {profile_name}")
    print("=" * 60)

    bt_optimized = SMCBacktester(
        initial_balance=balance,
        risk_pct=risk_pct,
        spread_buffer=GOLD_V2_DEMO["spread_buffer"] if use_gold else args.spread,
        max_sl_cap=GOLD_V2_DEMO["max_sl_cap"],
        contract_size=GOLD_V2_DEMO["contract_size"],
        partial_tp_enabled=GOLD_V2_DEMO["partial_tp_enabled"],
        partial_tp_r=GOLD_V2_DEMO["partial_tp_r"],
        partial_tp_ratio=GOLD_V2_DEMO["partial_tp_ratio"],
        be_trigger_r=1.0,
        extended_killzones=GOLD_V2_DEMO["extended_killzones"],
        tp_r=GOLD_V2_DEMO["tp_r"],
        min_body_ratio=GOLD_V2_DEMO["min_body_ratio"],
        max_sweep_pierce=GOLD_V2_DEMO["max_sweep_pierce"],
        sweep_lookback=GOLD_V2_DEMO["sweep_lookback"],
        max_sweep_to_mss_bars=GOLD_V2_DEMO["max_sweep_to_mss_bars"],
        max_mss_to_fvg_bars=GOLD_V2_DEMO["max_mss_to_fvg_bars"],
        require_choch=GOLD_V2_DEMO["require_choch"],
        is_proxy_feed=is_proxy,
        source_label=source_label,
    )
    summary = bt_optimized.run(df_m5, df_h1)
    print(format_backtest_summary(summary))

    if not summary.trades_df.empty:
        print("\n## Trade Log")
        display_cols = [
            c
            for c in [
                "entry_time",
                "direction",
                "entry_price",
                "sl_price",
                "tp_price",
                "lot_size",
                "exit_time",
                "exit_price",
                "exit_reason",
                "pnl_dollar",
                "pnl_r",
                "balance",
            ]
            if c in summary.trades_df.columns
        ]
        print(summary.trades_df[display_cols].to_string(index=False))
        if "lot_size" in summary.trades_df.columns:
            split_ok, full_only = count_split_eligible(summary.trades_df["lot_size"].tolist())
            print(
                f"\nTwo-tier eligible lots (>=0.02): {split_ok}; full-ticket only (<0.02): {full_only}"
            )

    return summary


if __name__ == "__main__":
    main()
