"""v6: once-per-previous-trade evaluation for prev-based shadow rules (preregister.md v6 section). Box-only. Reuses shadow.py / shadow_s4b.py definitions."""
P = '/workspace/c22-trade-journal/research/tuning-failed-20261126/'
src = open(P + 'shadow.py').read().split('L = 0.242791954602979')[0].replace("__file__.replace('shadow.py', 'tune.py')", repr(P + 'tune.py'))
exec(src)
exec(open(P + 'shadow.py').read().split('L = 0.242791954602979')[1].split('CELLS = {}')[0].join(['L = 0.242791954602979', '']))  # rule factories
SIGSET = {d: set(SIG[d].tolist()) for d in (-1, 1)}
def f_blk_obs(K):
    def rule(r, p):
        last_close = (p['tx'] // 900000) * 900000
        return any((last_close - j * 900000) in SIGSET[p['d']] and (last_close - j * 900000) > p['ts'] for j in range(K))
    return rule

def portfolio_o(c, start, end, rule=None, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    """portfolio_s + prev-based rule evaluated once per previous trade (first candidate passing all gates after it closed)."""
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    bal = bal0; open_ = None; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000); last_tx = 0; skipped = []; checked = -1
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
        if rule is not None and prev is not None and checked != len(res):
            checked = len(res)
            if rule(r, prev):
                skipped.append(dict(sig=sg, pnl=r.pnl, why=r.why, d=r.d)); continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, why=r.why, i=int(r.i), sig=sg)
    if open_ is not None: res.append(open_)
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    t.attrs['skipped'] = skipped
    return t
def run_o(kw, wn):
    a, z = WINS[wn]; sg = [(a, z)] if wn == '2024-26' else segs(a, z)
    return [(portfolio_o(CB, s0, s1, **kw), (s0, s1)) for s0, s1 in sg]
assert round(portfolio_o(CB, *WIN['2025-26 all']).net.sum(), 2) == 1898.96 and round(portfolio_o(CB, A24, END).net.sum(), 2) == 1826.95, 'portfolio_o parity failed - stop'
print('portfolio_o parity OK', flush=True)
CELLS = {}
for im, M in enumerate([7.5, 15, 30, 60]): CELLS[f's2_m{M}_once'] = ('S2o', (im,), f_leg(M))
for iw, W in enumerate([60, 240, None]): CELLS[f"s4_w{W if W else 'inf'}_once"] = ('S4o', (iw,), f_blk(W))
CELLS['s4_same_once'] = ('S4io', (), f_blk(None, True))
for ik, K in enumerate([1, 2, 4]): CELLS[f's4b_k{K}_once'] = ('S4bo', (ik,), f_blk_obs(K))
CELLS['pair_leg_blk_once'] = ('P2o', (), (lambda a, b_: lambda r, p: a(r, p) and b_(r, p))(f_leg(15), f_blk_obs(1)))
assert len(CELLS) == 12
NB = {'s4_same_once': ['s4_winf_once'], 'pair_leg_blk_once': ['s2_m15_once', 's4b_k1_once']}
def neighbours(nm):
    if nm in NB: return NB[nm]
    s, c, _ = CELLS[nm]; return [n2 for n2, (s2, c2, _) in CELLS.items() if n2 != nm and s2 == s and sum(abs(a - b_) for a, b_ in zip(c, c2)) == 1]
rows = []; MON = {}
for nm, (sub, _, rule) in list(CELLS.items()) + [('base_live', ('base', (), None))]:
    for wn in WINS:
        parts = run_o(dict(rule=rule) if rule else {}, wn); mt, mon = metrics(parts, *WINS[wn]); MON[(nm, wn)] = mon
        sk = pd.DataFrame(sum((p.attrs['skipped'] for p, _ in parts), []))
        mt['skipped_win'] = int((sk.pnl > 0).sum()) if len(sk) else 0; mt['skipped_loss'] = int((sk.pnl < 0).sum()) if len(sk) else 0
        rows.append(dict(cell=nm, fam='S', sub=sub, window=wn, **mt))
Wd = pd.DataFrame(rows); bse = Wd[Wd.cell == 'base_live']
bget = lambda wn, col: bse[bse.window == wn][col].iloc[0]
Wd['kept_pct'] = [round(100 * r.n / bget(r.window, 'n'), 1) for r in Wd.itertuples()]
for col in ('wr', 'net', 'exp', 'maxdd', 'wl'): Wd['d_' + col] = [round(getattr(r, col) - bget(r.window, col), 3) for r in Wd.itertuples()]
S0_ = pd.read_csv(OUT / 'shadow-cells-windows.csv'); S0_ = S0_[~S0_.cell.str.endswith('_once')]
pd.concat([S0_, Wd[Wd.cell != 'base_live']], ignore_index=True).to_csv(OUT / 'shadow-cells-windows.csv', index=False)
g = lambda nm, wn, col: Wd[(Wd.cell == nm) & (Wd.window == wn)].iloc[0][col]
TW = 'TUNE 2015-22'; B = 'base_live'; W2 = ('2025-26', '2024-26')
def tscore(nm):
    ok = g(nm, TW, 'exp') >= g(B, TW, 'exp') - 0.5 and g(nm, TW, 'kept_pct') >= 70 and g(nm, TW, 'maxdd') <= g(B, TW, 'maxdd')
    return round(g(nm, TW, 'wr') - g(B, TW, 'wr'), 2) if ok else -np.inf
crit = []
for nm in ['s2_m15_once', 's4b_k1_once', 's4_winf_once', 'pair_leg_blk_once']:
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
    crit += [dict(cell=nm, criterion='info: TUNE plateau score', passed=pl), dict(cell=nm, criterion='info: neighbours', passed=';'.join(nb_)),
             dict(cell=nm, criterion='info: months better/worse 2025-26 (net)', passed=f"{int((dm > 0.005).sum())}/{int((dm < -0.005).sum())}")]
C0 = pd.read_csv(OUT / 'shadow-pass-criteria.csv'); C0 = C0[~C0.cell.str.endswith('_once')]
pd.concat([C0, pd.DataFrame(crit)], ignore_index=True).to_csv(OUT / 'shadow-pass-criteria.csv', index=False)
pd.set_option('display.width', 400); pd.set_option('display.max_rows', 300)
print(Wd[['cell', 'window', 'n', 'wins', 'losses', 'ties', 'wr', 'd_wr', 'wl', 'net', 'd_net', 'exp', 'maxdd', 'net_dd', 'kept_pct', 'skipped', 'skipped_win', 'skipped_loss']].sort_values(['window', 'cell']).to_string(index=False))
print(pd.DataFrame(crit).pivot_table(index='criterion', columns='cell', values='passed', aggfunc='first').to_string())
