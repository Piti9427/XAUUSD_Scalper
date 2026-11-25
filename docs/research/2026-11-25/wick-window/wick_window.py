"""Wick-window SELL stop (pre-registered 25 Nov 2026 17:12 ICT, wick-window-preregister.md). Box-only research.
Imports the f2f3-validate harness (via sell-entry-sl-20261125/entry_sl.py helpers); harness files are not modified.
New SELL exit path: TP and BE tied to R_live = 2.5*ATR (NOT to the wide stop). Early hard SL = entry + W*ATR for the first
N closed M15 bars; at bar N close (if not stopped, not BE) tighten to entry + 2.5*ATR (tighten only, never loosen, never after BE).
SL checked before TP in each M1 bar. Risk cap uses the wide SL (W*ATR + slip) for the whole trade; over-cap trades are rejected.
Implementation note: if at bar-N close the ask is already >= the tightened stop, the trade is closed at market at that close
(close + spread + slip), since a SELL stop cannot be placed below the current ask (why=6)."""
import sys; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *          # core (m1/m15, ATR, signals), BASE, S0, BUYS, build, portfolio2, run, summ, WIN, T, sell_rows
import numba as nb
OUT = Path(__file__).parent

@nb.njit(cache=False)
def path_wick(j0, t1, O, H, L, C, last, sp, slip, atr, sig_ts, W, N, scratch, tp_rr, be_r, scr_r):
    n = len(t1)
    if j0 >= n or t1[j0] - sig_ts > 90000: return -1, -1, 0.0, 0.0, 0.0, -1, 0
    entry = O[j0] - slip; fill = j0
    Rl = 2.5 * atr; tight = entry + 2.5 * atr
    stop = entry + W * atr; target = entry - tp_rr * Rl
    prot = False; tightened = W <= 2.5; nc = 0
    for k in range(fill, n):
        if H[k] + sp >= stop:
            why = 1 if prot else (3 if tightened else 0)
            return t1[fill], t1[k], entry - (stop + slip), entry, W * atr, why, nc
        if L[k] + sp <= target:
            return t1[fill], t1[k], entry - target, entry, W * atr, 2, nc
        if last[k]:
            nc += 1; ex = C[k] + sp
            if (not prot) and (entry - ex) - slip >= be_r * Rl:
                prot = True
                if stop > entry - slip: stop = entry - slip
            if nc == N and (not prot) and (not tightened):
                if scratch and (entry - ex) - slip < scr_r * Rl:
                    return t1[fill], t1[k], entry - (ex + slip), entry, W * atr, 5, nc
                tightened = True
                if ex >= tight:
                    return t1[fill], t1[k], entry - (ex + slip), entry, W * atr, 6, nc
                if stop > tight: stop = tight
    return t1[fill], t1[n - 1], entry - (C[n - 1] + sp), entry, W * atr, 4, nc

def wick_rows(W, N, scratch=False):
    out = []; keep = []
    for r in S0.itertuples():
        i = int(r.i); ts = int(dec[i]); j = int(np.searchsorted(t1, ts)); a = float(A[i])
        res = path_wick(j, t1, O, H, L, C, last, SP, SLIP, a, ts, float(W), int(N), bool(scratch), 1.35, 1.0, 0.25)
        if res[0] < 0: continue
        out.append(res); keep.append(r.Index)
    o = np.array(out, dtype=float); s = S0.loc[keep].copy()
    s['sig'] = dec[s.i.to_numpy()]
    s = s.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), pnl=o[:, 2], entry=o[:, 3], R=o[:, 4], why=o[:, 5].astype(int), nc=o[:, 6].astype(int))
    s['rr_plan'] = 1.35 * 2.5 / W; s['sl_atr'] = s.R / s.atr
    return s

CELLS = {'base_live': (2.5, 2, False), 'wick_3.0_n2': (3.0, 2, False), 'wick_2.75_n2': (2.75, 2, False), 'wick_3.25_n2': (3.25, 2, False),
         'wick_3.0_n1': (3.0, 1, False), 'wick_3.0_n4': (3.0, 4, False), 'wick_3.0_n2_scratch': (3.0, 2, True)}
BN = 'base_live'; REF = 'ref_fullline_sl3.0_tp1.35R'
A24 = T('2024-01-01')
# ---------- 1. parity of the harness baseline ----------
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
p25 = portfolio(b0, *WIN['2025-26 all'], max_losses=1).net.sum(); p25b, _ = run(build(sell_rows()), *WIN['2025-26 all'])
p24 = portfolio2(build(sell_rows()), A24, END)
par = dict(core_2025_26=round(p25, 2), portfolio2_2025_26=round(p25b.net.sum(), 2), portfolio2_2024_26=round(p24.net.sum(), 2),
           dd_2024_26=round(stats_block(p24, BAL0, calendar_months(A24, END))['maxdd'], 2), dd_2025_26=round(stats_block(p25b, BAL0, calendar_months(*WIN['2025-26 all']))['maxdd'], 2))
print('harness parity', par, flush=True)
assert par['core_2025_26'] == 1898.96 and par['portfolio2_2025_26'] == 1898.96 and par['portfolio2_2024_26'] == 1826.95, 'PARITY FAILED - stop'
# ---------- 2. new simulator with W=2.5 must reproduce baseline ----------
CANDS = {nm: build(wick_rows(*v)) for nm, v in CELLS.items()}
cb = CANDS[BN]; old = build(sell_rows())
assert len(cb) == len(old) and np.allclose(cb.pnl.to_numpy(), old.pnl.to_numpy()) and (cb.tx.to_numpy() == old.tx.to_numpy()).all(), 'new-sim W=2.5 != baseline'
s25, _ = run(cb, *WIN['2025-26 all']); s24 = portfolio2(cb, A24, END)
assert round(s25.net.sum(), 2) == 1898.96 and round(s24.net.sum(), 2) == 1826.95, 'new-sim portfolio parity failed'
print('new simulator W=2.5 parity OK', round(s25.net.sum(), 2), round(s24.net.sum(), 2), flush=True)
CANDS[REF] = build(sell_rows(sl=3.0, tp=1.35))   # old path_sell full-line SL 3.0 / TP 1.35R, reference only
# ---------- 3. evaluate ----------
WINS = dict(WIN); WINS['2024-26 all'] = (A24, END)
TR = {}; rows = []
for nm, c in CANDS.items():
    for wn, (a, z) in WINS.items():
        if wn == '2024-26 all':
            t = portfolio2(c, a, z); parts = [(t, (a, z))]
        else: t, parts = run(c, a, z)
        TR[(nm, wn)] = t; rows.append(dict(variant=nm, window=wn, **summ(t, parts, a, z)))
Wdf = pd.DataFrame(rows); Wdf.to_csv(OUT / 'wick-windows.csv', index=False)
g = lambda nm, wn, col: Wdf[(Wdf.variant == nm) & (Wdf.window == wn)].iloc[0][col]
REASON = {0: 'sl_early_wide', 3: 'sl_after_tighten', 1: 'be_stop', 2: 'tp', 4: 'open_end', 5: 'scratch_exit', 6: 'tighten_mkt_exit'}
Ncell = lambda nm: CELLS[nm][1] if nm in CELLS else 2
out = []; mon = {}
for nm in CANDS:
    for wn in ('2025-26 all', '2024-26 all'):
        a, z = WINS[wn]; t = TR[(nm, wn)]; tb = TR[(BN, wn)]; months = calendar_months(a, z)
        m = pd.Series(stats_block(t, BAL0, months)['monthly']); mb = pd.Series(stats_block(tb, BAL0, months)['monthly'])
        mon[(nm, wn)] = m; dm = m.sub(mb, fill_value=0.0); sl_ = t[t.d == -1].copy(); c = CANDS[nm]
        if 'nc' in c: sl_['nc'] = c.loc[sl_.k.to_numpy(), 'nc'].to_numpy()
        rc = sl_.why.map(REASON).value_counts()
        dd = g(nm, wn, 'maxdd'); d = t.net.sum() - tb.net.sum()
        out.append(dict(variant=nm, window=wn, trades=len(t), sell_trades=len(sl_), net=round(t.net.sum(), 2), d_vs_base=round(d, 2), maxdd=dd,
            sell_win=round(100 * (sl_.net > 0).mean(), 1), sell_avg_loss=round(sl_[sl_.net < 0].net.mean(), 2), sell_max_loss=round(sl_.net.min(), 2),
            months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()),
            d_best_month=dm.idxmax() if (nm != BN and dm.max() > 0.005) else '', d_ex_best_month=round(d - dm.max(), 2) if nm != BN else 0.0,
            sl_hits_first_n=int(((sl_.why == 0) | ((sl_.why == 3) & (sl_.nc < Ncell(nm)))).sum()) if 'nc' in sl_.columns else None,
            sl_hits_after_n=int(((sl_.why == 3) & (sl_.nc >= Ncell(nm))).sum()) if 'nc' in sl_.columns else None,
            **{f'n_{v}': int(rc.get(v, 0)) for v in REASON.values()},
            net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_25H1=g(nm, '2025-26H1 (OPT)', 'net'), net_26H2=g(nm, '2026H2 (HOLD)', 'net'),
            dd_1518=g(nm, '2015-18', 'maxdd'), dd_1924=g(nm, '2019-24', 'maxdd'), dd_25H1=g(nm, '2025-26H1 (OPT)', 'maxdd'), dd_26H2=g(nm, '2026H2 (HOLD)', 'maxdd')))
Odf = pd.DataFrame(out); Odf.to_csv(OUT / 'wick-compact.csv', index=False)
for wn in ('2025-26 all', '2024-26 all'):
    pd.DataFrame({nm: mon[(nm, wn)] for nm in CANDS}).fillna(0.0).to_csv(OUT / f"wick-monthly-{wn[:7]}.csv")
pd.DataFrame([par]).to_csv(OUT / 'parity.csv', index=False)
pd.set_option('display.width', 500); pd.set_option('display.max_columns', 80)
print(Odf.to_string())
