"""Signal-bar bounce SELL filter (pre-registered in preregister.md, sha256 in preregister.sha256, 26 Nov 2026 09:49 ICT). Box-only research.
Derived from bounce-reentry-20261126/post_tp.py; only the SELL skip rule differs.
Imports f2f3-validate harness via sell-entry-sl-20261125/entry_sl.py (files not modified). Trade paths identical to base;
only extra SKIP rules for SELL signals, checked after all existing gates inside a copy of entry_sl.portfolio2."""
import sys; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
OUT = Path(__file__).parent
A24 = T('2024-01-01')
# extension at signal close: (prior 48-bar low - close) / ATR  (causal)
EXT_ALL = (LL48 - close) / A
# bounce off the signal-bar low (causal, signal bar i is closed)
BOUNCE = (close - lo15) / A
_rg = hi15 - lo15
WFRAC = np.where(_rg > 0, (close - lo15) / np.where(_rg > 0, _rg, 1.0), 0.0)

def portfolio_x(c, start, end, bounce=0.0, wfrac=0.0, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    """entry_sl.portfolio2 verbatim + SELL skip rule: bounce=(close-low)/ATR >= bounce and/or wfrac=(close-low)/(high-low) >= wfrac."""
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    bal = bal0; open_ = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0; last_tp = -10**15; skipped = []
    def nights(ts, tx):
        r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
        for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
        return n
    for k, r in zip(c.index, c.itertuples()):
        if open_ is not None and open_['tx'] <= r.ts:
            p = open_; open_ = None; bal += p['net']; last_tx = p['tx']
            if p['d'] == -1 and p['why'] == 2: last_tp = p['tx']
            if p['net'] < 0:
                day = p['tx'] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p['tx'] + cms
            res.append(p)
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
        if r.d == -1 and (bounce or wfrac):
            ii = int(r.i)
            hit = (bool(bounce) and BOUNCE[ii] >= bounce) or (bool(wfrac) and WFRAC[ii] >= wfrac)
            if hit:
                skipped.append(dict(k=k, sig=sg, ts=r.ts, pnl=r.pnl, why=r.why, bounce=BOUNCE[ii], wfrac=WFRAC[ii])); continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, rr_plan=getattr(r, 'rr_plan', np.nan), why=r.why, sl_atr=getattr(r, 'sl_atr', np.nan))
    if open_ is not None: res.append(open_)
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs['skipped'] = skipped
    return t

def run_x(c, a, z, **kw):
    parts = [(portfolio_x(c, s0, s1, **kw), (s0, s1)) for s0, s1 in segs(a, z)]
    t = pd.concat([p for p, _ in parts if len(p)], ignore_index=True)
    t.attrs['skipped'] = sum((p.attrs['skipped'] for p, _ in parts), [])
    return t, parts

CELLS = {'base_live': {}, 'bounce_0.5': dict(bounce=0.5), 'bounce_0.4': dict(bounce=0.4), 'bounce_0.6': dict(bounce=0.6),
         'wfrac_0.33': dict(wfrac=0.33), 'wfrac_0.5': dict(wfrac=0.5)}
BN = 'base_live'
# ---------- 1. parity ----------
CB = build(sell_rows())
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
p25 = portfolio(b0, *WIN['2025-26 all'], max_losses=1).net.sum()
q25, q25p = run(CB, *WIN['2025-26 all']); q24 = portfolio2(CB, A24, END)
x25, x25p = run_x(CB, *WIN['2025-26 all']); x24 = portfolio_x(CB, A24, END)
dd = lambda t, a, z: round(stats_block(t, BAL0, calendar_months(a, z))['maxdd'], 2)
par = dict(core_2025_26=round(p25, 2), portfolio2_2025_26=round(q25.net.sum(), 2), portfolio2_2024_26=round(q24.net.sum(), 2),
           portfolio_x_2025_26=round(x25.net.sum(), 2), portfolio_x_2024_26=round(x24.net.sum(), 2),
           dd_2025_26=max(dd(p, *g) for p, g in x25p), dd_2024_26=dd(x24, A24, END))
print('parity', par, flush=True)
pd.DataFrame([par]).to_csv(OUT / 'parity.csv', index=False)
assert par['core_2025_26'] == 1898.96 and par['portfolio2_2025_26'] == 1898.96 and par['portfolio2_2024_26'] == 1826.95, 'PARITY FAILED - stop'
assert par['portfolio_x_2025_26'] == 1898.96 and par['portfolio_x_2024_26'] == 1826.95, 'portfolio_x (no filter) != base - stop'
assert par['dd_2025_26'] == 224.89 or par['dd_2024_26'] == 224.89, 'DD parity failed - stop'
print('PARITY OK', flush=True)
# ---------- 2. evaluate ----------
WINS = dict(WIN); WINS['2024-26 all'] = (A24, END)
TR = {}; rows = []
for nm, kw in CELLS.items():
    for wn, (a, z) in WINS.items():
        if wn == '2024-26 all':
            t = portfolio_x(CB, a, z, **kw); parts = [(t, (a, z))]
        else: t, parts = run_x(CB, a, z, **kw)
        TR[(nm, wn)] = t; rows.append(dict(variant=nm, window=wn, skipped=len(t.attrs['skipped']), **summ(t, parts, a, z)))
Wdf = pd.DataFrame(rows); Wdf.to_csv(OUT / 'bounce-windows.csv', index=False)
g = lambda nm, wn, col: Wdf[(Wdf.variant == nm) & (Wdf.window == wn)].iloc[0][col]
out = []; mon = {}; skl = []
for nm in CELLS:
    for wn in ('2025-26 all', '2024-26 all'):
        a, z = WINS[wn]; t = TR[(nm, wn)]; tb = TR[(BN, wn)]; months = calendar_months(a, z)
        m = pd.Series(stats_block(t, BAL0, months)['monthly']); mb = pd.Series(stats_block(tb, BAL0, months)['monthly'])
        mon[(nm, wn)] = m; dm = m.sub(mb, fill_value=0.0); sl_ = t[t.d == -1]; d = t.net.sum() - tb.net.sum()
        sk = pd.DataFrame(t.attrs['skipped'])
        for s in t.attrs['skipped']: skl.append(dict(variant=nm, window=wn, **s))
        out.append(dict(variant=nm, window=wn, trades=len(t), sell_trades=len(sl_), skipped=len(sk),
            skipped_win=int((sk.pnl > 0).sum()) if len(sk) else 0, skipped_loss=int((sk.pnl <= 0).sum()) if len(sk) else 0,
            skipped_tp=int((sk.why == 2).sum()) if len(sk) else 0, skipped_sl=int((sk.why == 0).sum()) if len(sk) else 0,
            skipped_be=int((sk.why == 1).sum()) if len(sk) else 0, skipped_pnl=round(sk.pnl.sum(), 2) if len(sk) else 0.0,
            net=round(t.net.sum(), 2), d_vs_base=round(d, 2), maxdd=g(nm, wn, 'maxdd'), net_dd=round(t.net.sum() / g(nm, wn, 'maxdd'), 3),
            sell_win=round(100 * (sl_.net > 0).mean(), 1), sell_avg_loss=round(sl_[sl_.net < 0].net.mean(), 2),
            months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()),
            d_best_month=dm.idxmax() if (nm != BN and dm.max() > 0.005) else '', d_ex_best_month=round(d - max(dm.max(), 0.0), 2) if nm != BN else 0.0,
            net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_25H1=g(nm, '2025-26H1 (OPT)', 'net'), net_26H2=g(nm, '2026H2 (HOLD)', 'net'),
            dd_1518=g(nm, '2015-18', 'maxdd'), dd_1924=g(nm, '2019-24', 'maxdd'), dd_25H1=g(nm, '2025-26H1 (OPT)', 'maxdd'), dd_26H2=g(nm, '2026H2 (HOLD)', 'maxdd')))
Odf = pd.DataFrame(out); Odf.to_csv(OUT / 'bounce-compact.csv', index=False)
pd.DataFrame(skl).to_csv(OUT / 'bounce-skipped-trades.csv', index=False)
for wn in ('2025-26 all', '2024-26 all'):
    pd.DataFrame({nm: mon[(nm, wn)] for nm in CELLS}).fillna(0.0).to_csv(OUT / f"bounce-monthly-{wn[:7]}.csv")
# skipped winners/losers on the full 2015-26 hold-out panel (yearly reset segments)
hp = []
for nm in CELLS:
    if nm == BN: continue
    for wn in ('2015-18', '2019-24', '2025-26 all'):
        sk = pd.DataFrame(TR[(nm, wn)].attrs['skipped'])
        hp.append(dict(variant=nm, window=wn, skipped=len(sk), win=int((sk.pnl > 0).sum()) if len(sk) else 0, loss=int((sk.pnl <= 0).sum()) if len(sk) else 0))
pd.DataFrame(hp).to_csv(OUT / 'bounce-skipped-summary.csv', index=False)
# ---------- 3. pass criteria (primary bounce_0.5) ----------
o = lambda nm, wn, col: Odf[(Odf.variant == nm) & (Odf.window == wn)].iloc[0][col]
P = 'bounce_0.5'
W2 = ('2025-26 all', '2024-26 all')
crit = [
 ('1 net > base 2025-26 and 2024-26', all(o(P, w, 'd_vs_base') > 0 for w in W2)),
 ('2 maxDD <= base both periods', all(o(P, w, 'maxdd') <= o(BN, w, 'maxdd') for w in W2)),
 ('3 net/DD >= base both periods', all(o(P, w, 'net_dd') >= o(BN, w, 'net_dd') for w in W2)),
 ('4 best-month-removed diff > 0 in 2025-26', o(P, '2025-26 all', 'd_ex_best_month') > 0),
 ('5 months better >= worse (both periods)', all(o(P, w, 'months_better') >= o(P, w, 'months_worse') for w in W2)),
 ('6 bounce_0.4 and bounce_0.6 net >= base 2025-26', o('bounce_0.4', '2025-26 all', 'd_vs_base') >= 0 and o('bounce_0.6', '2025-26 all', 'd_vs_base') >= 0),
 ('7 hold-out 2019-24 net >= base', o(P, '2025-26 all', 'net_1924') >= o(BN, '2025-26 all', 'net_1924')),
]
C = pd.DataFrame(crit, columns=['criterion', 'pass']); C.to_csv(OUT / 'pass-criteria.csv', index=False)
pd.set_option('display.width', 600); pd.set_option('display.max_columns', 80)
print(Odf.to_string()); print(C.to_string()); print('PRIMARY PASS' if C['pass'].all() else 'PRIMARY FAIL -> keep live')
print('data end', END, '| live 5132994784 bar (from loss report): bounce', round((3490.673-3484.256)/(32.821/3.32),3), 'wfrac', round((3490.673-3484.256)/32.821,3))
