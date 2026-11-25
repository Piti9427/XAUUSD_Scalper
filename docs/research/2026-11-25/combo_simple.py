"""t202u add-on: 1-parameter ATR-skip combos (all else live) evaluated the same way as the top 5."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    from combo_eval import *
extra = [dict(LIVE, atr=a) for a in (0.75, 0.667, 0.6)]
for c in extra: SS.setdefault((c['sl'], c['stp'], c['spike']), sell_set(c['sl'], c['stp'], c['spike']))
rows2 = []
for c in extra:
    x = cand_frame(c, SS, BS); t = portfolio2(x, a24, z24); _, _, tall = run_all(x); m = monthly(t, a24, z24); MON[cname(c)] = m
    eq = BAL0 + t.net.cumsum(); k = NAMES.index(cname(c))
    rows2.append(dict(name=cname(c), tpm=round(len(t) / len(m), 2), win=round(100 * (t.net > 0).mean(), 1), net=round(t.net.sum(), 2), maxdd=round(float((eq.cummax() - eq).max()), 2),
        green=round(100 * (m > 0).mean(), 1), neg=int((m < 0).sum()), worst=round(m.min(), 2), P_net24=boot(daily(t, idx24), b24), P_net15_26=boot(daily(tall, idxall), ball),
        wf_pass=round(PASS[k], 1), k_params=int(NP[k]), nb_median_selJ=round(float(np.median(MS['J'][NB[k]])), 2), sel_J=round(MS['J'][k], 2), sel_G=round(MS['G'][k], 1), sel_neg=int(MS['Nn'][k]),
        val_net=round(MV['net'][k], 2), val_G=round(MV['G'][k], 1), val_neg=int(MV['Nn'][k]), hold_G=round(MH['G'][k], 1), hold_net=round(MH['net'][k], 2)))
X = pd.DataFrame(rows2); X.to_csv(OUT / 'combo-atr-only.csv', index=False); print(X.to_string())
pd.DataFrame(MON).round(2).rename(index=str).to_csv(OUT / 'combo-monthly-2024-26.csv')
print('live sel', round(MS['G'][LIVEK],1), int(MS['Nn'][LIVEK]), 'val', round(MV['G'][LIVEK],1), int(MV['Nn'][LIVEK]))
