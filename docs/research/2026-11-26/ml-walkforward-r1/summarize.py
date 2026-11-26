"""Collect arm results -> CSVs + pass criteria (preregister section 6)."""
from pathlib import Path; import numpy as np, pandas as pd
OUT = Path(__file__).parent; R = OUT / 'results'
refs = pd.read_pickle(R / 'refs.pkl'); B = refs[3.0]
ARMS = [f'{s}-{f}' for s in ('U', 'S', 'B', 'U20', 'U25') for f in ('LR', 'HGB', 'RF')]
W = ['2025-26', '2024-26', '2020-24']; rows = []; crit = []; sel = []; yrs = []; imp = []; py = []
def row(name, tag, w, m):
    b = B[w]; return dict(arm=name, run=tag, window=w, n=m['n'], wins=m['wins'], losses=m['losses'], ties=m['ties'], wr=round(m['wr'], 2), d_wr=round(m['wr'] - b['wr'], 2),
                          net=round(m['net'], 2), net_pct_base=round(100 * m['net'] / b['net'], 1) if b['net'] > 0 else None, exp=round(m['exp'], 3), maxdd=round(m['maxdd'], 2),
                          d_dd=round(m['maxdd'] - b['maxdd'], 2), kept_pct=round(100 * m['n'] / b['n'], 1))
for nm, btp in (('base live 7fe0', 3.0), ('ref BUY TP 2.0R (no ML)', 2.0), ('ref BUY TP 2.5R (no ML)', 2.5)):
    for w in W: rows.append(row(nm, 'main', w, refs[btp][w]))
for a in ARMS:
    f = R / f'{a}.pkl'
    if not f.exists(): print('missing', a); continue
    r = pd.read_pickle(f); sel.append(r['sel']); yrs.append(r['years']); imp.append(r['imp'])
    for tag in ('main', 'thr-0.05', 'thr+0.05'):
        for w in W: rows.append(row(a, tag, w, r['res'][tag][w]))
    for Yr, mm in r['res']['per_year'].items():
        bb = r['res']['per_year_base'][Yr]
        py.append(dict(arm=a, year=Yr, n=mm['n'], wins=mm['wins'], losses=mm['losses'], ties=mm['ties'], wr=round(mm['wr'], 2), net=round(mm['net'], 2), maxdd=round(mm['maxdd'], 2),
                       arm_base_n=bb['n'], arm_base_wr=round(bb['wr'], 2), arm_base_net=round(bb['net'], 2), arm_base_maxdd=round(bb['maxdd'], 2)))
    m = r['res']['main']; W2 = W[:2]
    p1 = all(m[w]['wr'] > B[w]['wr'] for w in W2); p2 = all(m[w]['maxdd'] < B[w]['maxdd'] for w in W2)
    p3 = all(m[w]['net'] > 0 and m[w]['net'] >= 0.9 * B[w]['net'] for w in W2)
    trade = p1 and p2 and all(0.8 * B[w]['net'] <= m[w]['net'] < 0.9 * B[w]['net'] for w in W2)
    p4 = all(m[w]['exp'] >= B[w]['exp'] - 0.5 for w in W2); p5 = all(m[w]['n'] >= 0.6 * B[w]['n'] for w in W2)
    p6 = all(r['res'][t][w]['wr'] > B[w]['wr'] and r['res'][t][w]['maxdd'] < B[w]['maxdd'] for t in ('thr-0.05', 'thr+0.05') for w in W2)
    p7 = m['2020-24']['wr'] >= B['2020-24']['wr'] and m['2020-24']['net'] >= B['2020-24']['net']
    ps = [p1, p2, p3, p4, p5, p6, p7]
    crit.append(dict(arm=a, P1_wr=p1, P2_dd=p2, P3_net90=p3, P4_exp=p4, P5_kept60=p5, P6_plateau=p6, P7_oos2020_24=p7, passed_n=sum(ps), PASS=all(ps), tradeoff_candidate=trade,
                     years_filter_on=int(r['years'].chosen_thr.notna().sum())))
pd.DataFrame(py).to_csv(OUT / 'per-year-oos.csv', index=False)
S = pd.DataFrame(rows); S.to_csv(OUT / 'summary-oos-windows.csv', index=False)
C = pd.DataFrame(crit); C.to_csv(OUT / 'pass-criteria.csv', index=False)
pd.concat(sel).to_csv(OUT / 'threshold-sensitivity-inner.csv', index=False)
Y = pd.concat(yrs); Y.to_csv(OUT / 'per-year-oos-selection-auc.csv', index=False)
I = pd.concat(imp); I.to_csv(OUT / 'feature-importance.csv', index=False)
# per-year OOS trade metrics are in summary via windows; add per-year breakdown
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 30)
print(S[S.run == 'main'].to_string(index=False)); print(C.to_string(index=False))
print(S[S.run != 'main'][['arm', 'run', 'window', 'n', 'wr', 'd_wr', 'net', 'maxdd', 'd_dd']].to_string(index=False))
print(Y.to_string(index=False))
