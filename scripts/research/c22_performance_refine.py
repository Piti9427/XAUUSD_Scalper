"""Five frozen C22 discovery combinations; no broker/execution interfaces."""
import argparse
from dataclasses import replace
import fcntl
import importlib.util
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

STAGE1 = ROOT/'runs/c22-performance-2026-10-25'
SPEC = ROOT/'specs/c22-performance-refine-2026-10-25.md'


def catalog():
    overrides = [
        ('stop25_cooldown4', dict(cooldown_bars=4)),
        ('stop25_daily1', dict(max_daily_losses=1)),
        ('stop25_sell2', dict(target_rr=2.0)),
        ('stop25_cooldown4_sell2', dict(cooldown_bars=4,target_rr=2.0)),
        ('stop25_cooldown4_daily1', dict(cooldown_bars=4,max_daily_losses=1)),
    ]
    return [dict(name=name,filters=[],rules=dict(buy_stop_atr=2.5,**changes)) for name,changes in overrides]


def run(out):
    first_complete=read(STAGE1/'COMPLETE.json')
    for name,expected in first_complete['artifacts'].items():
        assert sha(STAGE1/name)==expected,name
    first_protocol=read(STAGE1/'protocol.json')
    pins=dict(first_protocol['sources'])
    for p in (SPEC,Path(__file__)):
        pins[str(p.relative_to(ROOT))]=sha(p)
    for name,expected in pins.items():
        assert sha(ROOT/name)==expected,name
    manifest=read(INPUT/'manifest.json')
    for name,expected in first_protocol['input_hashes'].items():
        assert sha(INPUT/name)==expected,name
    protocol=dict(schema=1,cases=catalog(),source_pins=pins,
                  parent_completion_sha256=sha(STAGE1/'COMPLETE.json'),
                  parent_results_sha256=sha(STAGE1/'results.json'),
                  parent_protocol_sha256=sha(STAGE1/'protocol.json'),
                  input_manifest_sha256=sha(INPUT/'manifest.json'),
                  benchmark_id=BASE_ID,max_dd_pct=40,holdout=False,costs_status='COST_INCONCLUSIVE')
    if (out/'protocol.json').exists():
        assert read(out/'protocol.json')==protocol,'Protocol drift'
    else:
        write(out/'protocol.json',protocol)
        for name,digest in pins.items():
            target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target);assert sha(target)==digest
    if (out/'COMPLETE.json').exists():
        for name,expected in read(out/'COMPLETE.json')['artifacts'].items():
            assert sha(out/name)==expected,name
        print('Already complete; hashes verified',flush=True)
        return
    spec=importlib.util.spec_from_file_location('c22_refine_auditor',ROOT/'runs/c22-real-data-audit-2026-10-24/run_audit_v2.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    frame,rules=prepare(load_bars(INPUT/'bars.csv'),read(SEED))
    ticks=[np.load(INPUT/'tape'/f'{key}.npy',mmap_mode='r') for key in ('time','bid','ask')]
    broker=first_protocol['broker'];swap=SwapPolicy.from_broker(broker)
    costs={v:Costs(**first_protocol['views'][v]) for v in VIEWS}
    benchmarks={g:{v:read(OLD/'cells'/f'{BASE_ID}-{v}{"-cent" if g=="cent" else ""}.json')['metrics'] for v in VIEWS} for g in ('raw','cent')}
    cells={};cent=cent_engine()
    incumbent=first_complete['selected']
    assert incumbent is not None,'Missing qualified Stage1 candidate'
    for guard in ('raw','cent'):
        for view in VIEWS:
            key=f'{incumbent["name"]}-{view}-{guard}'
            source=STAGE1/'cells'/f'{key}.json'
            value=read(source)
            write(out/'reused'/f'{key}.json',dict(source=str(source.relative_to(ROOT)),sha256=sha(source)))
            cells[key]=value

    def execute(case,view,guard='raw',repeat=False):
        key=f'{case["name"]}-{view}-{guard}';folder='repeats' if repeat else 'cells'
        target=out/folder/f'{key}.json';proof=out/(folder+'-integrity')/f'{key}.json'
        if target.exists():
            assert sha(target)==read(proof)['sha256'],key
            value=read(target);assert value['case']==case
        else:
            begun=time.monotonic()
            result=(cent if guard=='cent' else replay)(frame,ticks,broker,replace(rules,**case['rules']),costs[view],
                start=pd.Timestamp(first_protocol['start']),end=pd.Timestamp(first_protocol['end']),
                swap_policy=swap,capture_events=True,capture_context=True)
            checks=audit.independent_audit(result,broker,costs[view])
            metrics=audit.metrics(result);minimum=min([200.]+[x['equity_usd'] for x in result['equity']])
            metrics.update(min_observed_equity=minimum,survival=bool(minimum>0 and result['final_balance']>0 and not result['rejections']['bankrupt']))
            value=dict(case=case,view=view,guard=guard,result=result,metrics=metrics,
                       diagnostics=diagnostics(result,manifest['last_quote_utc']),checks=checks)
            write(target,value);write(proof,dict(sha256=sha(target)))
            print(folder,key,'net',round(metrics['net_usd'],4),'DD',round(metrics['max_dd_pct'],4),
                  'trades',metrics['trades'],'seconds',round(time.monotonic()-begun,2),flush=True)
        if repeat:
            assert value==cells[key],key
        else:
            cells[key]=value
        return value

    for case in catalog():
        for view in VIEWS:
            execute(case,view)
    def metrics(case,guard):
        return {v:cells[f'{case["name"]}-{v}-{guard}']['metrics'] for v in VIEWS}
    finalists=sorted([c for c in catalog() if qualifies(metrics(c,'raw'),benchmarks['raw'])],
                     key=lambda c:(*score(metrics(c,'raw')),c['name']))[:2]
    for case in finalists:
        for view in VIEWS:
            execute(case,view,'cent')
    accepted=[c for c in [incumbent,*finalists] if all(qualifies(metrics(c,g),benchmarks[g]) for g in ('raw','cent'))]
    selected=min(accepted,key=lambda c:(*score(metrics(c,'raw')),c['name'])) if accepted else None
    if selected:
        for guard in ('raw','cent'):
            for view in VIEWS:
                execute(selected,view,guard,True)
    write(out/'results.json',dict(status='QUALIFIED_DISCOVERY_IMPROVEMENT' if selected else 'NO_QUALIFIER',
        selected=selected,parent_selected=incumbent,raw_finalists=finalists,
        raw_metrics={c['name']:metrics(c,'raw') for c in [incumbent,*catalog()]},
        cent_metrics={c['name']:metrics(c,'cent') for c in [incumbent,*finalists]},
        new_refinement_selected=bool(selected and selected!=incumbent),costs_status='COST_INCONCLUSIVE',holdout=False))
    if selected:
        write(out/'selected-research.json',dict(seed=read(SEED),changes=selected,runtime_qualified=False,
                                             protocol_sha256=sha(out/'protocol.json')))
    paths=[p for folder in ('cells','cells-integrity','repeats','repeats-integrity','reused') for p in (out/folder).glob('*.json')]
    paths += [out/'protocol.json',out/'results.json']
    if selected:
        paths.append(out/'selected-research.json')
    write(out/'COMPLETE.json',dict(status='COMPLETE_DISCOVERY',selected=selected,
        new_economic_cells=len(list((out/'cells').glob('*.json'))),reused_parent_paths=6,
        fresh_repeats=len(list((out/'repeats').glob('*.json'))),
        artifacts={str(p.relative_to(out)):sha(p) for p in paths}))
    print('COMPLETE',selected,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/c22-performance-refine-2026-10-25')
    args=parser.parse_args();out=(ROOT/args.output).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Machine outputs must remain under runs/')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);run(out)


if __name__=='__main__':
    main()
