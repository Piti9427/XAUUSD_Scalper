"""Trade-by-trade case study on Exness XAUUSDm M15 bars (box copy _raw/bars_m15.csv) for live bot SELLs 16-25 Nov 2026.
M15 resolution: a sell limit fills when bar high >= limit; after fill, SL is checked before TP in every bar (also the fill bar);
BE at 1R on M15 close. Spread 0.24, slip 0.10 like the backtest. F3/cooldown/cap are NOT applied here (single-trade view);
the g2 re-entry is shown as if allowed (the strictF3 version can never fire right after a loss)."""
import json; from pathlib import Path
import numpy as np, pandas as pd
OUT = Path(__file__).parent; SP, SLIP = 0.24, 0.10
b = pd.read_csv(OUT.parents[1] / '_raw/bars_m15.csv', parse_dates=['bar_open_utc']).set_index('bar_open_utc')
p = b.close.shift(); tr = pd.concat([b.high - b.low, (b.high - p).abs(), (b.low - p).abs()], axis=1).max(axis=1)
b['atr'] = tr.rolling(14).mean(); b['ll48'] = b.low.rolling(48).min().shift(1); b['ema20'] = b.close.ewm(span=20, adjust=False).mean()
ICT = 'Asia/Bangkok'; LAST = b.index[-1] + pd.Timedelta(minutes=15)
tr_ = pd.read_csv(OUT.parents[1] / 'trades.csv'); tr_ = tr_[(tr_.owner == 'bot') & (tr_.side == 'SELL')]
live = [dict(ticket=int(r.ticket), open_ict=r.open_time_ict[:19], entry=r.entry, sl=r.sl_initial, tp=r.tp_initial, exit_cause=r.exit_cause, net=r.net_pl)
        for r in tr_.itertuples() if r.open_time_ict >= '2026-11-16']
live.append(dict(ticket=5130044984, open_ict='2026-11-25 12:45:11', entry=3530.825, sl=3554.797, tp=None, exit_cause='open (screenshot)', net=None))
def fmt(t): return (t + pd.Timedelta(minutes=15)).tz_convert(ICT).strftime('%d %b %H:%M')
def sim(sig, entry_mode, lim=None, N=0, stop=None, sl_atr=2.5, tp_rr=1.35, tp_cap_atr=0.0, entry_px=None, start_after=None, min_r_atr=1.0):
    """sig = signal bar label (UTC bar open). returns dict."""
    a = float(b.atr[sig]); after = b[b.index > (start_after if start_after is not None else sig)]
    if entry_mode == 'mkt':
        entry = entry_px; k0 = 0
    else:
        win = after.iloc[:N]; hit = np.flatnonzero(win.high.to_numpy() >= lim)
        if not len(hit): return dict(result=f'ไม่ fill ใน {len(win)} แท่ง' + (' (ข้อมูลยังไม่ครบ)' if len(win) < N else ''), entry=None, pnl=0.0)
        k0 = int(hit[0]); entry = lim - SLIP
    st = stop if stop is not None else entry + sl_atr * a
    if st - entry < min_r_atr * a: st = entry + min_r_atr * a
    R = st - entry; dist = tp_rr * R
    if tp_cap_atr and dist > tp_cap_atr * a: dist = tp_cap_atr * a
    tgt = entry - dist; prot = False
    for t, r in after.iloc[k0:].iterrows():
        if r.high + SP >= st:
            return dict(result=('BE' if prot else 'SL') + ' ' + fmt(t), entry=round(entry, 2), sl=round(entry + R, 2), tp=round(tgt, 2), pnl=round(entry - (st + SLIP), 2), stop_t=t, stop_px=st)
        if r.low + SP <= tgt:
            return dict(result='TP ' + fmt(t), entry=round(entry, 2), sl=round(entry + R, 2), tp=round(tgt, 2), pnl=round(entry - tgt, 2))
        if not prot and (entry - (r.close + SP)) - SLIP >= R:
            prot = True; st = min(st, entry - SLIP)
    last = b.close.iloc[-1] + SP
    return dict(result=f'ยังเปิด ณ {fmt(b.index[-1])} (ข้อมูลสิ้นสุด)', entry=round(entry, 2), sl=round(entry + R, 2), tp=round(tgt, 2), pnl=round(entry - last, 2), open=True)
VAR = {
 'a_base (live 2.5ATR, 1.35R)': lambda s, e: sim(s, 'mkt', entry_px=e),
 'b_lim_ll48_N8': lambda s, e: sim(s, 'lim', lim=float(b.ll48[s]), N=8),
 'b_lim_0.5atr_N8': lambda s, e: sim(s, 'lim', lim=float(b.close[s] + 0.5 * b.atr[s]), N=8),
 'b_lim_1.0atr_N8': lambda s, e: sim(s, 'lim', lim=float(b.close[s] + 1.0 * b.atr[s]), N=8),
 'c_swing16_slmax2.5atr_tp2.0': lambda s, e: sim(s, 'mkt', entry_px=e, stop=min(float(b.high[:s].iloc[-16:].max()) + SP + 0.25 * b.atr[s], e + 2.5 * b.atr[s]), tp_rr=2.0),
 'd_sl3.0_1.35R': lambda s, e: sim(s, 'mkt', entry_px=e, sl_atr=3.0),
 'd_sl3.5_1.35R': lambda s, e: sim(s, 'mkt', entry_px=e, sl_atr=3.5),
}
for k in (1.5, 2.0, 2.5):
    for N in (16, 32):
        for slm in (1.0, 1.5):
            for tp in (2.0, 3.0):
                VAR[f'g1_rally{k}atr_N{N}_sl{slm}_tp{tp}'] = (lambda k, N, slm, tp: lambda s, e: sim(s, 'lim', lim=float(b.close[s] + k * b.atr[s]), N=N, sl_atr=slm, tp_rr=tp))(k, N, slm, tp)
rows = []
for L in live:
    ot = pd.Timestamp(L['open_ict'], tz=ICT).tz_convert('UTC'); sig = ot.floor('15min') - pd.Timedelta(minutes=15)
    if sig not in b.index: continue
    a = float(b.atr[sig]); info = dict(ticket=L['ticket'], open_ict=L['open_ict'][5:16], live_entry=L['entry'], live_sl=L['sl'], live_tp=L['tp'], live_exit=L['exit_cause'], live_net=L['net'],
               sig_close=round(float(b.close[sig]), 3), atr=round(a, 3), implied_atr_live=round((L['sl'] - L['entry']) / 2.5, 3),
               bar_range_atr=round(float((b.high[sig] - b.low[sig]) / a), 2), below_ema20_atr=round(float((b.ema20[sig] - b.close[sig]) / a), 2), ll48=round(float(b.ll48[sig]), 3),
               low_after_48bars=round(float(b.low[b.index > sig].iloc[:48].min()), 2), high_after_48bars=round(float(b.high[b.index > sig].iloc[:48].max()), 2))
    for nm, f in VAR.items():
        r = f(sig, L['entry']); rows.append(dict(**info, variant=nm, **{k: v for k, v in r.items() if k not in ('stop_t', 'stop_px')}))
        if nm.startswith('a_base') and r['result'].startswith('SL'):
            for slm, tp in ((1.0, 2.0), (1.5, 2.0), (1.5, 3.0)):
                j = int(np.searchsorted(b.index, r['stop_t']))
                rr = sim(b.index[j], 'mkt', entry_px=r['stop_px'] - SP - SLIP, sl_atr=slm, tp_rr=tp, start_after=r['stop_t'])
                rows.append(dict(**info, variant=f'g2_reentry_at_stop_sl{slm}_tp{tp} (เพิ่มจากไม้ฐาน)', **{k: v for k, v in rr.items() if k not in ('stop_t', 'stop_px')}))
D = pd.DataFrame(rows); D.to_csv(OUT / 'case-study-16-25nov.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
print('bars end', LAST.tz_convert(ICT))
print(D.drop_duplicates('ticket')[['ticket', 'open_ict', 'live_entry', 'live_sl', 'live_exit', 'live_net', 'sig_close', 'atr', 'implied_atr_live', 'bar_range_atr', 'below_ema20_atr', 'll48', 'low_after_48bars', 'high_after_48bars']].to_string())
print(D[['ticket', 'variant', 'result', 'entry', 'sl', 'tp', 'pnl']].to_string())
print(D.groupby('variant').pnl.agg(['sum', 'count']).sort_values('sum').to_string())
