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
    parser.add_argument("--demo", action="store_true", help="Run with Exness Demo profile ($2,254.16 balance, 30pt spread)")
    parser.add_argument("--small", action="store_true", help="Run with small-account profile ($100 balance, ADR-020 gate)")
    parser.add_argument("--balance", type=float, default=None, help="Initial account balance")
    parser.add_argument("--risk", type=float, default=None, help="Risk percentage per trade (e.g. 0.01)")
    parser.add_argument("--spread", type=float, default=0.30, help="Spread buffer in dollars (default 0.30)")
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

    # Check for M5 data first, fall back to M15
    m5_path = os.path.join(data_dir, "XAUUSD_M5.csv")
    m15_path = os.path.join(data_dir, "XAUUSD_M15.csv")
    h1_path = os.path.join(data_dir, "XAUUSD_H1.csv")

    if not os.path.exists(h1_path):
        print("ERROR: XAUUSD_H1.csv not found in data/")
        sys.exit(1)

    df_h1 = load_csv(h1_path)
    print(f"H1 data: {len(df_h1)} bars, {df_h1['time'].iloc[0]} to {df_h1['time'].iloc[-1]}")

    if os.path.exists(m5_path):
        df_m5 = load_csv(m5_path)
        print(f"M5 data: {len(df_m5)} bars")
    elif os.path.exists(m15_path):
        # Use M15 as proxy — backtester uses bar-by-bar simulation
        # Bar-count windows retain their configured values; this is not M5 parity.
        df_m5 = load_csv(m15_path)
        print(f"M15 data (used as M5 proxy): {len(df_m5)} bars, {df_m5['time'].iloc[0]} to {df_m5['time'].iloc[-1]}")
        print("DIAGNOSTIC ONLY: M15 proxy, unchanged bar-count windows; not a broker M5 readiness test.")
    else:
        print("ERROR: No M5 or M15 data found in data/")
        sys.exit(1)

    # Filter H1 to overlap with M5/M15 date range
    m5_start = df_m5["time"].iloc[0]
    m5_end = df_m5["time"].iloc[-1]
    h1_before = df_h1[df_h1["time"] < m5_start]
    if len(h1_before) < 200:
        print(f"WARNING: Only {len(h1_before)} H1 bars before M5 start. EMA200 may be inaccurate early on.")

    print(f"\nDate range: {m5_start.date()} to {m5_end.date()}")
    print(f"Calendar span: {(m5_end - m5_start).days} days\n")

    # Determine profile parameters
    if args.demo:
        balance = args.balance or 2254.16
        risk_pct = args.risk or 0.01
        profile_name = f"EXNESS DEMO PROFILE (${balance:,.2f}, Risk: {risk_pct*100:.1f}%, Spread: ${args.spread:.2f})"
    elif args.small:
        balance = args.balance or 100.0
        risk_pct = args.risk or 0.01
        profile_name = f"SMALL-ACCOUNT $100 PROFILE (ADR-020 Gate, Risk: {risk_pct*100:.1f}%, Spread: ${args.spread:.2f})"
    else:
        balance = args.balance or 10000.0
        risk_pct = args.risk or 0.005
        profile_name = f"STANDARD BACKTEST (${balance:,.2f}, Risk: {risk_pct*100:.1f}%, Spread: ${args.spread:.2f})"

    print("=" * 60)
    print(f"RUN: {profile_name}")
    print("=" * 60)

    bt_optimized = SMCBacktester(
        initial_balance=balance,
        risk_pct=risk_pct,
        spread_buffer=args.spread,
        max_sl_cap=25.00,
        contract_size=100.0,
        partial_tp_enabled=True,
        partial_tp_r=1.0,
        partial_tp_ratio=0.5,
        be_trigger_r=1.0,
        extended_killzones=True,
        tp_r=2.5,
        min_body_ratio=0.45,
        max_sweep_pierce=8.0,
        sweep_lookback=25,
        max_sweep_to_mss_bars=8,
        max_mss_to_fvg_bars=4,
    )
    summary = bt_optimized.run(df_m5, df_h1)
    print(format_backtest_summary(summary))

    if not summary.trades_df.empty:
        print("\n## Trade Log")
        display_cols = [c for c in ["entry_time", "direction", "entry_price", "sl_price", "tp_price", "lot_size", "exit_time", "exit_price", "exit_reason", "pnl_dollar", "pnl_r", "balance"] if c in summary.trades_df.columns]
        print(summary.trades_df[display_cols].to_string(index=False))

    return summary


if __name__ == "__main__":
    main()
