"""t202u combined grid + walk-forward on live 7fe0 (F2+F3, cooldown 30m, cap 10%, daily stop 10%, 0.01 lot, spread 0.24, slip 0.10, BUY swap).
Axes: ATR-regime skip (none / top 1/4 / top 1/3 / top 2/5, both sides), BUY 48-bar range <= p60/p50/p40 (or none), BUY London skip,
SELL SL 2.5/2.75/3.0 ATR, SELL TP 1.35/2.0/2.5/3.0R, BUY TP 2.5/3.0R, SELL spike guard (k=3, emergency 5 ATR; SELL only).
Monthly P&L 2015-03..2026-11: fresh $400 each year 2015-24, continuous from 2025-01-01 (same convention as earlier windows).
rng48 percentile thresholds from BUY signals 2015-03..2018-03 only (before the first walk-forward test), so no lookahead in any test window."""
import sys, itertools, json, re; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from quality import *
src = open(Path(__file__).parent / 'stop_modes.py').read()
exec(src[src.index('@nb.njit'):src.index('def rows_mode')])
hour_id = t1 // 3600000; h1_last = np.r_[hour_id[1:] != hour_id[:-1], True]
OUT = Path(__file__).parent
def sell_set(sl, tp, spike):
    out = []; keep = []
    for r in S0.itertuples():
        i = int(r.i); ts = int(dec[i]); j = int(np.searchsorted(t1, ts)); a = float(A[i])
        res = path_mode(j, t1, O, H, L, C, last, h1_last, bidx, SP, SLIP, a, ts, 3 if spike else 0, sl, 5.0, 3.0, tp, 1.0)
        if res[0] < 0: continue
        out.append(res); keep.append(r.Index)
    o = np.array(out, dtype=float); s = S0.loc[keep].copy(); s['sig'] = dec[s.i.to_numpy()]
    return s.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), pnl=o[:, 2], R=o[:, 3], entry=o[:, 4], why=o[:, 5].astype(int), rr_plan=tp, sl_atr=sl)
def buy_set(btp):
    if btp == 3.0: return BUYS
    g = gen(btp=btp); x = g[g.d == 1].copy(); x['sig'] = dec[x.i.to_numpy()]; x['rr_plan'] = btp; x['sl_atr'] = 2.5; return x
AX = dict(atr=[1.01, 0.75, 0.667, 0.6], rng=[None, 0.6, 0.5, 0.4], lon=[False, True], sl=[2.5, 2.75, 3.0], stp=[1.35, 2.0, 2.5, 3.0], btp=[3.0, 2.5], spike=[False, True])
LIVE = dict(atr=1.01, rng=None, lon=False, sl=2.5, stp=1.35, btp=3.0, spike=False)
COMBOS = [dict(zip(AX, v)) for v in itertools.product(*AX.values())]
def cname(c): return f"atr{'-' if c['atr'] > 1 else c['atr']}|rng{'-' if c['rng'] is None else c['rng']}|lon{int(c['lon'])}|sl{c['sl']}|stp{c['stp']}|btp{c['btp']}|spk{int(c['spike'])}"
def nparams(c): return sum(c[k] != LIVE[k] for k in AX)
EARLY = (BASEC.ts >= ms(T('2015-03-02'))) & (BASEC.ts < ms(T('2018-03-01'))) & (BASEC.d == 1)
RNG_T = {q: float(BASEC[EARLY].rng48.quantile(q)) for q in (0.4, 0.5, 0.6)}
FE = {k: BASEC.drop_duplicates('i').set_index('i')[k] for k in ('atr_pct', 'rng48', 'session')}
ATRP = pd.Series(atr_pct); RNGA = pd.Series(RNG48 / A)
SESS = None
YEARS = [(T(f'{y}-01-01') if y > 2015 else T('2015-03-02'), T(f'{y+1}-01-01')) for y in range(2015, 2025)] + [(T('2025-01-01'), END)]
MONTHS = pd.period_range('2015-03', (END - pd.Timedelta(seconds=1)).tz_convert(ICT).strftime('%Y-%m'), freq='M')
def cand_frame(c, SS, BS):
    s = SS[(c['sl'], c['stp'], c['spike'])]; bb = BS[c['btp']]
    x = pd.concat([bb, s]).sort_values(['ts', 'd']).reset_index(drop=True); x = x[~(x.h4dist < 10)]
    i = x.i.to_numpy(); keep = np.ones(len(x), bool)
    if c['atr'] < 1: keep &= ~(atr_pct[i] >= c['atr'])          # skip top part of the ATR percentile (NaN -> kept)
    isb = (x.d == 1).to_numpy()
    if c['rng'] is not None: keep &= ~(isb & ~(RNG48[i] / A[i] <= RNG_T[c['rng']]))
    if c['lon']: keep &= ~(isb & (x.session == 'london_07-13utc').to_numpy())
    return x[keep]
def run_all(x):
    """monthly net, monthly trade count over MONTHS; trade-level maxDD per segment; trades."""
    ts = []
    for a, z in YEARS:
        t = portfolio2(x, a, z)
        if len(t): ts.append(t)
    t = pd.concat(ts, ignore_index=True)
    m = pd.to_datetime(t.ts, unit='ms', utc=True).dt.tz_convert(ICT).dt.tz_localize(None).dt.to_period('M').to_numpy()
    net = t.groupby(m).net.sum().reindex(MONTHS, fill_value=0.0).to_numpy(); cnt = t.groupby(m).size().reindex(MONTHS, fill_value=0).to_numpy()
    return net, cnt, t
if __name__ == '__main__':
    import time; t0 = time.time()
    SS = {(sl, tp, sp): sell_set(sl, tp, sp) for sl in AX['sl'] for tp in AX['stp'] for sp in AX['spike']}
    BS = {b: buy_set(b) for b in AX['btp']}
    print('paths built', round(time.time() - t0), 's; rng thresholds', RNG_T, flush=True)
    chk = cand_frame(LIVE, SS, BS); b0 = BASEC
    assert len(chk) == len(b0) and np.allclose(chk.pnl.to_numpy(), b0.pnl.to_numpy()), 'live parity'
    NET = np.zeros((len(COMBOS), len(MONTHS))); CNT = np.zeros((len(COMBOS), len(MONTHS)), dtype=np.int32)
    for k, c in enumerate(COMBOS):
        NET[k], CNT[k], _ = run_all(cand_frame(c, SS, BS))
        if k % 100 == 0: print(k, round(time.time() - t0), 's', flush=True)
    np.save(OUT / 'combo-net.npy', NET); np.save(OUT / 'combo-cnt.npy', CNT)
    json.dump([cname(c) for c in COMBOS], open(OUT / 'combo-names.json', 'w'))
    print('done', round(time.time() - t0), 's')
