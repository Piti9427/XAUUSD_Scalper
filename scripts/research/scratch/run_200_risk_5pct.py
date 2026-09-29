from pathlib import Path
import json, yaml, numpy as np, pandas as pd
from scripts.research.feedback_round import directions
from scripts.research.b1_final import reference_bars, normalize_price
from scripts.research.b1_d_ticks import replay
from scripts.research.b1_d_comprehensive import summarize
from scripts.research.strategies import Spec

root = Path('data/b1_feedback_baseline_2026-09-28')
meta = json.loads((root / 'manifest.json').read_text())
broker = meta['broker_snapshot']
f = pd.read_csv(root / 'reference_bars.csv')
f.index = pd.DatetimeIndex(pd.to_datetime(f.pop('bar_open_utc'), utc=True))
f = reference_bars(f)
sigs = directions(f, yaml.safe_load(Path('config/settings.yaml').read_text()))
t, b, a = [np.load(root / 'tape' / f'{k}.npy', mmap_mode='r') for k in ('time', 'bid', 'ask')]
start = pd.Timestamp('2026-05-14', tz='UTC')
end = pd.Timestamp('2026-09-26', tz='UTC')
l, r = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
mask = (f.index + pd.Timedelta(minutes=15) >= start) & (f.index + pd.Timedelta(minutes=15) < end)

times = t[l:r]
bid = b[l:r]
ask = a[l:r]
signal = sigs['B1'].where(mask, 0).to_frame('direction')
spec = Spec('B1_TP25', 'research', sl=2.5, tp=2.5)

# Run replay with risk_pct = 0.05 (5%) on $200
log_5pct, stats_5pct = replay(
    times, bid, ask, f,
    signal,
    spec,
    broker,
    200.0,
    risk_pct=0.05,
    extra_cost_r=0.1,
    risk_state=None,  # no 1% tier drawdown scaler
    price_normalizer=normalize_price,
    entry_window_ms=900000,
    _validated_tape=True,
)
ret_pct = (stats_5pct['final_balance'] / 200.0 - 1.0) * 100.0
summary = summarize(log_5pct, stats_5pct)

print("=" * 60)
print("TEST: B1_TP25 on $200 with 5% Risk (risk_pct = 0.05)")
print("Period: 14 May 2026 - 26 Sep 2026 (Exness Tick Replay)")
print("=" * 60)
print(f"Trades Taken:      {summary['trades']}")
print(f"Net Return (%):    {ret_pct:+.2f}%")
print(f"Final Balance:     ${stats_5pct['final_balance']:.2f} (from $200.00)")
print(f"Profit Factor:     {summary['pf']}")
print(f"Max Tick DD:       {summary['max_tick_equity_dd_pct']:.2f}%")
print(f"Win Rate:          {summary['win_rate'] * 100:.2f}%" if summary['trades'] > 0 else "Win Rate: N/A")
print(f"Rejections:        {stats_5pct['rejections']}")
print("=" * 60)
