"""t200u entry-quality filters on live 7fe0 (26b8 + F2 + F3, cooldown 30m, cap 10%, daily stop, 0.01 lot), SELL and BUY.
Select on 2015-03..2024 (fresh $400 each year, as in earlier hold-out runs), validate on 2025-26 (continuous) + 2025-26H1 / 2026H2 hold-out.
All features causal: computed from bars closed at or before the signal bar (H1/H4 from fully closed H1/H4 bars).
Rank = mean rank of (% positive months desc, worst month desc, max DD asc, negative months asc); months with no trade count as not positive.
Thresholds that are percentiles are taken on the 2015-24 signal sample only."""
import sys, itertools, json; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry_sl import *
OUT = Path(__file__).parent
SEL = (T('2015-03-02'), T('2025-01-01'))
WV = {'SEL 2015-24': SEL, '2015-18': WIN['2015-18'], '2019-24': WIN['2019-24'], '2025-26 all': WIN['2025-26 all'],
      '2025-26H1': WIN['2025-26H1 (OPT)'], '2026H2 HOLD': WIN['2026H2 (HOLD)'], '2024-26 all': (T('2024-01-01'), END)}
# ---------- features on the M15 frame (index = bar open, UTC); signal decided at bar close dec[i]
cl = b.close
def htf(rule, span):
    h = b.resample(rule, label='left', closed='left').agg({'close': 'last'}).dropna()
    e = h.close.ewm(span=span, adjust=False).mean()
    end = (h.index + pd.Timedelta(rule)).as_unit('ms').asi8          # close time of each HTF bar
    pos = np.searchsorted(end, dec, side='right') - 1               # last HTF bar closed at/before signal
    ok = pos >= 3
    pc = np.where(ok, h.close.to_numpy()[pos.clip(0)], np.nan); pe = np.where(ok, e.to_numpy()[pos.clip(0)], np.nan)
    pe3 = np.where(ok, e.to_numpy()[(pos - 3).clip(0)], np.nan)
    return pc, pe, pe3
h1c, h1e, h1e3 = htf('1h', 50); h4c, h4e50, h4e50_3 = htf('4h', 50)
_, h4e200, _ = htf('4h', 200)
EMA20v = sig.ema(b, 20).to_numpy()
d_ = cl.diff(); up = d_.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); dn = (-d_.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
RSI14 = (100 - 100 / (1 + up / dn)).to_numpy()
ROC16 = (cl - cl.shift(16)).to_numpy()
RNG48 = (b.high.rolling(48).max().shift(1) - b.low.rolling(48).min().shift(1)).to_numpy()
BASEC = build(sell_rows())
def feats(c):
    i = c.i.to_numpy(); d = c.d.to_numpy(); a = A[i]
    c = c.copy()
    c['h1_side'] = d * (h1c[i] - h1e[i]) / a; c['h1_slope'] = d * (h1e[i] - h1e3[i]) / a
    c['h4_side50'] = d * (h4c[i] - h4e50[i]) / a; c['h4_slope50'] = d * (h4e50[i] - h4e50_3[i]) / a; c['h4_stack'] = d * (h4e50[i] - h4e200[i]) / a
    c['ext20'] = d * (close[i] - EMA20v[i]) / a                       # >0 = extended in trade direction
    c['rsi_dir'] = np.where(d == 1, RSI14[i], 100 - RSI14[i])         # high = strong momentum in trade direction
    c['roc16'] = d * ROC16[i] / a; c['rng48'] = RNG48[i] / a
    return c
BASEC = feats(BASEC)
selmask = (BASEC.ts >= ms(SEL[0])) & (BASEC.ts < ms(SEL[1]))
def pct(col, side, q): x = BASEC[selmask & (BASEC.d == side)][col].dropna(); return float(x.quantile(q))
# ---------- filter specs: (name, side(-1/1/0 both), function(df)->keep mask)
F = []
def add(nm, side, fn): F.append((nm, side, fn))
for side, sn in ((-1, 'S'), (1, 'B'), (0, 'SB')):
    sides = (-1, 1) if side == 0 else (side,)
    def mk(fn_by_side, sides=sides):
        def f(c):
            keep = np.ones(len(c), bool)
            for s in sides:
                m = (c.d == s).to_numpy(); keep[m] = fn_by_side(c[m], s)
            return keep
        return f
    add(f'{sn}:h1_side>0', side, mk(lambda c, s: (c.h1_side > 0).to_numpy()))
    add(f'{sn}:h1_slope>0', side, mk(lambda c, s: (c.h1_slope > 0).to_numpy()))
    add(f'{sn}:h1_side&slope>0', side, mk(lambda c, s: ((c.h1_side > 0) & (c.h1_slope > 0)).to_numpy()))
    add(f'{sn}:h4_slope50>0', side, mk(lambda c, s: (c.h4_slope50 > 0).to_numpy()))
    add(f'{sn}:h4_stack>0', side, mk(lambda c, s: (c.h4_stack > 0).to_numpy()))
    add(f'{sn}:h4slope200>0', side, mk(lambda c, s: (c.h4slope > 0).to_numpy()))
    add(f'{sn}:h1+h4_aligned', side, mk(lambda c, s: ((c.h1_slope > 0) & (c.h4_slope50 > 0) & (c.h4_stack > 0)).to_numpy()))
    for q in (0.5, 0.75, 0.9):
        add(f'{sn}:h4dist<=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.h4dist <= pct('h4dist', s, q)).to_numpy()))
        add(f'{sn}:ext20<=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.ext20 <= pct('ext20', s, q)).to_numpy()))
        add(f'{sn}:rng48<=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.rng48 <= pct('rng48', s, q)).to_numpy()))
    for q in (0.1, 0.25):
        add(f'{sn}:h4dist>=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.h4dist >= pct('h4dist', s, q)).to_numpy()))
        add(f'{sn}:rng48>=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.rng48 >= pct('rng48', s, q)).to_numpy()))
        add(f'{sn}:roc16>=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.roc16 >= pct('roc16', s, q)).to_numpy()))
        add(f'{sn}:roc16<=p{int(100-q*100)}', side, mk(lambda c, s, q=q: (c.roc16 <= pct('roc16', s, 1 - q)).to_numpy()))
        add(f'{sn}:rsi_dir<=p{int(100-q*100)}', side, mk(lambda c, s, q=q: (c.rsi_dir <= pct('rsi_dir', s, 1 - q)).to_numpy()))
        add(f'{sn}:rsi_dir>=p{int(q*100)}', side, mk(lambda c, s, q=q: (c.rsi_dir >= pct('rsi_dir', s, q)).to_numpy()))
    for lo, hi in ((0.0, 0.8), (0.2, 1.01), (0.2, 0.8), (0.0, 0.67), (0.33, 1.01)):
        add(f'{sn}:atr_pct[{lo},{min(hi,1.0)}]', side, mk(lambda c, s, lo=lo, hi=hi: ((c.atr_pct >= lo) & (c.atr_pct < hi)).to_numpy()))
    for ss in ('asia_00-07utc', 'london_07-13utc', 'ny_13-21utc', 'late_21-24utc'):
        add(f'{sn}:no_{ss}', side, mk(lambda c, s, ss=ss: (c.session != ss).to_numpy()))
    add(f'{sn}:london+ny_only', side, mk(lambda c, s: c.session.isin(['london_07-13utc', 'ny_13-21utc']).to_numpy()))
    for wd, wn in enumerate(('mon', 'tue', 'wed', 'thu', 'fri')):
        add(f'{sn}:no_{wn}', side, mk(lambda c, s, wd=wd: (c.wd_ict != wd).to_numpy()))
FD = {nm: (side, fn) for nm, side, fn in F}
def monthly(t, a, z):
    idx = pd.period_range(a.tz_convert(ICT).strftime('%Y-%m'), (z - pd.Timedelta(seconds=1)).tz_convert(ICT).strftime('%Y-%m'), freq='M')
    if len(t) == 0: return pd.Series(0.0, idx)
    m = pd.to_datetime(t.ts, unit='ms', utc=True).dt.tz_convert(ICT).dt.tz_localize(None).dt.to_period('M')
    return t.groupby(m.to_numpy()).net.sum().reindex(idx, fill_value=0.0)
def evalc(c, wn):
    a, z = WV[wn]
    if wn in ('SEL 2015-24', '2015-18', '2019-24'): t, parts = run(c, a, z)
    else: t = portfolio2(c, a, z); parts = [(t, (a, z))]
    if len(t) == 0: return dict(n=0), t
    m = monthly(t, a, z); dd = max(stats_block(p, BAL0, calendar_months(*g))['maxdd'] for p, g in parts if len(p))
    s = stats_block(t, BAL0, calendar_months(a, z))
    return dict(n=len(t), n_sell=int((t.d == -1).sum()), n_buy=int((t.d == 1).sum()), tpm=round(len(t) / len(m), 2), win=round(100 * (t.net > 0).mean(), 1),
                net=round(t.net.sum(), 2), pf=s['pf'], maxdd=round(dd, 2), green=round(100 * (m > 0).mean(), 1), neg=int((m < 0).sum()), zero=int((m == 0).sum()),
                worst=round(m.min(), 2), months=len(m), avg_month=round(m.mean(), 2)), t
def apply(names, base=BASEC):
    keep = np.ones(len(base), bool)
    for nm in names: keep &= FD[nm][1](base)
    return base[keep]
def rankdf(D):
    r = (D.green.rank(ascending=False) + D.worst.rank(ascending=False) + D.maxdd.rank() + D.neg.rank()) / 4
    return D.assign(score=r.round(2)).sort_values('score')
if __name__ == '__main__':
    print('filters', len(F), flush=True)
    base_sel, _ = evalc(BASEC, 'SEL 2015-24'); print('base', base_sel, flush=True)
    rows = [dict(variant='BASE', **base_sel)]
    for nm, side, fn in F:
        r, _ = evalc(apply([nm]), 'SEL 2015-24'); rows.append(dict(variant=nm, **r))
    S1 = rankdf(pd.DataFrame(rows)); S1.to_csv(OUT / 'quality-stage1-sel2015-24.csv', index=False)
    ok = S1[(S1.tpm >= 5) & (S1.variant != 'BASE')]
    print(S1.head(25).to_string(), flush=True)
    # stage 2: combos of top singles (at most one filter per feature family+side)
    def fam(nm):
        f = nm.split(':')[1]
        for ch in '<>[': f = f.split(ch)[0]
        if f.startswith('no_') and f[3:] in ('mon', 'tue', 'wed', 'thu', 'fri'): return 'dow'
        if f.startswith('no_') or f.startswith('london'): return 'session'
        return f.split('&')[0].replace('h1_side', 'h1').replace('h1_slope', 'h1')
    top = []
    for nm in ok.variant:
        if fam(nm) not in [fam(x) for x in top]: top.append(nm)
        if len(top) == 12: break
    rows2 = []
    for k in (2, 3):
        for combo in itertools.combinations(top, k):
            if len({fam(x) for x in combo}) < k: continue
            r, _ = evalc(apply(list(combo)), 'SEL 2015-24'); rows2.append(dict(variant=' + '.join(combo), **r))
    S2 = rankdf(pd.concat([pd.DataFrame(rows), pd.DataFrame(rows2)], ignore_index=True))
    S2.to_csv(OUT / 'quality-stage2-sel2015-24.csv', index=False)
    S2ok = S2[(S2.tpm >= 5)]
    print(S2ok.head(20).to_string(), flush=True)
    # validation of the top 12 (by selection rank) + BASE
    cand = ['BASE'] + [v for v in S2ok.variant if v != 'BASE'][:12]
    vrows = []; TRV = {}
    for v in cand:
        c = BASEC if v == 'BASE' else apply(v.split(' + '))
        for wn in WV:
            r, t = evalc(c, wn); TRV[(v, wn)] = t; vrows.append(dict(variant=v, window=wn, **r))
    VD = pd.DataFrame(vrows); VD.to_csv(OUT / 'quality-validation.csv', index=False)
    pd.to_pickle((cand, TRV), OUT / 'quality-trv.pkl')
    json.dump(dict(top_singles=top, cand=cand), open(OUT / 'quality-cands.json', 'w'), indent=1)
    pd.set_option('display.width', 400); pd.set_option('display.max_columns', 40)
    print(VD.to_string())
