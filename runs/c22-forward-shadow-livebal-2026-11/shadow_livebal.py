"""Forward shadow at the LIVE balance: native 26b8 vs candidate sell3R_risk25.0_BE05_veto on UNSEEN ticks only.

Owner request 2026-11-18 ("Freeze shadow ยอดจริง"). Research only: no VM, no orders, no real money.
Why a separate protocol: the frozen $200 shadow (runs/c22-forward-shadow-2026-11, 15bda721) can never exercise the
candidate (the 10% cap rejects SELL risk > $20 at $200; the candidate band is risk >= $25). This protocol does not
modify that shadow. It reads that shadow's input/ (rebuilt monthly by its own build(), with integrity checks) and its
ctx()/one() helpers. Every pinned file is re-hashed at run time.

Window: books start 2026-11-17T00:00Z. The last quote seen when this was frozen is 2026-11-16T23:59:58Z, so nothing
in the window had been seen. One continuous book per (balance, view, profile), starting at the given balance,
with no reset and no added funds.
  python shadow_livebal.py freeze   # writes protocol.json/.sha256 ONCE
  python shadow_livebal.py run      # writes reports/<end>-<input sha12>.json; never overwrites
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SH = Path('/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-forward-shadow-2026-11')
sys.path.insert(0, str(SH))
import shadow as S  # noqa: E402  (guarded by __main__)
from scripts.research.c22_frequency_adapter import prepare  # noqa: E402
from scripts.research.c22_profit_preservation import replay  # noqa: E402
from scripts.research.c22_profit_preservation_campaign import summary  # noqa: E402
from scripts.research.c22_virtual_admission import NativeAdmissionVeto  # noqa: E402
from scripts.research.rollover import SwapPolicy  # noqa: E402

HERE = Path(__file__).resolve().parent; REP = HERE / 'reports'
START = pd.Timestamp('2026-11-17T00:00:00Z')
SEEN_UNTIL = '2026-11-16T23:59:58.380000+00:00'
BALANCES = {'live360': 360.0, 'live313': 313.0}; PRIMARY_BAL = 'live360'
SWAP_KEY = 'br474'; COSTS = ('base', 'stress')
MATURE_DAYS, MATURE_NATIVE, MATURE_BAND = 28, 20, 5   # band = native SELL trades with initial risk >= $25
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ROOT = S.ROOT


def book(c, bal, cost, end, events=None, tape=None, frame=None, finalize=True):
    """Warm-up to first tick + 5 min (asserted trade-free), then carry state with the balance set."""
    tape = tape or c['tape']; frame = frame if frame is not None else c['frame']
    broker = {**c['matrix']['broker'], **S.SWAPS[SWAP_KEY]}
    t = tape[0]; i = int(np.searchsorted(t, START.value // 10**6))
    if i >= len(t):
        return None
    warm = pd.Timestamp(int(t[i]), unit='ms', tz='UTC') + pd.Timedelta(minutes=5)
    if warm >= end:
        return None
    opts = dict(swap_policy=SwapPolicy.from_broker(broker), entry_recipe_id=c['recipe'])
    if events is not None:
        opts.update(S.CAND, gate_name=f'livebal-shadow/{cost}')
    gate = (lambda: dict(gate=NativeAdmissionVeto(events))) if events is not None else (lambda: {})
    args = (frame, tape, broker, c['rules'], c['costs'][cost])
    w = replay(*args, start=START, end=warm, finalize=False, **opts, **gate())
    assert not w['ledger'], 'warm-up not trade-free'
    st = w['carry_state']; assert st['position'] is None and not st['daily_losses'] and not st['day_start']
    st['balance'] = st['peak'] = float(bal)
    return replay(*args, start=warm, end=end, state=st, finalize=finalize, **opts, **gate())


def causality(c, bal, cost, end, full_nat, full_can):
    """Prefix check at each Sat 00:00 and Wed 12:00 cutoff: ticks truncated, indicators re-prepared from bars before the cutoff."""
    seed = json.loads((ROOT / S.SEED).read_text()); t = c['tape'][0]; out = []
    cuts = sorted([START + pd.Timedelta(days=k, hours=h) for k in range(0, 400) for h in (0, 12)
                   if (START + pd.Timedelta(days=k)).dayofweek in (5, 2) and (h == 0) == ((START + pd.Timedelta(days=k)).dayofweek == 5)])
    pre = lambda evs, cut: [S.ev_key(e) for e in evs if pd.Timestamp(e['time_utc']) < cut]
    for cut in [x for x in cuts if START < x < end]:
        n = int(np.searchsorted(t, cut.value // 10**6)); tp = [a[:n] for a in c['tape']]
        fr = prepare(c['raw'].loc[c['raw'].index < cut], seed)[0]
        pn = book(c, bal, cost, cut, tape=tp, frame=fr, finalize=False)
        if pn is None:
            continue
        pc = book(c, bal, cost, cut, events=pn['admission_events'], tape=tp, frame=fr, finalize=False)
        out.append(dict(cutoff=str(cut), native=pre(pn['admission_events'], cut) == pre(full_nat['admission_events'], cut),
                        candidate=pre(pc['admission_events'], cut) == pre(full_can['admission_events'], cut)))
    return out


def pinned():
    files = {'shadow_livebal.py': sha(__file__), 'shadow.py': sha(SH / 'shadow.py'), 'shadow-protocol.json': sha(SH / 'protocol.json')}
    files.update({s: sha(ROOT / s) for s in S.engine_files() + [S.MATRIX, S.SEED, S.NATIVE_CELL]})
    return files


def freeze():
    p = HERE / 'protocol.json'
    if p.exists():
        raise SystemExit('protocol already frozen')
    S.ctx()
    proto = dict(
        schema='c22-forward-shadow-livebal-v1', frozen_utc=pd.Timestamp.now(tz='UTC').isoformat(),
        owner_request='2026-11-18 "Freeze shadow ยอดจริง"', research_only=True,
        profiles=dict(native='26b8bcd69e043653 replay', candidate=dict(name='sell3R_risk25.0_BE05_veto', knobs=S.CAND, veto='native admission events of the same book')),
        window=dict(start=str(START), seen_until=SEEN_UNTIL, end_rule='shadow.window_end(last_quote_utc)', input='runs/c22-forward-shadow-2026-11/input (monthly build; integrity per that protocol)'),
        account=dict(balances=BALANCES, primary=PRIMARY_BAL, mode='one continuous book per (balance, view, profile) from window start; fixed 0.01; 10% cost-inclusive cap; daily10%/2 losses; cooldown2; no reset, no funding'),
        swap=dict(key=SWAP_KEY, value=S.SWAPS[SWAP_KEY], views=list(COSTS)),
        maturity=dict(days=MATURE_DAYS, native_trades_primary_base=MATURE_NATIVE, native_sell_risk_ge_25_primary_base=MATURE_BAND,
                      rule='verdict only when (end-start)>=28d AND native trades >=20 AND native SELL trades with initial risk>=$25 >=5, all in live360|base; else INTERIM'),
        verdict=dict(rule='NOT_EXERCISED if candidate ledger == native ledger in live360 base AND stress; FORWARD_CONSISTENT iff in both views candidate net >= native net AND candidate maxDD <= native maxDD; else FORWARD_INCONSISTENT. live313 reported, not decisive.',
                     decision_use='CONSISTENT is evidence for an owner adoption decision only; it does not authorise runtime changes'),
        causality='each run, live360 base+stress: prefix runs at Sat 00:00 and Wed 12:00 cutoffs (ticks truncated, indicators re-prepared before cutoff) must reproduce admission events before cutoff for native and candidate; any mismatch or zero checked cutoffs once the window is mature -> INVALID',
        prior_peek='candidate and native at $313/$360 were evaluated post-hoc on 2026-10-24..11-16 and 2020-2026 history (docs/reviews/2026-11-18-c22-candidate-live-balance.md). This protocol excludes all of that by starting at 2026-11-17.',
        owner_constraints='real money PROHIBITED; no VM change; criteria fixed, no post-hoc change; no reselection on forward data',
        hashes=pinned())
    p.write_text(json.dumps(proto, indent=1, ensure_ascii=False)); (HERE / 'protocol.sha256').write_text(sha(p)); print('FROZEN', sha(p))


def run():
    proto = HERE / 'protocol.json'; assert sha(proto) == (HERE / 'protocol.sha256').read_text().strip(), 'protocol changed'
    P = json.loads(proto.read_text())
    c = S.ctx()  # loads engine modules
    now = pinned()
    drift = {k for k in P['hashes'] if k != 'shadow-protocol.json' and P['hashes'][k] != now.get(k)} | (set(now) ^ set(P['hashes']))
    assert not drift, ('source drift', drift)
    man = json.loads((S.INP / 'manifest.json').read_text())
    for rel, h in man['artifacts'].items():
        assert sha(S.INP / rel) == h, ('input artifact drift', rel)
    end = S.window_end(pd.Timestamp(man['last_quote_utc'])); days = max(0, (end - START).days)
    cells, caus = {}, {}
    for bk, bal in BALANCES.items():
        for cost in COSTS:
            nat = book(c, bal, cost, end)
            if nat is None:
                continue
            can = book(c, bal, cost, end, events=nat['admission_events'])
            for name, r in (('native', nat), ('candidate', can)):
                s = summary(r, bal); L = s.pop('ledger')
                s['ledger'] = [dict(entry_utc=str(t['entry_time_utc']), exit_utc=str(t['exit_time_utc']), side='BUY' if t['direction'] == 1 else 'SELL',
                                    reason=t['reason'], protected=bool(t['protection_active']), risk_usd=round(t['risk_usd'], 2), swap=round(t['swap_usd'], 2), net=round(t['net'], 2)) for t in L]
                cells[f'{name}|{bk}|{cost}'] = s
                print(f"{name:9s} {bk} {cost:6s} net {s['net']:+8.2f} final {s['final_balance']:8.2f} dd {s['dd']:5.1f} n {s['trades']}", flush=True)
            if bk == PRIMARY_BAL:
                caus[cost] = causality(c, bal, cost, end, nat, can)
    if not cells:
        verdict = 'NO_DATA'; mature = False; valid = True
    else:
        nb = cells[f'native|{PRIMARY_BAL}|base']['ledger']
        band = sum(1 for t in nb if t['side'] == 'SELL' and t['risk_usd'] >= 25.0)
        mature = days >= MATURE_DAYS and len(nb) >= MATURE_NATIVE and band >= MATURE_BAND
        valid = all(x['native'] and x['candidate'] for v in caus.values() for x in v) and (not mature or all(len(v) > 0 for v in caus.values()))
        g = lambda a, v, k: cells[f'{a}|{PRIMARY_BAL}|{v}'][k]
        same = all(g('candidate', v, 'ledger') == g('native', v, 'ledger') for v in COSTS)
        ok = all(g('candidate', v, 'net') >= g('native', v, 'net') - 1e-9 and g('candidate', v, 'dd') <= g('native', v, 'dd') + 1e-9 for v in COSTS)
        verdict = 'INVALID' if not valid else ('INTERIM' if not mature else ('NOT_EXERCISED' if same else ('FORWARD_CONSISTENT' if ok else 'FORWARD_INCONSISTENT')))
    REP.mkdir(exist_ok=True); out = REP / f"{end.date()}-{sha(S.INP / 'manifest.json')[:12]}.json"
    if out.exists():
        raise SystemExit(f'report exists, refusing overwrite: {out}')
    out.write_text(json.dumps(dict(protocol_sha256=sha(proto), input_manifest_sha256=sha(S.INP / 'manifest.json'), window=[str(START), str(end)], days=days,
                                   mature=mature, causality=caus, verdict=verdict, cells=cells), indent=1, default=str))
    print('WINDOW', START, end, 'days', days, 'mature', mature, 'causality_ok', valid); print('VERDICT', verdict); print('WROTE', out)


if __name__ == '__main__':
    {'freeze': freeze, 'run': run}[sys.argv[1]]()
