"""C22 ML walk-forward Round 3 (preregister.md). Box-only. Usage: ml.py ARM | rules | refs | all-names"""
import sys, hashlib, time, warnings, json; from pathlib import Path
import numpy as np, pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge, HuberRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.mixture import GaussianMixture
from sklearn.metrics import roc_auc_score, r2_score
from sklearn.inspection import permutation_importance
from scipy.stats import spearmanr
warnings.filterwarnings('ignore')
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
D = pd.read_pickle(OUT / 'cands_features.pkl'); END = D['END']; BAL0 = D['BAL0']; SLIP = D['SLIP']; ICT = 'Asia/Bangkok'
T = lambda s: pd.Timestamp(s, tz=ICT); ms = lambda t: int(pd.Timestamp(t).value // 10**6); Y0 = lambda y: ms(T(f'{y}-01-01'))
c3, X3df = D['store'][3.0]; c2, _ = D['store'][2.0]; n = len(c3)
assert (c3.i.values == c2.i.values).all() and (c3.d.values == c2.d.values).all() and (c3.ts.values == c2.ts.values).all()
FEATS = ['log_min_since_sl', 'bar_range_atr', 'atr_pct_price', 'd1_ema50_slope', 'd1_ema20_dist', 'dist_lo20_d1atr', 'h4dist', 'hour_sin', 'hour_cos',
         'ext_atr', 'rsi7', 'side', 'd1_atr_pctile252',
         'er10_m15', 'er20_m15', 'er10_h1', 'er20_h1', 'atr5_50', 'bbw_pctile', 'day_open_dist', 'day_high_dist', 'day_low_dist', 'color_run', 'body3',
         'meta_wr5', 'meta_wr10', 'meta_lstreak']
GMMF = ['er20_m15', 'd1_atr_pctile252', 'atr5_50', 'd1_ema50_slope_raw']
X = X3df[FEATS].to_numpy(float); XG = X3df[GMMF].to_numpy(float)
YR = c3.year.to_numpy(); DSIDE = c3.d.to_numpy(); TS = c3.ts.to_numpy(); TX3 = c3.tx.to_numpy()

def mix(sw):
    """live candidates with BUY rows in sw replaced by the BUY TP 2.0R version of the same signal"""
    if not sw.any(): return c3
    c = c3.copy()
    for col in ('tx', 'pnl', 'why', 'sw', 'R', 'net_est'): c.loc[sw, col] = c2.loc[sw, col].to_numpy()
    return c

def portfolio(c, skip, start, end, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10):
    """entry_sl.portfolio2 copy (live gates) + skip after all gates. returns (net, exit_ts)"""
    a, z = ms(start), ms(end); m = (c.ts.to_numpy() >= a) & (c.ts.to_numpy() < z)
    TSm = c.ts.to_numpy()[m]; TXm = c.tx.to_numpy()[m]; SG = c.sig.to_numpy()[m]; PNL = c.pnl.to_numpy()[m]; SW = c.sw.to_numpy()[m]
    RR = c.R.to_numpy()[m]; DD_ = c.d.to_numpy()[m]; SK = skip[m]
    bal = bal0; op = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0
    for k in range(len(TSm)):
        ts = TSm[k]
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
        if RR[k] + SLIP > bal * cap: continue
        if SK[k]: continue
        op = (ts, TXm[k], DD_[k], PNL[k] + SW[k])
    if op is not None: res.append(op)
    return np.array([r[3] for r in res]), np.array([r[1] for r in res])
def metr(net):
    k = len(net)
    if k == 0: return dict(n=0, wins=0, losses=0, ties=0, wr=0.0, net=0.0, exp=0.0, maxdd=0.0)
    eqc = np.r_[BAL0, BAL0 + np.cumsum(net)]; dd = float((np.maximum.accumulate(eqc) - eqc).max())
    return dict(n=k, wins=int((net > 0).sum()), losses=int((net < 0).sum()), ties=int((net == 0).sum()), wr=100 * float((net > 0).mean()), net=float(net.sum()), exp=float(net.sum() / k), maxdd=dd)
WINDOWS = {'2025-26': (T('2025-01-01'), END), '2024-26': (T('2024-01-01'), END)}
def yearly(c, skip, y0, y1):
    nets = []; dds = []
    for y in range(y0, y1 + 1):
        net = portfolio(c, skip, T(f'{y}-01-01'), min(T(f'{y+1}-01-01'), END))[0]; nets.append(net); dds.append(metr(net)['maxdd'])
    m = metr(np.concatenate(nets)); m['maxdd'] = max(dds); return m
def window_metrics(c, skip):
    out = {w: metr(portfolio(c, skip, a, z)[0]) for w, (a, z) in WINDOWS.items()}; out['2020-24'] = yearly(c, skip, 2020, 2024); return out
def per_year(c, skip): return {Y: metr(portfolio(c, skip, T(f'{Y}-01-01'), min(T(f'{Y+1}-01-01'), END))[0]) for Y in range(2020, 2027)}
def year_sim(c, skip, V): return metr(portfolio(c, skip, T(f'{V}-01-01'), T(f'{V+1}-01-01'))[0])
Z = np.zeros(n, bool)
par = window_metrics(c3, Z)
assert par['2025-26']['n'] == 313 and round(par['2025-26']['net'], 2) == 1898.96 and round(par['2025-26']['maxdd'], 2) == 224.89 and par['2025-26']['wins'] == 121, par['2025-26']
assert par['2024-26']['n'] == 429 and round(par['2024-26']['net'], 2) == 1826.95 and round(par['2024-26']['maxdd'], 2) == 224.89 and par['2024-26']['wins'] == 146, par['2024-26']
BASEY = {V: year_sim(c3, Z, V) for V in range(2018, 2027)}

def fold_ok(m, b):
    feas = (m['maxdd'] <= b['maxdd']) and (m['net'] >= b['net'] - 0.15 * abs(b['net']))
    return feas, (m['wr'] - b['wr']) + (20 * (b['maxdd'] - m['maxdd']) / b['maxdd'] if b['maxdd'] > 0 else 0.0)
def choose(S, keys, neigh):
    tab = {}
    for k in keys:
        nb = neigh(k); tab[k] = (float(np.mean([np.mean([s for _, s in S[x]]) for x in nb])), all(all(f for f, _ in S[x]) for x in nb), float(np.mean([s for _, s in S[k]])))
    feas = [k for k in keys if tab[k][1]]; pool = feas if feas else keys
    return max(pool, key=lambda k: tab[k][0]), tab

def train_mask(T_, scope, label):
    end = c3.lab_end.to_numpy() if label == 'mfe' else c3.y1r_end.to_numpy()
    m = (TS >= Y0(T_ - 4)) & (np.maximum(TX3, end) < Y0(T_))
    if scope in ('buy', 'buy20'): m &= DSIDE == 1
    return m
def side_mask(scope): return (DSIDE == 1) if scope in ('buy', 'buy20') else np.ones(n, bool)

# ---------------- model factories ----------------
REG_HP = {'Ridge': [dict(alpha=a) for a in (1.0, 10.0, 100.0)], 'Huber': [dict(alpha=a) for a in (0.0001, 0.01, 1.0)],
          'HGBR': [dict(max_depth=a, min_samples_leaf=b) for a in (2, 3) for b in (20, 50)]}
def make_reg(fam, hp):
    imp = SimpleImputer(strategy='median')
    if fam == 'Ridge': return make_pipeline(imp, StandardScaler(), Ridge(alpha=hp['alpha']))
    if fam == 'Huber': return make_pipeline(imp, StandardScaler(), HuberRegressor(epsilon=1.35, alpha=hp['alpha'], max_iter=1000))
    return make_pipeline(imp, HistGradientBoostingRegressor(max_depth=hp['max_depth'], min_samples_leaf=hp['min_samples_leaf'], learning_rate=0.05, max_iter=150,
                                                            l2_regularization=1.0, early_stopping=False, random_state=0))
Q = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]; QD = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

# ---------------- Arm 1: MFE/MAE filter ----------------
def mfe_fit(fam, hp, scope, T_):
    tr = train_mask(T_, scope, 'mfe'); sel = side_mask(scope)
    m1 = make_reg(fam, hp).fit(X[tr], c3.MFE_R.to_numpy()[tr]); m2 = make_reg(fam, hp).fit(X[tr], c3.MAE_R.to_numpy()[tr])
    pf = np.full(n, np.nan); pa = np.full(n, np.nan); pf[sel] = m1.predict(X[sel]); pa[sel] = m2.predict(X[sel])
    return tr, pf, pa, (m1, m2)
def score(pf, pa, f): return pf / (np.maximum(pa, 0.0) + 0.25) if f == 'ratio' else pf - pa

def run_quantile_arm(arm, kind, fam, scope):
    """kind: 'filter' (MFE/MAE), 'dyntp' (MFE switch), 'sparse' (y1r top-5)"""
    if kind == 'filter': params = [(hi, f) for hi in range(len(REG_HP[fam])) for f in ('ratio', 'diff')]; qs = Q; step = 0.05
    elif kind == 'dyntp': params = [(hi, 'mfe') for hi in range(len(REG_HP[fam]))]; qs = QD; step = 0.1
    else: params = [(hi, 'p') for hi in range(len(SP_HP[fam]))]; qs = Q; step = 0.05
    cand = c2 if scope == 'buy20' else c3
    def fitscore(p, T_):
        hi, f = p
        if kind == 'filter':
            tr, pf, pa, mods = mfe_fit(fam, REG_HP[fam][hi], scope, T_); s = score(pf, pa, f); return tr, s, mods, None
        if kind == 'dyntp':
            tr = train_mask(T_, 'buy', 'mfe'); mdl = make_reg(fam, REG_HP[fam][hi]).fit(X[tr], c3.MFE_R.to_numpy()[tr]); s = np.full(n, np.nan); b_ = DSIDE == 1
            s[b_] = mdl.predict(X[b_]); return tr, s, (mdl,), None
        tr, s, mdl, feats = sparse_fit(fam, SP_HP[fam][hi], scope, T_); return tr, s, (mdl,), feats
    def act(s, thr, mask):
        a = mask & np.isfinite(s) & (s < thr); return a
    def sim(a, V=None, window=None):
        if kind == 'dyntp': c = mix(a); sk = Z
        else: c = cand; sk = a
        return c, sk
    yrs = []; sel_rows = []; feat_rows = []; oos_s = np.full(n, np.nan); thr = {k: np.full(n, np.inf) for k in ('main', 'm', 'p')}; final = None
    basey = BASEY if scope != 'buy20' else {V: year_sim(c2, Z, V) for V in range(2018, 2027)}
    for Y in range(2020, 2027):
        S = {}
        for V in (Y - 2, Y - 1):
            pr = YR == V
            for p in params:
                tr, s, _, feats = fitscore(p, V)
                if feats is not None: feat_rows.append(dict(arm=arm, test_year=Y, fold=V, hp=p[0], features=','.join(feats)))
                ts_ = s[tr & np.isfinite(s)]
                for q in qs:
                    a = act(s, np.quantile(ts_, q), pr); c, sk = sim(a); S.setdefault((p, q), []).append(fold_ok(year_sim(c, sk, V), basey[V]))
        keys = [(p, q) for p in params for q in qs]
        best, tab = choose(S, keys, lambda k: [(k[0], q) for q in qs if abs(q - k[1]) <= step + 1e-9])
        for k, (sm, fe, raw) in tab.items(): sel_rows.append(dict(arm=arm, test_year=Y, param=str(k[0]), q=k[1], score=round(raw, 3), smoothed=round(sm, 3), feasible=fe))
        tr, s, mods, feats = fitscore(best[0], Y); pr = YR == Y; ts_ = s[tr & np.isfinite(s)]
        if feats is not None: feat_rows.append(dict(arm=arm, test_year=Y, fold='final', hp=best[0][0], features=','.join(feats)))
        oos_s[pr] = s[pr]
        for k_, sh in (('main', 0), ('m', -step), ('p', step)): thr[k_][pr] = np.quantile(ts_, min(max(best[1] + sh, 0.0), 1.0))
        d = dict(arm=arm, test_year=Y, chosen=str(best[0]), q=best[1], smoothed=round(tab[best][0], 3), feasible=tab[best][1], n_test=int(pr.sum()))
        m_ = pr & side_mask('buy' if kind == 'dyntp' else scope)
        if kind in ('filter', 'dyntp'):
            hi = best[0][0]; fam_hp = REG_HP[fam][hi]
            _, pf, pa, _ = mfe_fit(fam, fam_hp, 'buy' if kind == 'dyntp' else scope, Y)
            yt = c3.MFE_R.to_numpy()[m_]; ya = c3.MAE_R.to_numpy()[m_]
            d.update(mfe_r2=round(r2_score(yt, pf[m_]), 4), mfe_spearman=round(spearmanr(pf[m_], yt).correlation, 4),
                     mae_r2=round(r2_score(ya, pa[m_]), 4), mae_spearman=round(spearmanr(pa[m_], ya).correlation, 4))
        else:
            yy = cand.y1r.to_numpy()[m_]; d.update(y1r_auc=round(roc_auc_score(yy, s[m_]), 4) if len(set(yy)) > 1 else np.nan)
        yrs.append(d); print(d, flush=True)
        if Y == 2026: final = (mods, tr, feats)
    res = {}
    for k_ in ('main', 'm', 'p'):
        a = np.isfinite(oos_s) & (oos_s < thr[k_]); c, sk = sim(a); res[k_] = window_metrics(c, sk); res[k_]['acted_cands'] = int(a.sum())
        if k_ == 'main': res['per_year'] = per_year(c, sk); res['per_year_base'] = per_year(cand, Z)
    imp = []
    mods, tr, feats = final; cols = feats if feats is not None else FEATS
    for j, mdl in enumerate(mods):
        tgt = ['MFE_R', 'MAE_R'][j] if kind != 'sparse' else 'y1r'
        est = mdl[-1]
        if hasattr(est, 'coef_'):
            for f, v in zip(cols, np.ravel(est.coef_)): imp.append(dict(arm=arm, target=tgt, feature=f, kind='std_coef', value=float(v)))
        else:
            Xi = X[tr] if feats is None else X[tr][:, [FEATS.index(f) for f in feats]]
            yv = c3[tgt].to_numpy()[tr] if kind != 'sparse' else cand.y1r.to_numpy()[tr]
            pi = permutation_importance(mdl, Xi, yv, scoring='r2' if kind != 'sparse' else 'roc_auc', n_repeats=5, random_state=0, n_jobs=1)
            for f, v in zip(cols, pi.importances_mean): imp.append(dict(arm=arm, target=tgt, feature=f, kind='perm', value=float(v)))
    return dict(arm=arm, res=res, years=pd.DataFrame(yrs), sel=pd.DataFrame(sel_rows), imp=pd.DataFrame(imp), feats=pd.DataFrame(feat_rows))

# ---------------- Arm 3: sparse top-5 ----------------
SP_HP = {'LR': [dict(C=x) for x in (0.01, 0.1, 1.0)], 'HGB': [dict(min_samples_leaf=x) for x in (50, 100)]}
CPATH = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
def sparse_fit(fam, hp, scope, T_):
    cand = c2 if scope == 'buy20' else c3
    tr = train_mask(T_, scope, 'y1r'); y = cand.y1r.to_numpy(); sel = side_mask(scope)
    pre = make_pipeline(SimpleImputer(strategy='median'), StandardScaler()).fit(X[tr]); Xt = pre.transform(X[tr])
    coef = None
    for Cc in CPATH:
        l1 = LogisticRegression(penalty='l1', C=Cc, solver='liblinear', max_iter=2000).fit(Xt, y[tr]); co = np.abs(l1.coef_.ravel())
        if (co > 0).sum() >= 5: coef = co; break
    if coef is None: coef = co
    top = list(np.argsort(-coef)[:5]); feats = [FEATS[j] for j in top]
    if fam == 'LR': mdl = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=hp['C'], max_iter=2000))
    else: mdl = make_pipeline(SimpleImputer(strategy='median'), HistGradientBoostingClassifier(max_depth=2, min_samples_leaf=hp['min_samples_leaf'], learning_rate=0.05,
                                                                                            max_iter=100, l2_regularization=1.0, early_stopping=False, random_state=0))
    mdl.fit(X[tr][:, top], y[tr]); s = np.full(n, np.nan); s[sel] = mdl.predict_proba(X[sel][:, top])[:, 1]
    return tr, s, mdl, feats

# ---------------- Arm 2: GMM ----------------
def run_gmm(arm, K, mode, nmin_list=(10, 15, 20)):
    rows = []; acts = {nm: np.zeros(n, bool) for nm in nmin_list}
    for Y in range(2020, 2027):
        tr = (TS >= Y0(Y - 4)) & (TX3 < Y0(Y))
        pre = make_pipeline(SimpleImputer(strategy='median'), StandardScaler()).fit(XG[tr])
        g = GaussianMixture(n_components=K, covariance_type='full', n_init=5, random_state=0).fit(pre.transform(XG[tr]))
        lab = g.predict(pre.transform(XG)); inner = (YR == Y - 2) | (YR == Y - 1); pr = YR == Y
        net = c3.net_est.to_numpy()
        for cl in range(K):
            for sd, sn in ((1, 'BUY'), (-1, 'SELL')):
                m = inner & (lab == cl) & (DSIDE == sd); mt = pr & (lab == cl) & (DSIDE == sd)
                rows.append(dict(arm=arm, test_year=Y, cluster=cl, side=sn, inner_n=int(m.sum()), inner_wr=round(100 * (net[m] > 0).mean(), 2) if m.any() else None,
                                 inner_mean_net=round(net[m].mean(), 3) if m.any() else None, test_n=int(mt.sum()),
                                 test_wr=round(100 * (net[mt] > 0).mean(), 2) if mt.any() else None, test_mean_net=round(net[mt].mean(), 3) if mt.any() else None,
                                 centroid=json.dumps(dict(zip(GMMF, np.round(pre[-1].inverse_transform(g.means_)[cl], 3).tolist())))))
                for nm in nmin_list:
                    if m.sum() >= nm and net[m].mean() < 0 and (mode == 'gate' or sd == 1): acts[nm][mt] = True
    out = {}
    for nm in nmin_list:
        a = acts[nm]; c, sk = (c3, a) if mode == 'gate' else (mix(a), Z)
        out[nm] = window_metrics(c, sk); out[nm]['acted_cands'] = int(a.sum())
        if nm == 15: out['per_year'] = per_year(c, sk); out['per_year_base'] = per_year(c3, Z)
    return dict(arm=arm, res=out, clusters=pd.DataFrame(rows))

# ---------------- rules ----------------
def rule_skip(fam, k):
    sk = (DSIDE == 1) & (c3.bar_range_atr.to_numpy() > k)
    if fam == 'LsG_8': sk |= (DSIDE == 1) & (c3.min_since_loss_stream.to_numpy() < 480)
    return sk
def episodes(net, tx, top=5):
    eq = BAL0 + np.cumsum(net); peak = np.maximum.accumulate(np.r_[BAL0, eq])[1:]; dd = peak - eq; eps = []; k = 0
    while k < len(dd):
        if dd[k] > 0:
            s = k
            while k < len(dd) and dd[k] > 0: k += 1
            j = s + int(np.argmax(dd[s:k])); eps.append(dict(start=s, trough=j, end=k, depth=float(dd[j]), n_trades=k - s,
                                                          t_start=str(pd.Timestamp(tx[max(s - 1, 0)], unit='ms', tz='UTC').tz_convert(ICT).date()),
                                                          t_trough=str(pd.Timestamp(tx[j], unit='ms', tz='UTC').tz_convert(ICT).date())))
        else: k += 1
    return sorted(eps, key=lambda e: -e['depth'])[:top]
def rules():
    out = {}; ep = []
    for fam in ('G', 'LsG_8'):
        for k in (1.25, 1.5, 1.75):
            nm = f'{fam}_{k}'; sk = rule_skip(fam, k)
            out[nm] = dict(win=window_metrics(c3, sk), per_year=per_year(c3, sk), hold1519=yearly(c3, sk, 2015, 2019))
    out['base'] = dict(win=par, hold1519=yearly(c3, Z, 2015, 2019))
    for nm in ['base'] + [x for x in out if x != 'base']:
        sk = Z if nm == 'base' else rule_skip(nm.rsplit('_', 1)[0], float(nm.rsplit('_', 1)[1]))
        for w, (a, z) in WINDOWS.items():
            net, tx = portfolio(c3, sk, a, z)
            for r, e in enumerate(episodes(net, tx)): ep.append(dict(cell=nm, window=w, rank=r + 1, depth=round(e['depth'], 2), n_trades=e['n_trades'], start=e['t_start'], trough=e['t_trough']))
        # removed BUY trades inside base worst episode
    return dict(cells=out, episodes=pd.DataFrame(ep))

ARMS = {}
for fam in ('Ridge', 'Huber', 'HGBR'):
    for sc in ('All', 'BUY'): ARMS[f'MFE-MAE-Filter-{fam}-{sc}'] = ('filter', fam, sc.lower())
for fam in ('Ridge', 'HGBR'): ARMS[f'MFE-DynamicTP-{fam}'] = ('dyntp', fam, 'buy')
for fam in ('LR', 'HGB'):
    for sc in ('BUY', 'All', 'BUY20'): ARMS[f'Sparse-{fam}-{sc}'] = ('sparse', fam, sc.lower())
GMMS = {f'GMM-K{K}-{m}': (K, m.lower().replace('tpswitch', 'switch')) for K in (3, 4) for m in ('Gate', 'TPswitch')}

if __name__ == '__main__':
    (OUT / 'results').mkdir(exist_ok=True); t0 = time.time(); a = sys.argv[1]
    if a == 'names': print(' '.join(list(ARMS) + list(GMMS)))
    elif a == 'refs': pd.to_pickle({3.0: par, 2.0: window_metrics(c2, Z)}, OUT / 'results' / 'refs.pkl'); print('refs ok')
    elif a == 'rules': pd.to_pickle(rules(), OUT / 'results' / 'rules.pkl'); print('rules ok')
    elif a in GMMS: pd.to_pickle(run_gmm(a, *GMMS[a]), OUT / 'results' / f'{a}.pkl')
    else: pd.to_pickle(run_quantile_arm(a, *ARMS[a]), OUT / 'results' / f'{a}.pkl')
    print('done', a, round(time.time() - t0), 's')
