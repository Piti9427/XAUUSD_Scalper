"""R3 summary + pass criteria (preregister section 6)."""
from pathlib import Path; import numpy as np, pandas as pd, subprocess
OUT = Path(__file__).parent; R = OUT / 'results'
refs = pd.read_pickle(R / 'refs.pkl'); B = refs[3.0]; W = ['2025-26', '2024-26', '2020-24']; W2 = W[:2]
names = subprocess.run([str(OUT / '.venv/bin/python'), str(OUT / 'ml.py'), 'names'], capture_output=True, text=True).stdout.split('\n')[0].split()
rows = []; crit = []; py = []; yrs = []; imp = []; sel = []; feats = []; clus = []
def row(name, run, w, m):
    b = B[w]; return dict(arm=name, run=run, window=w, n=m['n'], wins=m['wins'], losses=m['losses'], ties=m['ties'], wr=round(m['wr'], 2), d_wr=round(m['wr'] - b['wr'], 2),
        net=round(m['net'], 2), net_pct_base=round(100 * m['net'] / b['net'], 1) if b['net'] > 0 else None, exp=round(m['exp'], 3), maxdd=round(m['maxdd'], 2),
        d_dd=round(m['maxdd'] - b['maxdd'], 2), net_dd=round(m['net'] / m['maxdd'], 2) if m['maxdd'] > 0 else None, kept_pct=round(100 * m['n'] / b['n'], 1))
def core(m):
    p1 = all(m[w]['wr'] > B[w]['wr'] for w in W2); p2 = all(m[w]['maxdd'] < B[w]['maxdd'] for w in W2)
    p3 = all(m[w]['net'] > 0 and m[w]['net'] >= 0.9 * B[w]['net'] for w in W2)
    trade = p1 and p2 and all(0.8 * B[w]['net'] <= m[w]['net'] < 0.9 * B[w]['net'] for w in W2)
    p4 = all(m[w]['exp'] >= B[w]['exp'] - 0.5 for w in W2); p5 = all(m[w]['n'] >= 0.6 * B[w]['n'] for w in W2)
    p7 = m['2020-24']['wr'] >= B['2020-24']['wr'] and m['2020-24']['net'] >= B['2020-24']['net']
    return dict(P1_wr=p1, P2_dd=p2, P3_net90=p3, P4_exp=p4, P5_kept60=p5, P7_2020_24=p7), trade
wrdd = lambda m: all(m[w]['wr'] > B[w]['wr'] and m[w]['maxdd'] < B[w]['maxdd'] for w in W2)
def addpy(a, r):
    for Yr, mm in r['per_year'].items():
        bb = r['per_year_base'][Yr]; py.append(dict(arm=a, year=Yr, n=mm['n'], wins=mm['wins'], losses=mm['losses'], ties=mm['ties'], wr=round(mm['wr'], 2), net=round(mm['net'], 2),
                 maxdd=round(mm['maxdd'], 2), base_n=bb['n'], base_wr=round(bb['wr'], 2), base_net=round(bb['net'], 2), base_maxdd=round(bb['maxdd'], 2)))
for nm, btp in (('base live 7fe0', 3.0), ('ref BUY TP 2.0R (no ML)', 2.0)):
    for w in W: rows.append(row(nm, 'main', w, refs[btp][w]))
for a in names:
    r = pd.read_pickle(R / f'{a}.pkl'); res = r['res']
    if a.startswith('GMM'):
        clus.append(r['clusters'])
        for nm_, tag in ((15, 'main (n_min 15)'), (10, 'n_min 10'), (20, 'n_min 20')):
            for w in W: rows.append(row(a, tag, w, res[nm_][w]))
        addpy(a, res); cr, trade = core(res[15])
        other = a.replace('K3', 'K4') if 'K3' in a else a.replace('K4', 'K3'); ro = pd.read_pickle(R / f'{other}.pkl')['res']
        p6 = wrdd(res[10]) and wrdd(res[20]) and wrdd(ro[15])
    else:
        yrs.append(r['years']); imp.append(r['imp']); sel.append(r['sel']); feats.append(r['feats'])
        step = '0.1' if 'Dynamic' in a else '0.05'
        for k_, tag in (('main', 'main (forced ON)'), ('m', f'q-{step}'), ('p', f'q+{step}')):
            for w in W: rows.append(row(a, tag, w, res[k_][w]))
        addpy(a, res); cr, trade = core(res['main']); p6 = wrdd(res['m']) and wrdd(res['p'])
    crit.append(dict(arm=a, **cr, P6_plateau=p6, passed_n=sum(cr.values()) + p6, PASS=all(cr.values()) and p6, tradeoff_candidate=trade))
RU = pd.read_pickle(R / 'rules.pkl'); rc = {}
for nm, v in RU['cells'].items():
    if nm == 'base': continue
    for w in W: rows.append(row(f'rule {nm}', 'fixed', w, v['win'][w]))
    rc[nm] = core(v['win'])
for nm in rc:
    fam, k = nm.rsplit('_', 1); ks = [1.25, 1.5, 1.75]; i = ks.index(float(k)); nb = [f'{fam}_{ks[j]}' for j in (i - 1, i + 1) if 0 <= j < 3]
    p6 = all(all(rc[o][0].values()) for o in nb); cr, trade = rc[nm]
    crit.append(dict(arm=f'rule {nm}', **cr, P6_plateau=p6, passed_n=sum(cr.values()) + p6, PASS=all(cr.values()) and p6, tradeoff_candidate=trade))
hold = []
for nm, v in RU['cells'].items():
    m = v['hold1519']; hold.append(dict(cell=nm, n=m['n'], wins=m['wins'], losses=m['losses'], ties=m['ties'], wr=round(m['wr'], 2), net=round(m['net'], 2), exp=round(m['exp'], 3), maxdd=round(m['maxdd'], 2)))
pd.DataFrame(hold).to_csv(OUT / 'rules-holdout-2015-19.csv', index=False); RU['episodes'].to_csv(OUT / 'rules-dd-episodes.csv', index=False)
S = pd.DataFrame(rows); S.to_csv(OUT / 'summary-oos-windows.csv', index=False)
C = pd.DataFrame(crit); C.to_csv(OUT / 'pass-criteria.csv', index=False)
pd.DataFrame(py).to_csv(OUT / 'per-year-oos.csv', index=False)
Y = pd.concat(yrs); Y.to_csv(OUT / 'per-year-selection-quality.csv', index=False)
Y[Y.arm.str.startswith('MFE')][['arm', 'test_year', 'chosen', 'q', 'mfe_r2', 'mfe_spearman', 'mae_r2', 'mae_spearman']].to_csv(OUT / 'mfe-mae-prediction-quality.csv', index=False)
pd.concat(imp).to_csv(OUT / 'feature-importance.csv', index=False); pd.concat(sel).to_csv(OUT / 'inner-selection-table.csv', index=False)
pd.concat(feats).to_csv(OUT / 'sparse-selected-features.csv', index=False); pd.concat(clus).to_csv(OUT / 'gmm-cluster-stats.csv', index=False)
S[~S.run.str.startswith('main') & (S.run != 'fixed')].to_csv(OUT / 'plateau-check.csv', index=False)
pd.set_option('display.width', 320); pd.set_option('display.max_rows', 800); pd.set_option('display.max_columns', 30)
k = ['arm', 'run', 'window', 'n', 'wins', 'losses', 'ties', 'wr', 'd_wr', 'net', 'net_pct_base', 'exp', 'maxdd', 'net_dd', 'kept_pct']
print(S[S.run.str.startswith('main') | (S.run == 'fixed')][k].to_string(index=False)); print(C.to_string(index=False))
print(pd.DataFrame(hold).to_string(index=False)); print(RU['episodes'].to_string(index=False))
print(Y.drop(columns=['n_test']).to_string(index=False))
