"""v5 S4b: bot-observable blocked-signal flag (preregister.md v5 section). Box-only. Reuses shadow.py definitions (exec up to cell list)."""
src = open(__file__.replace('shadow_s4b.py', 'shadow.py')).read().split('L = 0.242791954602979')[0]
src = src.replace("__file__.replace('shadow.py', 'tune.py')", "'/workspace/c22-trade-journal/research/tuning-failed-20261126/tune.py'")
exec(src)
SIGSET = {d: set(SIG[d].tolist()) for d in (-1, 1)}
def f_blk_obs(K): 
    def rule(r, p):
        if p is None: return False
        last_close = (p['tx'] // 900000) * 900000
        return any((last_close - j * 900000) in SIGSET[p['d']] and (last_close - j * 900000) > p['ts'] for j in range(K))
    return rule
Ks = [1, 2, 4]; CELLS = {f's4b_k{K}': f_blk_obs(K) for K in Ks}
S = pd.read_csv(OUT / 'shadow-cells-windows.csv'); S = S[~S.cell.str.startswith('s4b_')]
rows = []; MON = {}
for nm, rule in list(CELLS.items()) + [('base_live', None)]:
    for wn in WINS:
        parts = run_s(dict(rule=rule) if rule else {}, wn); mt, mon = metrics(parts, *WINS[wn]); MON[(nm, wn)] = mon
        sk = pd.DataFrame(sum((p.attrs['skipped'] for p, _ in parts), []))
        mt['skipped_win'] = int((sk.pnl > 0).sum()) if len(sk) else 0; mt['skipped_loss'] = int((sk.pnl < 0).sum()) if len(sk) else 0
        rows.append(dict(cell=nm, fam='S', sub='S4b', window=wn, **mt))
N = pd.DataFrame(rows); bse = N[N.cell == 'base_live']; N = N[N.cell != 'base_live']
bget = lambda wn, col: bse[bse.window == wn][col].iloc[0]
N['kept_pct'] = [round(100 * r.n / bget(r.window, 'n'), 1) for r in N.itertuples()]
for col in ('wr', 'net', 'exp', 'maxdd', 'wl'): N['d_' + col] = [round(getattr(r, col) - bget(r.window, col), 3) for r in N.itertuples()]
pd.concat([S, N], ignore_index=True).to_csv(OUT / 'shadow-cells-windows.csv', index=False)
Wd = pd.concat([N, bse.assign(kept_pct=100.0)], ignore_index=True)
g = lambda nm, wn, col: Wd[(Wd.cell == nm) & (Wd.window == wn)].iloc[0][col]
TW = 'TUNE 2015-22'; B = 'base_live'; W2 = ('2025-26', '2024-26')
def tscore(nm):
    ok = g(nm, TW, 'exp') >= g(B, TW, 'exp') - 0.5 and g(nm, TW, 'kept_pct') >= 70 and g(nm, TW, 'maxdd') <= g(B, TW, 'maxdd')
    return round(g(nm, TW, 'wr') - g(B, TW, 'wr'), 2) if ok else -np.inf
nm = 's4b_k1'; nb_ = ['s4b_k2']; pl = min(tscore(nm), tscore('s4b_k2'))
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
C0 = pd.read_csv(OUT / 'shadow-pass-criteria.csv'); C0 = C0[C0.cell != nm]
add = [dict(cell=nm, criterion=c_, passed=bool(ok)) for c_, ok in cr] + [dict(cell=nm, criterion='info: TUNE plateau score', passed=pl),
       dict(cell=nm, criterion='info: neighbours', passed='s4b_k2'), dict(cell=nm, criterion='info: months better/worse 2025-26 (net)', passed=f"{int((dm > 0.005).sum())}/{int((dm < -0.005).sum())}")]
pd.concat([C0, pd.DataFrame(add)], ignore_index=True).to_csv(OUT / 'shadow-pass-criteria.csv', index=False)
pd.set_option('display.width', 400)
print(Wd[['cell', 'window', 'n', 'wins', 'losses', 'ties', 'wr', 'wl', 'net', 'exp', 'maxdd', 'net_dd', 'kept_pct', 'skipped', 'skipped_win', 'skipped_loss']].sort_values(['window', 'cell']).to_string(index=False))
print(pd.DataFrame(add).to_string())
