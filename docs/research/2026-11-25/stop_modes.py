"""t201u stop-hunt protection for SELL (BUY unchanged), on live 7fe0 rules (F2+F3, cooldown 30m, cap 10%, daily stop, 0.01 lot).
Logical SL = entry + 2.5 ATR, TP = 1.35R of the logical SL (same price as live), BE at 1R on M15 close (hard, intrabar).
Modes:  0 hard intrabar SL (live baseline)
        1 close-based: exit only when an M15 bar CLOSES (ask) at/above the logical SL; emergency hard SL at entry + E*ATR intrabar
        2 same but H1 close
        3 spike guard (news proxy): hard 2.5 ATR SL intrabar, except while the CURRENT M15 bar's running range (so far, causal) > k*ATR,
          then the SL is checked only at that bar's close; emergency hard SL at E*ATR always
Risk for the 10% cap and for R = emergency distance (what a broker-side SL would be). Path on M1, SL before TP inside a bar."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry_sl import *
OUT = Path(__file__).parent
hour_id = t1 // 3600000; h1_last = np.r_[hour_id[1:] != hour_id[:-1], True]
@nb.njit(cache=False)
def path_mode(j0, t1, O, H, L, C, last, h1l, bidx, sp, slip, atr, sig_ts, mode, sl_mult, emerg, spike_k, tp_rr, be_r):
    n = len(t1)
    if j0 >= n or t1[j0] - sig_ts > 90000: return -1, -1, 0.0, 0.0, 0.0, -1
    entry = O[j0] - slip; fill = j0
    lsl = entry + sl_mult * atr; R0 = lsl - entry; target = entry - tp_rr * R0
    hard = lsl if mode == 0 else entry + emerg * atr
    risk = hard - entry
    prot = False
    # running range of the current M15 bar (bid), started at that bar's first M1
    k0 = fill
    while k0 > 0 and bidx[k0 - 1] == bidx[fill]: k0 -= 1
    rh = -1e18; rl = 1e18
    for q in range(k0, fill): 
        if H[q] > rh: rh = H[q]
        if L[q] < rl: rl = L[q]
    for k in range(fill, n):
        if k > fill and bidx[k] != bidx[k - 1]:
            rh = -1e18; rl = 1e18
        if H[k] > rh: rh = H[k]
        if L[k] < rl: rl = L[k]
        hi = H[k] + sp; lo = L[k] + sp
        if prot:
            if hi >= entry - slip: return t1[fill], t1[k], 0.0, risk, entry, 1
        else:
            if hi >= hard: return t1[fill], t1[k], entry - (hard + slip), risk, entry, 5   # 5 = hard/emergency stop
            if mode == 3 and (rh - rl) <= spike_k * atr and hi >= lsl:
                return t1[fill], t1[k], entry - (lsl + slip), risk, entry, 0
        if lo <= target: return t1[fill], t1[k], entry - target, risk, entry, 2
        cl = C[k] + sp
        if not prot:
            closed = (mode == 1 and last[k]) or (mode == 2 and h1l[k]) or (mode == 3 and last[k])
            if closed and cl >= lsl:
                return t1[fill], t1[k], entry - (cl + slip), risk, entry, 6               # 6 = close-based stop
        if last[k] and (not prot) and (entry - cl) - slip >= be_r * R0:
            prot = True
    return t1[fill], t1[n - 1], entry - (C[n - 1] + sp), risk, entry, 4
def rows_mode(mode, E=10.0, k=0.0, sl=2.5, tp=1.35):
    out = []; keep = []
    for r in S0.itertuples():
        i = int(r.i); ts = int(dec[i]); j = int(np.searchsorted(t1, ts)); a = float(A[i])
        res = path_mode(j, t1, O, H, L, C, last, h1_last, bidx, SP, SLIP, a, ts, mode, sl, E, k, tp, 1.0)
        if res[0] < 0: continue
        out.append(res); keep.append(r.Index)
    o = np.array(out, dtype=float); s = S0.loc[keep].copy(); s['sig'] = dec[s.i.to_numpy()]
    s = s.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), pnl=o[:, 2], R=o[:, 3], entry=o[:, 4], why=o[:, 5].astype(int))
    s['rr_plan'] = tp * sl / (s.R / s.atr); s['sl_atr'] = s.R / s.atr; s['tpx'] = s.entry - tp * sl * s.atr
    return s
V = {'base_hard2.5': dict(mode=0)}
for E in (3.5, 4.0, 5.0): V[f'm15close_emerg{E}'] = dict(mode=1, E=E)
for E in (4.0, 5.0): V[f'h1close_emerg{E}'] = dict(mode=2, E=E)
for k in (2.0, 3.0):
    for E in (4.0, 5.0): V[f'spike{k}atr_emerg{E}'] = dict(mode=3, k=k, E=E)
BN = 'base_hard2.5'
CANDS = {nm: build(rows_mode(**kw)) for nm, kw in V.items()}
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
assert np.allclose(CANDS[BN].pnl.to_numpy(), b0.pnl.to_numpy()), 'parity'
print('parity OK', flush=True)
W2 = dict(WIN); W2['2024-26 all'] = (T('2024-01-01'), END)
def run2(c, wn):
    a, z = W2[wn]
    if wn in ('2015-18', '2019-24'): return run(c, a, z)
    t = portfolio2(c, a, z); return t, [(t, (a, z))]
TR = {}; rows = []
for nm, c in CANDS.items():
    for wn in W2:
        t, parts = run2(c, wn); TR[(nm, wn)] = t
        rows.append(dict(variant=nm, window=wn, **summ(t, parts, *W2[wn])))
W = pd.DataFrame(rows); W.to_csv(OUT / 'stopmodes-windows.csv', index=False)
g = lambda nm, wn, col: W[(W.variant == nm) & (W.window == wn)].iloc[0][col]
def boot(wn):
    a, z = W2[wn]; idx = pd.date_range(a.normalize(), z, freq='D', tz=ICT)[:-1]; n = len(idx); Lb = 20; nb_ = int(np.ceil(n / Lb))
    st = rng.integers(0, n, size=(5000, nb_)); ix = ((st[:, :, None] + np.arange(Lb)[None, None, :]) % n).reshape(5000, -1)[:, :n]
    bd = daily(TR[(BN, wn)], idx); sb = bd[ix].sum(1); out = {}
    for nm in V:
        if nm == BN: continue
        out[nm] = round(((daily(TR[(nm, wn)], idx)[ix].sum(1) - sb) > 0).mean(), 3)
    return out
P = boot('2024-26 all')
out = []
for nm in V:
    t = TR[(nm, '2024-26 all')]; tb = TR[(BN, '2024-26 all')]; c = CANDS[nm]
    s = stats_block(t, BAL0, calendar_months(*W2['2024-26 all'])); m = pd.Series(s['monthly'])
    mb = pd.Series(stats_block(tb, BAL0, calendar_months(*W2['2024-26 all']))['monthly']); dm = m.sub(mb, fill_value=0.0)
    sl_ = t[t.d == -1]
    # stopped then continued: SELL closed by a stop (why 0/5/6), then ask reaches the trade's TP price within 12 h
    nst = ncont = 0
    for r in sl_[sl_.why.isin([0, 5, 6])].itertuples():
        cr = c.loc[r.k]; nst += 1
        j0 = int(np.searchsorted(t1, r.tx)); j1 = int(np.searchsorted(t1, r.tx + 12 * 3600 * 1000))
        if j1 > j0 and (L[j0:j1] + SP).min() <= cr.tpx: ncont += 1
    beats = [g(nm, w, 'net') > g(BN, w, 'net') for w in ('2015-18', '2019-24', '2025-26H1 (OPT)', '2026H2 (HOLD)')]
    out.append(dict(variant=nm, trades=len(t), sell_trades=len(sl_), sell_win=round(100 * (sl_.net > 0).mean(), 1),
        sell_avg_win=round(sl_[sl_.net > 0].net.mean(), 2), sell_avg_loss=round(sl_[sl_.net < 0].net.mean(), 2), sell_max_loss=round(sl_.net.min(), 2),
        sell_expectancy=round(sl_.net.mean(), 2), net=round(s['net'], 2), d_vs_base=round(s['net'] - tb.net.sum(), 2), maxdd=round(s['maxdd'], 2), pf=s['pf'],
        green_pct=round(100 * (m > 0).mean(), 1), worst_month=round(m.min(), 2), d_best_month=dm.idxmax() if nm != BN else '', d_ex_best_month=round(s['net'] - tb.net.sum() - dm.max(), 2) if nm != BN else 0.0,
        months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()), p_better=P.get(nm),
        net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_2526=g(nm, '2025-26 all', 'net'), net_hold=g(nm, '2026H2 (HOLD)', 'net'),
        holdout=('-' if nm == BN else ('PASS' if all(beats) else 'FAIL')), beats=(None if nm == BN else sum(beats)),
        n_close_exit=int((sl_.why == 6).sum()), n_emerg=int((sl_.why == 5).sum()) if nm != BN else 0, n_hard25=int((sl_.why == 0).sum()) + (int((sl_.why == 5).sum()) if nm == BN else 0),
        stopped=nst, stopped_then_continued=ncont, avg_loss_pct_bal=round(100 * -sl_[sl_.net < 0].net.mean() / 382.16, 2), max_loss_pct_bal=round(100 * -sl_.net.min() / 382.16, 2)))
O = pd.DataFrame(out); O.to_csv(OUT / 'stopmodes-compact.csv', index=False)
pd.DataFrame({nm: pd.Series(stats_block(TR[(nm, '2024-26 all')], BAL0, calendar_months(*W2['2024-26 all']))['monthly']) for nm in V}).fillna(0).to_csv(OUT / 'stopmodes-monthly-2024-26.csv')
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 60); print(O.to_string())
# --- Nov 2026 trade view
rowsN = []
for nm in V:
    t = TR[(nm, '2024-26 all')]; t = t[(t.d == -1) & (pd.to_datetime(t.ts, unit='ms', utc=True) >= T('2026-11-10'))]
    for r in t.itertuples():
        rowsN.append(dict(variant=nm, entry_ict=pd.to_datetime(r.ts, unit='ms', utc=True).tz_convert(ICT).strftime('%m-%d %H:%M'),
            exit_ict=pd.to_datetime(r.tx, unit='ms', utc=True).tz_convert(ICT).strftime('%m-%d %H:%M'), why=int(r.why), net=round(r.net, 2)))
N = pd.DataFrame(rowsN); N.to_csv(OUT / 'stopmodes-nov2026.csv', index=False); print(N.to_string()); print('END', END)
