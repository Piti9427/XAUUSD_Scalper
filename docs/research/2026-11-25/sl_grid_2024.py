"""Same SL x TP grid as sl_grid.py but one continuous $400 account from 2024-01-01 to data end (t198u)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry_sl import *
OUT = Path(__file__).parent; A0, Z0 = T('2024-01-01'), END
G = {}
for sl in (2.5, 2.75, 3.0, 3.25, 3.5):
    for tp in (1.0, 1.35, 1.5, 2.0): G[f'sl{sl}_tp{tp}R'] = dict(sl=sl, tp=tp)
    if sl in (2.5, 3.0, 3.25, 3.5):
        for tp in (2.5, 3.0): G[f'sl{sl}_tp{tp}R'] = dict(sl=sl, tp=tp)
    if sl != 2.5: G[f'sl{sl}_fixedTP(3.375ATR)'] = dict(sl=sl, tp=round(1.35 * 2.5 / sl, 6))
BN = 'sl2.5_tp1.35R'
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
TR = {}
for nm, kw in G.items():
    c = build(sell_rows(**kw))
    if nm == BN: assert np.allclose(c.pnl.to_numpy(), b0.pnl.to_numpy())
    TR[nm] = portfolio2(c, A0, Z0)
months = calendar_months(A0, Z0)
def mser(t): return pd.Series(stats_block(t, BAL0, months)['monthly'])
def yr(t, y):
    yy = pd.to_datetime(t.ts.to_numpy(), unit='ms', utc=True).tz_convert(ICT).year
    return t[yy == y]
idx = pd.date_range(A0.normalize(), Z0, freq='D', tz=ICT)[:-1]; n = len(idx); Lb = 20; nb_ = int(np.ceil(n / Lb))
st = rng.integers(0, n, size=(5000, nb_)); ix = ((st[:, :, None] + np.arange(Lb)[None, None, :]) % n).reshape(5000, -1)[:, :n]
bd = daily(TR[BN], idx); sb = bd[ix].sum(1); mb = mdd(bd[ix])
mb_base = mser(TR[BN]); rows = []; yrows = []
for nm, t in TR.items():
    s = stats_block(t, BAL0, months); m = mser(t); sl_ = t[t.d == -1]
    fd = daily(t, idx); xf = fd[ix]; dn = xf.sum(1) - sb
    dm = m.sub(mb_base, fill_value=0.0)
    rows.append(dict(variant=nm, trades=len(t), sell_trades=len(sl_), win=s['win'], sell_win=round(100 * (sl_.net > 0).mean(), 1),
        sell_avg_win=round(sl_[sl_.net > 0].net.mean(), 2), sell_avg_loss=round(sl_[sl_.net < 0].net.mean(), 2),
        realised_rr=round(sl_[sl_.net > 0].net.mean() / -sl_[sl_.net < 0].net.mean(), 2), sell_expectancy=round(sl_.net.mean(), 2), expectancy_all=round(t.net.mean(), 2),
        tp_rr=G[nm]['tp'], sl_atr=G[nm]['sl'], sell_be=int(((sl_.net >= 0) & (sl_.net < 0.5)).sum()), net=round(s['net'], 2), sell_net=round(sl_.net.sum(), 2),
        maxdd=round(s['maxdd'], 2), pf=s['pf'], green_pct=round(100 * (m > 0).mean(), 1), worst_month=round(m.min(), 2), best_month=m.idxmax(), best_month_net=round(m.max(), 2),
        net_ex_best_month=round(s['net'] - m.max(), 2), d_vs_base=round(s['net'] - TR[BN].net.sum(), 2),
        d_best_month=dm.idxmax() if nm != BN else '', d_best_month_val=round(dm.max(), 2) if nm != BN else 0.0,
        d_ex_best_month=round(s['net'] - TR[BN].net.sum() - dm.max(), 2) if nm != BN else 0.0,
        months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()),
        p_better=round((dn > 0).mean(), 3) if nm != BN else None, p_lower_dd=round((mdd(xf) - mb < 0).mean(), 3) if nm != BN else None))
    for y in (2024, 2025, 2026):
        ty = yr(t, y); sy = ty[ty.d == -1]
        eq = BAL0 + t.net.cumsum(); 
        yrows.append(dict(variant=nm, year=y, trades=len(ty), sell_trades=len(sy), sell_win=round(100 * (sy.net > 0).mean(), 1) if len(sy) else None,
                          net=round(ty.net.sum(), 2), sell_net=round(sy.net.sum(), 2)))
O = pd.DataFrame(rows); O.to_csv(OUT / 'slgrid2024-compact.csv', index=False)
Y = pd.DataFrame(yrows); Y.to_csv(OUT / 'slgrid2024-yearly.csv', index=False)
pd.DataFrame({k: mser(v) for k, v in TR.items()}).fillna(0.0).to_csv(OUT / 'slgrid2024-monthly.csv')
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 60)
print('window', A0, Z0); print(O.to_string()); print(Y[Y.variant.isin([BN, 'sl3.0_tp1.35R', 'sl3.5_tp1.0R'])].to_string())
print(O.sort_values('net', ascending=False).head(4)[['variant', 'net', 'd_vs_base', 'd_best_month', 'd_best_month_val', 'd_ex_best_month', 'months_better', 'months_worse', 'p_better']].to_string())
