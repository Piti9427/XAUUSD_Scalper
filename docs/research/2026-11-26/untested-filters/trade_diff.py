"""Base vs cell trade-set diff (same harness/cells as bounce.py). Explains why skipped-trade P/L and net delta differ."""
import sys; sys.argv=['x']
exec(open(__import__('pathlib').Path(__file__).parent / 'bounce.py').read().split('# ---------- 2. evaluate')[0])
rows = []
for wn, (a, z) in (('2025-26 all', WIN['2025-26 all']), ('2024-26 all', (A24, END))):
    f = (lambda kw: portfolio_x(CB, a, z, **kw)) if wn == '2024-26 all' else (lambda kw: run_x(CB, a, z, **kw)[0])
    tb = f({}); kb = set(tb.k)
    for nm, kw in CELLS.items():
        if nm == BN: continue
        t = f(kw); kc = set(t.k)
        rem = tb[tb.k.isin(kb - kc)]; add = t[t.k.isin(kc - kb)]
        rows.append(dict(variant=nm, window=wn, base_trades_removed=len(rem), removed_win=int((rem.net > 0).sum()), removed_loss=int((rem.net <= 0).sum()), removed_net=round(rem.net.sum(), 2),
                         new_trades_added=len(add), added_win=int((add.net > 0).sum()), added_loss=int((add.net <= 0).sum()), added_net=round(add.net.sum(), 2),
                         net_delta=round(t.net.sum() - tb.net.sum(), 2)))
D = pd.DataFrame(rows); D.to_csv(OUT / 'bounce-trade-diff.csv', index=False); print(D.to_string())
