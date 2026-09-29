import pandas as pd
from pathlib import Path
import json
import yaml
import numpy as np
from scripts.research.feedback_round import directions
from scripts.research.b1_final import reference_bars
from scripts.research.strategies import Spec

root = Path("data/b1_feedback_baseline_2026-09-28")
meta = json.loads((root / "manifest.json").read_text())
broker = meta["broker_snapshot"]
f = pd.read_csv(root / "reference_bars.csv")
f.index = pd.DatetimeIndex(pd.to_datetime(f.pop("bar_open_utc"), utc=True))
f = reference_bars(f)
sigs = directions(f, yaml.safe_load(Path("config/settings.yaml").read_text()))
t, b, a = [np.load(root / "tape" / f"{k}.npy", mmap_mode="r") for k in ("time", "bid", "ask")]
start = pd.Timestamp("2026-05-14", tz="UTC")
end = pd.Timestamp("2026-09-26", tz="UTC")
left_idx, right_idx = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
mask = (f.index + pd.Timedelta(minutes=15) >= start) & (f.index + pd.Timedelta(minutes=15) < end)

times = t[left_idx:right_idx]
bid = b[left_idx:right_idx]
ask = a[left_idx:right_idx]
signal = sigs["B1"].where(mask, 0).to_frame("direction")
spec = Spec("B1_TP25", "research", sl=2.5, tp=2.5)

balance = 200.0
peak = 200.0
max_dd = 0.0
dd_peak = 200.0
dd_trough = 200.0
dd_trade_idx = 0
busy = -1
grid = broker["trade_tick_size"]
contract = broker["trade_contract_size"]
volume = 0.01

curve = []

for idx, i in enumerate(np.flatnonzero(signal.direction.to_numpy())):
    when = f.index[i] + pd.Timedelta(minutes=15)
    stamp = when.value // 1_000_000
    j = int(np.searchsorted(times, stamp))
    if j >= len(times) or times[j] - stamp >= 900000 or j <= busy:
        continue
    direction = int(signal.direction.iloc[i])
    entry = float(ask[j] if direction == 1 else bid[j])
    distance = float(f.atr.iloc[i]) * spec.sl
    stop = round((entry - direction * distance) / grid) * grid
    distance = abs(entry - stop)
    target = round((entry + direction * distance * spec.tp) / grid) * grid

    quotes = bid if direction == 1 else ask
    hit = None
    for left in range(j, len(times), 100000):
        block = quotes[left : left + 100000]
        where = np.flatnonzero(
            (direction * (block - stop) <= 0) | (direction * (block - target) >= 0)
        )
        if len(where):
            hit = left + int(where[0])
            break
    k = len(times) - 1 if hit is None else hit
    reason = "END" if hit is None else ("SL" if direction * (quotes[k] - stop) <= 0 else "TP")
    exit_price = float(quotes[k]) if reason != "TP" else target
    gross = direction * (exit_price - entry) * contract * volume
    cost = 0.1 * distance * contract * volume
    net = gross - cost
    balance += net

    if balance > peak:
        peak = balance
    dd = (peak - balance) / peak * 100.0
    if dd > max_dd:
        max_dd = dd
        dd_peak = peak
        dd_trough = balance
        dd_trade_idx = len(curve) + 1
    curve.append(
        {
            "trade": len(curve) + 1,
            "date": str(when),
            "net": net,
            "reason": reason,
            "balance": balance,
            "peak": peak,
            "dd": dd,
        }
    )

df_c = pd.DataFrame(curve)
min_row = df_c.loc[df_c["balance"].idxmin()]

print("=" * 60)
print(f"Max DD Peak Balance:       ${dd_peak:.2f}")
print(f"Max DD Trough Balance:     ${dd_trough:.2f}")
print(f"Max Drawdown Percentage:   {max_dd:.2f}%")
print(f"Occurred on Trade Number:  {dd_trade_idx} ({df_c.iloc[dd_trade_idx - 1]['date']})")
print("-" * 60)
print(f"Lowest Balance Overall:    ${min_row['balance']:.2f}")
print(f"Lowest Balance Date:       {min_row['date']} (Trade #{min_row['trade']})")
print("=" * 60)

# Show trades leading up to the lowest point
start_idx = max(0, int(min_row["trade"]) - 8)
end_idx = min(len(df_c), int(min_row["trade"]) + 4)
print("\nTrades around the lowest point:")
for _, r in df_c.iloc[start_idx:end_idx].iterrows():
    print(
        f"Trade #{int(r['trade']):3d} | {r['date'][:10]} | {r['reason']:3s} | Net: ${r['net']:+6.2f} | Balance: ${r['balance']:6.2f} | Peak: ${r['peak']:6.2f} | DD: {r['dd']:5.2f}%"
    )
