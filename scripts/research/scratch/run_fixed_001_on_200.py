from pathlib import Path
import json, yaml, numpy as np, pandas as pd
from scripts.research.feedback_round import directions
from scripts.research.b1_final import reference_bars, normalize_price
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

# Simulate Fixed 0.01 lot on $200
balance = 200.0
peak = 200.0
max_dd = 0.0
trades = []
busy = -1
grid = broker['trade_tick_size']
contract = broker['trade_contract_size']
volume = 0.01

for i in np.flatnonzero(signal.direction.to_numpy()):
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
        where = np.flatnonzero((direction * (block - stop) <= 0) | (direction * (block - target) >= 0))
        if len(where):
            hit = left + int(where[0])
            break
    k = len(times) - 1 if hit is None else hit
    reason = 'END' if hit is None else ('SL' if direction * (quotes[k] - stop) <= 0 else 'TP')
    exit_price = float(quotes[k]) if reason != 'TP' else target
    gross = direction * (exit_price - entry) * contract * volume
    cost = 0.1 * distance * contract * volume
    net = gross - cost
    
    balance += net
    if balance > peak:
        peak = balance
    dd = (peak - balance) / peak * 100.0
    if dd > max_dd:
        max_dd = dd
    trades.append({'net': net, 'reason': reason, 'balance': balance, 'entry': entry, 'exit': exit_price})
    busy = k
    if balance <= 0:
        print('ACCOUNT BLOWN!')
        break

df_t = pd.DataFrame(trades)
wins = (df_t.net > 0).sum()
losses = (df_t.net <= 0).sum()
gross_profit = df_t[df_t.net > 0].net.sum()
gross_loss = df_t[df_t.net < 0].net.sum()
pf = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')

print("=" * 60)
print("SIMULATION: B1_TP25 with FIXED 0.01 Lot on $200 Account")
print("Period: 14 May 2026 - 26 Sep 2026 (Exness Tick Replay)")
print("=" * 60)
print(f"Total Trades:      {len(df_t)}")
print(f"Wins / Losses:     {wins} wins / {losses} losses")
print(f"Win Rate:          {wins / len(df_t) * 100:.2f}%")
print(f"Net Profit ($):    ${balance - 200.0:+.2f}")
print(f"Net Return (%):    {(balance / 200.0 - 1.0) * 100.0:+.2f}%")
print(f"Final Balance:     ${balance:.2f} (from $200.00)")
print(f"Profit Factor:     {pf:.3f}")
print(f"Max Drawdown:      {max_dd:.2f}%")
print(f"Gross Profit:      +${gross_profit:.2f}")
print(f"Gross Loss:        ${gross_loss:.2f}")
print("=" * 60)
