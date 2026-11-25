"""SELL SL-width x TP grid on live 7fe0 (F2+F3, cooldown 30m, cap 10%, daily stop, 0.01 lot). Box-only, 25 Nov 2026 (t195u).
Reuses entry_sl.py (f2f3-validate harness, M1 path, SL before TP inside a bar)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry_sl import *
OUT = Path(__file__).parent; BAL_NOW = 382.16; HZ = 12 * 3600 * 1000   # 'stopped then continued' horizon: 12 h after the stop-out
G = {}
for sl in (2.5, 2.75, 3.0, 3.25, 3.5):
    for tp in (1.0, 1.35, 1.5, 2.0): G[f'sl{sl}_tp{tp}R'] = dict(sl=sl, tp=tp)
    if sl != 2.5: G[f'sl{sl}_fixedTP(3.375ATR)'] = dict(sl=sl, tp=round(1.35 * 2.5 / sl, 6))
BASE_NM = 'sl2.5_tp1.35R'
CANDS = {nm: build(sell_rows(**kw)) for nm, kw in G.items()}
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
assert np.allclose(CANDS[BASE_NM].pnl.to_numpy(), b0.pnl.to_numpy()); print('parity OK', flush=True)
TR = {}; rows = []
for nm, c in CANDS.items():
    for wn, (a, z) in WIN.items():
        t, parts = run(c, a, z); TR[(nm, wn)] = (t, c)
        rows.append(dict(variant=nm, window=wn, **summ(t, parts, a, z)))
W = pd.DataFrame(rows); W.to_csv(OUT / 'slgrid-windows.csv', index=False)
TRb = {k: v[0] for k, v in TR.items()}
BR = bootstrap(TRb, list(G), base=BASE_NM); BR.to_csv(OUT / 'slgrid-bootstrap.csv', index=False)
def stopped_continued(t, c):
    s = t[(t.d == -1) & (t.why == 0)]; n = 0
    for r in s.itertuples():
        cr = c.loc[r.k]; target = cr.entry - cr.rr_plan * cr.R
        j0 = int(np.searchsorted(t1, r.tx)); j1 = int(np.searchsorted(t1, r.tx + HZ))
        if j1 > j0 and (L[j0:j1] + SP).min() <= target: n += 1
    return len(s), n
g = lambda nm, wn, col: W[(W.variant == nm) & (W.window == wn)].iloc[0][col]
out = []; mon = {}
for nm in G:
    t, c = TR[(nm, '2025-26 all')]; tb = TR[(BASE_NM, '2025-26 all')][0]
    sl_ = t[t.d == -1]; s = stats_block(t, BAL0, calendar_months(*WIN['2025-26 all']))
    m = pd.Series(s['monthly']); mon[nm] = m
    nsl, ncont = stopped_continued(t, c)
    beats = [g(nm, w, 'net') > g(BASE_NM, w, 'net') for w in ('2015-18', '2019-24', '2025-26H1 (OPT)', '2026H2 (HOLD)')]
    p = BR[(BR.variant == nm) & (BR.window == '2025-26 all')]
    dm = m.sub(pd.Series(stats_block(tb, BAL0, calendar_months(*WIN['2025-26 all']))['monthly']), fill_value=0)
    out.append(dict(variant=nm, trades=len(t), sell_trades=len(sl_), win=round(100 * (t.net > 0).mean(), 1), sell_win=round(100 * (sl_.net > 0).mean(), 1),
        sell_avg_win=round(sl_[sl_.net > 0].net.mean(), 2), sell_avg_loss=round(sl_[sl_.net < 0].net.mean(), 2), sell_max_loss=round(sl_.net.min(), 2),
        net=round(t.net.sum(), 2), sell_net=round(sl_.net.sum(), 2), maxdd=g(nm, '2025-26 all', 'maxdd'), pf=s['pf'],
        green_pct=round(100 * (m > 0).mean(), 1), net_ex_best_month=round(t.net.sum() - m.max(), 2), d_vs_base=round(t.net.sum() - tb.net.sum(), 2),
        d_ex_best_month=round(t.net.sum() - tb.net.sum() - dm.max(), 2) if nm != BASE_NM else 0.0,
        net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_opt=g(nm, '2025-26H1 (OPT)', 'net'), net_hold=g(nm, '2026H2 (HOLD)', 'net'),
        beats_windows=sum(beats) if nm != BASE_NM else None, holdout=('PASS' if all(beats) else 'FAIL') if nm != BASE_NM else '-',
        p_better=p.p_better_net.iloc[0] if len(p) else None, p_lower_dd=p.p_lower_dd.iloc[0] if len(p) else None,
        sell_full_sl=nsl, stopped_then_continued=ncont, cont_pct=round(100 * ncont / nsl, 1) if nsl else None,
        avg_loss_pct_bal=round(100 * -sl_[sl_.net < 0].net.mean() / BAL_NOW, 2), max_loss_pct_bal=round(100 * -sl_.net.min() / BAL_NOW, 2),
        risk_at_atr9_pct=round(100 * (G[nm]['sl'] * 9 + 0.1 + 0.1) / BAL_NOW, 2), rr=round(G[nm]['tp'], 3)))
O = pd.DataFrame(out); O.to_csv(OUT / 'slgrid-compact.csv', index=False)
M = pd.DataFrame(mon).reindex(calendar_months(*WIN['2025-26 all'])).fillna(0.0) if False else pd.DataFrame(mon).fillna(0.0)
M.to_csv(OUT / 'slgrid-monthly-2025-26.csv')
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 60)
print(O.to_string()); print(M[[BASE_NM, 'sl3.0_tp1.35R']].to_string())
