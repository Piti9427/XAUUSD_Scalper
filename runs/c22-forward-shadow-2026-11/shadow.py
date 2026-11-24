"""Offline forward shadow: native 26b8 vs selected candidate vs candidate+floor0.3_both on fresh public Exness ticks.

Research only. No VM, no orders, no real money. Owner decisions 2026-11-17: download monthly Exness zips; window starts
2026-10-24; swap VM -490.0 POINTS primary + archived -567.4 sensitivity; one continuous $200 book per spec (balance
moves with P&L, fixed 0.01 lot, 10% cost-inclusive cap unchanged).

  python shadow.py build    # (re)build input/ from zips (old Aug-Oct zips verified by hash + fresh Nov+ zips)
  python shadow.py freeze   # write protocol.json/.sha256 ONCE (refuses to overwrite)
  python shadow.py run      # evaluate on current input; writes reports/<end>.json; verdict only at maturity
"""
import hashlib, json, sys
from dataclasses import replace
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path('/Users/nopparuj/my-agents/XAUUSD_Scalper'); sys.path.insert(0, str(ROOT))
from scripts.research.breakout_models import Costs
from scripts.research.c22_frequency_adapter import prepare, config_id
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_profit_preservation import replay
from scripts.research.c22_profit_preservation_campaign import SEED, MATRIX, NATIVE_CELL, summary
from scripts.research.c22_virtual_admission import NativeAdmissionVeto
from scripts.research.public_exness_archive import import_month
from scripts.research.rollover import SwapPolicy

HERE = Path(__file__).resolve().parent; INP = HERE / 'input'; ZIPS = HERE / 'zips'; REP = HERE / 'reports'
OLD = ROOT / 'runs/c22-forward-2026-11'
START = pd.Timestamp('2026-10-24T00:00:00Z'); BAL = 200.0
CAND = dict(sell_target_rr=3.0, min_sell_target_risk_usd=25.0, conditional_sell_protect_after_r=0.5)
FLOOR = 0.3  # percent; 2.5*ATR/close*100 of completed signal bar, both sides (owner-chosen 2026-11-13, relaxed rule)
SWAPS = {'br474': dict(swap_long=-474.3), 'vm490': dict(swap_long=-490.0), 'arch567': dict(swap_long=-567.4)}  # swap_short 0, Wed triple, point 0.001 kept
COSTS = ('base', 'stress'); PRIMARY = 'br474'
MATURE_DAYS, MATURE_SIGNALS = 28, 20
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


OLD_MONTHS = ['2026-08', '2026-09', '2026-10']


def raw_sha(arrs):
    h = hashlib.sha256()
    for a in arrs: h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def build():
    """Rebuild input/. Manifest removed first, so a failed build leaves no manifest (run() then refuses).
    Previous manifest archived; new tape/bars must equal the previous ones on the previous prefix (no silent revision)."""
    old = dict(l.split()[::-1] for l in (OLD / 'zips.sha256').read_text().split('\n') if l.strip())
    INP.mkdir(exist_ok=True); (INP / 'discovery').mkdir(exist_ok=True); (INP / 'tape').mkdir(exist_ok=True); (HERE / 'manifests').mkdir(exist_ok=True)
    prev = None
    if (INP / 'manifest.json').exists():
        prev = json.loads((INP / 'manifest.json').read_text())
        (HERE / 'manifests' / f"{prev['last_quote_utc'][:19].replace(':', '')}.json").write_text(json.dumps(prev, indent=1))
        (INP / 'manifest.json').unlink()
    new = sorted(f'{p.name[15:19]}-{p.name[20:22]}' for p in ZIPS.glob('Exness_XAUUSDm_????_??.zip'))
    assert not set(new) & set(OLD_MONTHS) and new == sorted(new)
    audits, frames = [], []
    for month in OLD_MONTHS + new:
        name = f"Exness_XAUUSDm_{month.replace('-', '_')}.zip"; src = (OLD / 'zips' / name) if month in OLD_MONTHS else ZIPS / name
        if month in OLD_MONTHS: assert sha(src) == old[name], ('old zip hash', name)
        link = INP / name
        if link.is_symlink() or link.exists(): link.unlink()
        link.symlink_to(src)
        audit, frame = import_month(INP, dict(file=name, sha256=sha(src), month=month))
        audits.append(audit); frames.append(frame); print(month, audit['ticks'], audit['first_utc'], audit['last_utc'], flush=True)
    bars = pd.concat(frames); assert bars.index.is_monotonic_increasing and not bars.index.has_duplicates
    bars.to_csv(INP / 'bars.csv', index_label='bar_open_utc')
    for k in ('time', 'bid', 'ask'):
        parts = []
        for a in audits:
            with np.load(INP / 'discovery' / f"{a['month']}.npz") as t: parts.append(t[k])
        j = np.concatenate(parts)
        if k == 'time': assert not (np.diff(j) < 0).any()
        np.save(INP / 'tape' / f'{k}.npy', j)
    for p in (INP / 'discovery').glob('*.npz'): p.unlink()
    tape = [np.load(INP / 'tape' / f'{k}.npy', mmap_mode='r') for k in ('time', 'bid', 'ask')]; t = tape[0]
    last = pd.Timestamp(int(t[-1]), unit='ms', tz='UTC')
    nb = pd.read_csv(INP / 'bars.csv', index_col=0, parse_dates=True)
    # overlap parity vs old forward input (bars and ticks) on [2026-08-01, 2026-11-10 00:00)
    lo, hi = pd.Timestamp('2026-08-01', tz='UTC'), pd.Timestamp('2026-11-10', tz='UTC')
    ob = pd.read_csv(OLD / 'input/bars.csv', index_col=0, parse_dates=True)
    a = ob.loc[(ob.index >= lo) & (ob.index < hi)]; b = nb.loc[(nb.index >= lo) & (nb.index < hi)]
    bar_par = bool(a.index.equals(b.index) and np.array_equal(a.values, b.values))
    ot = np.load(OLD / 'input/tape/time.npy', mmap_mode='r'); hi_ms = hi.value // 10**6
    no, nn = int(np.searchsorted(ot, hi_ms)), int(np.searchsorted(t, hi_ms))
    tick_par = bool(no == nn and all(np.array_equal(np.load(OLD / f'input/tape/{k}.npy', mmap_mode='r')[:no], np.load(INP / f'tape/{k}.npy', mmap_mode='r')[:nn]) for k in ('time', 'bid', 'ask')))
    bars_raw = lambda n: raw_sha([nb.index.asi8[:n], nb.values[:n]])
    prev_par = None
    if prev is not None:  # previous build's full content must be a prefix of this build
        pn, pb = prev['prefix']['ticks'], prev['prefix']['bars']
        prev_par = bool(len(t) >= pn and len(nb) >= pb and raw_sha([x[:pn] for x in tape]) == prev['prefix']['tape_raw_sha'] and bars_raw(pb) == prev['prefix']['bars_raw_sha'])
    m = dict(zips={x['file']: x['sha256'] for x in audits}, months=[x['month'] for x in audits], ticks=int(sum(x['ticks'] for x in audits)),
             bars=len(bars), last_quote_utc=last.isoformat(), overlap_window=[str(lo), str(hi)], overlap_bar_parity=bar_par, overlap_tick_parity=tick_par,
             previous_manifest_last_quote=prev and prev['last_quote_utc'], previous_prefix_parity=prev_par,
             prefix=dict(ticks=len(t), bars=len(nb), tape_raw_sha=raw_sha(tape), bars_raw_sha=bars_raw(len(nb))),
             artifacts={str(p.relative_to(INP)): sha(p) for p in [INP / 'bars.csv', *sorted((INP / 'tape').glob('*.npy'))]})
    assert bar_par and tick_par, 'overlap parity failed'
    assert prev is None or prev_par, 'previous build is not a prefix of this build (data revised) -> investigate before any run'
    (INP / 'manifest.json').write_text(json.dumps(m, indent=1)); print(json.dumps({k: v for k, v in m.items() if k not in ('artifacts', 'prefix')}))


def window_end(last):
    """Exclusive end = start of the last UTC day that has quotes up to its final minute; else that day's start."""
    d = last.normalize()
    return d + pd.Timedelta(days=1) if last >= d + pd.Timedelta(hours=23, minutes=59) else d


def freeze():
    p = HERE / 'protocol.json'
    if p.exists(): raise SystemExit('protocol already frozen')
    ctx()  # load every lazily imported engine module before pinning
    src = engine_files() + [MATRIX, SEED, NATIVE_CELL]
    proto = dict(created='2026-11-17', version=3, status='FORWARD_SHADOW_RESEARCH_ONLY', cost_status='COST_INCONCLUSIVE',
        profiles=dict(native='26b8bcd69e043653 as replayed', candidate='sell3R_risk25.0_BE05_veto: ' + json.dumps(CAND) + ' + NativeAdmissionVeto(native book same tape/view)',
                      floor03='candidate + reject if 2.5*atr/close*100 < 0.3 (both sides), veto first'),
        account=dict(start_balance=BAL, mode='one continuous book per profile from window start, no reset; fixed 0.01; 10% cost-inclusive cap; daily10%/2 losses; cooldown2'),
        window=dict(start=str(START), end_rule='window_end(last_quote_utc): exclusive end at last complete UTC day', finalize='True: open position at end liquidated END_OF_SAMPLE, reported separately'),
        frame='single frame from input/bars.csv starting 2026-08-02 22:15 UTC (Aug-Oct old forward zips + new monthly zips); EMA200 frame-start dependence disclosed',
        views=dict(costs=list(COSTS), swaps={k: dict(swap_long=v['swap_long'], swap_short=0.0, point=0.001, triple='Wed->Thu') for k, v in SWAPS.items()}, primary_swap=PRIMARY,
                   swap_sources={'br474': 'broker probe 2026-11-17T11:19Z, owner-approved in cost renewal v4 (docs/reviews/2026-11-17-c22-cost-renewal-v4.md)', 'vm490': 'docs/ops/c22-selected-demo.md:10 owner-approved 2026-10-28 (superseded)', 'arch567': 'matrix protocol broker (archived)'}),
        maturity=dict(days=MATURE_DAYS, native_trades_primary_base=MATURE_SIGNALS, rule='verdict only when (end-start)>=28d AND native trades in br474|base >=20; earlier runs are INTERIM, no verdict'),
        verdict=dict(per_profile_vs_native='NOT_EXERCISED if ledger identical to native in br474|base and br474|stress; else FORWARD_CONSISTENT iff in both: net>=native AND maxDD<=native; else FORWARD_INCONSISTENT. vm490 and arch567 reported, not decisive.',
                     floor_vs_candidate='same rule floor03 vs candidate, reported separately', absolute='final_balance vs $200 reported, no pass/fail'),
        causality='each run, br474 base+stress: native/candidate/floor03 prefix runs at Wed 12:00 and Sat 00:00 cutoffs (finalize=False, ticks truncated, indicators re-prepared from bars before cutoff) must reproduce full-run admission events before cutoff; any mismatch or zero cutoffs -> INVALID',
        input_integrity='build(): manifest removed first; previous build must be byte prefix of new build; run(): every input artifact re-hashed vs manifest; engine module set = transitive closure pinned; reports never overwritten (name includes manifest sha)',
        prior_peek='native/B2/AB were run on 2026-10-24..11-11 earlier (seen). v1 protocol 173c07a8 produced one INTERIM report on 2026-10-24..11-17 where all three profiles had identical ledgers (8 SELL trades, risk<$25, floor not binding); review then found integrity defects and the vacuous-equality verdict, fixed in v2 before any verdict. Profiles, account, views, maturity and comparison thresholds unchanged from v1. v3 (2026-11-17, owner request): primary swap changed from vm490 to broker -474.3 after the cost renewal showed the broker rate; v2 INTERIM (identical ledgers, all SELL, swap_short 0) unaffected by swap_long; no other change.',
        owner_constraints='real money PROHIBITED; no VM change; criteria fixed, no post-hoc change; no reselection on forward data',
        hashes={**{s: sha(ROOT / s) for s in src}, 'shadow.py': sha(__file__)})
    p.write_text(json.dumps(proto, indent=1)); (HERE / 'protocol.sha256').write_text(sha(p)); print('FROZEN', sha(p))


class FloorGate:
    def __init__(s, events): s.veto = NativeAdmissionVeto(events)
    def __call__(s, row, ms, bal, led):
        r = s.veto(row, ms, bal, led)
        return r or ('vol_floor' if 250.0 * row.atr / row.close < FLOOR else None)


def ctx():
    matrix = json.loads((ROOT / MATRIX).read_text()); seed = json.loads((ROOT / SEED).read_text())
    raw = load_bars(INP / 'bars.csv'); frame, base_rules = prepare(raw, seed)
    rules = replace(base_rules, **json.loads((ROOT / NATIVE_CELL).read_text())['case']['rules'])
    tape = [np.load(INP / 'tape' / f'{n}.npy', mmap_mode='r') for n in ('time', 'bid', 'ask')]
    return dict(matrix=matrix, raw=raw, frame=frame, rules=rules, tape=tape, recipe=config_id(seed), costs={v: Costs(**matrix['views'][v]) for v in COSTS})


def one(c, swap_key, cost, end, profile, events=None, finalize=True, tape=None, frame=None):
    broker = {**c['matrix']['broker'], **SWAPS[swap_key]}
    opts = dict(start=START, end=end, swap_policy=SwapPolicy.from_broker(broker), entry_recipe_id=c['recipe'], finalize=finalize)
    if profile != 'native':
        opts.update(CAND, gate=NativeAdmissionVeto(events) if profile == 'candidate' else FloorGate(events), gate_name=f'forward-shadow/{profile}/{swap_key}-{cost}')
    return replay(frame if frame is not None else c['frame'], tape or c['tape'], broker, c['rules'], c['costs'][cost], **opts)


def ev_key(e): return json.dumps(e, sort_keys=True, default=str)


def causality(c, swap_key, cost, end, full):
    """Prefix check at Wed 12:00 and Sat 00:00 cutoffs: ticks truncated AND indicators re-prepared from bars before cutoff.
    native/candidate/floor03 admission events before cutoff must equal the full run's."""
    out = []; t = c['tape'][0]; seed = json.loads((ROOT / SEED).read_text())
    cuts = sorted([START + pd.Timedelta(days=7 * k + 4, hours=12) for k in range(60)] + [START + pd.Timedelta(days=7 * k) for k in range(1, 60)])
    for cut in [x for x in cuts if x < end]:
        n = int(np.searchsorted(t, cut.value // 10**6)); tp = [a[:n] for a in c['tape']]
        fr = prepare(c['raw'].loc[c['raw'].index < cut], seed)[0]
        pn = one(c, swap_key, cost, cut, 'native', finalize=False, tape=tp, frame=fr)
        row = dict(cutoff=str(cut))
        pre = lambda evs: [ev_key(e) for e in evs if pd.Timestamp(e['time_utc']) < cut]
        row['native'] = pre(pn['admission_events']) == pre(full['native']['admission_events'])
        for prof in ('candidate', 'floor03'):
            pc = one(c, swap_key, cost, cut, prof, events=pn['admission_events'], finalize=False, tape=tp, frame=fr)
            row[prof] = pre(pc['admission_events']) == pre(full[prof]['admission_events'])
        out.append(row)
    return out


def engine_files():
    """Every repo module actually loaded (transitive closure of imports), as repo-relative paths."""
    out = set()
    for m in list(sys.modules.values()):
        f = getattr(m, '__file__', None)
        if f and Path(f).resolve().is_relative_to(ROOT / 'scripts'): out.add(str(Path(f).resolve().relative_to(ROOT)))
    return sorted(out)


def run():
    proto = HERE / 'protocol.json'; psha = (HERE / 'protocol.sha256').read_text().strip(); assert sha(proto) == psha, 'protocol changed'
    P = json.loads(proto.read_text())
    for s, h in P['hashes'].items():
        f = HERE / s if s == 'shadow.py' else ROOT / s
        assert sha(f) == h, ('source drift', s)
    man = json.loads((INP / 'manifest.json').read_text()); assert man['overlap_bar_parity'] and man['overlap_tick_parity']
    for rel, h in man['artifacts'].items(): assert sha(INP / rel) == h, ('input artifact drift', rel)
    end = window_end(pd.Timestamp(man['last_quote_utc'])); c = ctx(); cells, caus = {}, {}
    pinned = {k for k in P['hashes'] if k.startswith('scripts/')}
    assert set(engine_files()) == pinned, ('engine module set changed', set(engine_files()) ^ pinned)
    for sk in SWAPS:
        for cost in COSTS:
            nat = one(c, sk, cost, end, 'native'); ev = nat['admission_events']
            res = {'native': nat, 'candidate': one(c, sk, cost, end, 'candidate', ev), 'floor03': one(c, sk, cost, end, 'floor03', ev)}
            for name, r in res.items():
                s = summary(r, BAL); L = s.pop('ledger')
                s['ledger'] = [dict(entry_utc=str(t['entry_time_utc']), exit_utc=str(t['exit_time_utc']), side='BUY' if t['direction'] == 1 else 'SELL',
                                    reason=t['reason'], protected=bool(t['protection_active']), risk_usd=round(t['risk_usd'], 2), swap=round(t['swap_usd'], 2), net=round(t['net'], 2)) for t in L]
                s['end_of_sample'] = [x for x in s['ledger'] if x['reason'] == 'END_OF_SAMPLE']
                cells[f'{name}|{sk}|{cost}'] = s
                print(f"{name:9s} {sk:7s} {cost:6s} net {s['net']:+8.2f} final {s['final_balance']:8.2f} dd {s['dd']:5.1f} n {s['trades']:3d} rej {dict((k, x) for k, x in s['rejections'].items() if x)}", flush=True)
            if sk == PRIMARY: caus[cost] = causality(c, sk, cost, end, res)
    days = (end - START).days; ntr = cells[f'native|{PRIMARY}|base']['trades']
    mature = days >= MATURE_DAYS and ntr >= MATURE_SIGNALS
    valid = bool(caus) and all(x['native'] and x['candidate'] and x['floor03'] for v in caus.values() for x in v) and all(len(v) > 0 for v in caus.values())
    same = lambda a, b: all(cells[f'{a}|{PRIMARY}|{v}']['ledger'] == cells[f'{b}|{PRIMARY}|{v}']['ledger'] for v in COSTS)
    def judge(a, b): return 'NOT_EXERCISED' if same(a, b) else ('FORWARD_CONSISTENT' if cmp(a, b) else 'FORWARD_INCONSISTENT')
    def cmp(a, b): return all(cells[f'{a}|{PRIMARY}|{v}']['net'] >= cells[f'{b}|{PRIMARY}|{v}']['net'] - 1e-9 and cells[f'{a}|{PRIMARY}|{v}']['dd'] <= cells[f'{b}|{PRIMARY}|{v}']['dd'] + 1e-9 for v in COSTS)
    verdict = 'INVALID' if not valid else ('INTERIM' if not mature else {'candidate': judge('candidate', 'native'), 'floor03': judge('floor03', 'native'), 'floor03_vs_candidate': judge('floor03', 'candidate')})
    REP.mkdir(exist_ok=True); out = REP / f"{end.date()}-{sha(INP / 'manifest.json')[:12]}.json"
    if out.exists(): raise SystemExit(f'report exists, refusing overwrite: {out}')
    out.write_text(json.dumps(dict(protocol_sha256=psha, input_manifest_sha256=sha(INP / 'manifest.json'), window=[str(START), str(end)], days=days,
                                   native_trades_primary_base=ntr, mature=mature, causality=caus, verdict=verdict, cells=cells), indent=1, default=str))
    print('WINDOW', START, end, 'days', days, 'native_trades', ntr, 'mature', mature, 'causality_ok', valid); print('VERDICT', verdict); print('WROTE', out)


if __name__ == '__main__':
    {'build': build, 'freeze': freeze, 'run': run}[sys.argv[1]]()
