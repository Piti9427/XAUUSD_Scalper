"""portfolio_m copied verbatim from two-position-20261126/two_pos.py (logic unchanged) + rejection counters.
Imports the f2f3-validate harness via sell-entry-sl-20261125/entry_sl.py (import only, no files modified)."""
import sys; from pathlib import Path
sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
A24 = T('2024-01-01')

def nights(ts, tx):
    r0 = (ts - 75600000) // 86400000; r1 = (tx - 75600000) // 86400000; n = 0
    for x in range(int(r0) + 1, int(r1) + 1): n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit='ms').weekday() == 2 else 1
    return n

def make_groups(c):
    G = []
    for k, r in zip(c.index, c.itertuples()):
        leg = dict(tx=int(r.tx), pnl=float(r.pnl), R=float(r.R), why=int(r.why), tbe=int(r.tbe), leg='A', lots=1)
        G.append(dict(k=k, sig=int(r.sig), ts=int(r.ts), d=int(r.d), i=int(r.i), legs=[leg]))
    return G

REASONS = ('maxpos', 'direction', 'need_be', 'cooldown', 'f3', 'daily_stop', 'cap')
def portfolio_m(G, start, end, maxpos=1, f3='set', need_be=False, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=SLIP):
    a, z = ms(start), ms(end)
    bal = bal0; open_ = []; dl = {}; cool = 0; daystart = {}; res = []; cms = int(cool_min * 60000)
    recent = []
    gid = 0; sid = 0; set_lost = {}
    info = dict(conc_risk_max=0.0, max_open=0, cands=0, **{f'rej_{r}': 0 for r in REASONS}, rej_cap_second=0, rej_cap_first=0, rej_ds_second=0, rej_ds_first=0)
    rej = []
    def close_until(t):
        nonlocal bal, cool, open_
        due = sorted([lg for lg in open_ if lg['tx'] <= t], key=lambda x: x['tx'])
        for lg in due:
            open_.remove(lg); bal += lg['net']
            if lg['net'] < 0:
                cool = lg['tx'] + cms; day = lg['tx'] // 86400000
                if f3 == 'pos' or not set_lost.get(lg['set']):
                    dl[day] = dl.get(day, 0) + 1; set_lost[lg['set']] = True
            res.append(lg)
            if not any(o['grp'] == lg['grp'] for o in open_): recent.append((lg['gtx'], lg['d']))
    for g in G:
        if not (a <= g['ts'] < z): continue
        info['cands'] += 1
        close_until(g['ts'])
        sg = g['sig']
        busy_open = {o['grp']: o['d'] for o in open_}
        busy = list(busy_open.values()) + [d for tx, d in recent[-8:] if tx > sg]
        if len(busy) >= maxpos: info['rej_maxpos'] += 1; continue
        if any(d != g['d'] for d in busy): info['rej_direction'] += 1; continue
        if need_be and open_ and not all(o['tbe'] >= 0 and o['tbe'] <= sg for o in open_): info['rej_need_be'] += 1; continue
        if g['ts'] < cool or sg < cool: info['rej_cooldown'] += 1; continue
        if dl.get(sg // 86400000, 0) >= max_losses: info['rej_f3'] += 1; continue
        day = g['ts'] // 86400000
        if dl.get(day, 0) >= max_losses: info['rej_f3'] += 1; continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop:
            info['rej_daily_stop'] += 1; info['rej_ds_second' if busy else 'rej_ds_first'] += 1
            rej.append(dict(reason='daily_stop', ts=g['ts'], d=g['d'], second=bool(busy), bal=round(bal, 2))); continue
        open_risk = sum(o['risk'] for o in open_ if not (o['tbe'] >= 0 and o['tbe'] <= g['ts']))
        new_risk = sum(lg['R'] + slip_r * lg['lots'] for lg in g['legs'])
        if open_risk + new_risk > bal * cap:
            info['rej_cap'] += 1; info['rej_cap_second' if busy else 'rej_cap_first'] += 1
            rej.append(dict(reason='cap', ts=g['ts'], d=g['d'], second=bool(busy), bal=round(bal, 2), open_risk=round(open_risk, 2), new_risk=round(new_risk, 2),
                            combined_pct=round(100 * (open_risk + new_risk) / bal, 2), would_net=round(sum(lg['pnl'] for lg in g['legs']), 2))); continue
        info['conc_risk_max'] = max(info['conc_risk_max'], 100 * (open_risk + new_risk) / bal)
        if not open_: sid += 1
        gid += 1; second = bool(busy_open)
        gtx = max(lg['tx'] for lg in g['legs'])
        for lg in g['legs']:
            sw = nights(g['ts'], lg['tx']) * (swap * lg['lots'] if g['d'] == 1 else 0.0)
            open_.append(dict(k=g['k'], ts=g['ts'], sig=sg, i=g['i'], tx=lg['tx'], gtx=gtx, d=g['d'], net=lg['pnl'] + sw, R=lg['R'] + slip_r * lg['lots'],
                              risk=lg['R'] + slip_r * lg['lots'], why=lg['why'], tbe=lg['tbe'], leg=lg['leg'], grp=gid, set=sid, second=second))
        info['max_open'] = max(info['max_open'], len({o['grp'] for o in open_}))
    res.extend(sorted(open_, key=lambda x: x['tx']))
    t = pd.DataFrame(res)
    if len(t): t['r'] = t.net / t.R
    info['rejections'] = rej
    t.attrs.update(info)
    return t

def run_m(G, a, z, **kw):
    parts = [(portfolio_m(G, s0, s1, **kw), (s0, s1)) for s0, s1 in segs(a, z)]
    t = pd.concat([p for p, _ in parts if len(p)], ignore_index=True)
    return t, parts

def window(G, wn, **kw):
    if wn == '2024-26 all': a, z = A24, END; t = portfolio_m(G, a, z, **kw); return t, [(t, (a, z))]
    return run_m(G, *WIN[wn], **kw)

def agg(parts, key):
    if key == 'conc_risk_max': return round(max(p.attrs['conc_risk_max'] for p, _ in parts), 2)
    return int(sum(p.attrs[key] for p, _ in parts))
