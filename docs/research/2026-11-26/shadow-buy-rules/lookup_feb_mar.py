"""Read-only lookup: BUY trades removed by G_1.25 / LsG_8_1.25 in the base worst DD episode (2025-26 window).
Imports R3 ml.py (no actions run) and re-runs its portfolio logic with candidate indices kept."""
import sys, os
os.environ.setdefault('OMP_NUM_THREADS', '1')
R3 = '/workspace/c22-trade-journal/research/ml-walkforward-r3-20261126'
sys.path.insert(0, R3); os.chdir(R3)
import numpy as np, pandas as pd
import ml
c3, X3 = ml.D['store'][3.0]
def port_idx(c, skip, start, end, cool_min=30, max_losses=1, bal0=ml.BAL0, cap=0.1, daily_stop=0.10):
    a, z = ml.ms(start), ml.ms(end); idx = np.where((c.ts.to_numpy() >= a) & (c.ts.to_numpy() < z))[0]
    bal = bal0; op = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0
    for q in idx:
        ts = c.ts.iat[q]
        if op is not None and op[1] <= ts:
            p = op; op = None; bal += p[3]; last_tx = p[1]
            if p[3] < 0:
                day = p[1] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p[1] + cms
            res.append(p)
        if op is not None or ts < cool: continue
        sg = c.sig.iat[q]
        if last_tx > sg or sg < cool: continue
        if dl.get(sg // 86400000, 0) >= max_losses: continue
        day = ts // 86400000
        if dl.get(day, 0) >= max_losses: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop: continue
        if c.R.iat[q] + ml.SLIP > bal * cap: continue
        if skip[q]: continue
        op = (ts, c.tx.iat[q], q, c.pnl.iat[q] + c.sw.iat[q])
    if op is not None: res.append(op)
    return res
a, z = ml.WINDOWS['2025-26']
base = port_idx(c3, ml.Z if hasattr(ml, 'Z') else np.zeros(len(c3), bool), a, z)
net = np.array([r[3] for r in base]); print('parity base 2025-26 net', round(net.sum(), 2), 'n', len(net))
ep0 = ml.T('2026-02-11'); ep1 = ml.T('2026-03-20')
base_q = {r[2] for r in base}
rows = []
for nm in ('G_1.25', 'G_1.5', 'LsG_8_1.25'):
    fam, k = nm.rsplit('_', 1); sk = ml.rule_skip(fam, float(k))
    res = port_idx(c3, sk, a, z); rn = np.array([r[3] for r in res]); kept = {r[2] for r in res}
    print(nm, 'net', round(rn.sum(), 2), 'n', len(rn))
    for q in sorted(base_q - kept):
        t = pd.Timestamp(c3.ts.iat[q], unit='ms', tz='UTC').tz_convert('Asia/Bangkok')
        rows.append(dict(rule=nm, removed_from_base=True, side='BUY' if c3.d.iat[q] == 1 else 'SELL', skipped_by_rule=bool(sk[q]),
                         entry_ict=str(t)[:19], signal_ict=str(pd.Timestamp(c3.sig.iat[q], unit='ms', tz='UTC').tz_convert('Asia/Bangkok'))[:19],
                         exit_ict=str(pd.Timestamp(c3.tx.iat[q], unit='ms', tz='UTC').tz_convert('Asia/Bangkok'))[:19],
                         bar_range_atr=round(float(c3.bar_range_atr.iat[q]), 4), min_since_loss_stream=round(float(c3.min_since_loss_stream.iat[q]), 1),
                         net_usd=round(float(c3.pnl.iat[q] + c3.sw.iat[q]), 2), why=int(c3.why.iat[q]), in_episode=bool(ep0 <= t < ep1)))
    for q in sorted(kept - base_q):
        t = pd.Timestamp(c3.ts.iat[q], unit='ms', tz='UTC').tz_convert('Asia/Bangkok')
        rows.append(dict(rule=nm, removed_from_base=False, side='BUY' if c3.d.iat[q] == 1 else 'SELL', skipped_by_rule=False, entry_ict=str(t)[:19],
                         signal_ict=str(pd.Timestamp(c3.sig.iat[q], unit='ms', tz='UTC').tz_convert('Asia/Bangkok'))[:19],
                         exit_ict=str(pd.Timestamp(c3.tx.iat[q], unit='ms', tz='UTC').tz_convert('Asia/Bangkok'))[:19],
                         bar_range_atr=round(float(c3.bar_range_atr.iat[q]), 4), min_since_loss_stream=round(float(c3.min_since_loss_stream.iat[q]), 1),
                         net_usd=round(float(c3.pnl.iat[q] + c3.sw.iat[q]), 2), why=int(c3.why.iat[q]), in_episode=bool(ep0 <= t < ep1)))
df = pd.DataFrame(rows); df.to_csv('removed-trades-2025-26.csv', index=False)
print(df[df.in_episode].to_string())
print('total diff rows', len(df), 'in episode', int(df.in_episode.sum()))
