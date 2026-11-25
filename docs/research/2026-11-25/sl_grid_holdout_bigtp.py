"""Hold-out check (same 4 windows as sl_grid.py) for the big-TP variants added in t199u."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry_sl import *
OUT = Path(__file__).parent
V = {'sl2.5_tp1.35R': (2.5, 1.35)}
for sl in (2.5, 3.0, 3.25, 3.5):
    for tp in (2.5, 3.0): V[f'sl{sl}_tp{tp}R'] = (sl, tp)
rows = []
for nm, (sl, tp) in V.items():
    c = build(sell_rows(sl=sl, tp=tp))
    for wn in ('2015-18', '2019-24', '2025-26H1 (OPT)', '2026H2 (HOLD)'):
        a, z = WIN[wn]; t, parts = run(c, a, z); rows.append(dict(variant=nm, window=wn, net=round(t.net.sum(), 2)))
D = pd.DataFrame(rows).pivot(index='variant', columns='window', values='net')
b = D.loc['sl2.5_tp1.35R']; D['beats'] = (D[b.index] > b).sum(axis=1); D['holdout'] = np.where(D.beats == 4, 'PASS', 'FAIL')
D.to_csv(OUT / 'slgrid2024-bigtp-holdout.csv'); print(D.to_string())
