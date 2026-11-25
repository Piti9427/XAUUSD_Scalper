"""SELL entry / SL variants on top of live 7fe0 (26b8 + F2 10 ATR + F3 max 1 loss/UTC day). Box-only research, 25 Nov 2026.
Reuses f2f3-validate core: M1 2015-03 .. 2026-11-24 08:00 ICT, spread 0.24, slip 0.10, BUY swap -0.4743/night, $400, 0.01 lot,
cap 10%, daily stop 10%, cooldown 30 min. BUY side unchanged. Path on M1 bars, SL checked before TP inside each M1 bar.
No lookahead: every level (48-bar low, swing high, ATR, EMA20) is from bars closed at or before the signal bar."""
import sys, json; from pathlib import Path
V = Path('/workspace/c22-trade-journal/research/f2f3-validate-20261124'); sys.path.insert(0, str(V))
from core import *
import numba as nb
OUT = Path(__file__).parent; rng = np.random.default_rng(20261125)
T = lambda s: pd.Timestamp(s, tz=ICT)
BASE = pd.read_pickle(V / 'cands_base.pkl')
hi15 = b.high.to_numpy(); lo15 = b.low.to_numpy()
LL48 = b.low.rolling(48).min().shift(1).to_numpy()
EMA20 = sig.ema(b, 20).to_numpy()

@nb.njit(cache=False)
def path_sell(j0, t1, O, H, L, C, last, sp, slip, atr, sig_ts, mode, lim, timeout_ms, stop_abs, sl_mult, min_r_atr, tp_rr, tp_cap_atr, be_r, max_r_atr):
    n = len(t1)
    if j0 >= n: return -1, -1, 0.0, 0.0, 0.0, -1, 0.0
    if mode == 0:
        if t1[j0] - sig_ts > 90000: return -1, -1, 0.0, 0.0, 0.0, -1, 0.0
        entry = O[j0] - slip; fill = j0
    else:
        fill = -1; entry = 0.0; deadline = sig_ts + timeout_ms
        for k in range(j0, n):
            if t1[k] >= deadline: return -1, -1, 0.0, 0.0, 0.0, -1, 0.0
            if H[k] >= lim:
                entry = lim - slip; fill = k; break
        if fill < 0: return -1, -1, 0.0, 0.0, 0.0, -1, 0.0
    if stop_abs > 0.0:
        stop = stop_abs
        if stop - entry < min_r_atr * atr: stop = entry + min_r_atr * atr
        if max_r_atr > 0.0 and stop - entry > max_r_atr * atr: stop = entry + max_r_atr * atr
    else:
        stop = entry + atr * sl_mult
    R = stop - entry
    if R <= 0.0: return -1, -1, 0.0, 0.0, 0.0, -1, 0.0
    dist = tp_rr * R
    if tp_cap_atr > 0.0 and dist > tp_cap_atr * atr: dist = tp_cap_atr * atr
    target = entry - dist
    prot = False
    for k in range(fill, n):
        if H[k] + sp >= stop:
            return t1[fill], t1[k], entry - (stop + slip), R, entry, (1 if prot else 0), dist / R
        if L[k] + sp <= target:
            return t1[fill], t1[k], entry - target, R, entry, 2, dist / R
        if last[k]:
            ex = C[k] + sp
            if (not prot) and (entry - ex) - slip >= be_r * R:
                prot = True
                if stop > entry - slip: stop = entry - slip
    return t1[fill], t1[n - 1], entry - (C[n - 1] + sp), R, entry, 4, dist / R

S0 = BASE[BASE.d == -1].copy()
SI = S0.i.to_numpy()
rng15 = (hi15[SI] - lo15[SI]) / A[SI]; ext20 = (EMA20[SI] - close[SI]) / A[SI]
S0['bar_range_atr'] = rng15; S0['below_ema20_atr'] = ext20

def swing_high(i, K): return hi15[i - K + 1:i + 1].max()

def sell_rows(mode='mkt', lvl=None, x=0.0, N=0, struct_k=0, buf=0.25, sl=2.5, min_r=1.0, tp=1.35, cap=0.0, be=1.0, filt=None, max_r=0.0):
    out = []; keep = []
    for r in S0.itertuples():
        i = int(r.i); ts = int(dec[i]); j = int(np.searchsorted(t1, ts)); a = float(A[i])
        if filt is not None:
            kind, k = filt
            if kind == 'range' and r.bar_range_atr > k: continue
            if kind == 'ema20' and r.below_ema20_atr > k: continue
        lim = 0.0; m = 0
        if mode == 'lim':
            m = 1; lim = float(LL48[i]) if lvl == 'll48' else float(close[i]) + x * a
        sa = (swing_high(i, struct_k) + SP + buf * a) if struct_k else 0.0
        res = path_sell(j, t1, O, H, L, C, last, SP, SLIP, a, ts, m, lim, int(N * 900000), sa, sl, min_r, tp, cap, be, max_r)
        if res[0] < 0: continue
        out.append(res); keep.append(r.Index)
    o = np.array(out, dtype=float); s = S0.loc[keep].copy()
    s['sig'] = s.ts.to_numpy() if False else dec[s.i.to_numpy()]
    s = s.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), pnl=o[:, 2], R=o[:, 3], entry=o[:, 4], why=o[:, 5].astype(int), rr_plan=o[:, 6])
    s['sl_atr'] = s.R / s.atr
    return s

def portfolio2(c, start, end, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    """core.portfolio + the bot must be flat / out of cooldown / not F3-blocked at SIGNAL time too (a limit order is only placed then)."""
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    bal = bal0; open_ = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0
    def nights(ts, tx):
        r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
        for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
        return n
    for k, r in zip(c.index, c.itertuples()):
        if open_ is not None and open_['tx'] <= r.ts:
            p = open_; open_ = None; bal += p['net']; last_tx = p['tx']
            if p['net'] < 0:
                day = p['tx'] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p['tx'] + cms
            res.append(p)
        if open_ is not None or r.ts < cool: continue
        sg = r.sig
        if last_tx > sg or sg < cool: continue          # position still open / cooling down when the signal fired
        if dl.get(sg // 86400000, 0) >= max_losses: continue
        day = r.ts // 86400000
        if dl.get(day, 0) >= max_losses: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop: continue
        risk = r.R + slip_r
        if risk > bal * cap: continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, rr_plan=getattr(r, 'rr_plan', np.nan), why=r.why, sl_atr=getattr(r, 'sl_atr', np.nan))
    if open_ is not None: res.append(open_)
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    return t

RE_SPECS = {f'g2_reentry_sl{m}_tp{tp}_{mode}': (m, tp, mode) for m in (1.0, 1.5) for tp in (1.35, 2.0, 3.0) for mode in ('strictF3', 'exceptF3')}
BUYS = BASE[BASE.d == 1].copy(); BUYS['sig'] = dec[BUYS.i.to_numpy()]
BUYS['rr_plan'] = 3.0; BUYS['sl_atr'] = 2.5
def build(s):
    c = pd.concat([BUYS, s]).sort_values(['ts', 'd']).reset_index(drop=True)
    return c[~(c.h4dist < 10)]   # F2

VARS = {'a_base': dict()}
for N in (4, 8, 16):
    VARS[f'b_lim_ll48_N{N}'] = dict(mode='lim', lvl='ll48', N=N)
    for x in (0.5, 1.0): VARS[f'b_lim_{x}atr_N{N}'] = dict(mode='lim', x=x, N=N)
for K in (8, 16):
    for tp in (1.35, 2.0):
        VARS[f'c_swing{K}_tp{tp}_tpcap2.5atr'] = dict(struct_k=K, tp=tp, cap=2.5)
        VARS[f'c_swing{K}_tp{tp}_nocap'] = dict(struct_k=K, tp=tp)
        VARS[f'c_swing{K}_slmax2.5atr_tp{tp}'] = dict(struct_k=K, tp=tp, max_r=2.5)
for slm in (3.0, 3.5):
    VARS[f'd_sl{slm}_samedist'] = dict(sl=slm, tp=round(1.35 * 2.5 / slm, 4))
    VARS[f'd_sl{slm}_1.35R'] = dict(sl=slm, tp=1.35)
for k in (1.5, 2.0):
    VARS[f'f_range>{k}atr_skip'] = dict(filt=('range', k))
    VARS[f'f_ema20>{k}atr_skip'] = dict(filt=('ema20', k))
for k in (1.5, 2.0, 2.5):
    for N in (8, 16, 32):
        for slm in ('1.0', '1.5', 'swing16'):
            for tp in (1.35, 2.0, 3.0):
                kw = dict(mode='lim', x=k, N=N, tp=tp)
                if slm == 'swing16': kw.update(struct_k=16)
                else: kw.update(sl=float(slm))
                VARS[f'g1_rally{k}atr_N{N}_sl{slm}_tp{tp}'] = kw
for nm in RE_SPECS: VARS[nm] = dict(reentry=nm)
WIN = {'2015-18': (T('2015-03-02'), T('2019-01-01')), '2019-24': (T('2019-01-02'), T('2025-01-01')),
       '2025-26H1 (OPT)': (T('2025-01-01'), T('2026-07-01')), '2026H2 (HOLD)': (T('2026-07-01'), END), '2025-26 all': (T('2025-01-01'), END)}
def segs(a, z):
    out = []; y = a.year
    while T(f'{y}-01-01') < z:
        s0, s1 = max(a, T(f'{y}-01-01')), min(z, T(f'{y+1}-01-01'))
        if y >= 2025: s1 = z
        if s0 < s1: out.append((s0, s1))
        if y >= 2025: break
        y += 1
    return out
def run(c, a, z, rex=None):
    if rex is None: parts = [(portfolio2(c, s0, s1), (s0, s1)) for s0, s1 in segs(a, z)]
    else: parts = [(portfolio3(c, rex[0], s0, s1, rex[1]), (s0, s1)) for s0, s1 in segs(a, z)]
    return pd.concat([p for p, _ in parts if len(p)], ignore_index=True), parts
def summ(t, parts, a, z):
    s = stats_block(t, BAL0, calendar_months(a, z)); dd = max(stats_block(p, BAL0, calendar_months(*g))['maxdd'] for p, g in parts)
    sl = t[t.d == -1]
    return dict(n=s['n'], n_sell=len(sl), win=s['win'], sell_win=round(100 * (sl.net > 0).mean(), 1) if len(sl) else None,
                avgR=round(t.r.mean(), 3), sell_avgR=round(sl.r.mean(), 3) if len(sl) else None, sell_rr_plan=round(sl.rr_plan.mean(), 2) if len(sl) else None,
                sell_sl_atr=round(sl.sl_atr.mean(), 2) if len(sl) else None,
                net=round(s['net'], 2), sell_net=round(sl.net.sum(), 2), pf=s['pf'], maxdd=round(dd, 2), worst_month=s['worst'],
                green_pct=round(100 * np.mean([v > 0 for v in s['monthly'].values()]), 1) if s['monthly'] else 0, losses=int((t.net < 0).sum()))

def evaluate(VARS, tag):
    global portfolio2_sel
    CANDS = {}; FILL = {}; REX = {}
    for nm, kw in VARS.items():
        if nm.startswith('g2_'):
            m, tp, mode = RE_SPECS[nm]; s, x = reentry_rows(m, tp); REX[nm] = (x, mode); FILL[nm] = (len(x), len(S0))
        else:
            s = sell_rows(**kw); FILL[nm] = (len(s), len(S0))
        CANDS[nm] = build(s)
    if 'a_base' in CANDS:
        b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True); chk = CANDS['a_base']
        assert len(chk) == len(b0) and np.allclose(chk.pnl.to_numpy(), b0.pnl.to_numpy()), 'parity failed'
        t_old = portfolio(b0, *WIN['2025-26 all'], max_losses=1); t_new = portfolio2(chk, *WIN['2025-26 all'])
        assert abs(t_old.net.sum() - t_new.net.sum()) < 1e-6, (t_old.net.sum(), t_new.net.sum())
        print('parity OK: a_base == f2f3-validate candidates; portfolio2 == core.portfolio on 2025-26 net', round(t_new.net.sum(), 2), flush=True)
    rows = []; TR = {}
    for nm, c in CANDS.items():
        for wn, (a, z) in WIN.items():
            t, parts = run(c, a, z, REX.get(nm)); TR[(nm, wn)] = t
            rows.append(dict(variant=nm, window=wn, sell_signals_filled=FILL[nm][0], sell_signals_all=FILL[nm][1], n_reentry=int(sum(p.attrs.get('n_re', 0) for p, _ in parts)), **summ(t, parts, a, z)))
    return CANDS, TR, pd.DataFrame(rows)

RE_SPECS = {f'g2_reentry_sl{m}_tp{tp}_{mode}': (m, tp, mode) for m in (1.0, 1.5) for tp in (1.35, 2.0, 3.0) for mode in ('strictF3', 'exceptF3')}
def reentry_rows(m, tp):
    """For every baseline SELL that hits its full SL (why 0), a new SELL at the next M1 open after the stop-out (market, ~1 min late)."""
    out = []; keep = []
    base = sell_rows()
    for r in base.itertuples():
        if r.why != 0: continue
        j = int(np.searchsorted(t1, r.tx)) + 1
        if j >= len(t1): continue
        res = path_sell(j, t1, O, H, L, C, last, SP, SLIP, float(r.atr), int(t1[j]), 0, 0.0, 0, 0.0, m, 1.0, tp, 0.0, 1.0, 0.0)
        if res[0] < 0: continue
        out.append(res); keep.append(r.Index)
    o = np.array(out, dtype=float); x = base.loc[keep].copy()
    x['parent_i'] = x.i
    x = x.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), pnl=o[:, 2], R=o[:, 3], entry=o[:, 4], why=o[:, 5].astype(int), rr_plan=o[:, 6])
    x['sig'] = x.ts; x['sl_atr'] = x.R / x.atr
    return base, x
def portfolio3(c, re, start, end, mode, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    """portfolio2 + re-entry: when a SELL closes at its full SL, the linked re-entry SELL opens at once.
    strictF3: re-entry must pass F3 (1 loss/UTC day) and the 30-min cooldown like any trade -> it can never fire right after a loss.
    exceptF3: re-entry is exempt from F3/cooldown for that one stop-out (still risk cap + daily stop); its own loss counts toward F3 afterwards."""
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    RE = {int(r.parent_i): r for r in re.itertuples()}
    bal = bal0; open_ = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0; n_re = 0
    def nights(ts, tx):
        r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
        for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
        return n
    def close_upto(t):
        nonlocal open_, bal, last_tx, cool, n_re
        while open_ is not None and open_['tx'] <= t:
            p = open_; open_ = None; bal += p['net']; last_tx = p['tx']
            if p['net'] < 0:
                day = p['tx'] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p['tx'] + cms
            res.append(p)
            q = RE.get(p.get('i', -1)) if (p['d'] == -1 and p['why'] == 0 and not p.get('re', False)) else None
            if q is None or q.ts >= ms(end): continue
            if mode == 'strictF3' and (q.ts < cool or dl.get(q.ts // 86400000, 0) >= max_losses): continue
            day = q.ts // 86400000; daystart.setdefault(day, bal)
            if daystart[day] - bal >= daystart[day] * daily_stop: continue
            if q.R + slip_r > bal * cap: continue
            open_ = dict(ts=q.ts, tx=q.tx, d=-1, net=q.pnl, R=q.R + slip_r, rr_plan=q.rr_plan, why=q.why, sl_atr=q.sl_atr, i=-1, re=True); n_re += 1
    for k, r in zip(c.index, c.itertuples()):
        close_upto(r.ts)
        if open_ is not None or r.ts < cool: continue
        sg = r.sig
        if last_tx > sg or sg < cool: continue
        if dl.get(sg // 86400000, 0) >= max_losses: continue
        day = r.ts // 86400000
        if dl.get(day, 0) >= max_losses: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop: continue
        risk = r.R + slip_r
        if risk > bal * cap: continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, rr_plan=r.rr_plan, why=r.why, sl_atr=r.sl_atr, i=int(r.i), re=False)
    close_upto(ms(end) + 10**13)
    if open_ is not None: res.append(open_)
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs['n_re'] = n_re
    return t

def daily(t, idx):
    d = pd.DatetimeIndex(pd.to_datetime(t.tx.to_numpy(), unit='ms', utc=True).tz_convert(ICT).normalize())
    return pd.Series(t.net.to_numpy(), index=d).groupby(level=0).sum().reindex(idx, fill_value=0.0).to_numpy()
def mdd(x):
    eq = np.cumsum(x, axis=-1); pk = np.maximum.accumulate(np.maximum(eq, 0), axis=-1); return (pk - eq).max(axis=-1)
def bootstrap(TR, names, base='a_base'):
    br = []
    for wn in ('2015-18', '2019-24', '2025-26 all', '2026H2 (HOLD)'):
        a, z = WIN[wn]; idx = pd.date_range(a.normalize(), z, freq='D', tz=ICT)[:-1]; n = len(idx); Lb = 20; nb_ = int(np.ceil(n / Lb))
        st = rng.integers(0, n, size=(5000, nb_)); ix = ((st[:, :, None] + np.arange(Lb)[None, None, :]) % n).reshape(5000, -1)[:, :n]
        bd = daily(TR[(base, wn)], idx); xb = bd[ix]; mb = mdd(xb); sb = xb.sum(1)
        for nm in names:
            if nm == base: continue
            fd = daily(TR[(nm, wn)], idx); xf = fd[ix]; dn = xf.sum(1) - sb; dd = mdd(xf) - mb
            br.append(dict(variant=nm, window=wn, d_net=round(fd.sum() - bd.sum(), 2), d_net_ci90=f"[{np.percentile(dn,5):.1f}, {np.percentile(dn,95):.1f}]",
                           p_better_net=round((dn > 0).mean(), 3), p_lower_dd=round((dd < 0).mean(), 3)))
    return pd.DataFrame(br)

if __name__ == '__main__':
    pd.set_option('display.width', 280); pd.set_option('display.max_columns', 40)
    CANDS, TR, W = evaluate(VARS, 'main')
    # (e) combination: best (b) and best (c) chosen on 2015-24 only (score = summed net / worst yearly DD)
    def score(nm):
        r1 = W[(W.variant == nm) & (W.window == '2015-18')].iloc[0]; r2 = W[(W.variant == nm) & (W.window == '2019-24')].iloc[0]
        return round((r1.net + r2.net) / max(r1.maxdd, r2.maxdd), 3), round(r1.net + r2.net, 2), max(r1.maxdd, r2.maxdd)
    sel = pd.DataFrame([dict(variant=nm, old_score=score(nm)[0], old_net=score(nm)[1], old_maxdd=score(nm)[2]) for nm in VARS]).sort_values('old_score', ascending=False)
    bb = sel[sel.variant.str.startswith('b_')].iloc[0].variant; cc = sel[sel.variant.str.startswith('c_')].iloc[0].variant
    kw = {**VARS[bb], **{k: v for k, v in VARS[cc].items()}}; ename = f'e_{bb[2:]}+{cc[2:]}'
    print('combo from 2015-24 selection:', ename, kw, flush=True)
    dd_ = sel[sel.variant.str.startswith('d_')].iloc[0].variant; kw2 = {**VARS[bb], **VARS[dd_]}; ename2 = f'e2_{bb[2:]}+{dd_[2:]}'
    print('extra combo (b+d):', ename2, kw2, flush=True)
    C2, TR2, W2 = evaluate({ename: kw, ename2: kw2}, 'combo'); VARS[ename2] = kw2
    CANDS.update(C2); TR.update(TR2); W = pd.concat([W, W2], ignore_index=True); VARS[ename] = kw
    sel = pd.concat([sel, pd.DataFrame([dict(variant=e_, old_score=score(e_)[0], old_net=score(e_)[1], old_maxdd=score(e_)[2]) for e_ in (ename, ename2)])]).sort_values('old_score', ascending=False)
    W.to_csv(OUT / 'windows.csv', index=False); sel.to_csv(OUT / 'selection-2015-24.csv', index=False)
    print(W.to_string(), flush=True); print(sel.to_string(), flush=True)
    BR = bootstrap(TR, list(VARS)); BR.to_csv(OUT / 'bootstrap-vs-base.csv', index=False); print(BR.to_string(), flush=True)
    # hold-out verdict: must beat the baseline net in every independent window (2015-18, 2019-24, 2025-26H1, 2026H2 HOLD)
    def robust(t, tb):
        d = t.net.sum() - tb.net.sum(); srt = t.net.sort_values(ascending=False)
        mon = pd.Series(t.net.to_numpy(), index=pd.to_datetime(t.ts.to_numpy(), unit='ms', utc=True).tz_convert(ICT).strftime('%Y-%m')).groupby(level=0).sum()
        monb = pd.Series(tb.net.to_numpy(), index=pd.to_datetime(tb.ts.to_numpy(), unit='ms', utc=True).tz_convert(ICT).strftime('%Y-%m')).groupby(level=0).sum()
        dm = mon.sub(monb, fill_value=0.0)
        return dict(best_trade=round(srt.iloc[0], 2), net_ex_best_trade=round(t.net.sum() - srt.iloc[0], 2), net_ex_top5=round(t.net.sum() - srt.iloc[:5].sum(), 2),
                    d_vs_base=round(d, 2), d_ex_best_month=round(d - dm.max(), 2) if len(dm) else 0.0, months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()))
    rows = []
    g = lambda nm, wn, col: W[(W.variant == nm) & (W.window == wn)].iloc[0][col]
    for nm in VARS:
        beats = {wn: g(nm, wn, 'net') > g('a_base', wn, 'net') for wn in ('2015-18', '2019-24', '2025-26H1 (OPT)', '2026H2 (HOLD)')}
        r = W[(W.variant == nm) & (W.window == '2025-26 all')].iloc[0]
        p = BR[(BR.variant == nm) & (BR.window == '2025-26 all')]
        rows.append(dict(variant=nm, trades=r.n, sell_trades=r.n_sell, win=r.win, sell_win=r.sell_win, net=r.net, sell_net=r.sell_net, maxdd=r.maxdd, pf=r.pf,
                         sell_avgR=r.sell_avgR, sell_rr_plan=r.sell_rr_plan, sell_sl_atr=r.sell_sl_atr, green_pct=r.green_pct, worst_month=r.worst_month,
                         net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_hold=g(nm, '2026H2 (HOLD)', 'net'),
                         old_rank=int(list(sel.variant).index(nm)) + 1,
                         beats_windows=sum(beats.values()), holdout='PASS' if all(beats.values()) else 'FAIL',
                         p_better_net=(p.p_better_net.iloc[0] if len(p) else None), p_lower_dd=(p.p_lower_dd.iloc[0] if len(p) else None),
                         fill=f"{r.sell_signals_filled}/{r.sell_signals_all}", n_reentry_2526=int(r.n_reentry),
                         **robust(TR[(nm, '2025-26 all')], TR[('a_base', '2025-26 all')])))
    CT = pd.DataFrame(rows); CT.to_csv(OUT / 'compact-table.csv', index=False); print(CT.to_string(), flush=True)
    # monthly 2025-26 per variant
    mrows = []
    for nm in VARS:
        t = TR[(nm, '2025-26 all')]; s = stats_block(t, BAL0, calendar_months(*WIN['2025-26 all']))
        for m, v in s['monthly'].items(): mrows.append(dict(variant=nm, month=m, net=v))
    pd.DataFrame(mrows).pivot(index='month', columns='variant', values='net').to_csv(OUT / 'monthly-2025-26.csv')
    json.dump({k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in VARS.items()}, open(OUT / 'variants.json', 'w'), indent=1)
    print('END', END)
