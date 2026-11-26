"""Info only (post-hoc, not used for selection): SELL vs BUY win rate split for base and a few cells. Reuses tune.py definitions (exec up to cells)."""
src = open(__file__.replace('sides.py', 'tune.py')).read().split('# ---------- 2. cells ----------')[0]
exec(src)
cells = {'base_live': CB, 'b0.4_e2.0': (CB, dict(rule=lambda i, sg, lt: BOUNCE[i] >= 0.4 and EXT[i] >= 2.0)),
         'buy1.5': build_b(sell_rows(), buys_for(1.5)), 'buy2.0': build_b(sell_rows(), buys_for(2.0)),
         's0.8_be0.75': build(sell_rows(tp=0.8, be=0.75)), 's1.0_be1.0': build(sell_rows(tp=1.0, be=1.0)), 's1.2_be1.0': build(sell_rows(tp=1.2, be=1.0))}
rows = []
for nm, v in cells.items():
    c, kw = v if isinstance(v, tuple) else (v, {})
    for wn in ('2025-26', '2024-26', 'WF 2023-24', '2019-24'):
        parts = run_parts('f', c, kw, wn); t = pd.concat([p for p, _ in parts if len(p)])
        for side, d in (('SELL', -1), ('BUY', 1)):
            s = t[t.d == d]; rows.append(dict(cell=nm, window=wn, side=side, n=len(s), wins=int((s.net > 0).sum()), losses=int((s.net < 0).sum()),
                                             ties=int((s.net == 0).sum()), wr=round(100 * (s.net > 0).mean(), 2), net=round(s.net.sum(), 2)))
D = pd.DataFrame(rows); D.to_csv(OUT / 'info-side-split.csv', index=False)
pd.set_option('display.width', 300); pd.set_option('display.max_rows', 300); print(D.to_string(index=False))
