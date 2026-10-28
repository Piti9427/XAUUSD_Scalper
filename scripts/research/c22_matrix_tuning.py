"""Two-round, source-bound C22 coordinate tuning; offline research only."""

import argparse
from dataclasses import asdict, replace
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from scripts.research.c22_performance_campaign import (
    ROOT, OLD, INPUT, SEED, BASE_ID, VIEWS, read, write, sha,
    diagnostics, qualifies, score, cent_engine,
)
from scripts.research.breakout_models import Costs
from scripts.research.breakout_replay import replay
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.rollover import SwapPolicy

PARENT = ROOT / 'runs/c22-performance-refine-2026-10-25'
FIRST = ROOT / 'runs/c22-performance-2026-10-25'
SPEC = ROOT / 'specs/c22-matrix-tuning-2026-10-25.md'
DOMAINS = {
    'buy_target_rr': (1.35, 1.5, 2.0, 3.0),
    'target_rr': (1.25, 1.35, 1.4, 1.45, 1.5, 2.0),
    'cooldown_bars': (0, 1, 2, 4),
    'stop_atr': (1.5, 2.0, 2.5),
    'buy_stop_atr': (1.5, 2.0, 2.5),
    'protect_after_r': (0.5, 1.0, 1.5),
    'buy_protect_mode': ('off', 'break_even'),
}


def identity(rules):
    return hashlib.sha256(json.dumps(asdict(rules), sort_keys=True).encode()).hexdigest()[:16]


def neighbors(parent, seen):
    result = []
    for key, values in DOMAINS.items():
        for value in values:
            if getattr(parent, key) == value:
                continue
            rules = replace(parent, **{key: value})
            name = identity(rules)
            if name not in seen:
                result.append(dict(name=name, parent=identity(parent), parameter=key,
                                   before=getattr(parent, key), after=value, rules=asdict(rules)))
    assert len({c['name'] for c in result}) == len(result)
    return result


def closing_recovery(result, last_quote):
    """Closing cash episodes only; an idle peak interval is not a drawdown."""
    peak = cash = 200.0
    peak_time = pd.Timestamp(result['start_utc'])
    active = None
    episodes = []
    for trade in result['ledger']:
        cash += trade['net']
        stamp = pd.Timestamp(trade['exit_time_utc'])
        if cash < peak and active is None:
            active = dict(start=peak_time.isoformat(), first_underwater_exit=stamp.isoformat(),
                          previous_peak=peak)
        if cash >= peak:
            if active is not None:
                episodes.append(dict(active, end=stamp.isoformat(), recovered_to=cash,
                                     days=(stamp-peak_time).total_seconds()/86400))
                active = None
            peak, peak_time = cash, stamp
    return dict(longest_completed=max(episodes, key=lambda e:e['days'], default=None),
                completed_count=len(episodes), ongoing=(dict(active, balance=cash,
                days=(pd.Timestamp(last_quote)-peak_time).total_seconds()/86400) if active else None))


def run(out):
    first = read(FIRST/'protocol.json')
    parent = read(PARENT/'COMPLETE.json')
    assert parent['selected']['name'] == 'stop25_cooldown4'
    for root in (FIRST, PARENT):
        for name, digest in read(root/'COMPLETE.json')['artifacts'].items():
            assert sha(root/name) == digest, name
    pins = dict(read(PARENT/'protocol.json')['source_pins'])
    for path in (Path(__file__), SPEC):
        pins[str(path.relative_to(ROOT))] = sha(path)
    for name, digest in pins.items():
        assert sha(ROOT/name) == digest, name
    for name, digest in first['input_hashes'].items():
        assert sha(INPUT/name) == digest, name
    floors, bound = {}, {}
    for guard in ('raw', 'cent'):
        floors[guard] = {}
        for view in VIEWS:
            path = OLD/'cells'/f'{BASE_ID}-{view}{"-cent" if guard=="cent" else ""}.json'
            assert sha(path) == read(OLD/'integrity'/path.name)['sha256']
            bound[str(path.relative_to(ROOT))] = sha(path)
            floors[guard][view] = read(path)['metrics']
    protocol = dict(schema=1, domains=DOMAINS, max_rounds=2, sources=pins,
                    input_hashes=first['input_hashes'], broker=first['broker'], views=first['views'],
                    start=first['start'], end=first['end'], original_floors=floors,
                    benchmark_hashes=bound, parent_complete_sha256=sha(PARENT/'COMPLETE.json'),
                    input_manifest_sha256=sha(INPUT/'manifest.json'), holdout=False,
                    cost_status='COST_INCONCLUSIVE', ranking='base net, stress net, smaller max DD',
                    max_dd_pct=40, cent_review='all raw-qualified candidates')
    # Normalize tuples before resume comparison.
    protocol = json.loads(json.dumps(protocol))
    if (out/'protocol.json').exists():
        assert read(out/'protocol.json') == protocol, 'Protocol drift'
    else:
        write(out/'protocol.json', protocol)
        for name, digest in pins.items():
            target = out/'source_snapshot'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, target)
            assert sha(target) == digest
    if (out/'COMPLETE.json').exists():
        for name, digest in read(out/'COMPLETE.json')['artifacts'].items():
            assert sha(out/name) == digest, name
        print('Already complete; hashes verified', flush=True)
        return
    spec = importlib.util.spec_from_file_location('matrix_tuning_audit', ROOT/'runs/c22-real-data-audit-2026-10-24/run_audit_v2.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    frame, base_rules = prepare(load_bars(INPUT/'bars.csv'), read(SEED))
    incumbent_rules = replace(base_rules, **parent['selected']['rules'])
    original = dict(name=identity(incumbent_rules), parent=None, parameter='incumbent',
                    before=None, after=None, rules=asdict(incumbent_rules))
    broker = protocol['broker']
    swap = SwapPolicy.from_broker(broker)
    assert swap is not None
    ticks = [np.load(INPUT/'tape'/f'{key}.npy', mmap_mode='r') for key in ('time','bid','ask')]
    costs = {view:Costs(**protocol['views'][view]) for view in VIEWS}
    last = read(INPUT/'manifest.json')['last_quote_utc']
    cells, cases = {}, {original['name']:original}
    cent = cent_engine()

    def execute(case, view, guard='raw', repeat=False):
        key = f'{case["name"]}-{view}-{guard}'
        folder = 'repeats' if repeat else 'cells'
        target = out/folder/f'{key}.json'
        proof = out/(folder+'-integrity')/f'{key}.json'
        if target.exists():
            assert sha(target) == read(proof)['sha256'], key
            cell = read(target)
            assert cell['case'] == case
        else:
            begun = time.monotonic()
            rules = replace(base_rules, **case['rules'])
            assert rules.sizing_mode == 'fixed' and rules.risk_cap == .1
            assert rules.daily_loss_limit == .1 and rules.max_daily_losses == 2
            result = (cent if guard=='cent' else replay)(frame, ticks, broker, rules, costs[view],
                start=pd.Timestamp(protocol['start']), end=pd.Timestamp(protocol['end']),
                swap_policy=swap, capture_events=True, capture_context=True)
            checks = audit.independent_audit(result, broker, costs[view])
            metrics = audit.metrics(result)
            minimum = min([200.0]+[x['equity_usd'] for x in result['equity']])
            metrics.update(min_observed_equity=minimum, survival=bool(minimum>0 and
                result['final_balance']>0 and not result['rejections']['bankrupt']))
            dx = diagnostics(result, last)
            dx['actual_closing_recovery'] = closing_recovery(result, last)
            cell = dict(case=case, view=view, guard=guard, result=result, metrics=metrics,
                        diagnostics=dx, checks=checks)
            write(target, cell)
            write(proof, dict(sha256=sha(target)))
            print(folder, key, 'net', round(metrics['net_usd'],4), 'DD',
                  round(metrics['max_dd_pct'],4), 'seconds', round(time.monotonic()-begun,2), flush=True)
        if repeat:
            assert cell == cells[key], key
        else:
            cells[key] = cell
        return cell

    def metrics(case, guard):
        return {v:cells[f'{case["name"]}-{v}-{guard}']['metrics'] for v in VIEWS}

    for guard in ('raw', 'cent'):
        for view in VIEWS:
            cell = execute(original, view, guard)
            old_cell = read(PARENT/'cells'/f'stop25_cooldown4-{view}-{guard}.json')
            assert cell['result'] == old_cell['result'], 'Incumbent full replay parity'
    assert all(qualifies(metrics(original,g), floors[g]) for g in ('raw','cent'))
    current, seen, rounds = original, {original['name']}, []
    stop_reason = 'ROUND_BUDGET_REACHED'
    for number in (1,2):
        catalog = neighbors(replace(base_rules, **current['rules']), seen)
        frozen = dict(round=number, incumbent=current['name'], catalog=catalog,
                      previous_result_sha256=sha(out/'rounds'/f'{number-1}-result.json') if number>1 else None)
        path = out/'rounds'/f'{number}-catalog.json'
        if path.exists():
            assert read(path) == frozen, 'Round catalog drift'
        else:
            write(path, frozen)
        for case in catalog:
            cases[case['name']] = case
            for view in VIEWS:
                execute(case, view)
            seen.add(case['name'])
            write(out/'progress.json', dict(round=number, raw_cases=sum(k.endswith('base-raw') for k in cells),
                                          frozen_neighbors=len(catalog), phase='raw'))
        raw_pass = [c for c in catalog if qualifies(metrics(c,'raw'), floors['raw'])]
        for case in raw_pass:
            for view in VIEWS:
                execute(case, view, 'cent')
        accepted = [c for c in raw_pass if qualifies(metrics(c,'cent'), floors['cent'])]
        selected = min([current,*accepted], key=lambda c:(*score(metrics(c,'raw')), c['name']))
        changed = selected['name'] != current['name']
        result = dict(round=number, incumbent=current['name'], selected=selected['name'], improved=changed,
                      candidates=[c['name'] for c in catalog], raw_qualified=[c['name'] for c in raw_pass],
                      fully_qualified=[c['name'] for c in accepted])
        write(out/'rounds'/f'{number}-result.json', result)
        rounds.append(result)
        current = selected
        print('ROUND', number, 'selected', current['name'], 'improved', changed, flush=True)
        if not changed:
            stop_reason = 'NO_QUALIFIED_LOCAL_IMPROVEMENT'
            break
    for guard in ('raw','cent'):
        for view in VIEWS:
            execute(current, view, guard, repeat=True)
    all_qualified = [c for c in cases.values() if all(f'{c["name"]}-{v}-{g}' in cells for v in VIEWS for g in ('raw','cent'))
                     and all(qualifies(metrics(c,g), floors[g]) for g in ('raw','cent'))]
    assert current['name'] == min(all_qualified, key=lambda c:(*score(metrics(c,'raw')), c['name']))['name']
    summary = dict(status='COMPLETE_DISCOVERY', original=original['name'], selected=current['name'],
                   improved=current['name']!=original['name'], rounds=rounds, stop_reason=stop_reason,
                   cases=cases, qualified=[c['name'] for c in all_qualified], holdout=False,
                   cost_status='COST_INCONCLUSIVE', new_contracts=len(cases)-1,
                   raw_metrics={c['name']:metrics(c,'raw') for c in cases.values()},
                   cent_metrics={c['name']:metrics(c,'cent') for c in cases.values()
                                 if f'{c["name"]}-base-cent' in cells})
    write(out/'results.json', summary)
    write(out/'selected-research.json', dict(status='RESEARCH_ONLY', rules=current['rules'],
        rules_id=current['name'], signal_seed=read(SEED), protocol_sha256=sha(out/'protocol.json'),
        runtime_qualified=False, adapter_required=True, real_money='PROHIBITED'))
    paths = [p for folder in ('cells','cells-integrity','repeats','repeats-integrity','rounds')
             for p in (out/folder).glob('*.json')]
    paths += [out/n for n in ('protocol.json','results.json','selected-research.json')]
    write(out/'COMPLETE.json', dict(status='COMPLETE_DISCOVERY', selected=current['name'],
        new_contracts=len(cases)-1, economic_cells=len(cells), fresh_repeats=6,
        stop_reason=stop_reason, artifacts={str(p.relative_to(out)):sha(p) for p in paths}))
    print('COMPLETE', current['name'], stop_reason, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='runs/c22-matrix-tuning-2026-10-25')
    args = parser.parse_args()
    out = (ROOT/args.output).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Machine outputs must stay under runs/')
    out.mkdir(parents=True, exist_ok=True)
    with (out/'.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(out)


if __name__ == '__main__':
    main()
