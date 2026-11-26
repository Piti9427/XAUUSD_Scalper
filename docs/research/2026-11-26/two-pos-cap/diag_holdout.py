"""Diagnostic add-on (not a cell, cap 10% only): rejections in the 2025-26H1 / 2026H2 hold-out windows (fresh $400 at window start)."""
from pm import *
OUT = Path(__file__).parent
CB = build(sell_rows()); G1 = make_groups(CB); rows = []
for nm, kw in (('base_live', dict()), ('m2_set', dict(maxpos=2)), ('m3_set', dict(maxpos=3))):
    for wn in ('2025-26H1 (OPT)', '2026H2 (HOLD)'):
        t, parts = window(G1, wn, **kw)
        rows.append(dict(variant=nm, window=wn, cands=agg(parts, 'cands'), trades=len(t), net=round(t.net.sum(), 2), rej_cap=agg(parts, 'rej_cap'),
                         rej_cap_second=agg(parts, 'rej_cap_second'), rej_daily_stop=agg(parts, 'rej_daily_stop'), max_conc_risk_pct=agg(parts, 'conc_risk_max')))
D = pd.DataFrame(rows); D.to_csv(OUT / 'diag-rejections-holdout.csv', index=False); print(D.to_string())
