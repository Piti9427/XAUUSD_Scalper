"""Independent artifact/accounting/closure audit for C22 learning-loop research."""

import argparse
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'runs/c22-real-data-audit-2026-10-24/input'
PARENT = ROOT / 'runs/c22-matrix-tuning-2026-10-25'
VIEWS = ('base', 'stress', 'fee')
GUARDS = ('raw', 'cent')


def read(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as stream:
        return json.load(stream)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def equal(left, right, label):
    assert math.isclose(left, right, abs_tol=1e-7, rel_tol=1e-11), (label, left, right)


def identity(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:16]


def loss(net, guard):
    assert guard in GUARDS
    return (Decimal(str(float(net))).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) < 0
            if guard == 'cent' else net < 0)


def qualify(metrics, floors):
    return set(metrics) == set(VIEWS) and all(
        m['survival'] and m['net_usd'] > 0 and m['max_dd_pct'] <= 40
        for m in metrics.values()
    ) and all(metrics[v]['net_usd'] + 1e-7 >= floors[v]['net_usd'] for v in ('base', 'stress'))


def score(metrics):
    return (-metrics['base']['net_usd'], -metrics['stress']['net_usd'],
            max(m['max_dd_pct'] for m in metrics.values()))


def ledger_risk(result, last_quote):
    """Independent downside summary; count and severity can describe different runs."""
    cash = peak = 200.0
    peak_time = pd.Timestamp(result['start_utc'])
    underwater = False
    completed_days = 0.0
    completed_count = 0
    streak = longest = 0
    run_net = 0.0
    run_start = None
    longest_net = longest_severity = 0.0
    worst_severity = 0.0
    for trade in result['ledger']:
        net = trade['net']
        if net < 0:
            if not streak:
                run_start = trade['entry_equity']
                run_net = 0.0
            streak += 1
            run_net += net
            if streak > longest:
                longest = streak
                longest_net = run_net
                longest_severity = -run_net / run_start * 100
            worst_severity = max(worst_severity, -run_net / run_start * 100)
        else:
            streak = 0
            run_start = None
        cash += net
        closed = pd.Timestamp(trade['exit_time_utc'])
        underwater = underwater or cash < peak
        if cash >= peak:
            if underwater:
                completed_days = max(completed_days, (closed - peak_time).total_seconds() / 86400)
                completed_count += 1
                underwater = False
            peak, peak_time = cash, closed
    ongoing_days = (pd.Timestamp(last_quote) - peak_time).total_seconds() / 86400 if underwater else 0.0
    minimum = min([200.0] + [mark['equity_usd'] for mark in result['equity']])
    return dict(dd=result['max_dd_pct'], count=longest, streak=longest, severity=worst_severity,
                recovery=max(completed_days, ongoing_days), completed_days=completed_days,
                ongoing_days=ongoing_days, completed_count=completed_count,
                longest_run_net=longest_net, longest_run_severity=longest_severity,
                min_equity=minimum)


class IndependentTapeAudit:
    """Point-mode swap/calendar and source-quote reconstruction, without replay imports."""

    def __init__(self, protocol, last_quote):
        self.protocol = protocol
        self.broker = protocol['broker']
        self.last_quote = last_quote
        broker = self.broker
        assert broker['swap_mode'] == 1
        assert broker['swap_rollover3days'] == 3
        days = pd.date_range(pd.Timestamp(protocol['start']).normalize(),
                             pd.Timestamp(protocol['end']).normalize(), freq='D')
        previous = (days.dayofweek.to_numpy() - 1) % 7
        weights = np.where(previous >= 5, 0, np.where(previous == 2, 3, 1))
        self.stamps = days.as_unit('ms').asi8
        self.accrued = np.r_[0.0, np.cumsum(weights)]
        self.times = np.load(DATA / 'tape/time.npy', mmap_mode='r')
        self.tape = {key: np.load(DATA / 'tape' / f'{key}.npy', mmap_mode='r')
                     for key in ('bid', 'ask')}

    def swap_value(self, trade, end):
        units = self.accrued[np.searchsorted(self.stamps, end, side='right')] - self.accrued[
            np.searchsorted(self.stamps, trade['entry_ms'], side='right')]
        broker = self.broker
        rate = broker['swap_long'] if trade['direction'] == 1 else broker['swap_short']
        return units * rate * broker['point'] * broker['trade_contract_size'] * trade['volume']

    def audit_cell(self, cell):
        result, metrics = cell['result'], cell['metrics']
        guard, view = cell['guard'], cell['view']
        assert guard in GUARDS and view in VIEWS
        rules, cost, trades = result['rules'], result['costs'], result['ledger']
        broker = self.broker
        assert result['initial_balance'] == 200
        assert result['start_utc'] == self.protocol['start']
        assert result['end_exclusive_utc'] == self.protocol['end']
        assert result['swap_policy'] == dict(long_points=broker['swap_long'],
            short_points=broker['swap_short'], point=broker['point'], triple_weekday=2)
        assert rules['sizing_mode'] == 'fixed' and rules['buy_sizing_mode'] in (None, 'fixed')
        assert rules['risk_cap'] == .1 and rules['daily_loss_limit'] == .1
        assert rules['max_daily_losses'] == 2 and rules['holding_mode'] == 'legacy'
        assert not rules['failed_closes'] and not rules['stagnant_bars']
        assert cost == self.protocol['views'][view]
        exits = np.array([pd.Timestamp(t['exit_time_utc']).value // 10**6 for t in trades], dtype=np.int64)
        prefix_cash = np.r_[200.0, 200.0 + np.cumsum([t['net'] for t in trades])]
        cash, counts, last_exit, cooldown_until = 200.0, Counter(), None, 0
        for trade in trades:
            born, closed = pd.Timestamp(trade['entry_time_utc']), pd.Timestamp(trade['exit_time_utc'])
            assert born.tzinfo and closed.tzinfo and born <= closed
            assert born.utcoffset().total_seconds() == closed.utcoffset().total_seconds() == 0
            assert last_exit is None or last_exit <= born
            assert trade['volume'] == .01
            equal(cash, trade['entry_equity'], 'entry cash')
            entry_ms, exit_ms = born.value // 10**6, closed.value // 10**6
            assert entry_ms == trade['entry_ms'] and entry_ms >= cooldown_until
            factor = broker['trade_contract_size'] * trade['volume']
            fee = cost['commission_per_lot'] * trade['volume']
            initial = (abs(trade['entry'] - trade['initial_stop']) + cost['slippage']) * factor + fee
            equal(initial, trade['risk_usd'], 'initial stop risk')
            equal(initial / cash * 100, trade['risk_pct'], 'initial risk percentage')
            assert trade['risk_pct'] <= trade['admission_cap_pct'] + 1e-8 <= 10 + 1e-8
            assert counts[str(born.date())] < rules['max_daily_losses']
            swap = self.swap_value(trade, exit_ms)
            equal(swap, trade['swap_usd'], 'calendar swap')
            net = trade['direction'] * (trade['exit'] - trade['entry']) * factor - fee + swap
            equal(net, trade['net'], 'trade net')
            equal(net / initial, trade['net_r'], 'trade net R')
            boundary = born.normalize().value // 10**6
            prior = int(np.searchsorted(exits, boundary, side='left'))
            baseline = float(prefix_cash[prior])
            if prior < len(trades):
                held = trades[prior]
                if held['entry_ms'] < boundary <= exits[prior]:
                    index = int(np.searchsorted(self.times, boundary))
                    stamp = int(self.times[index])
                    assert boundary <= stamp < boundary + 1000
                    direction = held['direction']
                    quote = float(self.tape['bid' if direction == 1 else 'ask'][index]) - direction * cost['extra_spread'] / 2
                    if held['reason'] == 'TP' and exits[prior] == stamp:
                        quote = held['target']
                    held_factor = broker['trade_contract_size'] * held['volume']
                    baseline += direction * (quote - held['entry']) * held_factor
                    baseline -= cost['commission_per_lot'] * held['volume']
                    baseline += self.swap_value(held, stamp)
            assert baseline - cash < baseline * rules['daily_loss_limit'] + 1e-7
            if loss(net, guard):
                counts[str(closed.date())] += 1
                cooldown_until = exit_ms + rules['cooldown_bars'] * 900000
            cash += net
            last_exit = closed
        equal(cash, result['final_balance'], 'final cash')
        equal(cash - 200, result['net_usd'], 'final net')
        for key in ('net_usd', 'final_balance', 'max_dd_pct'):
            equal(metrics[key], result[key], 'metric ' + key)
        minimum = min([200.0] + [mark['equity_usd'] for mark in result['equity']])
        equal(metrics['min_observed_equity'], minimum, 'minimum observed equity')
        assert metrics['survival'] == bool(minimum > 0 and cash > 0 and not result['rejections']['bankrupt'])
        equal(sum(t['swap_usd'] for t in trades), result['swap_usd'], 'total swap')
        assert result['trades'] == len(trades)
        risk = ledger_risk(result, self.last_quote)
        assert metrics['max_consecutive_losses'] == risk['count']
        diagnostics = cell.get('diagnostics', {})
        if diagnostics.get('worst_run_by_loss_pct'):
            equal(diagnostics['worst_run_by_loss_pct']['loss_pct_of_start_equity'], risk['severity'], 'worst-run severity')
        actual = diagnostics.get('actual_closing_recovery')
        if actual:
            assert actual['completed_count'] == risk['completed_count']
            equal(actual['longest_completed']['days'] if actual['longest_completed'] else 0,
                  risk['completed_days'], 'actual completed recovery')
            equal(actual['ongoing']['days'] if actual['ongoing'] else 0,
                  risk['ongoing_days'], 'actual ongoing drawdown age')
        return dict(entries=len(trades), metrics=metrics, risk=risk, rules=rules)

    def full_tick(self, cell):
        result, cost = cell['result'], cell['result']['costs']
        cash = peak = 200.0
        max_dd = 0.0
        minimum = 200.0
        quoted = 0
        for trade in result['ledger']:
            direction = trade['direction']
            factor = self.broker['trade_contract_size'] * trade['volume']
            fee = cost['commission_per_lot'] * trade['volume']
            entry = trade['entry_ms']
            exit_ms = pd.Timestamp(trade['exit_time_utc']).value // 10**6
            left = int(np.searchsorted(self.times, entry))
            raw = self.tape['bid' if direction == 1 else 'ask']
            a = int(np.searchsorted(self.times, exit_ms))
            b = int(np.searchsorted(self.times, exit_ms, side='right'))
            exit_quotes = raw[a:b] - direction * cost['extra_spread'] / 2
            if trade['reason'] == 'END_OF_SAMPLE':
                assert int(self.times[-1]) == exit_ms
                right = len(self.times)
                equal(float(exit_quotes[-1] - direction * cost['slippage']), trade['exit'], 'sample-end fill')
            else:
                assert trade['reason'] in ('SL', 'TP'), 'Unsupported selected exit contract'
                valid = (direction * (exit_quotes - trade['target']) >= 0 if trade['reason'] == 'TP' else
                    np.isclose(exit_quotes - direction * cost['slippage'], trade['exit'], atol=1e-8, rtol=0))
                matches = np.flatnonzero(valid)
                assert len(matches), 'Selected exit absent from source tape'
                right = a + int(matches[0]) + 1
            assert right > left
            equal(cash, trade['entry_equity'], 'full-tick entry cash')
            for cursor in range(left, right, 100000):
                stop = min(cursor + 100000, right)
                quote = raw[cursor:stop] - direction * cost['extra_spread'] / 2
                swap = self.swap_value(trade, self.times[cursor:stop])
                marks = cash - fee + direction * (quote - trade['entry']) * factor + swap
                if stop == right and trade['reason'] == 'TP':
                    marks[-1] = cash - fee + direction * (trade['target'] - trade['entry']) * factor + swap[-1]
                peaks = np.maximum.accumulate(np.r_[peak, marks])[1:]
                max_dd = max(max_dd, float(np.max((peaks - marks) / peaks)))
                peak = max(peak, float(marks.max()))
                minimum = min(minimum, float(marks.min()))
                quoted += len(marks)
            cash += trade['net']
            max_dd = max(max_dd, (peak - cash) / peak)
            peak, minimum = max(peak, cash), min(minimum, cash)
        equal(cash, result['final_balance'], 'full-tick final cash')
        equal(max_dd * 100, result['max_dd_pct'], 'full-tick DD')
        equal(minimum, cell['metrics']['min_observed_equity'], 'full-tick minimum equity')
        return dict(max_dd_pct=max_dd * 100, min_equity=minimum, final_cash=cash,
                    held_quote_observations=quoted)


RISK_FIELDS = ('dd', 'recovery', 'severity', 'streak')
BLOCKS = dict(core=('buy_target_rr', 'target_rr', 'cooldown_bars'),
              management=('buy_stop_atr', 'stop_atr', 'protect_after_r', 'buy_protect_mode'))
DOMAINS = dict(buy_target_rr=[1.35, 1.5, 2.0, 3.0],
               target_rr=[1.25, 1.35, 1.4, 1.45, 1.5, 2.0],
               cooldown_bars=[0, 1, 2, 4], stop_atr=[1.5, 2.0, 2.5],
               buy_stop_atr=[1.5, 2.0, 2.5], protect_after_r=[0.5, 1.0, 1.5],
               buy_protect_mode=['off', 'break_even'])
LANES = ('profit', 'repair')


def complete_rows(rows):
    return all(set(rows.get(guard, {})) == set(VIEWS) for guard in GUARDS)


def qualified_rows(rows, floors):
    return complete_rows(rows) and all(
        qualify({view: rows[guard][view]['metrics'] for view in VIEWS}, floors[guard])
        for guard in GUARDS)


def repair_eligible(rows, baseline):
    if not complete_rows(rows):
        return False
    return all(rows[guard][view]['metrics']['net_usd'] + 1e-7 >=
               baseline[guard][view]['metrics']['net_usd']
               for guard in GUARDS for view in ('base', 'stress')) and all(
        rows[guard][view]['risk'][field] <= baseline[guard][view]['risk'][field] + 1e-9
        for guard in GUARDS for view in VIEWS for field in RISK_FIELDS)


def reduced_risk(rows, baseline):
    return repair_eligible(rows, baseline) and any(
        rows[guard][view]['risk'][field] < baseline[guard][view]['risk'][field] - 1e-9
        for guard in GUARDS for view in VIEWS for field in RISK_FIELDS)


def objective(rows, lane):
    raw = {view: rows['raw'][view]['metrics'] for view in VIEWS}
    if lane == 'profit':
        return score(raw)
    assert lane == 'repair'
    return tuple(max(rows[guard][view]['risk'][field] for guard in GUARDS for view in VIEWS)
                 for field in RISK_FIELDS) + (-raw['base']['net_usd'], -raw['stress']['net_usd'])


def choose(current, names, summaries, lane, floors, baseline):
    accepted = [name for name in names if qualified_rows(summaries[name], floors) and
                (lane == 'profit' or repair_eligible(summaries[name], baseline))]
    assert current in accepted
    best = min(accepted, key=lambda name: (*objective(summaries[name], lane), name))
    return best if objective(summaries[best], lane) < objective(summaries[current], lane) else current


def expected_catalog(rules, block):
    result = []
    for values in itertools.product(*(DOMAINS[field] for field in BLOCKS[block])):
        candidate = dict(rules, **dict(zip(BLOCKS[block], values)))
        result.append(dict(name=identity(candidate), rules=candidate))
    return result


def payload(out, key, folder='cells'):
    assert folder in ('cells', 'repeats')
    parts = key.split('-')
    assert len(parts) == 3 and len(parts[0]) == 16
    assert all(character in '0123456789abcdef' for character in parts[0])
    assert parts[1] in VIEWS and parts[2] in GUARDS
    proof = read(out / (folder + '-integrity') / (key + '.json'))
    assert set(proof) == {'path', 'sha256', 'origin'}
    relative = Path(proof['path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    path = (ROOT / relative).resolve()
    assert path.is_relative_to((ROOT / 'runs').resolve())
    assert proof['origin'] in ('new', 'reused')
    if proof['origin'] == 'new':
        assert path == out / folder / (key + '.json.gz')
    else:
        assert folder == 'cells'
        assert path == PARENT / 'cells' / (key + '.json')
        assert read(PARENT / 'COMPLETE.json')['artifacts'][str(path.relative_to(PARENT))] == proof['sha256']
    assert sha(path) == proof['sha256'], key
    cell = read(path)
    rules = cell['result']['rules']
    assert identity(rules) == parts[0]
    assert cell['case']['name'] == parts[0] and cell['case']['rules'] == rules
    assert cell['view'] == parts[1] and cell['guard'] == parts[2]
    return cell, path, proof


def audit_closure(out, summary, summaries, floors, baseline, initial_names):
    """Replay only the declared search state machine, never the trading economics."""
    phases = summary['phases']
    current = {lane: summary['initial'] for lane in LANES}
    closed = {}
    active = set(initial_names)
    index = 0
    cycles = 0
    while True:
        cycles += 1
        assert cycles <= 2 * 5184 + 2
        assert cycles <= summary['cycles'], 'Claimed closure did not occur'
        for lane in LANES:
            promoted = choose(current[lane], active, summaries, lane, floors, baseline)
            if promoted != current[lane]:
                current[lane] = promoted
                closed.pop(lane, None)
            if closed.get(lane) == current[lane]:
                continue
            started = current[lane]
            for block in BLOCKS:
                assert index < len(phases), 'Missing complete block phase'
                phase = phases[index]
                number = index + 1
                frozen = read(out / 'phases' / f'{number:03}-catalog.json')
                assert read(out / 'phases' / f'{number:03}-result.json') == phase
                before = current[lane]
                assert phase['number'] == frozen['number'] == number
                assert phase['cycle'] == frozen['cycle'] == cycles
                assert phase['lane'] == frozen['lane'] == lane
                assert phase['block'] == frozen['block'] == block
                assert phase['incumbent'] == frozen['incumbent'] == before
                expected = expected_catalog(summary['cases'][before]['rules'], block)
                assert len(expected) == (96 if block == 'core' else 54)
                assert frozen['catalog'] == expected, 'Full conditional block omitted/changed'
                assert frozen['downside_before'] == {
                    guard: {view: summary['summaries'][before][guard][view]['risk'] for view in VIEWS}
                    for guard in GUARDS}
                for case in expected:
                    assert summary['cases'][case['name']] == case
                    assert set(summaries[case['name']].get('raw', {})) == set(VIEWS)
                raw_pass = [case['name'] for case in expected if qualify(
                    {view: summaries[case['name']]['raw'][view]['metrics'] for view in VIEWS}, floors['raw'])]
                full_pass = [case['name'] for case in expected if qualified_rows(summaries[case['name']], floors)]
                assert phase['raw_qualified'] == raw_pass
                assert phase['fully_qualified'] == full_pass
                active.update(case['name'] for case in expected)
                after = choose(before, active, summaries, lane, floors, baseline)
                assert phase['selected'] == after
                strict = objective(summaries[after], lane) < objective(summaries[before], lane)
                assert phase['improved'] == strict == (after != before)
                assert phase['objective_before'] == list(objective(summaries[before], lane))
                assert phase['objective_after'] == list(objective(summaries[after], lane))
                assert phase['visited_cases'] == len(active)
                current[lane] = after
                index += 1
            if current[lane] == started:
                closed[lane] = current[lane]
        if all(closed.get(lane) == current[lane] and
               choose(current[lane], active, summaries, lane, floors, baseline) == current[lane]
               for lane in LANES):
            break
    assert cycles == summary['cycles'] and index == len(phases)
    assert summary['selected'] == current and summary['closed'] == closed
    assert set(summary['visited']) == active
    for lane in LANES:
        for block in BLOCKS:
            expected = expected_catalog(summary['cases'][current[lane]]['rules'], block)
            assert all(case['name'] in active for case in expected)
            assert any(phase['lane'] == lane and phase['block'] == block and
                       phase['incumbent'] == phase['selected'] == current[lane] for phase in phases), \
                'Final lane lacks a full unchanged core/management cycle'
    return dict(cycles=cycles, phases=index, selected=current, closed=closed,
                visited_cases=len(active), scope='Conditional core96/management54 closure; not global5184 enumeration')


def run(out):
    completion = out / 'COMPLETE.json'
    assert completion.exists(), 'Learning campaign incomplete; audit cannot certify closure'
    complete_hash = sha(completion)
    complete = read(completion)
    protocol = read(out / 'protocol.json')
    summary = read(out / 'results.json')
    assert complete['status'] == summary['status'] == 'CONVERGED_BLOCK_SEARCH'
    assert protocol['domains'] == DOMAINS
    assert protocol['blocks'] == {key: list(value) for key, value in BLOCKS.items()}
    assert protocol['risk_fields'] == list(RISK_FIELDS) and protocol['lanes'] == list(LANES)
    assert protocol['finite_domain'] == summary['finite_domain'] == 5184
    assert protocol['cost_status'] == summary['cost_status'] == 'COST_INCONCLUSIVE'
    assert protocol['holdout'] is summary['holdout'] is False
    assert sha(PARENT / 'COMPLETE.json') == protocol['parent_complete_sha256']
    assert sha(PARENT / 'results.json') == protocol['parent_results_sha256']
    parent_protocol = read(PARENT / 'protocol.json')
    assert sha(DATA / 'manifest.json') == protocol['input_manifest_sha256'] == parent_protocol['input_manifest_sha256']
    old_audit = read(PARENT / 'independent-verification.json')
    assert old_audit['status'] == 'PASS'
    assert old_audit['parent_completion_sha256'] == protocol['parent_complete_sha256']
    assert sha(ROOT / 'scripts/research/c22_matrix_tuning_verify.py') == old_audit['source_sha256']
    for name, digest in read(PARENT / 'COMPLETE.json')['artifacts'].items():
        assert sha(PARENT / name) == digest, name
    for name, digest in protocol['sources'].items():
        assert sha(ROOT / name) == digest, name
        assert sha(out / 'source_snapshot' / name) == digest, name
    for name, digest in protocol['input_hashes'].items():
        assert sha(DATA / name) == digest, name
    for name, digest in protocol['benchmark_hashes'].items():
        assert sha(ROOT / name) == digest, name
        cell = read(ROOT / name)
        guard = 'cent' if name.endswith('-cent.json') else 'raw'
        view = Path(name).stem.removesuffix('-cent').rsplit('-', 1)[1]
        assert cell['metrics'] == protocol['original_floors'][guard][view]
    for name, digest in complete['artifacts'].items():
        assert sha(out / name) == digest, name
    auditor = IndependentTapeAudit(protocol, read(DATA / 'manifest.json')['last_quote_utc'])
    summaries = {}
    audited = []
    payload_hashes = {}
    entries = 0
    origins = Counter()
    initial_rules = summary['cases'][protocol['initial']]['rules']
    for number, proof_path in enumerate(sorted((out / 'cells-integrity').glob('*.json')), 1):
        key = proof_path.stem
        name, view, guard = key.split('-')
        cell, path, proof = payload(out, key)
        checked = auditor.audit_cell(cell)
        rules = checked['rules']
        assert summary['cases'][name] == dict(name=name, rules=rules)
        assert all(rules[field] in allowed for field, allowed in DOMAINS.items())
        assert all(rules[field] == value for field, value in initial_rules.items() if field not in DOMAINS)
        expected_summary = summary['summaries'][name][guard][view]
        assert expected_summary['metrics'] == checked['metrics']
        for field, value in expected_summary['risk'].items():
            equal(value, checked['risk'][field], 'summary risk ' + field)
        summaries.setdefault(name, {}).setdefault(guard, {})[view] = dict(
            metrics=checked['metrics'], risk=checked['risk'])
        entries += checked['entries']
        audited.append(str(proof_path.relative_to(ROOT)))
        payload_hashes[str(path.relative_to(ROOT))] = proof['sha256']
        origins[proof['origin']] += 1
        if number % 100 == 0:
            print('PASS saved accounting', number, 'cells /', entries, 'entries', flush=True)
    names = set(summary['visited'])
    assert names == set(summary['cases']) == set(summary['summaries']) == set(summaries)
    assert summary['visited'] == sorted(names) and len(names) <= 5184
    floors = protocol['original_floors']
    accepted = []
    for name, rows in summaries.items():
        assert set(rows.get('raw', {})) == set(VIEWS)
        if qualify({view: rows['raw'][view]['metrics'] for view in VIEWS}, floors['raw']):
            assert complete_rows(rows), 'Missing cent sensitivity for raw-qualified candidate'
        if qualified_rows(rows, floors):
            accepted.append(name)
    assert summary['qualified'] == sorted(accepted)
    baseline = summaries[protocol['initial']]
    assert summary['initial'] == protocol['initial'] == read(PARENT / 'results.json')['selected']
    assert qualified_rows(baseline, floors) and repair_eligible(baseline, baseline)
    strict = sorted(name for name in accepted if reduced_risk(summaries[name], baseline))
    assert summary['strict_downside_improvers'] == strict
    selected_repair_strict = reduced_risk(summaries[summary['selected']['repair']], baseline)
    assert summary['repair_status'] == ('STRICT_DOWNSIDE_IMPROVEMENT' if selected_repair_strict
                                       else 'NO_STRICT_DOWNSIDE_IMPROVEMENT')
    # Frozen runner's label describes selected repair only; existence is independently explicit.
    label_edge = bool(strict) and not selected_repair_strict
    initial_names = set(read(PARENT / 'results.json')['cases'])
    closure = audit_closure(out, summary, summaries, floors, baseline, initial_names)
    assert complete['selected'] == summary['selected']
    assert complete['visited_cases'] == len(names) and complete['cycles'] == summary['cycles']
    assert complete['new_economic_cells'] == origins['new']
    assert complete['reused_parent_cells'] == origins['reused'] == 153
    assert len(list((out / 'cells').glob('*.json.gz'))) == origins['new']
    diagnostic = dict(max_worst_net=min(accepted, key=lambda name: (
        -min(summaries[name][guard][view]['metrics']['net_usd'] for guard in GUARDS for view in VIEWS),
        *objective(summaries[name], 'profit'), name)))
    for field in RISK_FIELDS:
        diagnostic['min_' + field] = min(accepted, key=lambda name: (
            max(summaries[name][guard][view]['risk'][field] for guard in GUARDS for view in VIEWS),
            *objective(summaries[name], 'profit'), name))
    assert summary['diagnostic_alternatives'] == diagnostic
    repeat_names = {protocol['initial'], *summary['selected'].values()}
    repeat_keys = {f'{name}-{view}-{guard}' for name in repeat_names for guard in GUARDS for view in VIEWS}
    assert {p.stem for p in (out / 'repeats-integrity').glob('*.json')} == repeat_keys
    assert complete['fresh_repeats'] == len(repeat_keys)
    for key in sorted(repeat_keys):
        repeated, _, proof = payload(out, key, 'repeats')
        original, _, _ = payload(out, key)
        assert proof['origin'] == 'new'
        for field in ('result', 'metrics', 'diagnostics'):
            assert repeated[field] == original[field], (key, field, 'fresh repeat mismatch')
    full_tick = {}
    for name in sorted(set(summary['selected'].values())):
        for guard in GUARDS:
            for view in VIEWS:
                key = f'{name}-{view}-{guard}'
                cell, _, _ = payload(out, key)
                full_tick[key] = auditor.full_tick(cell)
                print('PASS full-tick', key, 'DD', round(full_tick[key]['max_dd_pct'], 6), flush=True)
    for lane, name in summary['selected'].items():
        descriptor = read(out / f'selected-{lane}-research.json')
        assert descriptor['status'] == 'RESEARCH_ONLY' and descriptor['rules_id'] == name
        assert descriptor['rules'] == summary['cases'][name]['rules']
        assert descriptor['protocol_sha256'] == sha(out / 'protocol.json')
        assert descriptor['runtime_qualified'] is False and descriptor['adapter_required'] is True
    assert sha(completion) == complete_hash
    report = dict(status='PASS', economic_replays=0, cells=len(audited), entries=entries,
        selected=summary['selected'], independent_full_tick_dd=full_tick, closure=closure,
        strict_downside_improvers=strict, any_strict_downside_improvement=bool(strict),
        selected_repair_strict=selected_repair_strict, repair_label_edge=label_edge,
        cost_status='COST_INCONCLUSIVE', source_sha256=sha(Path(__file__)),
        parent_completion_sha256=complete_hash, input_manifest_sha256=sha(DATA / 'manifest.json'),
        scope='All referenced/new cells: cash/swap/daily/cooldown/nonoverlap; conditional block closure; selected full-tick DD',
        audited_cells=audited, payload_hashes=payload_hashes)
    target = out / 'independent-verification.json'
    temporary = target.with_suffix('.json.pending')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    temporary.replace(target)
    print('PASS', len(audited), 'cells /', entries, 'entries /', closure['phases'], 'complete block phases', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='runs/c22-learning-loop-2026-10-25')
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to((ROOT / 'runs').resolve()):
        raise ValueError('Machine outputs must remain under runs/')
    run(out)


if __name__ == '__main__':
    main()
