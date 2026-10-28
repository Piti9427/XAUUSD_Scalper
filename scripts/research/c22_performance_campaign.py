"""Bounded offline C22 performance experiment; preserves frozen Demo and replay."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import fcntl
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs
from scripts.research.breakout_replay import replay
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.reward156_tuning import closed_h4_ema
from scripts.research.rollover import SwapPolicy

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'runs/c22-terminal-growth-2026-10-24'
INPUT = ROOT / 'runs/c22-real-data-audit-2026-10-24/input'
SEED = ROOT / 'config/research-c22-terminal-profit-9e511d195c52ef3d.json'
SPEC = ROOT / 'specs/c22-performance-2026-10-25.md'
BASE_ID = '646690b541405adf'
VIEWS = ('base', 'stress', 'fee')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + '.pending')
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    pending.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def catalog():
    cases = []

    def add(name, filters=(), **rules):
        cases.append(dict(name=name, filters=list(filters), rules=rules))

    add('baseline')
    add('buy_body', ['buy_body'])
    add('buy_close', ['buy_close'])
    add('sell_body', ['sell_body'])
    add('sell_depth', ['sell_depth'])
    add('sell_h4', ['sell_h4'])
    add('buy_h4', ['buy_h4'])
    add('buy_stop25', buy_stop_atr=2.5)
    add('cooldown4', cooldown_bars=4)
    add('protect05', protect_after_r=0.5)
    add('failed2', failed_closes=2)
    add('stagnant8', stagnant_bars=8)
    add('drawdown_steps', risk_mode='drawdown_steps')
    add('buy_body_sell_depth', ['buy_body', 'sell_depth'])
    add('buy_close_sell_depth', ['buy_close', 'sell_depth'])
    add('buy_body_sell_body', ['buy_body', 'sell_body'])
    add('buy_stop25_sell_depth', ['sell_depth'], buy_stop_atr=2.5)
    add('failed2_sell_depth', ['sell_depth'], failed_closes=2)
    assert len(cases) == 18
    return cases


def filtered(frame, case, h4):
    result = frame.copy()
    span = frame.high - frame.low
    flags = dict(
        buy_body=(span > 0) & ((frame.close-frame.open) >= span/2),
        buy_close=(span > 0) & (frame.close >= frame.low + .75*span),
        sell_body=(span > 0) & ((frame.open-frame.close) >= span/2),
        sell_depth=((frame.ll-frame.close)/frame.atr >= .15),
        sell_h4=h4.lt(h4.shift(16)), buy_h4=h4.gt(h4.shift(16)),
    )
    for mode in case['filters']:
        direction = 1 if mode.startswith('buy_') else -1
        result.loc[(result.direction == direction) & ~flags[mode].fillna(False), 'direction'] = 0
    assert ((result.direction == 0) | (result.direction == frame.direction)).all()
    return result


def diagnostics(result, last_quote):
    trades = result['ledger']
    runs, pending = [], []
    for index, trade in enumerate(trades):
        if trade['net'] < 0:
            pending.append(index)
        elif pending:
            runs.append(pending)
            pending = []
    if pending:
        runs.append(pending)
    summarized = []
    for indexes in runs:
        segment = [trades[i] for i in indexes]
        summarized.append(dict(
            indexes=indexes, trades=len(segment), net_usd=sum(t['net'] for t in segment),
            loss_pct_of_start_equity=-sum(t['net'] for t in segment)/segment[0]['entry_equity']*100,
            start_equity=segment[0]['entry_equity'], start=segment[0]['entry_time_utc'],
            end=segment[-1]['exit_time_utc'], sides=dict(Counter(str(t['direction']) for t in segment)),
            protection_exits=sum(t['stop_updates'] > 0 for t in segment),
            winning_excursion_at_least_half_r=sum(t['mfe_usd'] >= .5*t['risk_usd'] for t in segment),
            winning_excursion_at_least_one_r=sum(t['mfe_usd'] >= t['risk_usd'] for t in segment),
        ))
    cash = peak = 200.0
    peak_time = pd.Timestamp(result['start_utc'])
    peak_index = -1
    recoveries = []
    for index, trade in enumerate(trades):
        cash += trade['net']
        stamp = pd.Timestamp(trade['exit_time_utc'])
        if cash >= peak:
            segment = trades[peak_index+1:index+1]
            recoveries.append(dict(
                days=(stamp-peak_time).total_seconds()/86400, start=peak_time.isoformat(),
                end=stamp.isoformat(), previous_peak=peak, recovered_to=cash,
                first_index=peak_index+1, last_index=index, trades=len(segment),
                buy_net=sum(t['net'] for t in segment if t['direction']==1),
                sell_net=sum(t['net'] for t in segment if t['direction']==-1),
            ))
            peak, peak_time, peak_index = cash, stamp, index
    minimum = min(result['equity'], key=lambda x: x['equity_usd'], default=dict(time_utc=result['start_utc'], equity_usd=200))
    held = [dict(index=i, trade=t) for i,t in enumerate(trades)
            if pd.Timestamp(t['entry_time_utc']) <= pd.Timestamp(minimum['time_utc']) <= pd.Timestamp(t['exit_time_utc'])]
    return dict(
        longest_loss_run=max(summarized,key=lambda x:x['trades'], default=None),
        worst_run_by_loss_pct=max(summarized,key=lambda x:x['loss_pct_of_start_equity'], default=None),
        minimum_observed_equity=minimum, minimum_equity_held_positions=held,
        longest_completed_closing_recovery=max(recoveries,key=lambda x:x['days'],default=None),
        ongoing_closing_drawdown=dict(peak=peak, balance=cash, peak_time=peak_time.isoformat(),
            underwater=cash<peak, days_to_last_quote=(pd.Timestamp(last_quote)-peak_time).total_seconds()/86400 if cash<peak else 0),
        worst_trade=min(trades,key=lambda t:t['net_r'],default=None),
        loss_run_count=len(summarized),
    )


def qualifies(metrics, benchmark):
    if set(metrics) != set(VIEWS) or set(benchmark) != set(VIEWS):
        return False
    if not all(m['survival'] and m['net_usd']>0 and m['max_dd_pct']<=40 for m in metrics.values()):
        return False
    return all(metrics[v]['net_usd']+1e-7>=benchmark[v]['net_usd'] for v in ('base','stress'))


def score(metrics):
    return (-metrics['base']['net_usd'], -metrics['stress']['net_usd'],
            max(m['max_dd_pct'] for m in metrics.values()))


def cent_engine():
    source = inspect.getsource(replay)
    assert source.count('if net < 0:') == 1
    def cent_loss(net):
        return Decimal(str(float(net))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)<0
    scope = dict(replay.__globals__, _cent_loss=cent_loss)
    exec(compile(source.replace('if net < 0:', 'if _cent_loss(net):'), '<private-cent-replay>', 'exec'), scope)
    return scope['replay']


def run(output):
    old = read(OLD/'protocol.json')
    for name, expected in old['sources'].items():
        assert sha(ROOT/name)==expected, name
    manifest = read(INPUT/'manifest.json')
    for name, expected in manifest['artifacts'].items():
        assert sha(INPUT/name)==expected, name
    audit_spec = importlib.util.spec_from_file_location('c22_independent_audit',ROOT/'runs/c22-real-data-audit-2026-10-24/run_audit_v2.py')
    audit = importlib.util.module_from_spec(audit_spec)
    audit_spec.loader.exec_module(audit)
    sources = dict(old['sources'])
    for path in (Path(__file__), SPEC, SEED, Path(audit.__file__)):
        sources[str(path.relative_to(ROOT))] = sha(path)
    expected = dict(schema=1, seed=read(SEED), cases=catalog(), sources=sources,
                    input_manifest_sha256=sha(INPUT/'manifest.json'), input_hashes=manifest['artifacts'],
                    broker=old['broker'], views=old['views'], start=old['start'], end=old['end'],
                    max_observed_dd_pct=40, profit_floor='matched baseline base/stress',
                    ranking='max base net, stress net, lower max DD; no forced qualifier',
                    costs_status='COST_INCONCLUSIVE',holdout=False, sizing='fixed0.01')
    if (output/'protocol.json').exists():
        assert read(output/'protocol.json')==expected, 'Protocol drift'
    else:
        write(output/'protocol.json',expected)
        for name, expected_hash in sources.items():
            target = output/'source_snapshot'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
            assert sha(target)==expected_hash
    protocol = expected
    if (output/'COMPLETE.json').exists():
        for name, digest in read(output/'COMPLETE.json')['artifacts'].items():
            assert sha(output/name)==digest,name
        print('Already complete; hashes verified',flush=True)
        return
    bars = load_bars(INPUT/'bars.csv')
    base_frame, base_rules = prepare(bars,protocol['seed'])
    h4 = closed_h4_ema(bars,200)
    ticks = [np.load(INPUT/'tape'/f'{key}.npy',mmap_mode='r') for key in ('time','bid','ask')]
    swap = SwapPolicy.from_broker(protocol['broker'])
    costs = {view:Costs(**protocol['views'][view]) for view in VIEWS}
    benchmarks = {guard:{v:read(OLD/'cells'/f'{BASE_ID}-{v}{"-cent" if guard=="cent" else ""}.json')['metrics'] for v in VIEWS} for guard in ('raw','cent')}
    archived_diagnostics = {}
    for label, identity in [('current','58e12c454c623996'),('research',BASE_ID)]:
        for view in ('base','stress'):
            cell=read(OLD/'cells'/f'{identity}-{view}.json')
            assert sha(OLD/'cells'/f'{identity}-{view}.json')==read(OLD/'integrity'/f'{identity}-{view}.json')['sha256']
            archived_diagnostics[f'{label}-{view}']=diagnostics(cell['result'],manifest['last_quote_utc'])
    write(output/'baseline-diagnostics.json',archived_diagnostics)
    causal={}
    for cutoff in ('2025-01-01','2026-01-01','2026-10-07'):
        short_bars=bars.loc[bars.index+pd.Timedelta(minutes=15)<=pd.Timestamp(cutoff,tz='UTC')]
        short_frame,_=prepare(short_bars,protocol['seed']);short_h4=closed_h4_ema(short_bars,200)
        for case in catalog():
            actual=filtered(short_frame,case,short_h4).direction
            expected_direction=filtered(base_frame,case,h4).loc[actual.index,'direction']
            pd.testing.assert_series_equal(actual,expected_direction)
        causal[cutoff]=len(short_bars)
    write(output/'prefix-causality.json',causal)
    # Hand-derived selection edge cases: no raw-only winner or all-fail selection.
    passing={v:dict(net_usd=10.,survival=True,max_dd_pct=40.) for v in VIEWS}
    floor={v:dict(net_usd=10.) for v in VIEWS}
    assert qualifies(passing,floor)
    assert not qualifies({v:dict(m,max_dd_pct=40.00001) for v,m in passing.items()},floor)
    assert not qualifies({v:dict(m,survival=False) for v,m in passing.items()},floor)
    assert not qualifies({v:dict(m,net_usd=-1) for v,m in passing.items()},floor)
    assert not qualifies({'base':passing['base']},floor)
    cells={}
    cent=cent_engine()

    def execute(case,view,guard='raw',repeat=False):
        key=f'{case["name"]}-{view}-{guard}'
        folder='repeats' if repeat else 'cells'
        target=output/folder/f'{key}.json';proof=output/(folder+'-integrity')/f'{key}.json'
        if target.exists():
            assert sha(target)==read(proof)['sha256'],key
            cell=read(target)
            assert cell['case']==case
        else:
            begun=time.monotonic();frame=filtered(base_frame,case,h4)
            rules=replace(base_rules,**case['rules'])
            result=(cent if guard=='cent' else replay)(frame,ticks,protocol['broker'],rules,costs[view],
                start=pd.Timestamp(protocol['start']),end=pd.Timestamp(protocol['end']),swap_policy=swap,
                capture_events=True,capture_context=True)
            checks=audit.independent_audit(result,protocol['broker'],costs[view])
            metrics=audit.metrics(result)
            minimum=min([200.]+[x['equity_usd'] for x in result['equity']])
            metrics.update(min_observed_equity=minimum,survival=bool(minimum>0 and result['final_balance']>0 and not result['rejections']['bankrupt']))
            cell=dict(case=case,view=view,guard=guard,result=result,metrics=metrics,
                      diagnostics=diagnostics(result,manifest['last_quote_utc']),checks=checks)
            write(target,cell);write(proof,dict(sha256=sha(target)))
            print(folder,key,'net',round(metrics['net_usd'],4),'DD',round(metrics['max_dd_pct'],4),
                  'trades',metrics['trades'],'seconds',round(time.monotonic()-begun,2),flush=True)
        if repeat:
            assert cell==read(output/'cells'/f'{key}.json'),key
        else:
            cells[key]=cell
        return cell

    for case in catalog():
        for view in VIEWS:
            cell=execute(case,view)
            if case['name']=='baseline':
                assert cell['result']==read(OLD/'cells'/f'{BASE_ID}-{view}.json')['result'],view
        write(output/'progress.json',dict(completed_cases=len(cells)//3,total_cases=len(catalog())))
    raw={c['name']:{v:cells[f'{c["name"]}-{v}-raw']['metrics'] for v in VIEWS} for c in catalog()}
    improvements=[c for c in catalog() if c['name']!='baseline' and qualifies(raw[c['name']],benchmarks['raw']) and score(raw[c['name']])<score(raw['baseline'])]
    finalists=sorted(improvements,key=lambda c:(*score(raw[c['name']]),c['name']))[:2]
    for case in finalists:
        for view in VIEWS:
            execute(case,view,'cent')
    accepted=[c for c in finalists if qualifies({v:cells[f'{c["name"]}-{v}-cent']['metrics'] for v in VIEWS},benchmarks['cent'])]
    selected=min(accepted,key=lambda c:(*score(raw[c['name']]),c['name'])) if accepted else None
    if selected:
        for guard in ('raw','cent'):
            for view in VIEWS:
                execute(selected,view,guard,repeat=True)
    summary=dict(status='QUALIFIED_DISCOVERY_IMPROVEMENT' if selected else 'NO_QUALIFIER',
                 selected=selected,raw_finalists=finalists,costs_status='COST_INCONCLUSIVE',
                 raw_metrics=raw,cent_metrics={c['name']:{v:cells[f'{c["name"]}-{v}-cent']['metrics'] for v in VIEWS} for c in finalists},
                 claim='Retrospective bounded research only; no Demo adoption or future-profit qualification')
    write(output/'results.json',summary)
    if selected:
        write(output/'selected-research.json',dict(seed=protocol['seed'],changes=selected,
            runtime_qualified=False,source_protocol_sha256=sha(output/'protocol.json')))
    artifacts=[p for folder in ('cells','cells-integrity','repeats','repeats-integrity') for p in (output/folder).glob('*.json')]
    artifacts += [output/n for n in ('protocol.json','baseline-diagnostics.json','prefix-causality.json','results.json')]
    if selected:
        artifacts.append(output/'selected-research.json')
    write(output/'COMPLETE.json',dict(status=summary['status'],economic_cells=len(cells),fresh_repeats=6 if selected else 0,
          selected=selected,artifacts={str(p.relative_to(output)):sha(p) for p in artifacts}))
    print('COMPLETE',summary['status'],selected,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/c22-performance-2026-10-25')
    args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Machine output must stay under runs/')
    output.mkdir(parents=True,exist_ok=True)
    with (output/'.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(output)


if __name__=='__main__':
    main()
