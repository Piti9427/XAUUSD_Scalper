"""C22 ML walk-forward Round 1 (preregister.md). Box-only. Usage: ml.py ARM  (e.g. U-LR). Writes results/ARM.pkl"""
import sys, hashlib, time, warnings, itertools; from pathlib import Path
import numpy as np, pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.inspection import permutation_importance
warnings.filterwarnings('ignore')
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
D = pd.read_pickle(OUT / 'cands_features.pkl'); END = D['END']; BAL0 = D['BAL0']; SLIP = D['SLIP']; ICT = 'Asia/Bangkok'
T = lambda s: pd.Timestamp(s, tz=ICT); ms = lambda t: int(pd.Timestamp(t).value // 10**6)

def portfolio(c, skip, start, end, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10):
    """copy of entry_sl.portfolio2 (live gates) + ML skip applied after all gates; swap precomputed per candidate (same nights())."""
    a, z = ms(start), ms(end); m = (c.ts.to_numpy() >= a) & (c.ts.to_numpy() < z)
    TS = c.ts.to_numpy()[m]; TX = c.tx.to_numpy()[m]; SG = c.sig.to_numpy()[m]; PNL = c.pnl.to_numpy()[m]; SW = c.sw.to_numpy()[m]
    RR = c.R.to_numpy()[m]; DD_ = c.d.to_numpy()[m]; SK = skip[m]
    bal = bal0; op = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0
    for k in range(len(TS)):
        ts = TS[k]
        if op is not None and op[1] <= ts:
            p = op; op = None; bal += p[3]; last_tx = p[1]
            if p[3] < 0:
                day = p[1] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p[1] + cms
            res.append(p)
        if op is not None or ts < cool: continue
        sg = SG[k]
        if last_tx > sg or sg < cool: continue
        if dl.get(sg // 86400000, 0) >= max_losses: continue
        day = ts // 86400000
        if dl.get(day, 0) >= max_losses: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop: continue
        risk = RR[k] + SLIP
        if risk > bal * cap: continue
        if SK[k]: continue
        op = (ts, TX[k], DD_[k], PNL[k] + SW[k])
    if op is not None: res.append(op)
    return np.array([r[3] for r in res]), np.array([r[2] for r in res])

def metr(net, d=None):
    n = len(net)
    if n == 0: return dict(n=0, wins=0, losses=0, ties=0, wr=0.0, net=0.0, exp=0.0, maxdd=0.0)
    eq = BAL0 + np.cumsum(net); dd = float((np.maximum.accumulate(np.r_[BAL0, eq])[1:] - eq).max())
    eqc = np.r_[BAL0, eq]; dd = float((np.maximum.accumulate(eqc) - eqc).max())
    return dict(n=n, wins=int((net > 0).sum()), losses=int((net < 0).sum()), ties=int((net == 0).sum()), wr=100 * float((net > 0).mean()),
                net=float(net.sum()), exp=float(net.sum() / n), maxdd=dd)

def year_metrics(c, skip, y0, y1):
    """fresh $400 each calendar year, pooled trades, max yearly DD"""
    nets = []; dds = []
    for y in range(y0, y1 + 1):
        net, _ = portfolio(c, skip, T(f'{y}-01-01'), min(T(f'{y+1}-01-01'), END)); nets.append(net); dds.append(metr(net)['maxdd'])
    m = metr(np.concatenate(nets)); m['maxdd'] = max(dds); return m

WINDOWS = {'2025-26': (T('2025-01-01'), END), '2024-26': (T('2024-01-01'), END)}
def window_metrics(c, skip):
    out = {w: metr(portfolio(c, skip, a, z)[0]) for w, (a, z) in WINDOWS.items()}
    out['2020-24'] = year_metrics(c, skip, 2020, 2024); return out

# parity
c3, X3 = D['store'][3.0]; noskip = np.zeros(len(c3), bool)
par = window_metrics(c3, noskip)
assert par['2025-26']['n'] == 313 and round(par['2025-26']['net'], 2) == 1898.96 and round(par['2025-26']['maxdd'], 2) == 224.89 and par['2025-26']['wins'] == 121, par['2025-26']
assert par['2024-26']['n'] == 429 and round(par['2024-26']['net'], 2) == 1826.95 and round(par['2024-26']['maxdd'], 2) == 224.89 and par['2024-26']['wins'] == 146, par['2024-26']

HP = {'LR': [dict(C=x) for x in (0.01, 0.1, 1.0)],
      'HGB': [dict(max_depth=a, min_samples_leaf=b) for a in (2, 3) for b in (20, 50)],
      'RF': [dict(max_depth=a) for a in (3, 4)]}
def make(fam, hp):
    if fam == 'LR': return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=hp['C'], max_iter=2000))
    if fam == 'HGB': return make_pipeline(SimpleImputer(strategy='median'), HistGradientBoostingClassifier(max_depth=hp['max_depth'], min_samples_leaf=hp['min_samples_leaf'],
                                          learning_rate=0.05, max_iter=150, l2_regularization=1.0, early_stopping=False, random_state=0))
    return make_pipeline(SimpleImputer(strategy='median'), RandomForestClassifier(n_estimators=300, max_depth=hp['max_depth'], min_samples_leaf=20,
                                                                                  max_features='sqrt', random_state=0, n_jobs=1))
GRID_ABS = [round(0.15 + 0.025 * k, 3) for k in range(17)]
GRID_DEL = [round(-0.10 + 0.025 * k, 3) for k in range(11)]

def fit_margin(struct, fam, hp, c, X, tr, pr):
    """returns (margin for pred rows; skip if margin < thr), fitted models"""
    y = c.y.to_numpy(); d = c.d.to_numpy(); mg = np.full(pr.sum(), np.inf); models = {}
    if struct in ('U', 'U20', 'U25'):
        mdl = make(fam, hp).fit(X[tr], y[tr]); mg = mdl.predict_proba(X[pr])[:, 1]; models['all'] = (mdl, tr)
    elif struct == 'B':
        t = tr & (d == 1); mdl = make(fam, hp).fit(X[t], y[t]); pb = pr & (d == 1)
        mg[(d[pr] == 1)] = mdl.predict_proba(X[pb])[:, 1]; models['buy'] = (mdl, t)
    else:
        for sd, nm in ((1, 'buy'), (-1, 'sell')):
            t = tr & (d == sd); mdl = make(fam, hp).fit(X[t], y[t]); ps = pr & (d == sd)
            mg[(d[pr] == sd)] = mdl.predict_proba(X[ps])[:, 1] - y[t].mean(); models[nm] = (mdl, t)
    return mg, models

def score_fold(m, b):
    feas = (m['net'] >= b['net'] - 0.10 * abs(b['net'])) and (m['n'] >= 0.6 * b['n'])
    sc = (m['wr'] - b['wr']) + 20 * (b['maxdd'] - m['maxdd']) / b['maxdd'] if b['maxdd'] > 0 else (m['wr'] - b['wr'])
    return feas, sc

def run(arm):
    struct, fam = arm.split('-'); btp = {'U20': 2.0, 'U25': 2.5}.get(struct, 3.0)
    c, X = D['store'][btp]; X = X.to_numpy(float); n = len(c); yr = c.year.to_numpy(); tx = c.tx.to_numpy()
    grid = GRID_DEL if struct == 'S' else GRID_ABS
    sel_rows = []; oos_margin = np.full(n, np.inf); oos_thr = np.full(n, -np.inf); oos_on = np.zeros(n, bool); auc_rows = []; final_models = {}
    for Y in range(2020, 2027):
        S = {}
        for V in (Y - 2, Y - 1):
            tr = tx < ms(T(f'{V}-01-01')); pr = yr == V
            bV = metr(portfolio(c, np.zeros(n, bool), T(f'{V}-01-01'), T(f'{V+1}-01-01'))[0])
            for hi, hp in enumerate(HP[fam]):
                mg, _ = fit_margin(struct, fam, hp, c, X, tr, pr)
                for thr in grid:
                    sk = np.zeros(n, bool); sk[pr] = mg < thr
                    m = metr(portfolio(c, sk, T(f'{V}-01-01'), T(f'{V+1}-01-01'))[0]); f, s = score_fold(m, bV)
                    S.setdefault((hi, thr), []).append((f, s, m, bV))
        best = None; table = []
        for hi in range(len(HP[fam])):
            for thr in grid:
                nb = [t for t in grid if abs(t - thr) <= 0.05 + 1e-9]
                feas_all = all(all(f for f, *_ in S[(hi, t)]) for t in nb)
                sm = float(np.mean([np.mean([s for _, s, *_ in S[(hi, t)]]) for t in nb]))
                raw = float(np.mean([s for _, s, *_ in S[(hi, thr)]]))
                table.append(dict(arm=arm, test_year=Y, hp=str(HP[fam][hi]), thr=thr, feasible_smoothed=feas_all, score=round(raw, 3), smoothed=round(sm, 3)))
                if feas_all and sm > 0 and (best is None or sm > best[0] + 1e-12): best = (sm, hi, thr)
        sel_rows += table
        tr = tx < ms(T(f'{Y}-01-01')); pr = yr == Y
        hi_used = best[1] if best else max(table, key=lambda r: r['smoothed']) and HP[fam].index(eval(max(table, key=lambda r: r['smoothed'])['hp']))
        mg, models = fit_margin(struct, fam, HP[fam][hi_used], c, X, tr, pr)
        oos_margin[pr] = mg
        if best: oos_thr[pr] = best[2]; oos_on[pr] = True
        yy = c.y.to_numpy()[pr]; fin = np.isfinite(mg)
        auc = roc_auc_score(yy[fin], mg[fin]) if fin.sum() > 10 and len(set(yy[fin])) > 1 else np.nan
        auc_rows.append(dict(arm=arm, test_year=Y, chosen_hp=str(HP[fam][best[1]]) if best else 'off (no feasible cell)', chosen_thr=best[2] if best else None,
                             smoothed_score=round(best[0], 3) if best else None, hp_for_auc=str(HP[fam][hi_used]), oos_auc=round(auc, 4), n_test_cands=int(pr.sum())))
        if Y == 2026: final_models = (models, HP[fam][hi_used])
        print(arm, Y, auc_rows[-1], flush=True)
    res = {}
    for tag, sh in (('main', 0.0), ('thr-0.05', -0.05), ('thr+0.05', 0.05)):
        sk = oos_on & (oos_margin < oos_thr + sh); res[tag] = window_metrics(c, sk)
        if sh == 0.0:
            res['per_year'] = {Y: metr(portfolio(c, sk, T(f'{Y}-01-01'), min(T(f'{Y+1}-01-01'), END))[0]) for Y in range(2020, 2027)}
            res['per_year_base'] = {Y: metr(portfolio(c, np.zeros(n, bool), T(f'{Y}-01-01'), min(T(f'{Y+1}-01-01'), END))[0]) for Y in range(2020, 2027)}
            res['skip_main'] = sk.copy()
        res[tag]['skipped_cands_2020_26'] = int(sk.sum())
    # interpretability (model refit for 2026)
    imp = []
    models, hp = final_models; cols = list(D['store'][btp][1].columns)
    for nm, (mdl, t) in models.items():
        est = mdl[-1]
        if fam == 'LR':
            for f, v in zip(cols, est.coef_[0]): imp.append(dict(arm=arm, model=nm, feature=f, kind='std_coef', value=float(v)))
        else:
            pi = permutation_importance(mdl, X[t], c.y.to_numpy()[t], scoring='roc_auc', n_repeats=10, random_state=0, n_jobs=1)
            for f, v, s in zip(cols, pi.importances_mean, pi.importances_std): imp.append(dict(arm=arm, model=nm, feature=f, kind='perm_auc', value=float(v), std=float(s)))
            if fam == 'RF':
                for f, v in zip(cols, est.feature_importances_): imp.append(dict(arm=arm, model=nm, feature=f, kind='impurity', value=float(v)))
    pd.to_pickle(dict(arm=arm, res=res, sel=pd.DataFrame(sel_rows), years=pd.DataFrame(auc_rows), imp=pd.DataFrame(imp), hp2026=hp), OUT / 'results' / f'{arm}.pkl')

if __name__ == '__main__':
    (OUT / 'results').mkdir(exist_ok=True)
    if sys.argv[1] == 'refs':
        rows = {}
        for btp in (3.0, 2.0, 2.5):
            c, _ = D['store'][btp]; rows[btp] = window_metrics(c, np.zeros(len(c), bool))
        pd.to_pickle(rows, OUT / 'results' / 'refs.pkl'); print(rows)
    else:
        t0 = time.time(); run(sys.argv[1]); print('done', sys.argv[1], round(time.time() - t0), 's')
