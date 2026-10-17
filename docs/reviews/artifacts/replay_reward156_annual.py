"""
Replay Reward156 on the 1-year annual archive (2025-10-01 to 2026-10-01)
to measure full annual performance under base and stress costs.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

from scripts.research.public_exness_archive import load_discovery
from scripts.research.campaign_signals import candidate_frame
from scripts.research.breakout_logic import Costs, Rules, replay

ANNUAL_DATASET = Path("data/b1_public_exness_2025_10_2026_09")
START = pd.Timestamp("2025-10-01T00:00:00+00:00")
HALFWAY = pd.Timestamp("2026-04-01T00:00:00+00:00")
END = pd.Timestamp("2026-10-01T00:00:00+00:00")

BASE_COST = Costs()
STRESS_COST = Costs(extra_spread=0.20, slippage=0.10)

def main():
    print("Loading annual discovery dataset...")
    frame, ticks, broker, audit = load_discovery(ANNUAL_DATASET)
    print(f"Loaded {len(frame)} bars and {len(ticks[1])} ticks.")

    # Prepare Reward156 candidate signals
    # RSI7 BUY (threshold 35, trend_span 50) + D48 SELL
    print("Preparing Reward156 candidate signals...")
    base_frame = frame.copy()
    base_frame["direction"] = np.where(base_frame.close < base_frame.low.rolling(48).min().shift(1), -1, 0)
    base_frame["hh"] = base_frame.high.rolling(48).max().shift(1)
    base_frame["ll"] = base_frame.low.rolling(48).min().shift(1)

    signals = candidate_frame(
        base_frame,
        buy_filter="off",
        depth=0.0,
        oscillator_spec=dict(period=7, threshold=35, trend_span=50, side="buy"),
    )

    rules = Rules(
        buy_pause_drawdown=0.05,
        daily_loss_limit=0.2,
        target_rr=1.35,
        protect_mode="off",
        protect_after_r=1.0,
    )

    print("\nRunning Replay across all windows...")
    windows = [
        ("Full Base", START, END, BASE_COST),
        ("Full Stress", START, END, STRESS_COST),
        ("First Half Base", START, HALFWAY, BASE_COST),
        ("First Half Stress", START, HALFWAY, STRESS_COST),
        ("Second Half Base", HALFWAY, END, BASE_COST),
        ("Second Half Stress", HALFWAY, END, STRESS_COST),
    ]

    for label, w_start, w_end, cost in windows:
        result = replay(signals, ticks, broker, rules, cost, start=w_start, end=w_end)
        ledger = result.get("ledger", [])
        trades = len(ledger)
        buys = sum(1 for t in ledger if t.get("direction") == 1 or t.get("side") == "BUY")
        sells = sum(1 for t in ledger if t.get("direction") == -1 or t.get("side") == "SELL")
        net = result.get("net_usd", 0.0)
        dd = result.get("max_dd_pct", 0.0)
        wr = result.get("win_rate", 0.0)
        rr = result.get("realized_rr", 0.0)
        print(f"[{label:18}] Net: ${net:8.2f} | DD: {dd:5.2f}% | WR: {wr*100:5.2f}% | RR: {rr:6.4f} | Trades: {trades:3} (BUY:{buys} SELL:{sells})")

if __name__ == "__main__":
    main()
