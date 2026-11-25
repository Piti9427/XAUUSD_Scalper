"""t202u evaluation: objective, parameter penalty, neighbour stability, fixed split, walk-forward (train 36m / test 6m / step 6m), bootstrap."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from combo import *
NET = np.load(OUT / 'combo-net.npy'); CNT = np.load(OUT / 'combo-cnt.npy'); NAMES = json.load(open(OUT / 'combo-names.json'))
assert NAMES == [cname(c) for c in COMBOS]
K = len(COMBOS); MI = {str(p): j for j, p in enumerate(MONTHS)}; LIVEK = NAMES.index(cname(LIVE))
NP = np.array([nparams(c) for c in COMBOS])
idx_of = {tuple(AX[a].index(c[a]) for a in AX): k for k, c in enumerate(COMBOS)}
NB = []
for c in COMBOS:
    pos = [AX[a].index(c[a]) for a in AX]; nb = []
    for d in range(len(pos)):
        for s in (-1, 1):
            q = list(pos); q[d] += s
            if 0 <= q[d] < len(AX[list(AX)[d]]): nb.append(idx_of[tuple(q)])
    NB.append(nb)
def mets(cols):
    n = NET[:, cols]; c = CNT[:, cols]; L = len(cols)
    G = 100 * (n > 0).mean(1); Nn = (n < 0).sum(1); eq = np.cumsum(n, 1); DD = np.max(np.maximum.accumulate(np.maximum(eq, 0), 1) - eq, 1)
    W = n.min(1); net = n.sum(1); tpm = c.sum(1) / L
    J = (G - 100 * Nn / L) - 0.05 * DD - 0.05 * np.maximum(0, -W) + 0.01 * net * 12 / L - 2 * NP
    return dict(G=G, Nn=Nn, DD=DD, W=W, net=net, tpm=tpm, J=J)
def robust(J): return np.array([min(J[k], np.median(J[NB[k]])) for k in range(K)])
def cols(a, b): return [MI[a] + i for i in range(MI[b] - MI[a] + 1)]
SELc = cols('2015-03', '2024-12'); VALc = cols('2025-01', str(MONTHS[-1])); HOLc = cols('2026-07', str(MONTHS[-1])); C24 = cols('2024-01', str(MONTHS[-1]))
MS = mets(SELc); RJ = robust(MS['J']); MV = mets(VALc); MH = mets(HOLc); M24 = mets(C24)
# ---- walk-forward
WF = []; oos = []; picks = []
s0 = 0
while s0 + 36 < len(MONTHS):
    tr = list(range(s0, s0 + 36)); te = list(range(s0 + 36, min(s0 + 42, len(MONTHS))))
    mt = mets(tr); rj = robust(mt['J']); rj[mt['tpm'] < 4.5] = -1e9; k = int(np.argmax(rj))
    me = mets(te); WF.append((te, me)); picks.append(dict(train=f'{MONTHS[tr[0]]}..{MONTHS[tr[-1]]}', test=f'{MONTHS[te[0]]}..{MONTHS[te[-1]]}', pick=NAMES[k],
        test_net=round(me['net'][k], 2), live_net=round(me['net'][LIVEK], 2), test_neg=int(me['Nn'][k]), live_neg=int(me['Nn'][LIVEK])))
    oos += [(j, k) for j in te]; s0 += 6
PK = pd.DataFrame(picks); PK.to_csv(OUT / 'combo-wf-picks.csv', index=False)
score_live = lambda me, k: (me['G'][k] - 100 * me['Nn'][k] / max(1, len(me['G']))) 
PASS = np.zeros(K)
for te, me in WF:
    q = me['G'] - 100 * me['Nn'] / len(te)
    PASS += (me['net'] >= 0) & (q >= q[LIVEK])
PASS = 100 * PASS / len(WF)
oos_net = np.array([NET[k, j] for j, k in oos]); live_oos = NET[LIVEK, [j for j, _ in oos]]
def ser(n): eq = np.cumsum(n); return dict(G=round(100 * (n > 0).mean(), 1), neg=int((n < 0).sum()), DD=round(float(np.max(np.maximum.accumulate(np.maximum(eq, 0)) - eq)), 2), W=round(float(n.min()), 2), net=round(float(n.sum()), 2), months=len(n))
print('WF re-tuned OOS', ser(oos_net)); print('WF live same months', ser(live_oos))
print(PK.to_string())
T_ = pd.DataFrame(dict(name=NAMES, k_params=NP, sel_J=MS['J'].round(2), sel_robustJ=RJ.round(2), sel_G=MS['G'].round(1), sel_neg=MS['Nn'], sel_DD=MS['DD'].round(2), sel_W=MS['W'].round(2), sel_net=MS['net'].round(2), sel_tpm=MS['tpm'].round(2),
    val_G=MV['G'].round(1), val_neg=MV['Nn'], val_DD=MV['DD'].round(2), val_W=MV['W'].round(2), val_net=MV['net'].round(2), val_tpm=MV['tpm'].round(2),
    hold_G=MH['G'].round(1), hold_neg=MH['Nn'], hold_net=MH['net'].round(2), wf_pass=PASS.round(1), wf_picked=[int((PK.pick == n).sum()) for n in NAMES]))
T_.to_csv(OUT / 'combo-all.csv', index=False)
pool = T_[(T_.sel_tpm >= 4.5)].sort_values('sel_robustJ', ascending=False).head(30)
top5 = pool.sort_values(['wf_pass', 'sel_robustJ'], ascending=False).head(5)
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 40)
print('LIVE'); print(T_.iloc[[LIVEK]].to_string()); print('POOL30'); print(pool.to_string()); print('TOP5'); print(top5.to_string())
pool.to_csv(OUT / 'combo-pool30.csv', index=False)
# ---- trade-level 2024-26 continuous + bootstrap for top5 + live
need = [LIVE] + [COMBOS[NAMES.index(n)] for n in top5.name]
SS = {}; BS = {}
for c in need:
    SS.setdefault((c['sl'], c['stp'], c['spike']), sell_set(c['sl'], c['stp'], c['spike'])); BS.setdefault(c['btp'], buy_set(c['btp']))
a24, z24 = T('2024-01-01'), END
def daily(t, idx):
    if len(t) == 0: return np.zeros(len(idx))
    d = pd.to_datetime(t.tx, unit='ms', utc=True).dt.tz_convert(ICT).dt.normalize()
    return t.groupby(d.to_numpy()).net.sum().reindex(idx, fill_value=0.0).to_numpy()
idx24 = pd.date_range(a24, z24, freq='D', tz=ICT)[:-1]; idxall = pd.date_range(T('2015-03-02'), z24, freq='D', tz=ICT)[:-1]
def boot(dc, db, n=5000, Lb=20):
    N = len(dc); nb_ = int(np.ceil(N / Lb)); st = rng.integers(0, N, size=(n, nb_)); ix = ((st[:, :, None] + np.arange(Lb)[None, None, :]) % N).reshape(n, -1)[:, :N]
    return round(float(((dc[ix].sum(1) - db[ix].sum(1)) > 0).mean()), 3)
rows = []; MON = {}
for c in need:
    x = cand_frame(c, SS, BS); t = portfolio2(x, a24, z24); _, _, tall = run_all(x)
    m = monthly(t, a24, z24); MON[cname(c)] = m
    eq = BAL0 + t.net.cumsum(); dd = float((eq.cummax() - eq).max())
    rows.append(dict(name=cname(c), _t=t, _ta=tall, tpm=round(len(t) / len(m), 2), win=round(100 * (t.net > 0).mean(), 1), net=round(t.net.sum(), 2), maxdd=round(dd, 2),
                     green=round(100 * (m > 0).mean(), 1), neg=int((m < 0).sum()), worst=round(m.min(), 2)))
b24 = daily(rows[0]['_t'], idx24); ball = daily(rows[0]['_ta'], idxall)
for r in rows:
    r['P_net24'] = None if r is rows[0] else boot(daily(r['_t'], idx24), b24)
    r['P_net15_26'] = None if r is rows[0] else boot(daily(r['_ta'], idxall), ball)
    k = NAMES.index(r['name']); r['wf_pass'] = round(PASS[k], 1); r['k_params'] = int(NP[k]); r['nb_median_selJ'] = round(float(np.median(MS['J'][NB[k]])), 2)
    r['sel_J'] = round(MS['J'][k], 2); r['val_net'] = round(MV['net'][k], 2); r['val_G'] = round(MV['G'][k], 1); r['hold_G'] = round(MH['G'][k], 1); r['hold_net'] = round(MH['net'][k], 2)
R = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]); R.to_csv(OUT / 'combo-top5.csv', index=False); print(R.to_string())
pd.DataFrame(MON).round(2).rename(index=str).to_csv(OUT / 'combo-monthly-2024-26.csv')
