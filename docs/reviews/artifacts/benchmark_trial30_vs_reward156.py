"""
Exact Paired Head-to-Head Benchmark: Trial30 vs Reward156
Under 100% Identical Conditions, Data, and Cost Models.

Dataset 1: 6-Month Discovery Tape (2026-03-28 to 2026-09-28)
Dataset 2: 1-Year Annual Archive (2025-10-01 to 2026-10-01)
Starting Balance: $200.00
Sizing: Fixed 0.01 Lot
Risk Cap: 10% of current equity
Daily Loss Limit: 20% UTC
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

from scripts.research.public_exness_archive import load_discovery
from scripts.research.tune_breakout_logic import load_data
from scripts.research.campaign_signals import candidate_frame
from scripts.research.breakout_logic import Costs, Rules, replay

ANNUAL_DATASET = Path("data/b1_public_exness_2025_10_2026_09")
SIX_MO_DATASET = Path("data/b1_hybrid_exness_6mo_fixed_2026_09_28")

BASE_COST = Costs()
STRESS_COST = Costs(extra_spread=0.20, slippage=0.10)


def run_benchmark_on_dataset(dataset_path, start_ts, end_ts, label_prefix):
    print(f"\n{'='*70}\n[DATASET: {label_prefix}]\n{'='*70}")
    if dataset_path == SIX_MO_DATASET:
        frame, ticks, broker, audit = load_data()
    else:
        frame, ticks, broker, audit = load_discovery(dataset_path)
    print(f"Loaded {len(frame)} M15 bars, {len(ticks[1]):,} raw ticks.")

    # Base frame for signals
    base_frame = frame.copy()
    base_frame["direction"] = np.where(base_frame.close < base_frame.low.rolling(48).min().shift(1), -1, 0)
    base_frame["hh"] = base_frame.high.rolling(48).max().shift(1)
    base_frame["ll"] = base_frame.low.rolling(48).min().shift(1)

    # 1. Trial30 Signals: Pure D48 SELL-only
    t30_signals = base_frame.copy()
    t30_rules = Rules(
        target_atr=3.0,
        stop_atr=2.5,
        protect_mode="break_even",
        protect_after_r=1.0,
        daily_loss_limit=0.20,
        risk_cap=0.10,
    )

    # 2. Reward156 Signals: RSI7 BUY + D48 SELL
    r156_signals = candidate_frame(
        base_frame,
        buy_filter="off",
        depth=0.0,
        oscillator_spec=dict(period=7, threshold=35, trend_span=50, side="buy"),
    )
    r156_rules = Rules(
        buy_pause_drawdown=0.05,
        daily_loss_limit=0.20,
        target_rr=1.35,
        protect_mode="off",
        protect_after_r=1.0,
        risk_cap=0.10,
    )

    scenarios = [
        ("Base Spread", BASE_COST),
        ("Stress (+0.20 spr, +0.10 slip)", STRESS_COST),
    ]

    results = []

    for cost_label, cost_model in scenarios:
        # Run Trial30
        res_t30 = replay(t30_signals, ticks, broker, t30_rules, cost_model, start=start_ts, end=end_ts)
        l_t30 = res_t30.get("ledger", [])
        buys_t30 = sum(1 for t in l_t30 if t.get("direction") == 1 or t.get("side") == "BUY")
        sells_t30 = sum(1 for t in l_t30 if t.get("direction") == -1 or t.get("side") == "SELL")

        # Run Reward156
        res_r156 = replay(r156_signals, ticks, broker, r156_rules, cost_model, start=start_ts, end=end_ts)
        l_r156 = res_r156.get("ledger", [])
        buys_r156 = sum(1 for t in l_r156 if t.get("direction") == 1 or t.get("side") == "BUY")
        sells_r156 = sum(1 for t in l_r156 if t.get("direction") == -1 or t.get("side") == "SELL")

        entry = {
            "window": label_prefix,
            "cost_model": cost_label,
            "trial30": {
                "net_usd": round(res_t30.get("net_usd", 0.0), 2),
                "max_dd_pct": round(res_t30.get("max_dd_pct", 0.0), 2),
                "win_rate": round(res_t30.get("win_rate", 0.0) * 100, 2),
                "realized_rr": round(res_t30.get("realized_rr") or 0.0, 4),
                "trades": len(l_t30),
                "buy_trades": buys_t30,
                "sell_trades": sells_t30,
            },
            "reward156": {
                "net_usd": round(res_r156.get("net_usd", 0.0), 2),
                "max_dd_pct": round(res_r156.get("max_dd_pct", 0.0), 2),
                "win_rate": round(res_r156.get("win_rate", 0.0) * 100, 2),
                "realized_rr": round(res_r156.get("realized_rr") or 0.0, 4),
                "trades": len(l_r156),
                "buy_trades": buys_r156,
                "sell_trades": sells_r156,
            }
        }
        results.append(entry)

        # Print Side-by-Side Comparison
        t30 = entry["trial30"]
        r156 = entry["reward156"]
        net_diff = r156["net_usd"] - t30["net_usd"]
        dd_diff = r156["max_dd_pct"] - t30["max_dd_pct"]

        print(f"\n--- Scenario: {label_prefix} [{cost_label}] ---")
        print(f"{'Metric':<20} | {'Trial30 (Demo)':<18} | {'Reward156 (Challenger)':<22} | {'Difference':<15}")
        print(f"{'-'*20}-+-{'-'*18}-+-{'-'*22}-+-{'-'*15}")
        print(f"{'Net Profit ($)':<20} | ${t30['net_usd']:<17.2f} | ${r156['net_usd']:<21.2f} | {net_diff:+14.2f}")
        print(f"{'Max Drawdown (%)':<20} | {t30['max_dd_pct']:<17.2f}% | {r156['max_dd_pct']:<21.2f}% | {dd_diff:+14.2f}%")
        print(f"{'Win Rate (%)':<20} | {t30['win_rate']:<17.2f}% | {r156['win_rate']:<21.2f}% | {r156['win_rate']-t30['win_rate']:+14.2f}%")
        print(f"{'Realized RR':<20} | {t30['realized_rr']:<18.4f} | {r156['realized_rr']:<22.4f} | {r156['realized_rr']-t30['realized_rr']:+14.4f}")
        print(f"{'Total Trades':<20} | {t30['trades']:<18} | {r156['trades']:<22} | {r156['trades']-t30['trades']:+14}")
        print(f"{'BUY Trades':<20} | {t30['buy_trades']:<18} | {r156['buy_trades']:<22} | {r156['buy_trades']-t30['buy_trades']:+14}")
        print(f"{'SELL Trades':<20} | {t30['sell_trades']:<18} | {r156['sell_trades']:<22} | {r156['sell_trades']-t30['sell_trades']:+14}")

    return results


def main():
    all_results = []

    # 1. 6-Month Full Window (2026-03-28 to 2026-09-28)
    START_6M = pd.Timestamp("2026-03-28T00:00:00+00:00")
    END_6M = pd.Timestamp("2026-09-28T00:00:00+00:00")
    res_6m = run_benchmark_on_dataset(SIX_MO_DATASET, START_6M, END_6M, "6-Month Full (2026-03-28 to 2026-09-28)")
    all_results.extend(res_6m)

    # 2. 6-Month Second Half (2026-06-28 to 2026-09-28)
    HALF_6M = pd.Timestamp("2026-06-28T00:00:00+00:00")
    res_6m_h2 = run_benchmark_on_dataset(SIX_MO_DATASET, HALF_6M, END_6M, "6-Month H2 Choppy (2026-06-28 to 2026-09-28)")
    all_results.extend(res_6m_h2)

    # 3. 1-Year Annual Second Half (2026-04-01 to 2026-10-01)
    START_1Y_H2 = pd.Timestamp("2026-04-01T00:00:00+00:00")
    END_1Y = pd.Timestamp("2026-10-01T00:00:00+00:00")
    res_1y_h2 = run_benchmark_on_dataset(ANNUAL_DATASET, START_1Y_H2, END_1Y, "1-Year Annual H2 (2026-04-01 to 2026-10-01)")
    all_results.extend(res_1y_h2)

    # Save to JSON
    out_file = Path("docs/reviews/2026-10-04-trial30-vs-reward156-paired-benchmark.json")
    out_file.write_text(json.dumps(all_results, indent=2))
    print(f"\nAudit results successfully saved to: {out_file}")


if __name__ == "__main__":
    main()
