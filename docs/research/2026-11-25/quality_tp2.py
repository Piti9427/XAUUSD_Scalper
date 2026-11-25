"""t200u follow-up: best quality filter (selection rank #1) and runner-up, with TP 2.0R; monthly tables."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from quality import *
BEST = ['SB:atr_pct[0.0,0.67]', 'B:rng48<=p50', 'B:no_london_07-13utc']
ALT = ['SB:atr_pct[0.0,0.67]', 'SB:h1+h4_aligned', 'B:h4slope200>0']
g2 = gen(btp=2.0); B2 = g2[g2.d == 1].copy(); B2['sig'] = dec[B2.i.to_numpy()]; B2['rr_plan'] = 2.0; B2['sl_atr'] = 2.5
S2 = sell_rows(tp=2.0)
def mkbase(sell, buy):
    c = pd.concat([buy, sell]).sort_values(['ts', 'd']).reset_index(drop=True); c = c[~(c.h4dist < 10)]
    return feats(c)
BB = {'S1.35/B3': BASEC, 'S2.0/B3': mkbase(S2, BUYS), 'S2.0/B2.0': mkbase(S2, B2)}
rows = []; TRT = {}
for tpn, base in BB.items():
    for fn, names in (('BASE', []), ('BEST', BEST), ('ALT', ALT)):
        c = apply(names, base) if names else base
        for wn in WV:
            r, t = evalc(c, wn); TRT[(tpn, fn, wn)] = t; rows.append(dict(tp=tpn, filt=fn, window=wn, **r))
D = pd.DataFrame(rows); D.to_csv(OUT / 'quality-tp2.csv', index=False)
pd.set_option('display.width', 300)
for wn in ('SEL 2015-24', '2025-26 all', '2025-26H1', '2026H2 HOLD', '2024-26 all'):
    print(wn); print(D[D.window == wn][['tp', 'filt', 'n', 'tpm', 'win', 'net', 'maxdd', 'green', 'neg', 'zero', 'worst']].to_string(index=False))
# monthly 2024-26 (continuous)
a, z = WV['2024-26 all']
M = pd.DataFrame({f'{tpn}|{fn}': monthly(TRT[(tpn, fn, '2024-26 all')], a, z) for tpn in BB for fn in ('BASE', 'BEST', 'ALT')})
cnt = pd.DataFrame({f'n {fn}': monthly(TRT[('S1.35/B3', fn, '2024-26 all')].assign(net=1.0), a, z) for fn in ('BASE', 'BEST', 'ALT')})
M = pd.concat([M, cnt], axis=1); M.index = M.index.astype(str); M.round(2).to_csv(OUT / 'quality-monthly-2024-26.csv'); print(M.round(2).to_string())
for fn in ('BEST', 'ALT'):
    d = M[f'S1.35/B3|{fn}'] - M['S1.35/B3|BASE']; print(fn, 'better', int((d > 0.005).sum()), 'worse', int((d < -0.005).sum()))
