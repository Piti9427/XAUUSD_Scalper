"""B1-FINAL release evidence from MT5 Strategy Tester runs of `mql5/B1FinalEA.mq5`.

Reads EA outbox events, deal ledgers and consumed bars; never talks to a broker.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .b1_final import reference_bars

BLOCKS = (('May14-Jun', '2026-05-14', '2026-07-01'), ('Jul-Aug', '2026-07-01', '2026-09-01'),
          ('Sep1-25', '2026-09-01', None))
SCENARIOS = (('0.00R', 0.0, 0.0), ('0.10R', 0.1, 0.0), ('0.20R', 0.2, 0.0),
             ('0.10R+adverse0.10', 0.1, 0.1), ('0.20R+adverse0.10', 0.2, 0.1))
GATE_SCENARIOS = ('0.10R', '0.20R')
CONFIRMED_EXIT = 3
TRADE_DEAL_TYPES = (0, 1)
BALANCE_DEAL_TYPE = 2


def load_events(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def signal_parity(bars, events, first_live_epoch):
    """Reference detector on the exact bars the EA consumed vs EA SIGNAL events."""
    frame = bars.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop('bar_open_epoch'), unit='s', utc=True))
    ref = reference_bars(frame[['open', 'high', 'low', 'close']])
    epochs = ref.index.as_unit('ns').asi8//10**9
    expected = {int(t): int(d) for t, d in zip(epochs, ref.direction) if d != 0 and t >= first_live_epoch}
    observed = {int(e['fields']['bar_open_utc_epoch']): int(e['fields']['direction'])
                for e in events if e['type'] == 'SIGNAL'}
    last = int(epochs[-1])
    observed = {t: d for t, d in observed.items() if first_live_epoch <= t <= last}
    missing = sorted(set(expected)-set(observed))
    extra = sorted(set(observed)-set(expected))
    flipped = sorted(t for t in expected if t in observed and observed[t] != expected[t])
    return {'passed': bool(expected) and not (missing or extra or flipped), 'reference_signals': len(expected),
            'ea_signals': len(observed), 'missing': missing[:20], 'extra': extra[:20], 'direction_mismatch': flipped[:20],
            'bars': len(ref)}


def ledger_from_events(events):
    rows = [{'utc': e['utc'], **e['fields']} for e in events if e['type'] == 'CLOSE_CONFIRMED']
    columns = ['utc', 'request_id', 'net_profit', 'position_risk_money', 'net_r', 'reason', 'exit_state', 'volume']
    ledger = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)
    ledger['utc'] = pd.to_datetime(ledger['utc'], utc=True)
    for col in ('net_profit', 'position_risk_money', 'net_r', 'volume'):
        ledger[col] = ledger[col].astype(float)
    return ledger


def reconcile(ledger, deals, deposit, final_equity):
    trades = deals[deals['type'].isin(TRADE_DEAL_TYPES)]
    deal_net = float((trades['profit']+trades['commission']+trades['swap']).sum())
    event_net = float(ledger['net_profit'].sum())
    change = final_equity-deposit
    return {'passed': abs(deal_net-change) < .015 and abs(event_net-change) < .015*max(1, len(ledger)),
            'event_net': round(event_net, 2), 'deal_net': round(deal_net, 2), 'equity_change': round(change, 2)}


def metrics(ledger, deposit, max_dd, hard_stop, reserve_r, adverse_per_oz=0.0, contract=100.0):
    """Reserve and adverse-fill stress are post-hoc per-trade costs; exit paths are unchanged."""
    adverse = adverse_per_oz*contract*ledger['volume']*2
    net = ledger['net_profit']-reserve_r*ledger['position_risk_money']-adverse
    risk = ledger['position_risk_money'].where(ledger['position_risk_money'] > 0)
    r = ledger['net_r']-reserve_r-(adverse/risk).fillna(0.0)
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    n = len(ledger)
    return {'trades': n, 'reserve_r': reserve_r, 'adverse_per_oz': adverse_per_oz, 'total_net_r': float(r.sum()),
            'expectancy_r': float(r.mean()) if n else None,
            'profit_factor': float(wins/losses) if n and losses > 0 else None,
            'win_rate': float((net > 0).mean()) if n else None,
            'net_profit': float(net.sum()), 'return_pct': float(net.sum()/deposit*100),
            'max_dd_pct': float(max_dd*100), 'hard_stop': bool(hard_stop)}


def _mark_at(marks, day):
    after = marks[marks.index >= pd.Timestamp(day, tz='UTC')]
    return float(after.iloc[0]) if len(after) else None


def block_returns(events, final_equity, ledger, reserve_r, adverse_per_oz=0.0, contract=100.0):
    """Block result from boundary equity marks (includes floating PnL at the boundary)."""
    items = [(pd.Timestamp(e['utc']), float(e['fields']['equity'])) for e in events if e['type'] == 'EQUITY_MARK']
    marks = pd.Series([v for _, v in items], index=pd.DatetimeIndex([t for t, _ in items]), dtype=float).sort_index()
    out = {}
    for name, start, end in BLOCKS:
        first = _mark_at(marks, start)
        last = final_equity if end is None else _mark_at(marks, end)
        if first is None or last is None:
            out[name] = None
            continue
        closed = ledger[(ledger.utc >= pd.Timestamp(start, tz='UTC')) &
                        ((ledger.utc < pd.Timestamp(end, tz='UTC')) if end else True)]
        reserve = float((reserve_r*closed['position_risk_money']+adverse_per_oz*contract*closed['volume']*2).sum())
        out[name] = (last-first-reserve)/first*100
    return out


def exit_gate(base, variant):
    blocks = [k for k in base['blocks'] if base['blocks'][k] is not None and variant['blocks'].get(k) is not None]
    wins = sum(variant['blocks'][k] > base['blocks'][k] for k in blocks)
    checks = {'executable_sample': base['trades'] > 0 and variant['trades'] > 0,
              'total_net_r_above_baseline': variant['total_net_r'] > base['total_net_r'],
              'return_above_baseline': variant['return_pct'] > base['return_pct'],
              'expectancy_positive': (variant['expectancy_r'] or 0) > 0,
              'profit_factor_above_1': (variant['profit_factor'] or 0) > 1,
              'dd_no_worse_than_baseline': variant['max_dd_pct'] <= base['max_dd_pct'],
              'dd_below_12pct': variant['max_dd_pct'] < 12,
              'no_hard_stop': not variant['hard_stop'],
              'wins_2_of_3_blocks': wins >= 2}
    return {'passed': all(checks.values()), 'checks': checks, 'block_wins': int(wins)}


def _by_signal(ledger):
    """Request IDs are `<version code>|<bar epoch>|<direction>`; arms share the signal part."""
    return ledger.set_index(ledger['request_id'].str.split('|', n=1).str[-1])


def exit_attribution(base, variant):
    b = _by_signal(base)
    v = _by_signal(variant)
    common = b.index.intersection(v.index)
    moved = v.loc[common, 'exit_state'].astype(int) == CONFIRMED_EXIT
    saved = [k for k in common if moved[k] and b.at[k, 'net_profit'] < 0 and v.at[k, 'net_profit'] > b.at[k, 'net_profit']]
    displaced = [k for k in common if moved[k] and b.at[k, 'net_profit'] > 0 and v.at[k, 'net_profit'] < b.at[k, 'net_profit']]
    return {'saved_losers': len(saved), 'saved_loser_net': float(sum(v.at[k, 'net_profit']-b.at[k, 'net_profit'] for k in saved)),
            'displaced_winners': len(displaced),
            'displaced_winner_net': float(sum(v.at[k, 'net_profit']-b.at[k, 'net_profit'] for k in displaced)),
            'only_in_baseline': sorted(set(b.index)-set(v.index)), 'only_in_variant': sorted(set(v.index)-set(b.index))}


def verdicts(implementation_ok, account_verdict, baseline, exit_passed, costs_measured):
    strategy = 'STRATEGY_NO_GO'
    if baseline and baseline['trades'] and (baseline['expectancy_r'] or 0) > 0 and (baseline['profit_factor'] or 0) > 1 \
            and baseline['max_dd_pct'] < 12 and not baseline['hard_stop']:
        strategy = 'STRATEGY_UNQUALIFIED_PENDING_OOS_COSTS_FORWARD'
    return {'implementation': 'IMPLEMENTATION_VERIFIED' if implementation_ok else 'IMPLEMENTATION_INCOMPLETE',
            'account': account_verdict, 'strategy': strategy,
            'exit': 'COST_BE_PROMOTED' if exit_passed and costs_measured else 'FIXED_EXIT_FROZEN_BE_DISABLED',
            'deployment': 'NO_GO'}


def engine_tests_passed(path):
    """MQL FileWrite does not quote: the test name is the first field and the result the last."""
    rows = [line for line in Path(path).read_text().splitlines()[1:] if line.strip()]
    checks = [line.rsplit(',', 1)[-1] for line in rows if not line.startswith('SUMMARY,')]
    return bool(checks) and all(result == 'PASS' for result in checks) and rows[-1].endswith(',0 failed')


def run_summary(run_dir):
    run_dir = Path(run_dir)
    events = load_events(next(run_dir.glob('*_events.jsonl')))
    deals = pd.read_csv(next(run_dir.glob('*_deals.csv')))
    summary = next(e['fields'] for e in events if e['type'] == 'RUN_SUMMARY')
    deposit = float(deals.loc[deals['type'] == BALANCE_DEAL_TYPE, 'profit'].sum())
    ledger = ledger_from_events(events)
    admissions = pd.Series([e['fields'].get('reason', e['fields'].get('outcome')) for e in events if e['type'] == 'ADMISSION'])
    out = {'run': run_dir.name, 'manifest': json.loads((run_dir/'run_manifest.json').read_text()),
           'deposit': deposit, 'final_equity': float(summary['final_equity']), 'summary': summary,
           'admissions': admissions.value_counts().to_dict(),
           'confirmed_events': int(sum(e['confirmed'] for e in events)),
           'reconciliation': reconcile(ledger, deals, deposit, float(summary['final_equity'])),
           'artifact_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run_dir.iterdir()) if p.is_file()}}
    out['metrics'] = {}
    for key, reserve, adverse in SCENARIOS:
        m = metrics(ledger, deposit, float(summary['max_dd']), bool(summary['dd_stop']), reserve, adverse)
        m['blocks'] = block_returns(events, float(summary['final_equity']), ledger, reserve, adverse)
        out['metrics'][key] = m
    bars_path = next(run_dir.glob('*_bars.csv'), None)
    if bars_path is not None:
        # The last seed bar's entry window opens at the Tester start, so it is the first live signal bar.
        start = pd.Timestamp(out['manifest']['from'].replace('.', '-'), tz='UTC')
        first = int(start.timestamp())-900
        out['signal_parity'] = signal_parity(pd.read_csv(bars_path), events, first)
    return out, ledger


def compare_exits(base, variant, base_ledger, variant_ledger):
    gates = {key: exit_gate(base['metrics'][key], variant['metrics'][key]) for key, _, _ in SCENARIOS}
    return {'baseline': base['run'], 'variant': variant['run'], 'gates': gates,
            'passed_required': all(gates[k]['passed'] for k in GATE_SCENARIOS),
            'attribution': exit_attribution(base_ledger, variant_ledger)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', action='append', required=True, help='Tester output directory')
    p.add_argument('--compare', action='append', default=[], help='BASE_RUN:VARIANT_RUN (directory names)')
    p.add_argument('--account-run', help='run name that carries target-account evidence (actual equity)')
    p.add_argument('--preflight', type=Path, help='preflight report JSON')
    p.add_argument('--engine-tests', type=Path, help='B1_engine_tests.csv from the Tester')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error('output exists')
    results, ledgers = {}, {}
    for run in args.run:
        summary, ledger = run_summary(run)
        results[summary['run']], ledgers[summary['run']] = summary, ledger
    comparisons = []
    for pair in args.compare:
        base, variant = pair.split(':')
        comparisons.append(compare_exits(results[base], results[variant], ledgers[base], ledgers[variant]))
    decision = None
    if args.account_run and args.preflight and args.engine_tests:
        implementation_ok = engine_tests_passed(args.engine_tests) and all(
            r['reconciliation']['passed'] and (r.get('signal_parity') or {}).get('passed') for r in results.values())
        preflight = json.loads(args.preflight.read_text())
        actual = next((s['verdict'] for s in preflight.get('scenarios', []) if s['scenario'] == 'actual_demo_equity'),
                      preflight.get('status'))
        account = results[args.account_run]
        if account['metrics']['0.00R']['trades'] == 0:
            actual = 'ACCOUNT_BLOCKED'
        baseline = account['metrics']['0.10R'] if account['metrics']['0.10R']['trades'] else None
        decision = verdicts(implementation_ok, actual, baseline,
                            bool(comparisons) and any(c['passed_required'] for c in comparisons), costs_measured=False)
        print('verdicts', decision)
    args.output.write_text(json.dumps({'runs': results, 'exit_comparisons': comparisons, 'verdicts': decision},
                                      indent=2, default=str)+'\n')
    for c in comparisons:
        print('exit', c['variant'], 'vs', c['baseline'], 'required gates passed:', c['passed_required'],
              {k: g['passed'] for k, g in c['gates'].items()},
              {k: c['attribution'][k] for k in ('saved_losers', 'displaced_winners')})
    for name, r in results.items():
        base = r['metrics']['0.00R']
        print(name, {'trades': base['trades'], 'net_r': round(base['total_net_r'], 2), 'return_pct': round(base['return_pct'], 2),
                     'dd_pct': round(base['max_dd_pct'], 2), 'reconciled': r['reconciliation']['passed'],
                     'signal_parity': (r.get('signal_parity') or {}).get('passed')})


if __name__ == '__main__':
    main()
