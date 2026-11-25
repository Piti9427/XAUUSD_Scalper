"""SELL TP / trailing / partial variants on top of live 7fe0 (26b8 + F2 10 ATR + F3 max 1 loss/UTC day). Box-only research.
Reuses f2f3-validate core (extended data 2015-03 .. 2026-11-24 08:00 ICT, research path_exec2, spread 0.24, slip 0.10, BUY swap -0.4743/night)."""
import sys, json; from pathlib import Path
V = Path('/workspace/c22-trade-journal/research/f2f3-validate-20261124'); sys.path.insert(0, str(V))
from core import *
OUT = Path(__file__).parent; rng = np.random.default_rng(20261124)
T = lambda s: pd.Timestamp(s, tz=ICT)
BASE = pd.read_pickle(V / 'cands_base.pkl')
# SELL exit variants: (tp_rr, be_r, pfrac, prr, trail, tk)
VARS = {
    'base_TP1.35':      (1.35, 1.0, 0.0, 1.35, 0, 0.0),
    'A_TP1.5':          (1.5, 1.0, 0.0, 1.35, 0, 0.0),
    'A_TP2.0':          (2.0, 1.0, 0.0, 1.35, 0, 0.0),
    'A_TP2.5':          (2.5, 1.0, 0.0, 1.35, 0, 0.0),
    'A_TP3.0':          (3.0, 1.0, 0.0, 1.35, 0, 0.0),
    'B_trail1.0_cap5':  (5.0, 1.0, 0.0, 1.0, 1, 1.0),
    'B_trail1.5_cap5':  (5.0, 1.0, 0.0, 1.0, 1, 1.5),
    'B_trail2.0_cap5':  (5.0, 1.0, 0.0, 1.0, 1, 2.0),
    'C_half1.35_rest3R':     (3.0, 1.0, 0.5, 1.35, 0, 0.0),
    'C_half1.35_trail1.5':   (5.0, 1.0, 0.5, 1.35, 1, 1.5),
}
def sell_rows(tp, be, pf, prr, tr, tk):
    S = BASE[BASE.d == -1]; out = []
    for i in S.i.to_numpy():
        ts = int(dec[i]); j = int(np.searchsorted(t1, ts)); a = float(A[i])
        r = E.path_exec2(-1, j, t1, O, H, L, C, last, bidx, A, m5, SP, SLIP, a, 2.5, float(tp), float(be), float(pf), float(prr), int(tr), float(tk),
                         0, 0.0, 0, 0.0, 0.0, float(close[i]), ts, 0, 0.5, 0, 0.0)
        out.append(r)
    o = np.array(out, dtype=float)
    return S.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), tbe=o[:, 2].astype(np.int64), pnl=o[:, 3], R=o[:, 4], entry=o[:, 5], why=o[:, 6].astype(int))
CANDS = {}
for nm, p in VARS.items():
    s = sell_rows(*p); c = pd.concat([BASE[BASE.d == 1], s]).sort_values(['ts', 'd']).reset_index(drop=True)
    c = c[~(c.h4dist < 10)]   # F2
    CANDS[nm] = c
chk = CANDS['base_TP1.35']; b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
assert np.allclose(chk.pnl.to_numpy(), b0.pnl.to_numpy()), 'baseline parity with f2f3-validate failed'
print('parity OK: base_TP1.35 SELL path == f2f3-validate candidates', flush=True)
def segs(a, z):
    out = []; y = a.year
    while T(f'{y}-01-01') < z:
        s0, s1 = max(a, T(f'{y}-01-01')), min(z, T(f'{y+1}-01-01'))
        if y >= 2025: s1 = z
        if s0 < s1: out.append((s0, s1))
        if y >= 2025: break
        y += 1
    return out
def run(c, a, z):
    parts = [(portfolio(c, s0, s1, max_losses=1), (s0, s1)) for s0, s1 in segs(a, z)]
    t = pd.concat([p for p, _ in parts if len(p)], ignore_index=True); return t, parts
def summ(t, parts, a, z):
    s = stats_block(t, BAL0, calendar_months(a, z)); dd = max(stats_block(p, BAL0, calendar_months(*g))['maxdd'] for p, g in parts)
    sl = t[t.d == -1]
    return dict(n=s['n'], n_sell=len(sl), win=s['win'], sell_win=round(100 * (sl.net > 0).mean(), 1) if len(sl) else None,
                avgR=round(t.r.mean(), 3), sell_avgR=round(sl.r.mean(), 3) if len(sl) else None,
                sell_avg_win_R=round(sl[sl.net > 0].r.mean(), 3) if (sl.net > 0).any() else None,
                net=round(s['net'], 2), sell_net=round(sl.net.sum(), 2), pf=s['pf'], maxdd=round(dd, 2), worst_month=s['worst'],
                green_pct=round(100 * np.mean([v > 0 for v in s['monthly'].values()]), 1) if s['monthly'] else 0, losses=int((t.net < 0).sum()))
WIN = {'2015-18': (T('2015-03-02'), T('2019-01-01')), '2019-24': (T('2019-01-02'), T('2025-01-01')),
       '2025-26H1 (OPT)': (T('2025-01-01'), T('2026-07-01')), '2026H2 (HOLD)': (T('2026-07-01'), END), '2025-26 all': (T('2025-01-01'), END)}
rows = []; TR = {}
for nm, c in CANDS.items():
    for wn, (a, z) in WIN.items():
        t, parts = run(c, a, z); TR[(nm, wn)] = t; rows.append(dict(variant=nm, window=wn, **summ(t, parts, a, z)))
W = pd.DataFrame(rows); W.to_csv(OUT / 'windows.csv', index=False)
pd.set_option('display.width', 250); print(W.to_string(), flush=True)
# quarterly walk-forward (fresh $400 each quarter) and quarters won vs baseline
quarters = [str(q) for q in pd.period_range('2015Q2', pd.Timestamp(END.tz_localize(None)).to_period('Q'), freq='Q')]
QN = {}
for nm, c in CANDS.items():
    for q in quarters:
        p = pd.Period(q); a = max(T(str(p.start_time.date())), T('2015-03-02')); z = min(T(str((p.end_time + pd.Timedelta(seconds=1)).date())), END)
        t = portfolio(c, a, z, max_losses=1); s = stats_block(t, BAL0, calendar_months(a, z)); QN[(nm, q)] = (round(s['net'], 2), round(s['maxdd'], 2))
QD = pd.DataFrame([dict(variant=k[0], q=k[1], net=v[0], maxdd=v[1]) for k, v in QN.items()]); QD.to_csv(OUT / 'quarterly.csv', index=False)
qrows = []
for nm in CANDS:
    for lab, lo, hi in (('2015-18', '2015Q2', '2018Q4'), ('2019-24', '2019Q1', '2024Q4'), ('2025-26', '2025Q1', '2026Q4')):
        qs = [q for q in quarters if lo <= q <= hi]
        dn = [QN[(nm, q)][0] - QN[('base_TP1.35', q)][0] for q in qs]
        qrows.append(dict(variant=nm, period=lab, quarters=len(qs), won=sum(x > 0.005 for x in dn), lost=sum(x < -0.005 for x in dn), tied=sum(abs(x) <= 0.005 for x in dn),
                          sum_net=round(sum(QN[(nm, q)][0] for q in qs), 2)))
QW = pd.DataFrame(qrows); QW.to_csv(OUT / 'walkforward-quarters-vs-base.csv', index=False); print(QW.pivot(index='variant', columns='period', values=['won', 'lost']).to_string(), flush=True)
# hold-out selection: choose on 2015-24 only (score = summed net over the two old windows / worst DD of the two), confirm on 2025-26
sel = []
for nm in CANDS:
    r1 = W[(W.variant == nm) & (W.window == '2015-18')].iloc[0]; r2 = W[(W.variant == nm) & (W.window == '2019-24')].iloc[0]
    sel.append(dict(variant=nm, old_net=round(r1.net + r2.net, 2), old_maxdd=max(r1.maxdd, r2.maxdd), old_score=round((r1.net + r2.net) / max(r1.maxdd, r2.maxdd), 3)))
SEL = pd.DataFrame(sel).sort_values('old_score', ascending=False); SEL.to_csv(OUT / 'selection-2015-24.csv', index=False); print(SEL.to_string(), flush=True)
# paired block bootstrap vs baseline on daily P&L (20-day blocks, 5000)
def daily(t, idx):
    d = pd.DatetimeIndex(pd.to_datetime(t.tx.to_numpy(), unit='ms', utc=True).tz_convert(ICT).normalize())
    return pd.Series(t.net.to_numpy(), index=d).groupby(level=0).sum().reindex(idx, fill_value=0.0).to_numpy()
def mdd(x):
    eq = np.cumsum(x, axis=-1); pk = np.maximum.accumulate(np.maximum(eq, 0), axis=-1); return (pk - eq).max(axis=-1)
br = []
for wn in ('2015-18', '2019-24', '2025-26 all', '2026H2 (HOLD)'):
    a, z = WIN[wn]; idx = pd.date_range(a.normalize(), z, freq='D', tz=ICT)[:-1]; n = len(idx); Lb = 20; nb = int(np.ceil(n / Lb))
    st = rng.integers(0, n, size=(5000, nb)); ix = ((st[:, :, None] + np.arange(Lb)[None, None, :]) % n).reshape(5000, -1)[:, :n]
    bd = daily(TR[('base_TP1.35', wn)], idx); xb = bd[ix]; mb = mdd(xb); sb = xb.sum(1)
    for nm in CANDS:
        if nm == 'base_TP1.35': continue
        fd = daily(TR[(nm, wn)], idx); xf = fd[ix]; dn = xf.sum(1) - sb; dd = mdd(xf) - mb
        br.append(dict(variant=nm, window=wn, d_net=round(fd.sum() - bd.sum(), 2), d_net_ci90=f"[{np.percentile(dn,5):.1f}, {np.percentile(dn,95):.1f}]",
                       p_better_net=round((dn > 0).mean(), 3), p_lower_dd=round((dd < 0).mean(), 3)))
BR = pd.DataFrame(br); BR.to_csv(OUT / 'bootstrap-vs-base.csv', index=False); print(BR.to_string(), flush=True)
# monthly series for the record
for nm in CANDS:
    pass
