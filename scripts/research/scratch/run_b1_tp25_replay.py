from pathlib import Path
import json
import numpy as np
import pandas as pd
import yaml
from scripts.research.feedback_round import directions
from scripts.research.b1_final import reference_bars, RiskState, normalize_price
from scripts.research.b1_d_ticks import replay
from scripts.research.b1_d_comprehensive import summarize
from scripts.research.strategies import Spec

root = Path("data/b1_feedback_baseline_2026-09-28")
meta = json.loads((root / "manifest.json").read_text())
f = pd.read_csv(root / "reference_bars.csv")
f.index = pd.DatetimeIndex(pd.to_datetime(f.pop("bar_open_utc"), utc=True))
f = reference_bars(f)
sigs = directions(f, yaml.safe_load(Path("config/settings.yaml").read_text()))
t, b, a = [np.load(root / "tape" / f"{k}.npy", mmap_mode="r") for k in ("time", "bid", "ask")]
start = pd.Timestamp("2026-05-14", tz="UTC")
end = pd.Timestamp("2026-09-26", tz="UTC")
left_idx, right_idx = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
mask = (f.index + pd.Timedelta(minutes=15) >= start) & (f.index + pd.Timedelta(minutes=15) < end)

# Run B1_TP25 at cost=0.1
spec = Spec("B1_TP25", "research", sl=2.5, tp=2.5)
log, stats = replay(
    t[left_idx:right_idx],
    b[left_idx:right_idx],
    a[left_idx:right_idx],
    f,
    sigs["B1"].where(mask, 0).to_frame("direction"),
    spec,
    meta["broker_snapshot"],
    10000,
    extra_cost_r=0.1,
    risk_state=RiskState(10000),
    price_normalizer=normalize_price,
    entry_window_ms=900000,
    _validated_tape=True,
)
ret_pct = (stats["final_balance"] / 10000.0 - 1.0) * 100.0
summary = summarize(log, stats)

print("=" * 55)
print("REPLAY 1: B1_TP25 on $10,000 Capital (Benchmark)")
print("=" * 55)
print(f"Trades:            {summary['trades']}")
print(f"Return:            +{ret_pct:.2f}%")
print(f"Final Balance:     ${stats['final_balance']:.2f}")
print(f"Profit Factor:     {summary['pf']:.3f}")
print(f"Max Tick DD:       {summary['max_tick_equity_dd_pct']:.2f}%")
print(f"Win Rate:          {summary['win_rate'] * 100:.2f}%")
print(f"Rejections:        {stats['rejections']}")
print("=" * 55)

# Run same test on $200 capital
log_200, stats_200 = replay(
    t[left_idx:right_idx],
    b[left_idx:right_idx],
    a[left_idx:right_idx],
    f,
    sigs["B1"].where(mask, 0).to_frame("direction"),
    spec,
    meta["broker_snapshot"],
    200.0,
    extra_cost_r=0.1,
    risk_state=RiskState(200.0),
    price_normalizer=normalize_price,
    entry_window_ms=900000,
    _validated_tape=True,
)
ret_pct_200 = (stats_200["final_balance"] / 200.0 - 1.0) * 100.0
summary_200 = summarize(log_200, stats_200)

print("\n" + "=" * 55)
print("REPLAY 2: B1_TP25 on $200 Capital (Real Account Size)")
print("=" * 55)
print(f"Trades:            {summary_200['trades']}")
print(f"Return:            {ret_pct_200:.2f}%")
print(f"Final Balance:     ${stats_200['final_balance']:.2f}")
print(f"Profit Factor:     {summary_200['pf']}")
print(f"Max Tick DD:       {summary_200['max_tick_equity_dd_pct']:.2f}%")
print(f"Rejections:        {stats_200['rejections']}")
print("=" * 55)
