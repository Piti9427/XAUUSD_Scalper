"""
B1 SL/TP Parameter Sweep — Find survivable config on $200 XAUUSD M15.

Replays all B1 signals from the 6-month baseline with:
  - Pure single-position (NO Recovery / Basket)
  - Fixed 0.01 lot
  - Variable SL and TP multipliers of ATR14
  - $200 starting capital
  - Margin check: reject if risk > 50% of current equity

Outputs a matrix of (SL_mult, TP_mult) → return%, win_rate, max_dd, trade_count
to find the sweet spot where the strategy survives.

Usage: python scripts/research/scratch/b1_sl_tp_sweep.py
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from itertools import product

DATA_DIR = Path("data/b1_hybrid_baseline_6mo_fixed_2026_09_28")
TICK_DIR = Path("data/b1_hybrid_exness_6mo_fixed_2026_09_28")
CAPITAL = 200.0
LOT = 0.01
CONTRACT = 100  # oz per lot
POSITION_SIZE = LOT * CONTRACT  # 1 oz


def load_signals():
    """Load B1 signals from the baseline decisions."""
    df = pd.read_csv(DATA_DIR / "continuous_decisions.csv")
    df["signal_time"] = pd.to_datetime(df["signal_time"], format="ISO8601")
    df["entry_time"] = pd.to_datetime(df["entry_time"], format="ISO8601")
    # entry price is actual tick-fill
    return df[["signal_time", "entry_time", "direction", "atr", "entry"]].copy()


def load_tick_index():
    """Load manifest to find tick files by date."""
    manifest = json.loads((TICK_DIR / "manifest.json").read_text())
    return manifest


def simulate(signals, sl_mult, tp_mult, daily_limit_pct=0.40):
    """
    Simulate pure B1 single-position trading.

    SL = sl_mult * ATR
    TP = tp_mult * ATR
    Fixed 0.01 lot, $200 start.
    Daily loss limit = daily_limit_pct of day-start equity.
    No recovery, no basket. One trade at a time.
    """
    balance = CAPITAL
    trades = []
    day_start_equity = {}

    for _, sig in signals.iterrows():
        direction = int(sig["direction"])
        atr = float(sig["atr"])
        entry = float(sig["entry"])

        # SL and TP distances
        sl_distance = atr * sl_mult
        tp_distance = atr * tp_mult

        # Risk per trade in dollars
        risk = sl_distance * POSITION_SIZE

        # Skip if risk > 50% of current equity (margin safety)
        if risk > balance * 0.50:
            continue

        # Skip if balance too low for minimum margin
        if balance < 5.0:
            continue

        # Daily loss limit
        day_key = sig["signal_time"].strftime("%Y-%m-%d")
        if day_key not in day_start_equity:
            day_start_equity[day_key] = balance
        day_start = day_start_equity[day_key]
        if day_start - balance >= day_start * daily_limit_pct:
            continue

        # Calculate SL and TP prices
        if direction == 1:  # BUY
            stop = entry - sl_distance
            target = entry + tp_distance
        else:  # SELL
            stop = entry + sl_distance
            target = entry - tp_distance

        # Simple outcome simulation using the known TP/SL ratio
        # and direction. We use tick data if available, otherwise
        # use the reference bar high/low to determine if SL or TP
        # was hit first. For this sweep we use a simplified model:
        # check subsequent M15 bars to see which level is hit first.

        # For speed, use a probabilistic model based on the known
        # B1 win rates at different SL/TP configs from the baseline.
        # The original B1_TP25 (SL 2.5, TP 2.5R=6.25 ATR) had 35% win rate.
        # Tighter SL → lower win rate but smaller losses.
        # We'll use the reference bars to check actual outcomes.

        # Mark this trade - we'll resolve outcomes below
        trades.append(
            {
                "entry_time": sig["signal_time"],
                "direction": direction,
                "entry": entry,
                "atr": atr,
                "stop": stop,
                "target": target,
                "sl_distance": sl_distance,
                "tp_distance": tp_distance,
                "risk": risk,
                "reward": tp_distance * POSITION_SIZE,
            }
        )

    return trades


def replay_with_bars(signals, bars, sl_mult, tp_mult, daily_limit_pct=0.40):
    """
    Replay signals against actual M15 bars to determine outcomes.
    One position at a time. Check each bar's high/low to see if SL or TP hit.
    """
    balance = CAPITAL
    peak = CAPITAL
    max_dd = 0.0
    wins = 0
    losses = 0
    total_pnl = 0.0
    day_start_equity = {}
    equity_curve = [CAPITAL]

    bars = bars.sort_values("bar_open_utc").reset_index(drop=True)
    bar_times = bars["bar_open_utc"].values

    for _, sig in signals.iterrows():
        direction = int(sig["direction"])
        atr = float(sig["atr"])
        entry = float(sig["entry"])

        sl_distance = atr * sl_mult
        tp_distance = atr * tp_mult
        risk = sl_distance * POSITION_SIZE

        # Margin safety
        if risk > balance * 0.50 or balance < 5.0:
            continue

        # Daily loss limit
        day_key = sig["signal_time"].strftime("%Y-%m-%d")
        if day_key not in day_start_equity:
            day_start_equity[day_key] = balance
        day_start = day_start_equity[day_key]
        if day_start - balance >= day_start * daily_limit_pct:
            continue

        # SL/TP levels
        if direction == 1:
            stop = entry - sl_distance
            target = entry + tp_distance
        else:
            stop = entry + sl_distance
            target = entry - tp_distance

        # Find entry bar index
        signal_time = sig["signal_time"]
        entry_idx = np.searchsorted(bar_times, np.datetime64(signal_time))

        # Walk forward through bars to find outcome
        outcome = None
        for i in range(entry_idx, len(bars)):
            bar = bars.iloc[i]
            high = float(bar["high"])
            low = float(bar["low"])

            if direction == 1:  # BUY
                if low <= stop:
                    outcome = "SL"
                    break
                if high >= target:
                    outcome = "TP"
                    break
            else:  # SELL
                if high >= stop:
                    outcome = "SL"
                    break
                if low <= target:
                    outcome = "TP"
                    break

        if outcome is None:
            # Trade still open at end of data — close at last bar close
            last_close = float(bars.iloc[-1]["close"])
            pnl = direction * (last_close - entry) * POSITION_SIZE
        elif outcome == "TP":
            pnl = tp_distance * POSITION_SIZE
            wins += 1
        else:  # SL
            pnl = -sl_distance * POSITION_SIZE
            losses += 1

        balance += pnl
        total_pnl += pnl
        peak = max(peak, balance)
        dd = (peak - balance) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        equity_curve.append(balance)

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0

    return {
        "sl_mult": sl_mult,
        "tp_mult": tp_mult,
        "final_balance": round(balance, 2),
        "return_pct": round((balance / CAPITAL - 1) * 100, 2),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate * 100, 1),
        "max_dd_pct": round(max_dd * 100, 1),
        "avg_risk_usd": round(total_pnl / total_trades, 2) if total_trades > 0 else 0,
        "profit_factor": round((wins * tp_mult) / (losses * sl_mult), 2)
        if losses > 0
        else float("inf"),
    }


def main():
    print("Loading signals and bars...")
    signals = load_signals()
    bars = pd.read_csv(DATA_DIR / "reference_bars.csv")
    bars["bar_open_utc"] = pd.to_datetime(bars["bar_open_utc"])

    print(f"Signals: {len(signals)}, Bars: {len(bars)}")
    print(f"Capital: ${CAPITAL}, Lot: {LOT}")
    print()

    # Sweep SL and TP multipliers
    sl_range = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]
    tp_range = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.25]

    results = []
    for sl_mult, tp_mult in product(sl_range, tp_range):
        result = replay_with_bars(signals, bars, sl_mult, tp_mult)
        results.append(result)

    # Sort by return
    results.sort(key=lambda x: x["return_pct"], reverse=True)

    # Print top 15
    print("=" * 120)
    print(
        f"{'SL':>5} {'TP':>5} {'Return%':>10} {'Balance':>10} {'Trades':>8} {'Wins':>6} {'WR%':>6} {'MaxDD%':>8} {'PF':>6}"
    )
    print("=" * 120)
    for r in results[:20]:
        print(
            f"{r['sl_mult']:>5.2f} {r['tp_mult']:>5.2f} {r['return_pct']:>10.2f} {r['final_balance']:>10.2f} {r['total_trades']:>8} {r['wins']:>6} {r['win_rate']:>6.1f} {r['max_dd_pct']:>8.1f} {r['profit_factor']:>6.2f}"
        )

    print()
    print("--- Bottom 5 ---")
    for r in results[-5:]:
        print(
            f"{r['sl_mult']:>5.2f} {r['tp_mult']:>5.2f} {r['return_pct']:>10.2f} {r['final_balance']:>10.2f} {r['total_trades']:>8} {r['wins']:>6} {r['win_rate']:>6.1f} {r['max_dd_pct']:>8.1f} {r['profit_factor']:>6.2f}"
        )

    # Save all results
    output = Path("data/b1_sl_tp_sweep_200usd.json")
    output.write_text(json.dumps(results, indent=2))
    print(f"\nAll {len(results)} results saved to {output}")

    # Find breakeven or profitable configs
    profitable = [r for r in results if r["return_pct"] > 0]
    if profitable:
        print(f"\n🟢 PROFITABLE configs found: {len(profitable)}")
        for r in profitable[:5]:
            print(
                f"  SL={r['sl_mult']} TP={r['tp_mult']}: {r['return_pct']:+.1f}% WR={r['win_rate']}% DD={r['max_dd_pct']}%"
            )
    else:
        breakeven = [r for r in results if r["return_pct"] > -10]
        if breakeven:
            print(f"\n🟡 Near-breakeven configs: {len(breakeven)}")
            for r in breakeven[:5]:
                print(
                    f"  SL={r['sl_mult']} TP={r['tp_mult']}: {r['return_pct']:+.1f}% WR={r['win_rate']}% DD={r['max_dd_pct']}%"
                )
        else:
            print("\n🔴 No profitable or near-breakeven config found with these parameters.")
            print("Strategy may need fundamental redesign for $200 XAUUSD.")


if __name__ == "__main__":
    main()
