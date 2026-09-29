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

# Test various risk levels on $200 account
risk_levels = [0.08, 0.10, 0.12, 0.15]
results = []

for r_pct in risk_levels:
    log, stats = replay(
        times, bid, ask, f,
        signal,
        spec,
        broker,
        200.0,
        risk_pct=r_pct,
        extra_cost_r=0.1,
        risk_state=None,
        price_normalizer=normalize_price,
        entry_window_ms=900000,
        _validated_tape=True,
    )
    ret_pct = (stats['final_balance'] / 200.0 - 1.0) * 100.0
    s = summarize(log, stats)
    results.append({
        'risk_pct': f"{r_pct*100:.0f}%",
        'budget': f"${200*r_pct:.0f}",
        'trades': s['trades'],
        'return_pct': f"{ret_pct:+.2f}%",
        'final_bal': f"${stats['final_balance']:.2f}",
        'pf': f"{s['pf']:.3f}" if s['pf'] is not None else "N/A",
        'max_dd': f"{s['max_tick_equity_dd_pct']:.2f}%",
        'win_rate': f"{s['win_rate']*100:.1f}%" if s['trades'] > 0 else "N/A",
        'rejections': stats['rejections']['risk_below_min']
    })

print("=" * 80)
print("TEST: B1_TP25 on $200 Account with Different Risk %")
print("Period: 14 May 2026 - 26 Sep 2026 (Exness Tick Replay)")
print("=" * 80)
df_res = pd.DataFrame(results)
print(df_res.to_string(index=False))
print("=" * 80)
