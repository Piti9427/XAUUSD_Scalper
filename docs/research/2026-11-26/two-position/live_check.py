"""Live journal check (box copy _raw/extract.json, extracted 2026-11-25 19:14:52 ICT; no VM access).
1) SIGNAL records whose bar closed while a bot position was open; when they were logged and how they ended.
2) Every FILLED entry: delay between its signal bar close and the fill (does the bot ever send a stale/queued signal?).
3) Live SELLs entered <= 15 min after the previous bot exit."""
import json, pandas as pd
J = '/workspace/c22-trade-journal/'
d = json.load(open(J + '_raw/extract.json')); ICT = 'Asia/Bangkok'
tz = lambda s: pd.Timestamp(s).tz_convert(ICT)
t = pd.read_csv(J + 'trades.csv'); t = t[t.owner == 'bot'].copy()
t['o'] = pd.to_datetime(t.open_time_ict.str[:19]).dt.tz_localize(ICT); t['c'] = pd.to_datetime(t.close_time_ict.str[:19]).dt.tz_localize(ICT)
t = t.sort_values('o').reset_index(drop=True)
rows = []
for s in d['signals']:
    bar = tz(s['bar']); logged = tz(s['utc'])
    op = t[(t.o < bar) & (t.c > bar)]
    if len(op):
        p = op.iloc[0]; fu = s.get('followup', {})
        rows.append(dict(signal_id=s['id'], bar_close_ict=bar, logged_ict=logged, open_ticket=p.ticket, open_ticket_close_ict=p.c,
                         logged_after_close_s=round((logged - p.c).total_seconds(), 1), bar_age_at_log_min=round((logged - bar).total_seconds() / 60, 2),
                         prior_low=s['observed']['prior_low'], close=s['observed']['close'], atr=round(s['observed']['atr'], 3),
                         entry_window_expired='BLOCKER:entry_window_expired' in fu, followup=';'.join(f'{k}={v}' for k, v in fu.items())))
A = pd.DataFrame(rows); A.to_csv('live-signals-while-open.csv', index=False); print(A.drop(columns='followup').to_string())
rq = []
for x in d['lifecycle']:
    if x.get('kind') != 'FILLED': continue
    bar = tz(x['active']['bar']); fill = pd.Timestamp(int(x['active']['entry_ms']), unit='ms', tz='UTC').tz_convert(ICT)
    rq.append(dict(ticket=x['event']['ticket'], signal_bar_close_ict=bar, fill_ict=fill, bar_to_fill_s=round((fill - bar).total_seconds(), 1),
                   signal_to_fill_ms=x['event'].get('signal_to_fill_ms')))
R = pd.DataFrame(rq); R.to_csv('live-fill-delays.csv', index=False)
print('FILLED events', len(R), '| bar close -> fill seconds: max', R.bar_to_fill_s.max(), 'median', R.bar_to_fill_s.median()); print(R.to_string())
le = []
for j in range(1, len(t)):
    p, r = t.iloc[j - 1], t.iloc[j]
    gap = (r.o - p.c).total_seconds() / 60
    if 0 <= gap <= 15: le.append(dict(ticket=r.ticket, side=r.side, open_ict=r.o, prev_ticket=p.ticket, prev_close_ict=p.c, prev_exit=p.exit_cause, gap_min=round(gap, 2), net=r.net_pl))
L = pd.DataFrame(le); L.to_csv('live-reentry-within-15min.csv', index=False); print(L.to_string())
