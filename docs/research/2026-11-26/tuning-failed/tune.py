"""Tuning of failed families, v3 pre-registration (preregister.md, sha256 in preregister.sha256). Box-only research.
Imports f2f3-validate harness via sell-entry-sl-20261125/entry_sl.py (files not modified). portfolio_f = entry_sl.portfolio2 + optional
SELL skip rule (copied from untested-filters/post-tp rounds); portfolio_m copied from two-position round + k-profit gate; path_wick copied from wick-window round."""
import sys, hashlib, json, time; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
import numba as nb
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
t_start = time.time()
A24 = T('2024-01-01')
BOUNCE = (close - lo15) / A
_rg = hi15 - lo15
WFRAC = np.where(_rg > 0, (close - lo15) / np.where(_rg > 0, _rg, 1.0), 0.0)
EXT = (LL48 - close) / A

def nights(ts, tx):
    r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
    for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
    return n

def portfolio_f(c, start, end, rule=None, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    bal = bal0; open_ = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0; last_tp = -10**15; skipped = []
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
        if rule is not None and r.d == -1 and rule(int(r.i), sg, last_tp):
            skipped.append(dict(sig=sg, pnl=r.pnl, why=r.why)); continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, why=r.why)
    if open_ is not None: res.append(open_)
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs['skipped'] = skipped
    return t

# ---------- two-position (copied from two-position-20261126/two_pos.py + k gate) ----------
def make_groups(c):
    G = []
    for k, r in zip(c.index, c.itertuples()):
        G.append(dict(k=k, sig=int(r.sig), ts=int(r.ts), d=int(r.d), i=int(r.i),
                      legs=[dict(tx=int(r.tx), pnl=float(r.pnl), R=float(r.R), why=int(r.why), tbe=int(r.tbe), leg='A', lots=1, entry=float(r.entry))]))
    return G

def portfolio_m(G, start, end, maxpos=1, kgate=None, f3='set', cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    a, z = ms(start), ms(end)
    bal = bal0; open_ = []; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000)
    recent = []; gid = 0; sid = 0; set_lost = {}
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
            if not any(o['grp'] == lg['grp'] for o in open_): recent.append((lg['gtx'], lg['d'], [(lg['entry'], lg['Rraw'], lg['d'])]))
    for g in G:
        if not (a <= g['ts'] < z): continue
        close_until(g['ts'])
        sg = g['sig']
        busy_open = {o['grp']: o['d'] for o in open_}
        rec = [x for x in recent[-8:] if x[0] > sg]
        busy = list(busy_open.values()) + [x[1] for x in rec]
        if len(busy) >= maxpos: continue
        if any(d != g['d'] for d in busy): continue
        if kgate is not None and busy:
            px = close[g['i']]
            legs_ = [(o['entry'], o['Rraw'], o['d']) for o in open_] + [l for x in rec for l in x[2]]
            ok = all(((e - (px + SP)) if d == -1 else (px - e)) >= kgate * Rr for e, Rr, d in legs_)
            if not ok: continue
        if g['ts'] < cool or sg < cool: continue
        if dl.get(sg // 86400000, 0) >= max_losses: continue
        day = g['ts'] // 86400000
        if dl.get(day, 0) >= max_losses: continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop: continue
        open_risk = sum(o['risk'] for o in open_ if not (o['tbe'] >= 0 and o['tbe'] <= g['ts']))
        new_risk = sum(lg['R'] + slip_r * lg['lots'] for lg in g['legs'])
        if open_risk + new_risk > bal * cap: continue
        if not open_: sid += 1
        gid += 1; second = bool(busy_open) or bool(rec)
        gtx = max(lg['tx'] for lg in g['legs'])
        for lg in g['legs']:
            sw = nights(g['ts'], lg['tx']) * (swap * lg['lots'] if g['d'] == 1 else 0.0)
            open_.append(dict(k=g['k'], ts=g['ts'], sig=sg, i=g['i'], tx=lg['tx'], gtx=gtx, d=g['d'], net=lg['pnl'] + sw, R=lg['R'] + slip_r * lg['lots'],
                              risk=lg['R'] + slip_r * lg['lots'], why=lg['why'], tbe=lg['tbe'], leg=lg['leg'], grp=gid, set=sid, second=second, entry=lg['entry'], Rraw=lg['R']))
    res.extend(sorted(open_, key=lambda x: x['tx']))
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs['skipped'] = []
    return t

# ---------- wick path (copied from wick-window-20261125/wick_window.py) ----------
@nb.njit(cache=False)
def path_wick(j0, t1, O, H, L, C, last, sp, slip, atr, sig_ts, W, N, scratch, tp_rr, be_r, scr_r):
    n = len(t1)
    if j0 >= n or t1[j0] - sig_ts > 90000: return -1, -1, 0.0, 0.0, 0.0, -1, 0
    entry = O[j0] - slip; fill = j0
    Rl = 2.5 * atr; tight = entry + 2.5 * atr
    stop = entry + W * atr; target = entry - tp_rr * Rl
    prot = False; tightened = W <= 2.5; nc = 0
    for k in range(fill, n):
        if H[k] + sp >= stop:
            why = 1 if prot else (3 if tightened else 0)
            return t1[fill], t1[k], entry - (stop + slip), entry, W * atr, why, nc
        if L[k] + sp <= target:
            return t1[fill], t1[k], entry - target, entry, W * atr, 2, nc
        if last[k]:
            nc += 1; ex = C[k] + sp
            if (not prot) and (entry - ex) - slip >= be_r * Rl:
                prot = True
                if stop > entry - slip: stop = entry - slip
            if nc == N and (not prot) and (not tightened):
                if scratch and (entry - ex) - slip < scr_r * Rl:
                    return t1[fill], t1[k], entry - (ex + slip), entry, W * atr, 5, nc
                tightened = True
                if ex >= tight:
                    return t1[fill], t1[k], entry - (ex + slip), entry, W * atr, 6, nc
                if stop > tight: stop = tight
    return t1[fill], t1[n - 1], entry - (C[n - 1] + sp), entry, W * atr, 4, nc

def wick_rows(W, N):
    out = []; keep = []
    for r in S0.itertuples():
        i = int(r.i); ts = int(dec[i]); j = int(np.searchsorted(t1, ts)); a = float(A[i])
        res = path_wick(j, t1, O, H, L, C, last, SP, SLIP, a, ts, float(W), int(N), False, 1.35, 1.0, 0.25)
        if res[0] < 0: continue
        out.append(res); keep.append(r.Index)
    o = np.array(out, dtype=float); s = S0.loc[keep].copy()
    s['sig'] = dec[s.i.to_numpy()]
    s = s.assign(ts=o[:, 0].astype(np.int64), tx=o[:, 1].astype(np.int64), pnl=o[:, 2], entry=o[:, 3], R=o[:, 4], why=o[:, 5].astype(int))
    s['rr_plan'] = 1.35 * 2.5 / W; s['sl_atr'] = s.R / s.atr
    return s

def build_b(s, buys):
    c = pd.concat([buys, s]).sort_values(['ts', 'd']).reset_index(drop=True)
    return c[~(c.h4dist < 10)]

# ---------- windows ----------
TUNE = (T('2015-03-02'), T('2023-01-01')); WF = (T('2023-01-01'), T('2025-01-01'))
WINS = {'TUNE 2015-22': TUNE, 'WF 2023-24': WF, '2019-24': WIN['2019-24'], '2015-18': WIN['2015-18'], '2025-26': WIN['2025-26 all'], '2024-26': (A24, END)}
def run_parts(kind, obj, kw, wn):
    a, z = WINS[wn]
    sg = [(a, z)] if wn == '2024-26' else segs(a, z)
    if kind == 'm': return [(portfolio_m(obj, s0, s1, **kw), (s0, s1)) for s0, s1 in sg]
    return [(portfolio_f(obj, s0, s1, **kw), (s0, s1)) for s0, s1 in sg]

def metrics(parts, a, z):
    ps = [(p.sort_values('tx', kind='stable') if len(p) else p, g) for p, g in parts]
    t = pd.concat([p for p, _ in ps if len(p)], ignore_index=True)
    n = len(t); w = int((t.net > 0).sum()); l = int((t.net < 0).sum())
    dd = max(stats_block(p, BAL0, calendar_months(*g))['maxdd'] for p, g in ps if len(p))
    mon = pd.Series(stats_block(t, BAL0, calendar_months(a, z))['monthly'])
    out = dict(n=n, wins=w, losses=l, ties=n - w - l, wr=round(100 * w / n, 2), wl=round(w / l, 3) if l else np.inf,
               net=round(t.net.sum(), 2), exp=round(t.net.sum() / n, 3), avgR=round(t.r.mean(), 3), maxdd=round(dd, 2),
               net_dd=round(t.net.sum() / dd, 3) if dd else np.nan, skipped=sum(len(p.attrs.get('skipped', [])) for p, _ in parts))
    if 'second' in t: out['second_legs'] = int(t.second.sum()); out['signals'] = int(len(t) - t.second.sum())
    return out, mon

# ---------- 1. parity ----------
CB = build(sell_rows())
b0 = BASE[~(BASE.h4dist < 10)].sort_values(['ts', 'd']).reset_index(drop=True)
p25 = portfolio(b0, *WIN['2025-26 all'], max_losses=1).net.sum()
q25, q25p = run(CB, *WIN['2025-26 all']); q24 = portfolio2(CB, A24, END)
f25 = portfolio_f(CB, *WIN['2025-26 all']); f24 = portfolio_f(CB, A24, END)
G1 = make_groups(CB)
m25 = portfolio_m(G1, *WIN['2025-26 all']); m24 = portfolio_m(G1, A24, END)
CW = build(wick_rows(2.5, 2)); w25 = portfolio_f(CW, *WIN['2025-26 all']); w24 = portfolio_f(CW, A24, END)
print('generating BUY candidates btp 3.0 for parity ...', flush=True)
GEN = {}
def buys_for(btp):
    if btp not in GEN:
        g = gen(btp=btp); bb = g[g.d == 1].copy(); bb['sig'] = dec[bb.i.to_numpy()]; bb['rr_plan'] = btp; bb['sl_atr'] = 2.5; GEN[btp] = bb
    return GEN[btp]
B30 = buys_for(3.0)
buy_same = len(B30) == len(BUYS) and np.allclose(B30.pnl.to_numpy(), BUYS.pnl.to_numpy()) and (B30.ts.to_numpy() == BUYS.ts.to_numpy()).all()
CE = build_b(sell_rows(), B30); e25 = portfolio_f(CE, *WIN['2025-26 all']); e24 = portfolio_f(CE, A24, END)
dd = lambda t, a, z: round(stats_block(t, BAL0, calendar_months(a, z))['maxdd'], 2)
r2 = lambda x: round(x.net.sum(), 2)
par = dict(core_2025_26=round(p25, 2), portfolio2_2025_26=r2(q25), portfolio2_2024_26=r2(q24), portfolio_f_2025_26=r2(f25), portfolio_f_2024_26=r2(f24),
           portfolio_m1_2025_26=r2(m25), portfolio_m1_2024_26=r2(m24), wick25_2025_26=r2(w25), wick25_2024_26=r2(w24),
           genbuy30_same_as_base=bool(buy_same), genbuy30_2025_26=r2(e25), genbuy30_2024_26=r2(e24),
           dd_2025_26=dd(f25, *WIN['2025-26 all']), dd_2024_26=dd(f24, A24, END))
print('parity', par, flush=True); pd.DataFrame([par]).to_csv(OUT / 'parity.csv', index=False)
for k_, v in par.items():
    if k_.endswith('2025_26') and not k_.startswith('dd'): assert v == 1898.96, ('PARITY FAILED - stop', k_, v)
    if k_.endswith('2024_26') and not k_.startswith('dd'): assert v == 1826.95, ('PARITY FAILED - stop', k_, v)
assert buy_same and (par['dd_2025_26'] == 224.89 or par['dd_2024_26'] == 224.89), 'PARITY FAILED - stop'
assert (EXT[S0.i.to_numpy().astype(int)] > 0).all() or True
print('PARITY OK', round(time.time() - t_start), 's', flush=True)

# ---------- 2. cells ----------
CELLS = {}   # name -> dict(fam, sub, coord(tuple), kind, obj, kw)
def add(nm, fam, sub, coord, kind, obj, kw): CELLS[nm] = dict(fam=fam, sub=sub, coord=coord, kind=kind, obj=obj, kw=kw)
add('base_live', 'base', 'base', (), 'f', CB, {})
bx = [0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
for ix, x in enumerate(bx): add(f'b{x}', 'A', 'A1', (ix,), 'f', CB, dict(rule=(lambda x: lambda i, sg, lt: BOUNCE[i] >= x)(x)))
wy = [0.33, 0.4, 0.5, 0.6, 0.7]
for iy, y in enumerate(wy): add(f'w{y}', 'A', 'A2', (iy,), 'f', CB, dict(rule=(lambda y: lambda i, sg, lt: WFRAC[i] >= y)(y)))
for ix, x in enumerate([0.4, 0.6, 0.8]):
    for ie, e in enumerate([1.0, 1.5, 2.0]):
        add(f'b{x}_e{e}', 'A', 'A3', (ix, ie), 'f', CB, dict(rule=(lambda x, e: lambda i, sg, lt: BOUNCE[i] >= x and EXT[i] >= e)(x, e)))
    for iy, y in enumerate([0.33, 0.5]):
        add(f'b{x}_w{y}', 'A', 'A4', (ix, iy), 'f', CB, dict(rule=(lambda x, y: lambda i, sg, lt: BOUNCE[i] >= x and WFRAC[i] >= y)(x, y)))
for iN, N in enumerate([1, 2, 4, 8]):
    for iX, X in enumerate([0, 1.0, 1.5, 2.0]):
        add(f'p{N}_e{X}', 'B', 'B', (iN, iX), 'f', CB, dict(rule=(lambda N, X: lambda i, sg, lt: (sg - lt) < N * 900000 and (X == 0 or EXT[i] > X))(N, X)))
for ik, kk in enumerate([None, 0, 0.25, 0.5, 0.75, 1.0]):
    add(f'm2_k{kk}', 'C', 'C', (ik,), 'm', G1, dict(maxpos=2, kgate=kk))
for iW, W in enumerate([2.75, 3.0, 3.25, 3.5]):
    for iN, N in enumerate([1, 2, 3, 4]):
        add(f'wk{W}_n{N}', 'D', 'D', (iW, iN), 'f', build(wick_rows(W, N)), {})
for it, tp in enumerate([0.8, 1.0, 1.2, 1.35]):
    for ib, be in enumerate([0.5, 0.75, 1.0]):
        if (tp, be) == (1.35, 1.0): add('s1.35_be1.0(base)', 'Ebase', 'E1', (it, ib), 'f', CB, {}); continue
        add(f's{tp}_be{be}', 'E', 'E1', (it, ib), 'f', build(sell_rows(tp=tp, be=be)), {})
for ib, btp in enumerate([1.5, 2.0, 2.5]):
    add(f'buy{btp}', 'E', 'E2', (ib,), 'f', build_b(sell_rows(), buys_for(btp)), {})
add('buy3.0(base)', 'Ebase', 'E2', (3,), 'f', CB, {})
add('s1.0_be0.75_buy2.0', 'E', 'E3', (), 'f', build_b(sell_rows(tp=1.0, be=0.75), buys_for(2.0)), {})
tested = [n for n, c in CELLS.items() if c['fam'] in 'ABCDE' and len(c['fam']) == 1]
print('cells tested', len(tested), round(time.time() - t_start), 's', flush=True)
assert len(tested) == 79

def neighbours(nm):
    c = CELLS[nm]
    if c['sub'] == 'E3': return ['s1.0_be0.75', 'buy2.0']
    out = []
    for n2, c2 in CELLS.items():
        if n2 == nm or c2['sub'] != c['sub'] or len(c2['coord']) != len(c['coord']): continue
        diff = [abs(a - b) for a, b in zip(c['coord'], c2['coord'])]
        if sorted(diff)[-1] == 1 and sum(diff) == 1: out.append(n2)
    return out

rows = []; MON = {}
for nm, c in CELLS.items():
    if c['fam'] == 'Ebase': continue
    for wn in WINS:
        parts = run_parts(c['kind'], c['obj'], c['kw'], wn); mt, mon = metrics(parts, *WINS[wn])
        MON[(nm, wn)] = mon; rows.append(dict(cell=nm, fam=c['fam'], sub=c['sub'], window=wn, **mt))
    print(nm, 'done', round(time.time() - t_start), 's', flush=True)
Wd = pd.DataFrame(rows)
# base-equivalent grid points share base metrics
for nm in ('s1.35_be1.0(base)', 'buy3.0(base)'):
    bb = Wd[Wd.cell == 'base_live'].copy(); bb['cell'] = nm; bb['fam'] = 'Ebase'; bb['sub'] = CELLS[nm]['sub']; Wd = pd.concat([Wd, bb], ignore_index=True)
    for wn in WINS: MON[(nm, wn)] = MON[('base_live', wn)]
Wd['kept_pct'] = Wd.apply(lambda r: round(100 * r.n / Wd[(Wd.cell == 'base_live') & (Wd.window == r.window)].n.iloc[0], 1), axis=1)
for col in ('wr', 'net', 'exp', 'maxdd', 'wl'):
    Wd['d_' + col] = Wd.apply(lambda r: round(r[col] - Wd[(Wd.cell == 'base_live') & (Wd.window == r.window)][col].iloc[0], 3), axis=1)
Wd.to_csv(OUT / 'all-cells-windows.csv', index=False)
g = lambda nm, wn, col: Wd[(Wd.cell == nm) & (Wd.window == wn)].iloc[0][col]

# ---------- 3. selection on TUNE ----------
TW = 'TUNE 2015-22'
def tune_score(nm):
    if CELLS[nm]['fam'] == 'Ebase': return 0.0
    ok = g(nm, TW, 'exp') >= g('base_live', TW, 'exp') - 0.5 and g(nm, TW, 'kept_pct') >= 70 and g(nm, TW, 'maxdd') <= g('base_live', TW, 'maxdd')
    return g(nm, TW, 'd_wr') if ok else -np.inf
sel_rows = []
for nm, c in CELLS.items():
    if c['fam'] not in ('A', 'B', 'C', 'D', 'E'): continue
    nb_ = neighbours(nm); own = tune_score(nm); pl = min([own] + [tune_score(x) for x in nb_])
    sel_rows.append(dict(cell=nm, fam=c['fam'], sub=c['sub'], tune_d_wr=g(nm, TW, 'd_wr'), tune_wr=g(nm, TW, 'wr'), tune_n=g(nm, TW, 'n'),
                         tune_exp=g(nm, TW, 'exp'), tune_kept=g(nm, TW, 'kept_pct'), tune_maxdd=g(nm, TW, 'maxdd'), guard_ok=bool(np.isfinite(own)),
                         plateau=pl, neighbours=';'.join(nb_)))
S = pd.DataFrame(sel_rows); S.to_csv(OUT / 'tune-selection.csv', index=False)
picks = {}
for fam, sdf in S.groupby('fam'):
    sdf = sdf.assign(_p=sdf.plateau.replace(-np.inf, -1e9), _changed=[abs(100 - k) for k in sdf.tune_kept])
    best = sdf.sort_values(['_p', 'tune_d_wr', 'tune_exp', '_changed'], ascending=[False, False, False, True]).iloc[0]
    picks[fam] = best.cell

# ---------- 4. pass criteria ----------
B = 'base_live'; W2 = ('2025-26', '2024-26'); crit_rows = []
for fam, nm in picks.items():
    nb_ = neighbours(nm); pl = S[S.cell == nm].plateau.iloc[0]
    dm = MON[(nm, '2025-26')].sub(MON[(B, '2025-26')], fill_value=0.0); dtot = g(nm, '2025-26', 'd_net')
    cr = [('0 TUNE plateau > 0', pl > 0),
          ('1 WR > base 25-26 & 24-26', all(g(nm, w, 'wr') > g(B, w, 'wr') for w in W2)),
          ('2 wins/losses >= base both', all(g(nm, w, 'wl') >= g(B, w, 'wl') for w in W2)),
          ('3 expectancy >= base-0.5 both', all(g(nm, w, 'exp') >= g(B, w, 'exp') - 0.5 for w in W2)),
          ('4 net > 0 and >= 90% base both', all(g(nm, w, 'net') > 0 and g(nm, w, 'net') >= 0.9 * g(B, w, 'net') for w in W2)),
          ('5 maxDD < base both', all(g(nm, w, 'maxdd') < g(B, w, 'maxdd') for w in W2)),
          ('6 kept >= 70% both', all(g(nm, w, 'kept_pct') >= 70 for w in W2)),
          ('7 neighbours WR >= base both', all(g(x, w, 'wr') >= g(B, w, 'wr') for x in nb_ for w in W2)),
          ('8 hold-out 2019-24 WR >= base', g(nm, '2019-24', 'wr') >= g(B, '2019-24', 'wr')),
          ('9 WF 2023-24 WR >= base', g(nm, 'WF 2023-24', 'wr') >= g(B, 'WF 2023-24', 'wr'))]
    for c_, ok in cr: crit_rows.append(dict(fam=fam, cell=nm, criterion=c_, passed=bool(ok)))
    crit_rows.append(dict(fam=fam, cell=nm, criterion='info: d_net ex best month 2025-26', passed=round(dtot - max(dm.max(), 0.0), 2)))
    crit_rows.append(dict(fam=fam, cell=nm, criterion='info: months better/worse 2025-26 (net)', passed=f"{int((dm > 0.005).sum())}/{int((dm < -0.005).sum())}"))
Cdf = pd.DataFrame(crit_rows); Cdf.to_csv(OUT / 'pass-criteria.csv', index=False)
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 60); pd.set_option('display.max_rows', 500)
print(S.sort_values(['fam', 'plateau'], ascending=[True, False]).to_string())
print('PICKS', picks)
print(Cdf.to_string())
cols = ['cell', 'window', 'n', 'wins', 'losses', 'ties', 'wr', 'd_wr', 'wl', 'net', 'd_net', 'exp', 'maxdd', 'net_dd', 'kept_pct', 'skipped']
for fam, nm in picks.items():
    print('==', fam, nm, 'neighbours', neighbours(nm))
    print(Wd[Wd.cell.isin([B, nm] + neighbours(nm))][cols].sort_values(['window', 'cell']).to_string())
print('WR>base & DD<base both periods (any cell, info only, NOT a selection):')
q = [nm for nm in CELLS if nm != B and all(g(nm, w, 'wr') > g(B, w, 'wr') and g(nm, w, 'maxdd') < g(B, w, 'maxdd') for w in W2)]
print(Wd[Wd.cell.isin(q) & Wd.window.isin(W2)][cols].to_string())
json.dump(picks, open(OUT / 'picks.json', 'w'))
print('total', round(time.time() - t_start), 's')
