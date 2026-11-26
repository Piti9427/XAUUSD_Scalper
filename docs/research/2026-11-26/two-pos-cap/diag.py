"""Step 1 diagnostic (not a cell): signals rejected by the 10% combined cap and by the daily stop. Cap 10% only."""
from pm import *
OUT = Path(__file__).parent
CB = build(sell_rows()); G1 = make_groups(CB)
rows = []; rj = []
for nm, kw in (('base_live', dict()), ('m2_set', dict(maxpos=2)), ('m3_set', dict(maxpos=3))):
    per = {}
    for wn in ('2015-18', '2019-24', '2025-26 all', '2024-26 all'):
        t, parts = window(G1, wn, **kw)
        per[wn] = (t, parts)
        r = dict(variant=nm, window=wn, cands=agg(parts, 'cands'), trades=len(t), net=round(t.net.sum(), 2), max_conc_risk_pct=agg(parts, 'conc_risk_max'))
        for k in ['rej_' + x for x in REASONS] + ['rej_cap_second', 'rej_cap_first', 'rej_ds_second', 'rej_ds_first']: r[k] = agg(parts, k)
        rows.append(r)
        for p, _ in parts:
            for x in p.attrs['rejections']: rj.append(dict(variant=nm, window=wn, **x))
    # 2015-26 = 2015-18 + 2019-24 + 2025-26 all (yearly $400 reset to 2024, continuous from 2025; same as harness hold-outs)
    s = [r for r in rows if r['variant'] == nm and r['window'] in ('2015-18', '2019-24', '2025-26 all')]
    tot = dict(variant=nm, window='2015-26 (sum)')
    for k in s[0]:
        if k in ('variant', 'window'): continue
        tot[k] = max(x[k] for x in s) if k == 'max_conc_risk_pct' else round(sum(x[k] for x in s), 2)
    rows.append(tot)
D = pd.DataFrame(rows); D.to_csv(OUT / 'diag-rejections.csv', index=False)
R = pd.DataFrame(rj)
if len(R): R['ts_ict'] = pd.to_datetime(R.ts, unit='ms', utc=True).dt.tz_convert(ICT)
R.to_csv(OUT / 'diag-rejected-signals.csv', index=False)
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 40)
print(D.to_string()); print(R.to_string() if len(R) else 'no cap/daily-stop rejections')
