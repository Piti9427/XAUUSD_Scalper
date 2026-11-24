"""Forward shadow for the F2+F3 live rules (contract 7fe09f7246068bc9) and two pre-registered variants.

Owner request 2026-11-24 ("Set up shadow"). Research only: no VM, no orders, no real money.
Profiles (same tape, same cost view, one continuous book each, fixed 0.01, 10% cost-inclusive cap, daily stop 10%,
cooldown 2 bars, BE at 1R, BUY TP 3R):
  native  = 26b8bcd69e043653 (reference / rollback watch only, never decisive)
  live    = native + F2 (skip unless direction*(close - closed H4 EMA200) >= 10*ATR14 on the completed M15 signal bar)
            + F3 (max 1 losing trade per UTC day)          -> mirrors release selected-ff17a3a8c0890cb0
  f2ml2   = native + F2, max 2 losses per UTC day (native value)
  tp20    = live + SELL target 2.0R (BE trigger unchanged at 1R)
Window: books start 2026-11-25T00:00Z, after every quote any research on 2026-11-24 had seen.
Input: runs/c22-forward-shadow-2026-11/input (rebuilt monthly by that shadow's build(); re-hashed here).
  python shadow_f2.py parity   # informational SEEN-window run (2026-10-24..input end); never a verdict
  python shadow_f2.py freeze   # writes protocol.json/.sha256 ONCE
  python shadow_f2.py run      # writes reports/<end>-<input sha12>.json; never overwrites
"""
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

SH = Path('/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-forward-shadow-2026-11')
sys.path.insert(0, str(SH))
import shadow as S  # noqa: E402
from scripts.research.c22_frequency_adapter import prepare  # noqa: E402
from scripts.research.c22_profit_preservation import replay  # noqa: E402
from scripts.research.c22_profit_preservation_campaign import summary  # noqa: E402
from scripts.research.reward156_tuning import closed_h4_ema  # noqa: E402
from scripts.research.rollover import SwapPolicy  # noqa: E402

HERE = Path(__file__).resolve().parent; REP = HERE / 'reports'; ROOT = S.ROOT
START = pd.Timestamp('2026-11-25T00:00:00Z')
SEEN_START = pd.Timestamp('2026-10-24T00:00:00Z')
F2_ATR = 10.0
PROFILES = {
    'native': dict(f2=False, max_daily_losses=2, sell_target_rr=None),
    'live': dict(f2=True, max_daily_losses=1, sell_target_rr=None),
    'f2ml2': dict(f2=True, max_daily_losses=2, sell_target_rr=None),
    'tp20': dict(f2=True, max_daily_losses=1, sell_target_rr=2.0),
}
ARMS = ('f2ml2', 'tp20')  # judged against 'live'
BALANCES = {'b400': 400.0, 'b300': 300.0}; PRIMARY_BAL = 'b400'
SWAP_KEY = 'br474'; COSTS = ('base', 'stress')
MATURE_DAYS, MATURE_LIVE, MATURE_LIVE_SELL = 90, 60, 40
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


class F2Gate:
    """F2: reject unless the completed signal bar is >= 10 ATR beyond the closed H4 EMA200 on the trade side."""
    def __init__(self, ema): self.ema = ema
    def __call__(self, row, ms, bal, led):
        e = self.ema.get(row.Index, np.nan)
        if not np.isfinite(e) or not np.isfinite(row.atr) or row.atr <= 0:
            return 'macro_distance_unavailable'
        return 'macro_distance_too_small' if int(row.direction) * (row.close - e) < F2_ATR * row.atr else None


def book(c, profile, bal, cost, start, end, tape=None, raw=None, frame=None, finalize=True):
    """Warm-up to first tick + 5 min (asserted trade-free), then carry state with the balance set."""
    spec = PROFILES[profile]
    tape = tape or c['tape']; raw = raw if raw is not None else c['raw']; frame = frame if frame is not None else c['frame']
    broker = {**c['matrix']['broker'], **S.SWAPS[SWAP_KEY]}
    t = tape[0]; i = int(np.searchsorted(t, start.value // 10**6))
    if i >= len(t):
        return None
    warm = pd.Timestamp(int(t[i]), unit='ms', tz='UTC') + pd.Timedelta(minutes=5)
    if warm >= end:
        return None
    rules = replace(c['rules'], max_daily_losses=spec['max_daily_losses'])
    opts = dict(swap_policy=SwapPolicy.from_broker(broker), entry_recipe_id=c['recipe'], gate_name=f'f2-shadow/{profile}/{cost}')
    if spec['sell_target_rr'] is not None:
        opts['sell_target_rr'] = spec['sell_target_rr']
    gate = (lambda: dict(gate=F2Gate(closed_h4_ema(raw, 200)))) if spec['f2'] else (lambda: {})
    args = (frame, tape, broker, rules, c['costs'][cost])
    w = replay(*args, start=start, end=warm, finalize=False, **opts, **gate())
    assert not w['ledger'], 'warm-up not trade-free'
    st = w['carry_state']; assert st['position'] is None and not st['daily_losses'] and not st['day_start']
    st['balance'] = st['peak'] = float(bal)
    return replay(*args, start=warm, end=end, state=st, finalize=finalize, **opts, **gate())


def cell(r, bal):
    s = summary(r, bal); L = s.pop('ledger')
    s['ledger'] = [dict(entry_utc=str(t['entry_time_utc']), exit_utc=str(t['exit_time_utc']), side='BUY' if t['direction'] == 1 else 'SELL',
                        reason=t['reason'], protected=bool(t['protection_active']), risk_usd=round(t['risk_usd'], 2),
                        swap=round(t['swap_usd'], 2), net=round(t['net'], 2), net_r=round(t['net_r'], 3)) for t in L]
    n = len(L); s['win_pct'] = round(100 * sum(t['net'] > 0 for t in L) / n, 1) if n else None
    m = pd.Series([t['net'] for t in L], index=pd.to_datetime([t['exit_time_utc'] for t in L], utc=True), dtype=float)
    monthly = m.groupby(m.index.strftime('%Y-%m')).sum() if n else pd.Series(dtype=float)
    s['monthly'] = {k: round(v, 2) for k, v in monthly.items()}
    s['worst_month'] = round(float(monthly.min()), 2) if n else None
    return s


def causality(c, bal, cost, start, end, full):
    """Prefix check at each Sat 00:00 and Wed 12:00 cutoff: ticks truncated, bars/indicators/EMA re-prepared before cutoff."""
    seed = json.loads((ROOT / S.SEED).read_text()); t = c['tape'][0]; out = []
    cuts = sorted([start + pd.Timedelta(days=k) for k in range(400) if (start + pd.Timedelta(days=k)).dayofweek == 5]
                  + [start + pd.Timedelta(days=k, hours=12) for k in range(400) if (start + pd.Timedelta(days=k)).dayofweek == 2])
    pre = lambda evs, cut: [S.ev_key(e) for e in evs if pd.Timestamp(e['time_utc']) < cut]
    for cut in [x for x in cuts if start < x < end]:
        n = int(np.searchsorted(t, cut.value // 10**6)); tp = [a[:n] for a in c['tape']]
        raw = c['raw'].loc[c['raw'].index < cut]; fr = prepare(raw, seed)[0]
        row = dict(cutoff=str(cut))
        for prof in PROFILES:
            p = book(c, prof, bal, cost, start, cut, tape=tp, raw=raw, frame=fr, finalize=False)
            row[prof] = None if p is None else pre(p['admission_events'], cut) == pre(full[prof]['admission_events'], cut)
        out.append(row)
    return out


def evaluate(c, start, end, with_causality):
    cells, caus = {}, {}
    for bk, bal in BALANCES.items():
        for cost in COSTS:
            res = {p: book(c, p, bal, cost, start, end) for p in PROFILES}
            if any(r is None for r in res.values()):
                continue
            for name, r in res.items():
                s = cell(r, bal); cells[f'{name}|{bk}|{cost}'] = s
                print(f"{name:7s} {bk} {cost:6s} net {s['net']:+8.2f} final {s['final_balance']:8.2f} dd {s['dd']:5.1f} n {s['trades']:3d} "
                      f"win {s['win_pct']} rej {dict((k, x) for k, x in s['rejections'].items() if x)}", flush=True)
            if with_causality and bk == PRIMARY_BAL:
                caus[cost] = causality(c, bal, cost, start, end, res)
    return cells, caus


def pinned():
    files = {'shadow_f2.py': sha(__file__), 'shadow.py': sha(SH / 'shadow.py'), 'shadow-protocol.json': sha(SH / 'protocol.json')}
    files.update({s: sha(ROOT / s) for s in S.engine_files() + [S.MATRIX, S.SEED, S.NATIVE_CELL]})
    return files


def check_input():
    man = json.loads((S.INP / 'manifest.json').read_text())
    for rel, h in man['artifacts'].items():
        assert sha(S.INP / rel) == h, ('input artifact drift', rel)
    return man


def parity():
    """Informational only: SEEN window 2026-10-24..input end. Not a verdict; written under reports/seen-*."""
    c = S.ctx(); man = check_input(); end = S.window_end(pd.Timestamp(man['last_quote_utc']))
    cells, _ = evaluate(c, SEEN_START, end, with_causality=False)
    REP.mkdir(exist_ok=True); out = REP / f"seen-{SEEN_START.date()}-{end.date()}-{sha(S.INP / 'manifest.json')[:12]}.json"
    if out.exists():
        raise SystemExit(f'report exists, refusing overwrite: {out}')
    out.write_text(json.dumps(dict(kind='SEEN_INFORMATIONAL_NOT_A_VERDICT', window=[str(SEEN_START), str(end)], cells=cells), indent=1, default=str))
    print('WROTE', out)


def freeze():
    p = HERE / 'protocol.json'
    if p.exists():
        raise SystemExit('protocol already frozen')
    S.ctx()
    proto = dict(
        schema='c22-forward-shadow-f2-v1', frozen_utc=pd.Timestamp.now(tz='UTC').isoformat(),
        owner_request='2026-11-24 "Set up shadow" (arms: F2+F3 live / F2 + max 2 losses / SELL TP 2.0R)', research_only=True,
        profiles={k: dict(v, f2_rule=('direction*(close - closed_h4_ema(raw,200)) >= 10*atr on completed M15 signal bar, else reject macro_distance_too_small' if v['f2'] else None))
                  for k, v in PROFILES.items()},
        shared_rules='26b8 native rules from NATIVE_CELL: SELL 48-bar breakdown below H4 EMA, SL 2.5ATR, TP 1.35R, BE 1R; BUY RSI7>30 above rising EMA50, TP 3R; cooldown 2 bars; daily stop 10%; fixed 0.01; 10% cost-inclusive cap; loss day = UTC day',
        window=dict(start=str(START), seen_until='2026-11-24T08:00Z (F2/F3 research data end); local input ends 2026-11-16', end_rule='shadow.window_end(last_quote_utc)',
                    input='runs/c22-forward-shadow-2026-11/input (monthly build; integrity per that protocol, re-hashed at run)'),
        account=dict(balances=BALANCES, primary=PRIMARY_BAL, mode='one continuous book per (balance, view, profile) from window start; no reset; no funding',
                     note='b400 = research basis of docs/research/2026-11-24 and approx live balance; live balance not read from VM at freeze'),
        swap=dict(key=SWAP_KEY, value=S.SWAPS[SWAP_KEY], views=list(COSTS)),
        maturity=dict(days=MATURE_DAYS, live_trades_primary_base=MATURE_LIVE, live_sell_trades_primary_base=MATURE_LIVE_SELL,
                      rule='verdict only when (end-start)>=90d AND live has >=60 trades AND >=40 SELL trades in b400|base; else INTERIM',
                      power_note='at ~13 trades/month a 1-2 month window cannot separate TP 1.35R from 2.0R; INTERIM reports are descriptive only'),
        verdict=dict(rule='per arm vs live: NOT_EXERCISED if ledger identical in b400 base AND stress; FORWARD_CONSISTENT iff in both views arm net >= live net AND arm maxDD <= live maxDD; else FORWARD_INCONSISTENT. b300 reported, not decisive.',
                     decision_use='CONSISTENT is evidence for the owner to consider a new release; it never changes the bot by itself. INCONSISTENT -> keep live.',
                     rollback_watch='each run reports live vs native (net, maxDD, worst month) per README 2026-11-24 item 7; informational, owner decides'),
        causality='each run, b400 base+stress: prefix runs of all profiles at Sat 00:00 and Wed 12:00 cutoffs (ticks truncated, bars/indicators/EMA re-prepared before cutoff) must reproduce admission events before cutoff; any mismatch, or zero cutoffs once mature -> INVALID',
        parity=dict(f2_distance='2026-11-24 check: F2 distance on this input vs live-crosscheck.csv for 9 live trades differs by 0.04-0.19 ATR; skip decision equal on all 9 (4.70 and 8.45 skipped, rest >= 15.8). Borderline signals within ~0.2 ATR of 10 may differ from live.',
                    seen_run='reports/seen-* (2026-10-24..input end) is informational and seen; not used for any verdict'),
        prior_peek='F2 threshold 10 and F3 were chosen on 2025-26 history including data up to 2026-11-24 08:00 ICT. TP 2.0R was seen on 2025-26 and failed 2023-24 OOS on 2026-11-11 (without F2). Nothing from 2026-11-25 on has been seen. Seen run 2026-10-24..11-17 (b400 base, 11-23 trades, not evidence): native +99.65, live +155.27, f2ml2 +141.12, tp20 +31.70; tp20 had 17 daily_loss_count rejections vs 1 for live, diagnosed as genuine (unprotected SL reversals lock the UTC day; 1 of 11 tp20 trades was a protected exit below BE, -1.97), not a loss-definition artefact: live admission counts a loss as position cash sum < 0, same as engine net < 0.',
        owner_constraints='real money PROHIBITED; no VM change; criteria fixed, no post-hoc change; no reselection on forward data; no-regression tolerance still open',
        hashes=pinned())
    p.write_text(json.dumps(proto, indent=1, default=str)); (HERE / 'protocol.sha256').write_text(sha(p)); print('FROZEN', sha(p))


def run():
    proto = HERE / 'protocol.json'; assert sha(proto) == (HERE / 'protocol.sha256').read_text().strip(), 'protocol changed'
    P = json.loads(proto.read_text())
    c = S.ctx(); now = pinned()
    drift = {k for k in P['hashes'] if k != 'shadow-protocol.json' and P['hashes'][k] != now.get(k)} | (set(now) ^ set(P['hashes']))
    assert not drift, ('source drift', drift)
    man = check_input(); end = S.window_end(pd.Timestamp(man['last_quote_utc'])); days = max(0, (end - START).days)
    cells, caus = evaluate(c, START, end, with_causality=True)
    g = lambda a, v, k: cells[f'{a}|{PRIMARY_BAL}|{v}'][k]
    if not cells:
        verdict, mature, valid, watch = 'NO_DATA', False, True, None
    else:
        lb = g('live', 'base', 'ledger'); nsell = sum(t['side'] == 'SELL' for t in lb)
        mature = days >= MATURE_DAYS and len(lb) >= MATURE_LIVE and nsell >= MATURE_LIVE_SELL
        valid = all(x[p] is not False for v in caus.values() for x in v for p in PROFILES) and (not mature or all(len(v) > 0 for v in caus.values()))
        def judge(a):
            if all(g(a, v, 'ledger') == g('live', v, 'ledger') for v in COSTS):
                return 'NOT_EXERCISED'
            ok = all(g(a, v, 'net') >= g('live', v, 'net') - 1e-9 and g(a, v, 'dd') <= g('live', v, 'dd') + 1e-9 for v in COSTS)
            return 'FORWARD_CONSISTENT' if ok else 'FORWARD_INCONSISTENT'
        verdict = 'INVALID' if not valid else ('INTERIM' if not mature else {a: judge(a) for a in ARMS})
        watch = {v: dict(live=dict(net=g('live', v, 'net'), dd=g('live', v, 'dd'), worst_month=g('live', v, 'worst_month')),
                         native=dict(net=g('native', v, 'net'), dd=g('native', v, 'dd'), worst_month=g('native', v, 'worst_month')),
                         live_dd_above_native=g('live', v, 'dd') > g('native', v, 'dd') + 1e-9) for v in COSTS}
    REP.mkdir(exist_ok=True); out = REP / f"{end.date()}-{sha(S.INP / 'manifest.json')[:12]}.json"
    if out.exists():
        raise SystemExit(f'report exists, refusing overwrite: {out}')
    out.write_text(json.dumps(dict(protocol_sha256=sha(proto), input_manifest_sha256=sha(S.INP / 'manifest.json'), window=[str(START), str(end)], days=days,
                                   mature=mature, causality=caus, verdict=verdict, rollback_watch=watch, cells=cells), indent=1, default=str))
    print('WINDOW', START, end, 'days', days, 'mature', mature, 'causality_ok', valid); print('VERDICT', verdict); print('WROTE', out)


if __name__ == '__main__':
    {'parity': parity, 'freeze': freeze, 'run': run}[sys.argv[1]]()
