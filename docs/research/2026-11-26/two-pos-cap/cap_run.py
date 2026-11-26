"""Pre-registered cap cells (preregister.md, sha256 checked). Box-only research."""
import hashlib
from pm import *
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
CB = build(sell_rows()); G1 = make_groups(CB)
# ---- parity ----
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
p25 = round(portfolio(b0, *WIN['2025-26 all'], max_losses=1).net.sum(), 2)
q25, _ = run(CB, *WIN['2025-26 all']); q24 = portfolio2(CB, A24, END)
CELLS = {'base_live': dict(), 'm2_set_c10': dict(maxpos=2, cap=0.10), 'm2_set_c15': dict(maxpos=2, cap=0.15), 'm2_set_c125': dict(maxpos=2, cap=0.125),
         'm2_set_c20': dict(maxpos=2, cap=0.20), 'm3_set_c15': dict(maxpos=3, cap=0.15), 'm3_set_c20': dict(maxpos=3, cap=0.20)}
WINS = ('2015-18', '2019-24', '2025-26H1 (OPT)', '2026H2 (HOLD)', '2025-26 all', '2024-26 all')
TR = {}; rows = []
for nm, kw in CELLS.items():
    for wn in WINS:
        t, parts = window(G1, wn, **kw); TR[(nm, wn)] = (t, parts)
        mdd = max(stats_block(p.sort_values('tx', kind='stable'), BAL0, calendar_months(*gg))['maxdd'] for p, gg in parts if len(p))
        rows.append(dict(variant=nm, window=wn, trades=len(t), net=round(t.net.sum(), 2), maxdd=round(mdd, 2), rej_cap=agg(parts, 'rej_cap'),
                         rej_daily_stop=agg(parts, 'rej_daily_stop'), max_conc_risk_pct=agg(parts, 'conc_risk_max')))
W = pd.DataFrame(rows); W.to_csv(OUT / 'cap-windows.csv', index=False)
g = lambda nm, wn, col: W[(W.variant == nm) & (W.window == wn)].iloc[0][col]
par = dict(core_2025_26=p25, portfolio2_2025_26=round(q25.net.sum(), 2), portfolio2_2024_26=round(q24.net.sum(), 2),
           pm_base_2025_26=g('base_live', '2025-26 all', 'net'), pm_base_2024_26=g('base_live', '2024-26 all', 'net'),
           dd_base_2025_26=g('base_live', '2025-26 all', 'maxdd'), dd_base_2024_26=g('base_live', '2024-26 all', 'maxdd'),
           m2_set_c10_2025_26=g('m2_set_c10', '2025-26 all', 'net'), m2_set_c10_dd=g('m2_set_c10', '2025-26 all', 'maxdd'))
print('parity', par, flush=True); pd.DataFrame([par]).to_csv(OUT / 'parity.csv', index=False)
assert par['core_2025_26'] == 1898.96 and par['portfolio2_2025_26'] == 1898.96 and par['portfolio2_2024_26'] == 1826.95, 'PARITY FAILED - stop'
assert par['pm_base_2025_26'] == 1898.96 and par['pm_base_2024_26'] == 1826.95 and par['dd_base_2025_26'] == 224.89, 'pm base parity failed - stop'
assert par['m2_set_c10_2025_26'] == 2567.92, 'm2_set reproduction failed - stop'
print('PARITY OK', flush=True)
BN = 'base_live'; P = 'm2_set_c15'; out = []; mon = {}
for nm in CELLS:
    for wn in ('2025-26 all', '2024-26 all'):
        a, z = (A24, END) if wn == '2024-26 all' else WIN[wn]; t, parts = TR[(nm, wn)]; tb = TR[(BN, wn)][0]; months = calendar_months(a, z)
        m = pd.Series(stats_block(t, BAL0, months)['monthly']); mb = pd.Series(stats_block(tb, BAL0, months)['monthly'])
        mon[(nm, wn)] = m; dm = m.sub(mb, fill_value=0.0); d = t.net.sum() - tb.net.sum()
        net_ = t.net.sum(); mdd = g(nm, wn, 'maxdd'); bdd = g(BN, wn, 'maxdd'); dayl = t.groupby(t.tx // 86400000).net.sum()
        out.append(dict(variant=nm, window=wn, trades=len(t), net=round(net_, 2), d_vs_base=round(d, 2), maxdd=mdd, net_dd=round(net_ / mdd, 3),
            base_scaled_to_cell_dd=round(tb.net.sum() * mdd / bdd, 2), cell_at_base_dd=round(net_ * bdd / mdd, 2),
            rej_cap=g(nm, wn, 'rej_cap'), rej_daily_stop=g(nm, wn, 'rej_daily_stop'), max_conc_risk_pct=g(nm, wn, 'max_conc_risk_pct'),
            worst_day_utc=round(dayl.min(), 2), worst_day=str(pd.Timestamp(int(dayl.idxmin()) * 86400000, unit='ms').date()),
            months_better=int((dm > 0.005).sum()), months_worse=int((dm < -0.005).sum()),
            d_ex_best_month=round(d - max(dm.max(), 0.0), 2) if nm != BN else 0.0,
            net_1518=g(nm, '2015-18', 'net'), net_1924=g(nm, '2019-24', 'net'), net_25H1=g(nm, '2025-26H1 (OPT)', 'net'), net_26H2=g(nm, '2026H2 (HOLD)', 'net'),
            dd_1518=g(nm, '2015-18', 'maxdd'), dd_1924=g(nm, '2019-24', 'maxdd'), dd_25H1=g(nm, '2025-26H1 (OPT)', 'maxdd'), dd_26H2=g(nm, '2026H2 (HOLD)', 'maxdd'),
            rej_cap_1518=g(nm, '2015-18', 'rej_cap'), rej_cap_1924=g(nm, '2019-24', 'rej_cap')))
O = pd.DataFrame(out); O.to_csv(OUT / 'cap-compact.csv', index=False)
for wn in ('2025-26 all', '2024-26 all'):
    pd.DataFrame({nm: mon[(nm, wn)] for nm in CELLS}).fillna(0.0).to_csv(OUT / f"cap-monthly-{wn[:7]}.csv")
o = lambda nm, wn, col: O[(O.variant == nm) & (O.window == wn)].iloc[0][col]
W2 = ('2025-26 all', '2024-26 all')
crit = [
 ('1 net > base 2025-26 and 2024-26', all(o(P, w, 'd_vs_base') > 0 for w in W2)),
 ('2 maxDD <= base both periods', all(o(P, w, 'maxdd') <= o(BN, w, 'maxdd') for w in W2)),
 ('3 net/DD > base both periods', all(o(P, w, 'net_dd') > o(BN, w, 'net_dd') for w in W2)),
 ('4 best-month-removed diff > 0 in 2025-26', o(P, '2025-26 all', 'd_ex_best_month') > 0),
 ('5 months better >= worse (both periods)', all(o(P, w, 'months_better') >= o(P, w, 'months_worse') for w in W2)),
 ('6 neighbours net >= base 2025-26', all(o(n, '2025-26 all', 'd_vs_base') >= 0 for n in ('m2_set_c125', 'm2_set_c20', 'm3_set_c15', 'm3_set_c20'))),
 ('7 hold-out 2019-24 net >= base', o(P, '2025-26 all', 'net_1924') >= o(BN, '2025-26 all', 'net_1924')),
]
C = pd.DataFrame(crit, columns=['criterion', 'pass']); C.to_csv(OUT / 'pass-criteria.csv', index=False)
# identical-trade check vs cap 10%
same = {nm: {wn: bool(len(TR[(nm, wn)][0]) == len(TR[('m2_set_c10' if nm.startswith('m2') else nm, wn)][0])) for wn in W2} for nm in CELLS}
for nm in ('m2_set_c125', 'm2_set_c15', 'm2_set_c20'):
    for wn in WINS:
        a_, b_ = TR[(nm, wn)][0], TR[('m2_set_c10', wn)][0]
        print('identical_to_c10', nm, wn, len(a_) == len(b_) and np.allclose(a_.net.to_numpy(), b_.net.to_numpy()))
pd.set_option('display.width', 700); pd.set_option('display.max_columns', 80)
print(W.to_string()); print(O.to_string()); print(C.to_string()); print('PRIMARY PASS' if C['pass'].all() else 'PRIMARY FAIL -> keep live')
