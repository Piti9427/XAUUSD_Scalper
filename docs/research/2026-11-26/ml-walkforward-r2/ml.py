"""C22 ML walk-forward Round 2 (preregister.md). Box-only. Usage: ml.py ARM | rules | refs"""
import sys, hashlib, time, warnings; from pathlib import Path
import numpy as np, pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import roc_auc_score
from sklearn.inspection import permutation_importance
from scipy.stats import spearmanr
warnings.filterwarnings('ignore')
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
D = pd.read_pickle(OUT / 'cands_features.pkl'); END = D['END']; BAL0 = D['BAL0']; SLIP = D['SLIP']; ICT = 'Asia/Bangkok'
T = lambda s: pd.Timestamp(s, tz=ICT); ms = lambda t: int(pd.Timestamp(t).value // 10**6)

def portfolio(c, skip, start, end, lb_h=0.0, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10):
    """entry_sl.portfolio2 copy + ML/rule skip after all live gates; lb_h > 0: also skip BUY if the bot's own last loss exited < lb_h hours before signal."""
    a, z = ms(start), ms(end); m = (c.ts.to_numpy() >= a) & (c.ts.to_numpy() < z)
    TS = c.ts.to_numpy()[m]; TX = c.tx.to_numpy()[m]; SG = c.sig.to_numpy()[m]; PNL = c.pnl.to_numpy()[m]; SW = c.sw.to_numpy()[m]
    RR = c.R.to_numpy()[m]; DD_ = c.d.to_numpy()[m]; SK = skip[m]
    bal = bal0; op = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0; last_loss = -10**15; lbm = lb_h * 3600000
    for k in range(len(TS)):
        ts = TS[k]
        if op is not None and op[1] <= ts:
            p = op; op = None; bal += p[3]; last_tx = p[1]
            if p[3] < 0:
                day = p[1] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p[1] + cms; last_loss = p[1]
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
        if lbm > 0 and DD_[k] == 1 and sg - last_loss < lbm: continue
        op = (ts, TX[k], DD_[k], PNL[k] + SW[k])
    if op is not None: res.append(op)
    return np.array([r[3] for r in res])

def metr(net):
    n = len(net)
    if n == 0: return dict(n=0, wins=0, losses=0, ties=0, wr=0.0, net=0.0, exp=0.0, maxdd=0.0)
    eqc = np.r_[BAL0, BAL0 + np.cumsum(net)]; dd = float((np.maximum.accumulate(eqc) - eqc).max())
    return dict(n=n, wins=int((net > 0).sum()), losses=int((net < 0).sum()), ties=int((net == 0).sum()), wr=100 * float((net > 0).mean()),
                net=float(net.sum()), exp=float(net.sum() / n), maxdd=dd)
def year_metrics(c, skip, y0, y1, lb_h=0.0):
    nets = []; dds = []
    for y in range(y0, y1 + 1):
        net = portfolio(c, skip, T(f'{y}-01-01'), min(T(f'{y+1}-01-01'), END), lb_h); nets.append(net); dds.append(metr(net)['maxdd'])
    m = metr(np.concatenate(nets)); m['maxdd'] = max(dds); return m
WINDOWS = {'2025-26': (T('2025-01-01'), END), '2024-26': (T('2024-01-01'), END)}
def window_metrics(c, skip, lb_h=0.0):
    out = {w: metr(portfolio(c, skip, a, z, lb_h)) for w, (a, z) in WINDOWS.items()}
    out['2020-24'] = year_metrics(c, skip, 2020, 2024, lb_h); return out
def per_year(c, skip, lb_h=0.0):
    return {Y: metr(portfolio(c, skip, T(f'{Y}-01-01'), min(T(f'{Y+1}-01-01'), END), lb_h)) for Y in range(2020, 2027)}

c3, X3 = D['store'][3.0]
par = window_metrics(c3, np.zeros(len(c3), bool))
assert par['2025-26']['n'] == 313 and round(par['2025-26']['net'], 2) == 1898.96 and round(par['2025-26']['maxdd'], 2) == 224.89 and par['2025-26']['wins'] == 121, par['2025-26']
assert par['2024-26']['n'] == 429 and round(par['2024-26']['net'], 2) == 1826.95 and round(par['2024-26']['maxdd'], 2) == 224.89 and par['2024-26']['wins'] == 146, par['2024-26']

Q = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
HP = {'Ridge': [dict(alpha=x) for x in (1.0, 10.0, 100.0)], 'LR': [dict(C=x) for x in (0.01, 0.1, 1.0)],
      'HGBR': [dict(max_depth=a, min_samples_leaf=b) for a in (2, 3) for b in (20, 50)], 'HGB': [dict(max_depth=a, min_samples_leaf=b) for a in (2, 3) for b in (20, 50)]}
ARMS = {'RegAll-Ridge': ('all', 'Ridge', 'R', 3.0), 'RegAll-HGBR': ('all', 'HGBR', 'R', 3.0),
        'RegBUY-Ridge': ('buy', 'Ridge', 'R', 3.0), 'RegBUY-HGBR': ('buy', 'HGBR', 'R', 3.0),
        'Cls1R-BUY-LR': ('buy', 'LR', '1R', 3.0), 'Cls1R-BUY-HGB': ('buy', 'HGB', '1R', 3.0),
        'Cls1R-All-LR': ('all', 'LR', '1R', 3.0), 'Cls1R-All-HGB': ('all', 'HGB', '1R', 3.0),
        'BUY20-Ridge': ('buy', 'Ridge', 'R', 2.0), 'BUY20-Cls1R-LR': ('buy', 'LR', '1R', 2.0)}
def make(fam, hp):
    imp = SimpleImputer(strategy='median')
    if fam == 'Ridge': return make_pipeline(imp, StandardScaler(), Ridge(alpha=hp['alpha']))
    if fam == 'LR': return make_pipeline(imp, StandardScaler(), LogisticRegression(C=hp['C'], max_iter=2000))
    kw = dict(max_depth=hp['max_depth'], min_samples_leaf=hp['min_samples_leaf'], learning_rate=0.05, max_iter=150, l2_regularization=1.0, early_stopping=False, random_state=0)
    return make_pipeline(imp, HistGradientBoostingRegressor(**kw) if fam == 'HGBR' else HistGradientBoostingClassifier(**kw))
def pred(mdl, X, fam): return mdl.predict_proba(X)[:, 1] if fam in ('LR', 'HGB') else mdl.predict(X)

def fit_pred(scope, fam, hp, c, X, y, T_):
    """rolling 4y window before year T_; returns model, train mask, train preds, preds for all rows (inf where side not filtered)"""
    d = c.d.to_numpy(); ts = c.ts.to_numpy(); tx = c.tx.to_numpy()
    tr = (ts >= ms(T(f'{T_-4}-01-01'))) & (tx < ms(T(f'{T_}-01-01')))
    if scope == 'buy': tr &= (d == 1)
    mdl = make(fam, hp).fit(X[tr], y[tr]); ptr = pred(mdl, X[tr], fam)
    p = np.full(len(c), np.inf); sel = (d == 1) if scope == 'buy' else np.ones(len(c), bool); p[sel] = pred(mdl, X[sel], fam)
    return mdl, tr, ptr, p

def fold_ok(m, b):
    feas = (m['maxdd'] <= b['maxdd']) and (m['net'] >= b['net'] - 0.15 * abs(b['net']))
    sc = (m['wr'] - b['wr']) + (20 * (b['maxdd'] - m['maxdd']) / b['maxdd'] if b['maxdd'] > 0 else 0.0)
    return feas, sc
def choose(S, keys, neigh):
    """S[key] -> list of (feas, score) per fold. returns (forced_key, allowoff_key or None, table)"""
    tab = {}
    for k in keys:
        nb = neigh(k); sm = float(np.mean([np.mean([s for _, s in S[x]]) for x in nb])); fe = all(all(f for f, _ in S[x]) for x in nb)
        tab[k] = (sm, fe, float(np.mean([s for _, s in S[k]])))
    feas = [k for k in keys if tab[k][1]]
    pool = feas if feas else keys
    best = max(pool, key=lambda k: tab[k][0])     # max keeps first on ties = lower q / earlier hp (keys ordered)
    off = None
    f2 = [k for k in feas if tab[k][0] > 0]
    if f2: off = max(f2, key=lambda k: tab[k][0])
    return best, off, tab

def run(arm):
    scope, fam, tgt, btp = ARMS[arm]; c, Xd = D['store'][btp]; X = Xd.to_numpy(float); n = len(c); yr = c.year.to_numpy()
    y = c.R_mult.to_numpy() if tgt == 'R' else c.y1r.to_numpy()
    base_y = lambda V: metr(portfolio(c, np.zeros(n, bool), T(f'{V}-01-01'), T(f'{V+1}-01-01')))
    oos_p = np.full(n, np.inf); thr = {s: np.full(n, -np.inf) for s in ('main', 'm05', 'p05', 'off')}; yrs = []; seltab = []; final = None
    for Y in range(2020, 2027):
        S = {}
        for V in (Y - 2, Y - 1):
            bV = base_y(V); pr = yr == V
            for hi, hp in enumerate(HP[fam]):
                _, _, ptr, p = fit_pred(scope, fam, hp, c, X, y, V)
                for q in Q:
                    t = np.quantile(ptr, q); sk = pr & (p < t)
                    m = metr(portfolio(c, sk, T(f'{V}-01-01'), T(f'{V+1}-01-01'))); S.setdefault((hi, q), []).append(fold_ok(m, bV))
        keys = [(hi, q) for hi in range(len(HP[fam])) for q in Q]
        neigh = lambda k: [(k[0], q) for q in Q if abs(q - k[1]) <= 0.05 + 1e-9]
        best, off, tab = choose(S, keys, neigh)
        for k, (sm, fe, raw) in tab.items(): seltab.append(dict(arm=arm, test_year=Y, hp=str(HP[fam][k[0]]), q=k[1], score=round(raw, 3), smoothed=round(sm, 3), feasible_smoothed=fe))
        mdl, tr, ptr, p = fit_pred(scope, fam, HP[fam][best[0]], c, X, y, Y); pr = yr == Y
        oos_p[pr] = p[pr]
        for s, qq in (('main', best[1]), ('m05', best[1] - 0.05), ('p05', best[1] + 0.05)): thr[s][pr] = np.quantile(ptr, qq)
        if off is not None:
            if off[0] == best[0]: thr['off'][pr] = np.quantile(ptr, off[1])
            else:
                _, _, ptr2, p2 = fit_pred(scope, fam, HP[fam][off[0]], c, X, y, Y); thr['off'][pr] = np.quantile(ptr2, off[1]) - p2[pr] + p[pr]  # equivalent skip p2 < t2
        yy = y[pr]; fin = np.isfinite(p[pr])
        if tgt == 'R': q_ = spearmanr(p[pr][fin], yy[fin]).correlation; met = 'spearman'
        else: q_ = roc_auc_score(yy[fin], p[pr][fin]) if len(set(yy[fin])) > 1 else np.nan; met = 'auc'
        yrs.append(dict(arm=arm, test_year=Y, chosen_hp=str(HP[fam][best[0]]), chosen_q=best[1], smoothed=round(tab[best][0], 3), feasible=tab[best][1],
                        allow_off=f"{HP[fam][off[0]]} q={off[1]}" if off else 'OFF', oos_metric=met, oos_value=round(float(q_), 4), n_test=int(pr.sum())))
        print(yrs[-1], flush=True)
        if Y == 2026: final = (mdl, tr)
    res = {}
    for s in ('main', 'm05', 'p05', 'off'):
        sk = oos_p < thr[s]; res[s] = window_metrics(c, sk); res[s]['skipped_cands'] = int(sk.sum())
        if s == 'main': res['per_year'] = per_year(c, sk); res['per_year_base'] = per_year(c, np.zeros(n, bool))
    mdl, tr = final; cols = list(Xd.columns); imp = []
    if fam in ('Ridge', 'LR'):
        co = mdl[-1].coef_.ravel()
        for f, v in zip(cols, co): imp.append(dict(arm=arm, feature=f, kind='std_coef', value=float(v)))
    else:
        pi = permutation_importance(mdl, X[tr], y[tr], scoring='r2' if fam == 'HGBR' else 'roc_auc', n_repeats=10, random_state=0, n_jobs=1)
        for f, v, s_ in zip(cols, pi.importances_mean, pi.importances_std): imp.append(dict(arm=arm, feature=f, kind='perm', value=float(v), std=float(s_)))
    pd.to_pickle(dict(arm=arm, res=res, years=pd.DataFrame(yrs), sel=pd.DataFrame(seltab), imp=pd.DataFrame(imp)), OUT / 'results' / f'{arm}.pkl')

# ---------------- rules ----------------
def rule_cells():
    cells = {}
    for N in (2, 4, 8): cells[f'Ls_{N}'] = ('Ls', N, None); cells[f'Lb_{N}'] = ('Lb', N, None)
    for k in (1.5, 2.0, 2.5): cells[f'G_{k}'] = ('G', None, k)
    for N in (2, 4, 8):
        for k in (1.5, 2.0, 2.5): cells[f'LsG_{N}_{k}'] = ('LsG', N, k)
    return cells
CELLS = rule_cells()
def rule_neigh(nm):
    fam, N, k = CELLS[nm]; Ns = [2, 4, 8]; Ks = [1.5, 2.0, 2.5]; out = []
    for x, xs in ((N, Ns), (k, Ks)):
        pass
    for o, (f2, N2, k2) in CELLS.items():
        if f2 != fam or o == nm: continue
        dN = 0 if N is None else abs(Ns.index(N2) - Ns.index(N)); dk = 0 if k is None else abs(Ks.index(k2) - Ks.index(k))
        if dN + dk == 1: out.append(o)
    return out
def rule_skip(c, nm):
    fam, N, k = CELLS[nm]; d = c.d.to_numpy(); sk = np.zeros(len(c), bool)
    if fam in ('Ls', 'LsG'): sk |= (d == 1) & (c.min_since_loss_stream.to_numpy() < N * 60)
    if fam in ('G', 'LsG'): sk |= (d == 1) & (c.bar_range_atr.to_numpy() > k)
    return sk, (float(N) if fam == 'Lb' else 0.0)
def rules():
    c = c3; n = len(c); yr = c.year.to_numpy(); out = {}
    for nm in CELLS:
        sk, lb = rule_skip(c, nm); out[nm] = dict(win=window_metrics(c, sk, lb), per_year=per_year(c, sk, lb))
        print(nm, {w: (out[nm]['win'][w]['n'], round(out[nm]['win'][w]['wr'], 2), round(out[nm]['win'][w]['net'], 2), round(out[nm]['win'][w]['maxdd'], 2)) for w in out[nm]['win']}, flush=True)
    # Rule-WF: per test year choose cell on folds Y-2, Y-1 (per-year sims already computed for 2020+; need 2018, 2019 folds too)
    fy = {nm: {} for nm in CELLS}; base = {}
    for V in range(2018, 2026):
        base[V] = metr(portfolio(c, np.zeros(n, bool), T(f'{V}-01-01'), T(f'{V+1}-01-01')))
        for nm in CELLS:
            sk, lb = rule_skip(c, nm); fy[nm][V] = metr(portfolio(c, sk, T(f'{V}-01-01'), T(f'{V+1}-01-01'), lb))
    chosen = {}; rows = []
    for Y in range(2020, 2027):
        S = {nm: [fold_ok(fy[nm][V], base[V]) for V in (Y - 2, Y - 1)] for nm in CELLS}
        best, off, tab = choose(S, list(CELLS), lambda k: [k] + rule_neigh(k))
        chosen[Y] = best; rows.append(dict(arm='Rule-WF', test_year=Y, chosen_cell=best, smoothed=round(tab[best][0], 3), feasible=tab[best][1], allow_off=off or 'OFF'))
    # stitched Rule-WF: build per-candidate skip by year; Lb depends on sim state -> run per year segment with that year's lb; for continuous windows
    # we stitch by giving each candidate the chosen cell of its year (Lb cells applied through a per-candidate lb hours array)
    sk = np.zeros(n, bool); lbh = np.zeros(n)
    for Y, nm in chosen.items():
        s_, lb = rule_skip(c, nm); m = yr == Y; sk[m] = s_[m]; lbh[m] = lb
    res = dict(main=stitched(c, sk, lbh)); res['per_year'] = {Y: metr(portfolio_v(c, sk, lbh, T(f'{Y}-01-01'), min(T(f'{Y+1}-01-01'), END))) for Y in range(2020, 2027)}
    pd.to_pickle(dict(cells=out, wf=res, wf_years=pd.DataFrame(rows), neigh={k: rule_neigh(k) for k in CELLS}), OUT / 'results' / 'rules.pkl')
    print(pd.DataFrame(rows).to_string())
def portfolio_v(c, skip, lbh, start, end):
    """portfolio with per-candidate Lb hours (Rule-WF stitching); identical gates."""
    a, z = ms(start), ms(end); m = (c.ts.to_numpy() >= a) & (c.ts.to_numpy() < z)
    TS = c.ts.to_numpy()[m]; TX = c.tx.to_numpy()[m]; SG = c.sig.to_numpy()[m]; PNL = c.pnl.to_numpy()[m]; SW = c.sw.to_numpy()[m]
    RR = c.R.to_numpy()[m]; DD_ = c.d.to_numpy()[m]; SK = skip[m]; LB = lbh[m] * 3600000
    bal = BAL0; op = None; dl = {}; cool = 0; daystart = {}; res = []; cms = 30 * 60000; last_tx = 0; last_loss = -10**15
    for k in range(len(TS)):
        ts = TS[k]
        if op is not None and op[1] <= ts:
            p = op; op = None; bal += p[3]; last_tx = p[1]
            if p[3] < 0:
                day = p[1] // 86400000; dl[day] = dl.get(day, 0) + 1; cool = p[1] + cms; last_loss = p[1]
            res.append(p)
        if op is not None or ts < cool: continue
        sg = SG[k]
        if last_tx > sg or sg < cool: continue
        if dl.get(sg // 86400000, 0) >= 1: continue
        day = ts // 86400000
        if dl.get(day, 0) >= 1: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * 0.10: continue
        if RR[k] + SLIP > bal * 0.1: continue
        if SK[k]: continue
        if LB[k] > 0 and DD_[k] == 1 and sg - last_loss < LB[k]: continue
        op = (ts, TX[k], DD_[k], PNL[k] + SW[k])
    if op is not None: res.append(op)
    return np.array([r[3] for r in res])
def stitched(c, sk, lbh):
    out = {w: metr(portfolio_v(c, sk, lbh, a, z)) for w, (a, z) in WINDOWS.items()}
    nets = []; dds = []
    for y in range(2020, 2025):
        net = portfolio_v(c, sk, lbh, T(f'{y}-01-01'), T(f'{y+1}-01-01')); nets.append(net); dds.append(metr(net)['maxdd'])
    m = metr(np.concatenate(nets)); m['maxdd'] = max(dds); out['2020-24'] = m; return out

if __name__ == '__main__':
    (OUT / 'results').mkdir(exist_ok=True); t0 = time.time()
    # portfolio_v must equal portfolio when lbh = 0
    z = np.zeros(len(c3), bool); assert abs(stitched(c3, z, np.zeros(len(c3)))['2024-26']['net'] - par['2024-26']['net']) < 1e-9
    if sys.argv[1] == 'refs':
        pd.to_pickle({btp: window_metrics(D['store'][btp][0], np.zeros(len(D['store'][btp][0]), bool)) for btp in (3.0, 2.0)}, OUT / 'results' / 'refs.pkl'); print('refs ok')
    elif sys.argv[1] == 'rules': rules()
    else: run(sys.argv[1])
    print('done', sys.argv[1], round(time.time() - t0), 's')
