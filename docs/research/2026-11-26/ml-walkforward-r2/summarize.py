"""R2 summary + pass criteria (preregister section 7)."""
from pathlib import Path; import numpy as np, pandas as pd
OUT = Path(__file__).parent; R = OUT / 'results'
refs = pd.read_pickle(R / 'refs.pkl'); B = refs[3.0]; W = ['2025-26', '2024-26', '2020-24']; W2 = W[:2]
ARMS = ['RegAll-Ridge', 'RegAll-HGBR', 'RegBUY-Ridge', 'RegBUY-HGBR', 'Cls1R-BUY-LR', 'Cls1R-BUY-HGB', 'Cls1R-All-LR', 'Cls1R-All-HGB', 'BUY20-Ridge', 'BUY20-Cls1R-LR']
rows = []; crit = []; py = []; yrs = []; imp = []; sel = []
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
for nm, btp in (('base live 7fe0', 3.0), ('ref BUY TP 2.0R (no ML)', 2.0)):
    for w in W: rows.append(row(nm, 'main', w, refs[btp][w]))
for a in ARMS:
    r = pd.read_pickle(R / f'{a}.pkl'); yrs.append(r['years']); imp.append(r['imp']); sel.append(r['sel'])
    for s in ('main', 'm05', 'p05', 'off'):
        for w in W: rows.append(row(a, {'main': 'main (forced ON)', 'm05': 'q-0.05', 'p05': 'q+0.05', 'off': 'allow-OFF (info)'}[s], w, r['res'][s][w]))
    for Yr, mm in r['res']['per_year'].items():
        bb = r['res']['per_year_base'][Yr]; py.append(dict(arm=a, year=Yr, n=mm['n'], wins=mm['wins'], losses=mm['losses'], ties=mm['ties'], wr=round(mm['wr'], 2), net=round(mm['net'], 2),
                 maxdd=round(mm['maxdd'], 2), arm_base_n=bb['n'], arm_base_wr=round(bb['wr'], 2), arm_base_net=round(bb['net'], 2), arm_base_maxdd=round(bb['maxdd'], 2)))
    cr, trade = core(r['res']['main']); p6 = wrdd(r['res']['m05']) and wrdd(r['res']['p05'])
    crit.append(dict(arm=a, **cr, P6_plateau=p6, passed_n=sum(cr.values()) + p6, PASS=all(cr.values()) and p6, tradeoff_candidate=trade))
RU = pd.read_pickle(R / 'rules.pkl')
for nm, v in RU['cells'].items():
    for w in W: rows.append(row(f'rule {nm}', 'fixed', w, v['win'][w]))
rule_core = {nm: core(v['win']) for nm, v in RU['cells'].items()}
for nm in RU['cells']:
    cr, trade = rule_core[nm]; nb = RU['neigh'][nm]
    p6 = len(nb) > 0 and all(all(v for k, v in rule_core[o][0].items()) for o in nb)
    crit.append(dict(arm=f'rule {nm}', **cr, P6_plateau=p6, passed_n=sum(cr.values()) + p6, PASS=all(cr.values()) and p6, tradeoff_candidate=trade, neighbours=','.join(nb)))
wf = RU['wf']['main']
for w in W: rows.append(row('Rule-WF', 'main', w, wf[w]))
cr, trade = core(wf); top = RU['wf_years'].chosen_cell.value_counts().index[0]
p6 = all(all(rule_core[o][0].values()) for o in RU['neigh'][top])
crit.append(dict(arm='Rule-WF', **cr, P6_plateau=p6, passed_n=sum(cr.values()) + p6, PASS=all(cr.values()) and p6, tradeoff_candidate=trade, neighbours=f'most-chosen {top}: ' + ','.join(RU['neigh'][top])))
for Yr, mm in RU['wf']['per_year'].items(): py.append(dict(arm='Rule-WF', year=Yr, n=mm['n'], wins=mm['wins'], losses=mm['losses'], ties=mm['ties'], wr=round(mm['wr'], 2), net=round(mm['net'], 2), maxdd=round(mm['maxdd'], 2)))
for nm, v in RU['cells'].items():
    for Yr, mm in v['per_year'].items(): py.append(dict(arm=f'rule {nm}', year=Yr, n=mm['n'], wins=mm['wins'], losses=mm['losses'], ties=mm['ties'], wr=round(mm['wr'], 2), net=round(mm['net'], 2), maxdd=round(mm['maxdd'], 2)))
S = pd.DataFrame(rows); S.to_csv(OUT / 'summary-oos-windows.csv', index=False)
C = pd.DataFrame(crit); C.to_csv(OUT / 'pass-criteria.csv', index=False)
pd.DataFrame(py).to_csv(OUT / 'per-year-oos.csv', index=False)
Y = pd.concat(yrs + [RU['wf_years']]); Y.to_csv(OUT / 'per-year-selection.csv', index=False)
pd.concat(imp).to_csv(OUT / 'feature-importance.csv', index=False); pd.concat(sel).to_csv(OUT / 'inner-selection-table.csv', index=False)
S[S.run.isin(['q-0.05', 'q+0.05'])].to_csv(OUT / 'plateau-check.csv', index=False)
pd.set_option('display.width', 320); pd.set_option('display.max_rows', 600); pd.set_option('display.max_columns', 30)
print(S[~S.arm.str.startswith('rule')].to_string(index=False)); print(C.to_string(index=False)); print(Y.to_string(index=False))
