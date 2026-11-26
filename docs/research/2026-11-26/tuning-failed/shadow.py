"""Family S shadow_conditions (preregister.md v4 section, t217u). Box-only. Reuses tune.py harness definitions (exec up to cells; includes sha256 + parity asserts).
Definitions mirror tools/loss_review.py flags; skip rules checked after all existing gates (same structure as portfolio_f)."""
src = open(__file__.replace('shadow.py', 'tune.py')).read().split('# ---------- 2. cells ----------')[0]
exec(src)
HH48 = b.high.rolling(48).max().shift(1).to_numpy()
EXT_SIDE = lambda i, d: (LL48[i] - close[i]) / A[i] if d == -1 else (close[i] - HH48[i]) / A[i]
SIG = {d: np.sort(CB[CB.d == d].sig.to_numpy().astype(np.int64)) for d in (-1, 1)}
def blocked(prev):
    s = SIG[prev['d']]; lo = np.searchsorted(s, prev['ts'], 'right'); hi = np.searchsorted(s, prev['tx'], 'left')
    return hi > lo

def portfolio_s(c, start, end, rule=None, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    bal = bal0; open_ = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0; skipped = []
    for k, r in zip(c.index, c.itertuples()):
        if open_ is not None and open_['tx'] <= r.ts:
            p = open_; open_ = None; bal += p['net']; last_tx = p['tx']
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
        prev = res[-1] if res else None
        if rule is not None and rule(r, prev):
            skipped.append(dict(sig=sg, pnl=r.pnl, why=r.why, d=r.d)); continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, why=r.why, i=int(r.i), sig=sg)
    if open_ is not None: res.append(open_)
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs['skipped'] = skipped
    return t

def run_s(kw, wn):
    a, z = WINS[wn]; sg = [(a, z)] if wn == '2024-26' else segs(a, z)
    return [(portfolio_s(CB, s0, s1, **kw), (s0, s1)) for s0, s1 in sg]
# parity of portfolio_s with no rule
ps25 = portfolio_s(CB, *WIN['2025-26 all']).net.sum(); ps24 = portfolio_s(CB, A24, END).net.sum()
assert round(ps25, 2) == 1898.96 and round(ps24, 2) == 1826.95, ('portfolio_s parity failed - stop', ps25, ps24)
print('portfolio_s parity OK', round(ps25, 2), round(ps24, 2), flush=True)

L = 0.242791954602979
def f_ext(X, sell_only=False): return lambda r, p: (r.d == -1 or not sell_only) and EXT_SIDE(int(r.i), r.d) > X
def f_leg(M): return lambda r, p: p is not None and p['d'] == r.d and 0 <= (r.ts - p['tx']) <= M * 60000 and (int(r.i) - p['i']) <= 48
def f_atr(th): return lambda r, p: (r.atr / r.entry * 100) >= th
def f_blk(W=None, same=False): return lambda r, p: p is not None and blocked(p) and (W is None or (r.ts - p['tx']) <= W * 60000) and (not same or p['d'] == r.d)
CELLS = {}
def add(nm, sub, coord, rule): CELLS[nm] = dict(sub=sub, coord=coord, rule=rule)
for ix, X in enumerate([1.25, 1.5, 1.75]):
    add(f's1_all_x{X}', 'S1a', (ix,), f_ext(X)); add(f's1_sell_x{X}', 'S1b', (ix,), f_ext(X, True))
for im, M in enumerate([7.5, 15, 30, 60]): add(f's2_m{M}', 'S2', (im,), f_leg(M))
TH = [('p60', 0.1142894374340652), ('p67', 0.1239098618887887), ('p75', 0.14259489308313106), ('0.85L', 0.85 * L), ('L', L), ('1.15L', 1.15 * L)]
for it, (nm_, th) in enumerate(TH): add(f's3_{nm_}', 'S3', (it,), f_atr(th))
for iw, W in enumerate([60, 240, None]): add(f"s4_w{W if W else 'inf'}", 'S4', (iw,), f_blk(W))
add('s4_same', 'S4i', (), f_blk(None, True))
add('pair_ext_atr', 'P1', (), (lambda a, b_: lambda r, p: a(r, p) and b_(r, p))(f_ext(1.5), f_atr(L)))
add('pair_leg_blk', 'P2', (), (lambda a, b_: lambda r, p: a(r, p) and b_(r, p))(f_leg(15), f_blk(None)))
assert len(CELLS) == 22
NB = {'s4_same': ['s4_winf'], 'pair_ext_atr': ['s1_all_x1.5', 's3_L'], 'pair_leg_blk': ['s2_m15', 's4_winf']}
def neighbours(nm):
    if nm in NB: return NB[nm]
    c = CELLS[nm]; return [n2 for n2, c2 in CELLS.items() if n2 != nm and c2['sub'] == c['sub'] and sum(abs(a - b_) for a, b_ in zip(c['coord'], c2['coord'])) == 1]
PRIMARY = ['s1_all_x1.5', 's2_m15', 's3_L', 's4_winf', 'pair_ext_atr', 'pair_leg_blk']

base = pd.read_csv(OUT / 'all-cells-windows.csv'); base = base[base.cell == 'base_live']
rows = []; MON = {}
for nm, c in CELLS.items():
    for wn in WINS:
        parts = run_s(dict(rule=c['rule']), wn); mt, mon = metrics(parts, *WINS[wn]); MON[(nm, wn)] = mon
        sk = pd.DataFrame(sum((p.attrs['skipped'] for p, _ in parts), []))
        mt['skipped_win'] = int((sk.pnl > 0).sum()) if len(sk) else 0; mt['skipped_loss'] = int((sk.pnl < 0).sum()) if len(sk) else 0
        rows.append(dict(cell=nm, fam='S', sub=c['sub'], window=wn, **mt))
    print(nm, 'done', flush=True)
# base row recomputed with portfolio_s for monthly
for wn in WINS:
    parts = run_s({}, wn); mt, mon = metrics(parts, *WINS[wn]); MON[('base_live', wn)] = mon
    b_ = base[base.window == wn].iloc[0]; assert mt['n'] == b_.n and abs(mt['net'] - b_.net) < 0.006 and abs(mt['maxdd'] - b_.maxdd) < 0.006, ('base mismatch', wn)
    rows.append(dict(cell='base_live', fam='base', sub='base', window=wn, skipped_win=0, skipped_loss=0, **mt))
Wd = pd.DataFrame(rows)
bget = lambda wn, col: Wd[(Wd.cell == 'base_live') & (Wd.window == wn)][col].iloc[0]
Wd['kept_pct'] = [round(100 * r.n / bget(r.window, 'n'), 1) for r in Wd.itertuples()]
for col in ('wr', 'net', 'exp', 'maxdd', 'wl'): Wd['d_' + col] = [round(getattr(r, col) - bget(r.window, col), 3) for r in Wd.itertuples()]
Wd.to_csv(OUT / 'shadow-cells-windows.csv', index=False)
g = lambda nm, wn, col: Wd[(Wd.cell == nm) & (Wd.window == wn)].iloc[0][col]
TW = 'TUNE 2015-22'; B = 'base_live'; W2 = ('2025-26', '2024-26')
def tscore(nm):
    ok = g(nm, TW, 'exp') >= g(B, TW, 'exp') - 0.5 and g(nm, TW, 'kept_pct') >= 70 and g(nm, TW, 'maxdd') <= g(B, TW, 'maxdd')
    return g(nm, TW, 'd_wr') if ok else -np.inf
crit = []
for nm in PRIMARY:
    nb_ = neighbours(nm); pl = min([tscore(nm)] + [tscore(x) for x in nb_])
    dm = MON[(nm, '2025-26')].sub(MON[(B, '2025-26')], fill_value=0.0)
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
    for c_, ok in cr: crit.append(dict(cell=nm, criterion=c_, passed=bool(ok)))
    crit.append(dict(cell=nm, criterion='info: TUNE plateau score', passed=pl))
    crit.append(dict(cell=nm, criterion='info: neighbours', passed=';'.join(nb_)))
    crit.append(dict(cell=nm, criterion='info: months better/worse 2025-26 (net)', passed=f"{int((dm > 0.005).sum())}/{int((dm < -0.005).sum())}"))
Cd = pd.DataFrame(crit); Cd.to_csv(OUT / 'shadow-pass-criteria.csv', index=False)
pd.set_option('display.width', 400); pd.set_option('display.max_rows', 500); pd.set_option('display.max_columns', 40)
cols = ['cell', 'window', 'n', 'wins', 'losses', 'ties', 'wr', 'd_wr', 'wl', 'net', 'd_net', 'exp', 'maxdd', 'net_dd', 'kept_pct', 'skipped', 'skipped_win', 'skipped_loss']
print(Wd[cols].sort_values(['window', 'cell']).to_string(index=False)); print(Cd.to_string())
