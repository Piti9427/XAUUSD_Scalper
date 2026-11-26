"""Feature-only (no outcomes): ATR%price thresholds for the shadow_conditions family. Verifies the locked live value and computes
60/67/75th percentiles over base-portfolio fills (both sides) in TUNE 2015-03-02..2023-01-01 (yearly reset)."""
src = open(__file__.replace('atr_thresholds.py', 'tune.py')).read().split('# ---------- 2. cells ----------')[0]
exec(src)
def fills(a, z):
    t = pd.concat([p for p, _ in run_parts('f', CB, {}, a) if len(p)]) if isinstance(a, str) else None
    return t
tb = pd.concat([p for p, _ in run_parts('f', CB, {}, 'TUNE 2015-22') if len(p)])
x = CB.loc[tb.k]; ap = (x.atr / x.entry * 100).to_numpy()
t25 = portfolio_f(CB, *WIN['2025-26 all']); x25 = CB.loc[t25.k]; s25 = x25[x25.d == -1]
locked = np.quantile((s25.atr / s25.entry * 100).to_numpy(), 2 / 3)
out = dict(locked_recomputed=locked, locked_live=0.242791954602979, n_sell_2025_26=len(s25), tune_n=len(ap),
           tune_p60=np.quantile(ap, 0.60), tune_p67=np.quantile(ap, 2 / 3), tune_p75=np.quantile(ap, 0.75))
print(out); pd.DataFrame([out]).to_csv(OUT / 'shadow-atr-thresholds.csv', index=False)
