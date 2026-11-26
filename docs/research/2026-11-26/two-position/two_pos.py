"""Two-position / set-level F3 research (pre-registered in preregister.md, sha256 in preregister.sha256). Box-only.
Imports f2f3-validate harness via sell-entry-sl-20261125/entry_sl.py (files not modified). Trade paths = base paths
(split leg B uses entry_sl.path_sell with tp 2.7R, same SL 2.5 ATR / BE 1R)."""
import sys, hashlib; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
A24 = T('2024-01-01')

def nights(ts, tx):
    r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
    for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
    return n

def make_groups(c, mode='single', legB=None):
    """candidate groups: list of dict(sig, ts, d, i, k, legs=[dict(tx,pnl,R,why,tbe)])"""
    G = []
    for k, r in zip(c.index, c.itertuples()):
        leg = dict(tx=int(r.tx), pnl=float(r.pnl), R=float(r.R), why=int(r.why), tbe=int(r.tbe), leg='A')
        if mode == 'dbl':
            legs = [dict(leg, pnl=2 * leg['pnl'], R=2 * leg['R'], lots=2)]
        elif mode == 'split' and r.d == -1:
            b_ = legB.loc[int(r.i)]
            assert abs(b_.entry - r.entry) < 1e-9 and int(b_.ts) == int(r.ts)
            legs = [leg, dict(tx=int(b_.tx), pnl=float(b_.pnl), R=float(b_.R), why=int(b_.why), tbe=leg['tbe'] if leg['tbe'] >= 0 else -1, leg='B')]
        else:
            legs = [leg]
        for lg in legs: lg.setdefault('lots', 1)
        G.append(dict(k=k, sig=int(r.sig), ts=int(r.ts), d=int(r.d), i=int(r.i), legs=legs))
    return G

def portfolio_m(G, start, end, maxpos=1, f3='set', need_be=False, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    a, z = ms(start), ms(end)
    bal = bal0; open_ = []; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000)
    recent = []          # closed groups: (gmax_tx, d)
    gid = 0; sid = 0; set_lost = {}; info = dict(conc_risk_max=0.0, max_open=0)
    def close_until(t):
        nonlocal bal, cool, open_
        due = sorted([lg for lg in open_ if lg['tx'] <= t], key=lambda x: x['tx'])
        for lg in due:
            open_.remove(lg); bal += lg['net']
            if lg['net'] < 0:
                cool = lg['tx'] + cms; day = lg['tx'] // 86400000
                if f3 == 'pos' or not set_lost.get(lg['set']):
                    dl[day] = dl.get(day, 0) + 1; set_lost[lg['set']] = True
            res.append(lg)
            if not any(o['grp'] == lg['grp'] for o in open_): recent.append((lg['gtx'], lg['d']))
    for g in G:
        if not (a <= g['ts'] < z): continue
        close_until(g['ts'])
        sg = g['sig']
        busy_open = {o['grp']: o['d'] for o in open_}
        busy = list(busy_open.values()) + [d for tx, d in recent[-8:] if tx > sg]
        if len(busy) >= maxpos: continue
        if any(d != g['d'] for d in busy): continue
        if need_be and open_ and not all(o['tbe'] >= 0 and o['tbe'] <= sg for o in open_): continue
        if g['ts'] < cool or sg < cool: continue
        if dl.get(sg // 86400000, 0) >= max_losses: continue
        day = g['ts'] // 86400000
        if dl.get(day, 0) >= max_losses: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop: continue
        open_risk = sum(o['risk'] for o in open_ if not (o['tbe'] >= 0 and o['tbe'] <= g['ts']))
        new_risk = sum(lg['R'] + slip_r * lg['lots'] for lg in g['legs'])
        if open_risk + new_risk > bal * cap: continue
        info['conc_risk_max'] = max(info['conc_risk_max'], 100 * (open_risk + new_risk) / bal)
        if not open_: sid += 1
        gid += 1; second = bool(busy_open)
        gtx = max(lg['tx'] for lg in g['legs'])
        for lg in g['legs']:
            sw = nights(g['ts'], lg['tx']) * (swap * lg['lots'] if g['d'] == 1 else 0.0)
            open_.append(dict(k=g['k'], ts=g['ts'], sig=sg, i=g['i'], tx=lg['tx'], gtx=gtx, d=g['d'], net=lg['pnl'] + sw, R=lg['R'] + slip_r * lg['lots'],
                              risk=lg['R'] + slip_r * lg['lots'], why=lg['why'], tbe=lg['tbe'], leg=lg['leg'], grp=gid, set=sid, second=second))
        info['max_open'] = max(info['max_open'], len({o['grp'] for o in open_}))
    res.extend(sorted(open_, key=lambda x: x['tx']))
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs.update(info)
    return t

def run_m(G, a, z, **kw):
    parts = [(portfolio_m(G, s0, s1, **kw), (s0, s1)) for s0, s1 in segs(a, z)]
    t = pd.concat([p for p, _ in parts if len(p)], ignore_index=True)
    t.attrs['conc_risk_max'] = max(p.attrs['conc_risk_max'] for p, _ in parts); t.attrs['max_open'] = max(p.attrs['max_open'] for p, _ in parts)
    return t, parts

# ---------- 1. parity ----------
CB = build(sell_rows())
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
p25 = portfolio(b0, *WIN['2025-26 all'], max_losses=1).net.sum()
q25, q25p = run(CB, *WIN['2025-26 all']); q24 = portfolio2(CB, A24, END)
G1 = make_groups(CB)
m25, m25p = run_m(G1, *WIN['2025-26 all']); m24 = portfolio_m(G1, A24, END)
dd = lambda t, a, z: round(stats_block(t, BAL0, calendar_months(a, z))['maxdd'], 2)
same = len(m25) == len(q25) and np.allclose(m25.net.to_numpy(), q25.net.to_numpy()) and (m25.ts.to_numpy() == q25.ts.to_numpy()).all()
par = dict(core_2025_26=round(p25, 2), portfolio2_2025_26=round(q25.net.sum(), 2), portfolio2_2024_26=round(q24.net.sum(), 2),
           portfolio_m1_2025_26=round(m25.net.sum(), 2), portfolio_m1_2024_26=round(m24.net.sum(), 2), m1_tradewise_equal_2025_26=bool(same),
           dd_2025_26=max(dd(p, *g) for p, g in m25p), dd_2024_26=dd(m24, A24, END))
print('parity', par, flush=True); pd.DataFrame([par]).to_csv(OUT / 'parity.csv', index=False)
assert par['core_2025_26'] == 1898.96 and par['portfolio2_2025_26'] == 1898.96 and par['portfolio2_2024_26'] == 1826.95, 'PARITY FAILED - stop'
assert par['portfolio_m1_2025_26'] == 1898.96 and par['portfolio_m1_2024_26'] == 1826.95 and same, 'portfolio_m(maxpos=1) != base - stop'
assert par['dd_2025_26'] == 224.89 or par['dd_2024_26'] == 224.89, 'DD parity failed - stop'
print('PARITY OK', flush=True)

# ---------- 2. cells ----------
LB = sell_rows(tp=2.7).set_index('i')
GD = make_groups(CB, 'dbl'); GS = make_groups(CB, 'split', LB)
CELLS = {'base_live': (G1, dict()), 'm2_set': (G1, dict(maxpos=2)), 'm3_set': (G1, dict(maxpos=3)), 'm2_pos': (G1, dict(maxpos=2, f3='pos')),
         'm2_be': (G1, dict(maxpos=2, need_be=True)), 'dbl_002': (GD, dict()), 'split_135_270': (GS, dict())}
BN = 'base_live'; P = 'm2_set'
WINS = dict(WIN); WINS['2024-26 all'] = (A24, END)
TR = {}; rows = []
for nm, (G, kw) in CELLS.items():
    for wn, (a, z) in WINS.items():
        if wn == '2024-26 all':
            t = portfolio_m(G, a, z, **kw); parts = [(t, (a, z))]
        else: t, parts = run_m(G, a, z, **kw)
        TR[(nm, wn)] = (t, parts)
        mdd = max(stats_block(p.sort_values('tx', kind='stable'), BAL0, calendar_months(*gg))['maxdd'] for p, gg in parts if len(p))
        rows.append(dict(variant=nm, window=wn, legs=len(t), signals=t.grp.nunique() if 'grp' in t else 0, net=round(t.net.sum(), 2), maxdd=round(mdd, 2)))
Wdf = pd.DataFrame(rows); Wdf.to_csv(OUT / 'two-pos-windows.csv', index=False)
g = lambda nm, wn, col: Wdf[(Wdf.variant == nm) & (Wdf.window == wn)].iloc[0][col]
out = []; mon = {}
for nm in CELLS:
    for wn in ('2025-26 all', '2024-26 all'):
        a, z = WINS[wn]; t, parts = TR[(nm, wn)]; tb = TR[(BN, wn)][0]; months = calendar_months(a, z)
        m = pd.Series(stats_block(t, BAL0, months)['monthly']); mb = pd.Series(stats_block(tb, BAL0, months)['monthly'])
        mon[(nm, wn)] = m; dm = m.sub(mb, fill_value=0.0); d = t.net.sum() - tb.net.sum()
        sec = t[t.second]
        setloss = t[t.net < 0].groupby('set').size() if len(t) else pd.Series(dtype=int)
        gnet = t.groupby('grp').net.sum()
        dayl = t.groupby(t.tx // 86400000).net.sum()
        net_ = t.net.sum(); mdd = g(nm, wn, 'maxdd'); bdd = g(BN, wn, 'maxdd')
        out.append(dict(variant=nm, window=wn, signals=t.grp.nunique(), legs=len(t), net=round(net_, 2), d_vs_base=round(d, 2), maxdd=mdd,
            net_dd=round(net_ / mdd, 3), net_at_base_dd=round(net_ * bdd / mdd, 2), win_pct_signals=round(100 * (gnet > 0).mean(), 1),
            second_opened=int(sec.grp.nunique()), second_win=int((sec.groupby('grp').net.sum() > 0).sum()), second_loss=int((sec.groupby('grp').net.sum() < 0).sum()),
            second_pnl=round(sec.net.sum(), 2), sets_2plus_losses=int((setloss >= 2).sum()), worst_day_utc=round(dayl.min(), 2),
            max_conc_risk_pct=round(max(p.attrs['conc_risk_max'] for p, _ in parts), 2), max_open=max(p.attrs['max_open'] for p, _ in parts),
            months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()),
            d_best_month=dm.idxmax() if (nm != BN and dm.max() > 0.005) else '', d_ex_best_month=round(d - max(dm.max(), 0.0), 2) if nm != BN else 0.0,
            net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_25H1=g(nm, '2025-26H1 (OPT)', 'net'), net_26H2=g(nm, '2026H2 (HOLD)', 'net'),
            dd_1518=g(nm, '2015-18', 'maxdd'), dd_1924=g(nm, '2019-24', 'maxdd'), dd_25H1=g(nm, '2025-26H1 (OPT)', 'maxdd'), dd_26H2=g(nm, '2026H2 (HOLD)', 'maxdd')))
Odf = pd.DataFrame(out); Odf.to_csv(OUT / 'two-pos-compact.csv', index=False)
for wn in ('2025-26 all', '2024-26 all'):
    pd.DataFrame({nm: mon[(nm, wn)] for nm in CELLS}).fillna(0.0).to_csv(OUT / f"two-pos-monthly-{wn[:7]}.csv")
sl = []
for nm in ('m2_set', 'm3_set', 'm2_pos', 'm2_be'):
    for wn in ('2015-18', '2019-24', '2025-26 all', '2024-26 all'):
        t = TR[(nm, wn)][0]; s = t[t.second]
        for r in s.itertuples(): sl.append(dict(variant=nm, window=wn, sig_ict=pd.Timestamp(r.sig, unit='ms', tz='UTC').tz_convert(ICT), exit_ict=pd.Timestamp(r.tx, unit='ms', tz='UTC').tz_convert(ICT), d=r.d, why=r.why, net=round(r.net, 2)))
pd.DataFrame(sl).to_csv(OUT / 'two-pos-second-trades.csv', index=False)
# ---------- 3. pass criteria ----------
o = lambda nm, wn, col: Odf[(Odf.variant == nm) & (Odf.window == wn)].iloc[0][col]
W2 = ('2025-26 all', '2024-26 all')
crit = [
 ('1 net > base 2025-26 and 2024-26', all(o(P, w, 'd_vs_base') > 0 for w in W2)),
 ('2 maxDD <= base both periods', all(o(P, w, 'maxdd') <= o(BN, w, 'maxdd') for w in W2)),
 ('3 net/DD > base both periods', all(o(P, w, 'net_dd') > o(BN, w, 'net_dd') for w in W2)),
 ('4 best-month-removed diff > 0 in 2025-26', o(P, '2025-26 all', 'd_ex_best_month') > 0),
 ('5 months better >= worse (both periods)', all(o(P, w, 'months_better') >= o(P, w, 'months_worse') for w in W2)),
 ('6 m3_set and m2_pos net >= base 2025-26', o('m3_set', '2025-26 all', 'd_vs_base') >= 0 and o('m2_pos', '2025-26 all', 'd_vs_base') >= 0),
 ('7 hold-out 2019-24 net >= base', o(P, '2025-26 all', 'net_1924') >= o(BN, '2025-26 all', 'net_1924')),
]
C = pd.DataFrame(crit, columns=['criterion', 'pass']); C.to_csv(OUT / 'pass-criteria.csv', index=False)
pd.set_option('display.width', 700); pd.set_option('display.max_columns', 80)
print(Odf.to_string()); print(C.to_string()); print('PRIMARY PASS' if C['pass'].all() else 'PRIMARY FAIL -> keep live')

# ---------- 4. diagnostic: same-leg re-entry in base ----------
dg = []; drows = []
for wn in ('2015-18', '2019-24', '2025-26 all'):
    t = TR[(BN, wn)][0]; s = t[t.d == -1].sort_values('ts').reset_index(drop=True)
    for j in range(1, len(s)):
        p, r = s.iloc[j - 1], s.iloc[j]
        gap = (r.sig - p.tx) / 60000; leg = (0 <= r.sig - p.tx <= 900000) and (r.i - p.i <= 48)
        drows.append(dict(window=wn, sig_ict=pd.Timestamp(int(r.sig), unit='ms', tz='UTC').tz_convert(ICT), prev_exit_ict=pd.Timestamp(int(p.tx), unit='ms', tz='UTC').tz_convert(ICT),
                          gap_min=round(gap, 2), bars_since_prev_signal=int(r.i - p.i), prev_why=int(p.why), same_leg_1bar=leg, why=int(r.why), net=round(r.net, 2)))
D = pd.DataFrame(drows); D.to_csv(OUT / 'same-leg-reentry-base.csv', index=False)
D['ts'] = D.sig_ict
for lab, msk in (('2015-26', D.window.notna()), ('2024-26', D.sig_ict >= A24), ('2025-26', D.window == '2025-26 all')):
    x = D[msk]; y = x[x.same_leg_1bar]
    row = dict(period=lab, sell_trades=len(x), sell_win_pct=round(100 * (x.net > 0).mean(), 1), same_leg_n=len(y), same_leg_win_pct=round(100 * (y.net > 0).mean(), 1) if len(y) else None,
               same_leg_net=round(y.net.sum(), 2), same_leg_avg=round(y.net.mean(), 2) if len(y) else None, other_avg=round(x[~x.same_leg_1bar].net.mean(), 2))
    for pw, nmw in ((2, 'after_tp'), (0, 'after_sl'), (1, 'after_be')):
        z_ = y[y.prev_why == pw]; row[f'{nmw}_n'] = len(z_); row[f'{nmw}_win_pct'] = round(100 * (z_.net > 0).mean(), 1) if len(z_) else None
    dg.append(row)
DG = pd.DataFrame(dg); DG.to_csv(OUT / 'same-leg-reentry-summary.csv', index=False); print(DG.to_string())
print('data end', END)
