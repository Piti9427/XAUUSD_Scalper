"""Bounded, hash-frozen $200 campaign. Offline only; artifacts stay in runs/."""

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np
import pandas as pd

from .breakout_models import Costs
from .breakout_replay import replay as native_replay
from .c22_frequency_adapter import prepare, validate, config_id
from .c22_frequency_data import load_bars
from .c22_profit_preservation import passes, replay, select
from .rollover import SwapPolicy


ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    'w2022': 'runs/c22-26b8-asia-holdout-2020-2022/input',
    'w2324': '.claude/worktrees/github-issues-review-69212b/runs/c22-two-slot-loop-2026-11-01/holdout/input',
    'disc': 'runs/c22-real-data-audit-2026-10-24/input',
}
SEGMENTS = {
    '2020': ('w2022', '2020-01-01', '2021-01-01'),
    '2021': ('w2022', '2021-01-01', '2022-01-01'),
    '2022': ('w2022', '2022-01-01', '2023-01-01'),
    '2023': ('w2324', '2023-01-01', '2024-01-01'),
    '2024a': ('w2324', '2024-01-01', '2024-09-01'),
    '2024b25': ('disc', '2024-09-01', '2026-01-01'),
    '2026': ('disc', '2026-01-01', '2026-10-24'),
}
SEED = 'config/research-c22-terminal-profit-9e511d195c52ef3d.json'
MATRIX = 'runs/c22-matrix-tuning-2026-10-25/protocol.json'
NATIVE_CELL = 'runs/c22-matrix-tuning-2026-10-25/cells/26b8bcd69e043653-fee-raw.json'
CATALOG = {'native': {}, 'buy_be_1R': {'buy_be': [1.0, 5]},
           'buy_after_loss': {'gate': 'buy_after_loss'}}
NATIVE_ENTRY = dict(strategy='reward156', formula='archived', rsi_period=7,
                    rsi_threshold=30, sell_lookback=48, sell_ema=50,
                    buy_ema=50, macro_span=200, entry_session='all')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    payload = json.dumps(value, indent=2, allow_nan=False)
    with path.open('x') as stream:
        stream.write(payload + '\n')


def guard():
    if shutil.disk_usage(ROOT).free < 2 * 1024**3:
        raise RuntimeError('less than 2 GiB free; campaign stopped')


def require_native_reference(catalog):
    """Prevent a changed candidate from silently becoming the named benchmark."""
    if not isinstance(catalog, dict) or catalog.get('native') != {}:
        raise ValueError('native reference must exist with an empty spec')


def require_native_entry_recipe(seed):
    """Pin historical 26b8 signals independently of its exit/risk RulesID."""
    if any(seed.get(key) != value for key, value in NATIVE_ENTRY.items()):
        raise ValueError('native reference entry recipe mismatch')


def freeze(output, *, catalog=None, parent=None):
    chosen_catalog = catalog if catalog is not None else CATALOG
    require_native_reference(chosen_catalog)
    require_native_entry_recipe(json.loads((ROOT / SEED).read_text()))
    guard()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'protocol.json').exists():
        raise ValueError('protocol already exists; never overwrite a frozen run')
    paths = [ROOT / p for p in (SEED, MATRIX, NATIVE_CELL)]
    paths += list((ROOT / 'scripts').rglob('*.py'))
    for source in INPUTS.values():
        paths += [ROOT / source / 'bars.csv']
        paths += [ROOT / source / 'tape' / (k + '.npy') for k in ('time', 'bid', 'ask')]
    protocol = dict(
        schema='c22-profit-preservation-200-v1', frozen_utc=datetime.now(timezone.utc).isoformat(),
        rules_id='26b8bcd69e043653', initial_balance=200, fixed_volume=0.01, cap=0.1,
        views=['base', 'stress'], inputs=INPUTS, segments=SEGMENTS,
        catalog=chosen_catalog, parent=parent, native_signal_reference=NATIVE_ENTRY,
        gates='every segment net >= native and Max DD <= native, both views; some net strictly improves',
        precision='raw USD and percentage-point DD; numerical tolerance 1e-8',
        selection='LOYO training-only strict gate; rank maximin view sum net delta; lexical tie; native fallback',
        continuous='start $200 once; globally prepared indicators; account state carry; final liquidation only; net >= native, DD <= native, min equity >= native, cap rejection span <= native',
        costs_status='COST_INCONCLUSIVE: archived current-spec sensitivity, not verified historical or current broker costs',
        swap_calendar='UTC midnight, preceding business day; Wednesday triple posts Thursday; weekend zero weights',
        iterations='one primary and at most one attribution-derived iteration per mechanism; no combined families',
        data_status='all historical data already seen; no new forward evidence',
        resource_policy='one process; mmap ticks; check >=2GiB free before each replay',
        artifacts={str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))},
    )
    write(output / 'protocol.json', protocol)
    (output / 'protocol.sha256').write_text(digest(output / 'protocol.json') + '\n')
    for name in protocol['artifacts']:
        if name.endswith('.py'):
            snapshot = output / 'source_snapshot' / name
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, snapshot)
    print('FROZEN', digest(output / 'protocol.json'), flush=True)


def summary(result, initial):
    ledger = result['ledger']
    equity = [initial] + [e['equity_usd'] for e in result['equity']]
    net = sum(t['net'] for t in ledger)
    events = result.get('admission_events', [])
    first = last = None
    span = 0.0
    for event in events:
        if event['reason'] == 'risk_cap':
            now = pd.Timestamp(event['time_utc'])
            first = first if first is not None else now
            last = now
            span = max(span, (last - first).total_seconds() / 86400)
        else:
            first = last = None
    return dict(net=float(net), dd=result['max_dd_pct'], minimum_equity=float(min(equity)),
                final_balance=float(result['final_balance']), trades=len(ledger),
                rejections=result['rejections'], cap_rejection_span_days=span,
                cap_span_note='consecutive observed risk-cap events only; not proof of continuous lock',
                buy_net=sum(t['net'] for t in ledger if t['direction'] == 1),
                sell_net=sum(t['net'] for t in ledger if t['direction'] == -1),
                swap=sum(t['swap_usd'] for t in ledger), ledger=ledger)


def gate_for(name):
    if name is None:
        return None
    if name not in ('buy_after_loss', 'buy_after_buy_loss'):
        raise ValueError('unknown gate')

    def gate(row, ms, balance, ledger):
        if row.direction != 1:
            return None
        day = ms // 86400000
        for trade in reversed(ledger):
            if pd.Timestamp(trade['exit_time_utc']).value // 10**6 // 86400000 < day:
                break
            if trade['net'] < 0 and (name == 'buy_after_loss' or trade['direction'] == 1):
                return name
        return None
    return gate


def entry_recipe(seed, spec):
    """Allow owner-authorized C22 entry parameters; keep risk/exit keys locked."""
    overrides = spec.get('entry_overrides', {})
    if not isinstance(overrides, dict) or set(overrides) - {
        'rsi_period', 'rsi_threshold', 'sell_lookback', 'buy_ema', 'sell_ema', 'entry_session',
        'macro_span'
    }:
        raise ValueError('unsupported entry override')
    config = seed | overrides
    validate(config)
    return config


def evaluate(output):
    p = json.loads((output / 'protocol.json').read_text())
    require_native_reference(p.get('catalog'))
    sha = digest(output / 'protocol.json')
    if (output / 'protocol.sha256').read_text().strip() != sha:
        raise ValueError('protocol drift')
    if (output / 'result.json').exists():
        raise ValueError('completed output exists; do not overwrite results')
    for path, expected in p['artifacts'].items():
        if digest(ROOT / path) != expected:
            raise ValueError('source/input drift: ' + path)
    print('VERIFIED source and input hashes', flush=True)
    matrix = json.loads((ROOT / MATRIX).read_text())
    broker = matrix['broker']
    swap = SwapPolicy.from_broker(broker)
    seed = json.loads((ROOT / SEED).read_text())
    require_native_entry_recipe(seed)
    tapes, raw = {}, {}
    for key, path in p['inputs'].items():
        folder = ROOT / path
        raw[key] = load_bars(folder / 'bars.csv')
        tapes[key] = [np.load(folder / 'tape' / (k + '.npy'), mmap_mode='r')
                      for k in ('time', 'bid', 'ask')]
    frames = {key: prepare(bars, seed)[0] for key, bars in raw.items()}
    _, base_rules = prepare(raw['disc'], seed)
    rules = replace(base_rules, **json.loads((ROOT / NATIVE_CELL).read_text())['case']['rules'])
    if hashlib.sha256(json.dumps(asdict(rules), sort_keys=True).encode()).hexdigest()[:16] != p['rules_id']:
        raise ValueError('native RulesID mismatch')
    costs = {v: Costs(**matrix['views'][v]) for v in p['views']}
    continuous_bars = pd.concat([raw[t].loc[(raw[t].index >= pd.Timestamp(a, tz='UTC'))
                                          & (raw[t].index < pd.Timestamp(b, tz='UTC'))]
                                 for t, a, b in p['segments'].values()])
    continuous_frame, _ = prepare(continuous_bars, seed)
    cells: dict[str, dict[tuple[str, str], dict[str, Any]]] = {name: {} for name in p['catalog']}
    continuous = {}
    parity = {}
    recipes = {}
    (output / 'cells').mkdir(exist_ok=True)
    for name, spec in p['catalog'].items():
        recipe = entry_recipe(seed, spec)
        recipes[name] = dict(entry_recipe_id=config_id(recipe), config=recipe,
                             purpose='Signal preparation only; effective risk/exits use control Rules plus catalog overrides.')
        case_frames = frames if recipe == seed else {key: prepare(bars, recipe)[0]
                                                     for key, bars in raw.items()}
        case_continuous_frame = continuous_frame if recipe == seed else prepare(continuous_bars, recipe)[0]
        for view in p['views']:
            state = None
            all_ledger, all_equity, all_events = [], [], []
            counts: dict[str, int] = {}
            for seg, (tape, a, b) in p['segments'].items():
                guard()
                start, end = pd.Timestamp(a, tz='UTC'), pd.Timestamp(b, tz='UTC')
                options = dict(buy_be=spec.get('buy_be'), gate=gate_for(spec.get('gate')),
                               gate_name=spec.get('gate', 'native'),
                               buy_be_max_risk_pct=spec.get('buy_be_max_risk_pct'),
                               buy_swap_be_fraction=spec.get('buy_swap_be_fraction', 0.0),
                               buy_swap_be_min_cost_r=spec.get('buy_swap_be_min_cost_r', 0.0),
                               buy_target_rr=spec.get('buy_target_rr'),
                               sell_target_rr=spec.get('sell_target_rr'),
                               min_sell_target_risk_usd=spec.get('min_sell_target_risk_usd'),
                               conditional_sell_protect_after_r=spec.get('conditional_sell_protect_after_r'),
                               entry_recipe_id=config_id(recipe), entry_guard=spec.get('entry_guard'),
                               min_buy_target_risk_pct=spec.get('min_buy_target_risk_pct'),
                               buy_stop_atr=spec.get('buy_stop_atr'), sell_stop_atr=spec.get('sell_stop_atr'))
                args = (case_frames[tape], tapes[tape], broker, rules, costs[view])
                result = replay(*args, start=start, end=end, swap_policy=swap, **options)
                if name == 'native':
                    control = native_replay(*args, start=start, end=end, swap_policy=swap,
                                            capture_events=True)
                    parity[(seg, view)] = bool(control['ledger'] == result['ledger']
                                          and control['admission_events'] == result['admission_events']
                                          and control['max_dd_pct'] == result['max_dd_pct']
                                          and control['final_balance'] == result['final_balance'])
                    if not parity[(seg, view)]:
                        raise ValueError('native parity failed')
                    del control
                cell = summary(result, 200)
                if not np.isclose(cell['final_balance'], 200 + cell['net'], rtol=0, atol=1e-8):
                    raise ValueError('ledger accounting failed')
                if any(t['volume'] != .01 or t['risk_pct'] > 10 + 1e-8 for t in result['ledger']):
                    raise ValueError('risk/sizing invariant failed')
                cells[name][(seg, view)] = cell
                write(output / 'cells' / f'{name}-{seg}-{view}.json', cell)
                del result
                # A single account across all boundaries; no end-of-segment exit.
                result = replay(case_continuous_frame, tapes[tape], broker, rules, costs[view],
                                start=start, end=end, swap_policy=swap, state=state,
                                finalize=seg == list(p['segments'])[-1], **options)
                state = result['carry_state']
                all_ledger.extend(result['ledger'])
                all_equity.extend(result['equity'])
                all_events.extend(result['admission_events'])
                for k, value in result['rejections'].items():
                    counts[k] = counts.get(k, 0) + value
                print(name, seg, view, 'net', round(cell['net'], 2),
                      'DD', round(cell['dd'], 2), 'continuous balance',
                      round(result['final_balance'], 2), flush=True)
            merged = dict(result, ledger=all_ledger, equity=all_equity,
                          admission_events=all_events, rejections=counts)
            cont = summary(merged, 200)
            if not np.isclose(cont['final_balance'], 200 + cont['net'], rtol=0, atol=1e-8):
                raise ValueError('continuous accounting failed')
            continuous[(name, view)] = cont
            write(output / 'cells' / f'{name}-continuous-{view}.json', cont)
    folds = {held: select(cells, [g for g in p['segments'] if g != held]) for held in p['segments']}
    chosen = select(cells, list(p['segments']))
    heldout = {(g, v): cells[folds[g]][(g, v)] for g in p['segments'] for v in p['views']}
    cont_pass = all(continuous[(chosen, v)]['net'] >= continuous[('native', v)]['net'] - 1e-8
                    and continuous[(chosen, v)]['dd'] <= continuous[('native', v)]['dd'] + 1e-8
                    and continuous[(chosen, v)]['minimum_equity'] >= continuous[('native', v)]['minimum_equity'] - 1e-8
                    and continuous[(chosen, v)]['cap_rejection_span_days'] <= continuous[('native', v)]['cap_rejection_span_days'] + 1e-8
                    for v in p['views'])
    compact = lambda rows: {'|'.join(k): {a: b for a, b in row.items() if a != 'ledger'}
                            for k, row in rows.items()}
    out = dict(protocol_sha256=sha, rules=asdict(rules), costs={k: asdict(v) for k, v in costs.items()},
               swap=asdict(swap), entry_recipes=recipes, status=p['costs_status'], parity={'|'.join(k): v for k, v in parity.items()},
               cells={n: compact(rows) for n, rows in cells.items()}, continuous=compact(continuous),
               folds=folds, chosen=chosen,
               passing=[n for n in cells if n != 'native' and passes(cells[n], cells['native'])],
               verdict='RESEARCH_PASS' if chosen != 'native' and passes(heldout, cells['native']) and cont_pass else 'FAIL')
    write(output / 'result.json', out)
    print('VERDICT', out['verdict'], 'LOYO', folds, 'chosen', chosen, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'run'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'runs'):
        raise ValueError('campaign output must be under runs/')
    if args.action == 'freeze':
        freeze(output)
    else:
        evaluate(output)


if __name__ == '__main__':
    main()
