"""Build candidate sets (live BUY TP 3.0 / 2.0 / 2.5, F2 applied) + causal features. Box-only. See preregister.md."""
import sys, hashlib; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
OUT = Path(__file__).parent
assert hashlib.sha256((OUT / 'preregister.md').read_bytes()).hexdigest() == (OUT / 'preregister.sha256').read_text().split()[0], 'preregister changed - stop'
def nights(ts, tx):
    r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
    for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
    return n
SR = sell_rows()
def buys_for(btp):
    if btp == 3.0: return BUYS
    g = gen(btp=btp); bb = g[g.d == 1].copy(); bb['sig'] = dec[bb.i.to_numpy()]; bb['rr_plan'] = btp; bb['sl_atr'] = 2.5; return bb
rsi, _ = sig.rsi7(b); RSI = rsi.to_numpy(); RSI1 = rsi.shift(1).to_numpy()
E50 = sig.ema(b, 50).to_numpy(); AM96 = ATR.rolling(96).mean().to_numpy()
C5 = b.close.shift(5).to_numpy(); C20 = b.close.shift(20).to_numpy()
def features(c):
    c = c.sort_values(['ts', 'd']).reset_index(drop=True)
    i = c.i.to_numpy(); d = c.d.to_numpy().astype(float); a = A[i]; cl = close[i]
    X = pd.DataFrame(index=c.index)
    X['side'] = d; X['atr_pct_price'] = a / cl * 100; rg = hi15[i] - lo15[i]
    X['bar_range_atr'] = rg / a; X['bounce_atr'] = (cl - lo15[i]) / a
    X['wfrac'] = np.where(rg > 0, (cl - lo15[i]) / np.where(rg > 0, rg, 1), 0.0)
    X['ext_atr'] = np.where(d < 0, (LL48[i] - cl) / a, 0.0)
    X['rsi7'] = RSI[i]; X['rsi7_slope'] = RSI[i] - RSI1[i]
    X['ema50_dist_atr'] = d * (cl - E50[i]) / a; X['h4dist'] = c.h4dist.to_numpy(); X['h4slope'] = c.h4slope.to_numpy()
    hu = pd.to_datetime(c.sig, unit='ms', utc=True).dt.hour.to_numpy()
    X['hour_sin'] = np.sin(2 * np.pi * hu / 24); X['hour_cos'] = np.cos(2 * np.pi * hu / 24); X['dow'] = c.wd_ict.to_numpy()
    X['vol_ratio'] = a / AM96[i]; X['ret5_atr'] = d * (cl - C5[i]) / a; X['ret20_atr'] = d * (cl - C20[i]) / a
    sw = np.array([nights(s, x) * (-0.4743 if dd == 1 else 0.0) for s, x, dd in zip(c.ts, c.tx, c.d)])
    c['sw'] = sw; c['net_est'] = c.pnl + sw; c['y'] = (c.net_est > 0).astype(int)
    sg = c.sig.to_numpy(); tx = c.tx.to_numpy(); ts = c.ts.to_numpy(); why = c.why.to_numpy(); lossx = c.net_est.to_numpy() < 0
    CAP = 10080.0
    def since(mask):
        ex = np.sort(tx[mask]); k = np.searchsorted(ex, sg, side='right') - 1
        v = np.where(k >= 0, (sg - ex[np.clip(k, 0, None)]) / 60000.0, CAP); return np.log1p(np.minimum(v, CAP))
    X['log_min_since_exit'] = since(np.ones(len(c), bool)); X['log_min_since_tp'] = since(why == 2); X['log_min_since_sl'] = since(lossx)
    # signal fired while an earlier candidate was open
    open_at = np.zeros(len(c), bool)
    for k in range(len(c)):
        m = (ts[:k] <= sg[k]) & (tx[:k] > sg[k]); open_at[k] = m.any()
    H8 = 8 * 3600000; same = np.zeros(len(c), int); pb = np.zeros(len(c), int)
    for k in range(len(c)):
        m = (np.arange(len(c)) != k) & (d == d[k]) & (sg < sg[k]) & (sg > sg[k] - H8)
        same[k] = int(m.any()); pb[k] = int((m & open_at).any())
    X['same_leg'] = same; X['prior_blocked'] = pb
    c['year'] = pd.to_datetime(c.ts, unit='ms', utc=True).dt.tz_convert(ICT).dt.year.to_numpy()
    return c, X
store = {}
for btp in (3.0, 2.0, 2.5):
    c = pd.concat([buys_for(btp), SR]).sort_values(['ts', 'd']).reset_index(drop=True)
    c = c[~(c.h4dist < 10)]
    c, X = features(c); store[btp] = (c, X); print('btp', btp, len(c), c.d.value_counts().to_dict(), 'NaN feats', int(X.isna().sum().sum()), flush=True)
pd.to_pickle(dict(store=store, END=END, BAL0=BAL0, SLIP=SLIP), OUT / 'cands_features.pkl')
print('saved')
