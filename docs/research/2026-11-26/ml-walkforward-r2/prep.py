"""R2 candidates + features + labels (preregister.md). Box-only. R1 features copied verbatim from ../ml-walkforward-r1-20261126/prep.py."""
import sys, hashlib; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
import numba as nb
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
# ---- D1 (UTC days), shifted so day t only sees completed days <= t-1
d1 = b.resample('1D').agg({'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
pc = d1.close.shift(1)
tr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1)
datr = tr.rolling(14).mean()
D1 = pd.DataFrame(index=d1.index)
D1['atr'] = datr.shift(1); D1['pclose'] = d1.close.shift(1)
D1['atr_pctile'] = datr.rolling(252, min_periods=60).rank(pct=True).shift(1)
D1['hi20'] = d1.high.rolling(20).max().shift(1); D1['lo20'] = d1.low.rolling(20).min().shift(1)
e20 = d1.close.ewm(span=20, adjust=False, min_periods=20).mean(); e50 = d1.close.ewm(span=50, adjust=False, min_periods=50).mean()
D1['e20'] = e20.shift(1); D1['e20_5'] = e20.shift(6); D1['e50'] = e50.shift(1); D1['e50_5'] = e50.shift(6)
bday = b.index.floor('1D')
D1b = D1.reindex(bday)  # row per M15 bar (signal day)
@nb.njit(cache=False)
def hit1r(d, j, t1, H, L, sp, entry, R, horizon_ms):
    n = len(t1); t_end = t1[j] + horizon_ms
    for k in range(j, n):
        if t1[k] > t_end: return 0
        if d == 1:
            if L[k] <= entry - R: return 0
            if H[k] >= entry + R: return 1
        else:
            if H[k] + sp >= entry + R: return 0
            if L[k] + sp <= entry - R: return 1
    return 0
def features(c):
    c = c.sort_values(['ts', 'd']).reset_index(drop=True)
    i = c.i.to_numpy(); d = c.d.to_numpy().astype(float); a = A[i]; cl = close[i]
    X = pd.DataFrame(index=c.index)
    X['side'] = d; X['atr_pct_price'] = a / cl * 100; rg = hi15[i] - lo15[i]
    X['bar_range_atr'] = rg / a
    X['ext_atr'] = np.where(d < 0, (LL48[i] - cl) / a, 0.0)
    X['rsi7'] = RSI[i]; X['rsi7_slope'] = RSI[i] - RSI1[i]
    X['ema50_dist_atr'] = d * (cl - E50[i]) / a; X['h4dist'] = c.h4dist.to_numpy(); X['h4slope'] = c.h4slope.to_numpy()
    hu = pd.to_datetime(c.sig, unit='ms', utc=True).dt.hour.to_numpy()
    X['hour_sin'] = np.sin(2 * np.pi * hu / 24); X['hour_cos'] = np.cos(2 * np.pi * hu / 24)
    X['vol_ratio'] = a / AM96[i]; X['ret20_atr'] = d * (cl - C20[i]) / a
    sw = np.array([nights(s, x) * (-0.4743 if dd == 1 else 0.0) for s, x, dd in zip(c.ts, c.tx, c.d)])
    c['sw'] = sw; c['net_est'] = c.pnl + sw
    sg = c.sig.to_numpy(); tx = c.tx.to_numpy(); why = c.why.to_numpy(); lossx = c.net_est.to_numpy() < 0
    CAP = 10080.0
    def since(mask):
        ex = np.sort(tx[mask]); k = np.searchsorted(ex, sg, side='right') - 1
        v = np.where(k >= 0, (sg - ex[np.clip(k, 0, None)]) / 60000.0, CAP); return np.log1p(np.minimum(v, CAP)), np.minimum(v, CAP)
    X['log_min_since_tp'] = since(why == 2)[0]; X['log_min_since_sl'], c['min_since_loss_stream'] = since(lossx)
    # D1 regime
    r = D1b.iloc[i]; da = r.atr.to_numpy()
    X['d1_atr_pct_price'] = da / r.pclose.to_numpy() * 100; X['d1_atr_pctile252'] = r.atr_pctile.to_numpy()
    X['dist_hi20_d1atr'] = (r.hi20.to_numpy() - cl) / da; X['dist_lo20_d1atr'] = (cl - r.lo20.to_numpy()) / da
    X['d1_ema20_slope'] = d * (r.e20.to_numpy() - r.e20_5.to_numpy()) / da; X['d1_ema50_slope'] = d * (r.e50.to_numpy() - r.e50_5.to_numpy()) / da
    X['d1_ema20_dist'] = d * (cl - r.e20.to_numpy()) / da
    for nm, (h0, h1) in dict(asia=(0, 7), london=(7, 12), overlap=(12, 16), ny=(16, 21), late=(21, 24)).items():
        X[f'sess_{nm}'] = ((hu >= h0) & (hu < h1)).astype(int)
    # labels
    c['R_mult'] = c.net_est / (c.R + SLIP)
    j = np.searchsorted(t1, c.ts.to_numpy())
    c['y1r'] = [hit1r(int(dd), int(jj), t1, H, L, SP, float(e), float(rr), 10 * 86400000) for dd, jj, e, rr in zip(c.d, j, c.entry, c.R)]
    c['bar_range_atr'] = X['bar_range_atr'].to_numpy()
    c['year'] = pd.to_datetime(c.ts, unit='ms', utc=True).dt.tz_convert(ICT).dt.year.to_numpy()
    return c, X
store = {}
for btp in (3.0, 2.0):
    c = pd.concat([buys_for(btp), SR]).sort_values(['ts', 'd']).reset_index(drop=True)
    c = c[~(c.h4dist < 10)]
    c, X = features(c); store[btp] = (c, X)
    print('btp', btp, len(c), c.d.value_counts().to_dict(), 'NaN per feat', {k: int(v) for k, v in X.isna().sum().items() if v}, flush=True)
    print('  y1r rate BUY/SELL', round(c[c.d == 1].y1r.mean(), 3), round(c[c.d == -1].y1r.mean(), 3), 'ties labelled 1:', int(((c.net_est == 0) & (c.y1r == 1)).sum()), '/', int((c.net_est == 0).sum()))
pd.to_pickle(dict(store=store, END=END, BAL0=BAL0, SLIP=SLIP), OUT / 'cands_features.pkl')
print('saved')
