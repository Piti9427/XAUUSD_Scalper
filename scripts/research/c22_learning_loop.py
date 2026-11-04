"""Offline C22 block search: profit and explicit downside-repair alternatives."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import fcntl
from itertools import product
import math
import multiprocessing
from pathlib import Path
import shutil

from scripts.research.c22_matrix_tuning import DOMAINS, identity
from scripts.research.c22_performance_campaign import ROOT, INPUT, VIEWS, read, write, sha, qualifies, score
from scripts.research.breakout_models import Rules
from scripts.research.c22_loop_store import add_reference, read_cell, load_summary, init_worker, execute_cell

PARENT = ROOT/'runs/c22-matrix-tuning-2026-10-25'
SPEC = ROOT/'specs/c22-learning-loop-2026-10-25.md'
BLOCKS = {
    'core': ('buy_target_rr','target_rr','cooldown_bars'),
    'management': ('buy_stop_atr','stop_atr','protect_after_r','buy_protect_mode'),
}
RISK_FIELDS = ('dd','recovery','severity','streak')
LANES = ('profit','repair')
SPACE = math.prod(len(values) for values in DOMAINS.values())


def catalog(rules, block):
    result = []
    for values in product(*(DOMAINS[k] for k in BLOCKS[block])):
        candidate = Rules(**(rules | dict(zip(BLOCKS[block],values))))
        result.append(dict(name=identity(candidate),rules=asdict(candidate)))
    assert len({c['name'] for c in result}) == len(result)
    return result


def complete(rows):
    return all(set(rows.get(g,{})) == set(VIEWS) for g in ('raw','cent'))


def qualified(rows, floors):
    return complete(rows) and all(qualifies({v:rows[g][v]['metrics'] for v in VIEWS},floors[g])
                                  for g in ('raw','cent'))


def repair_eligible(rows, baseline):
    if not complete(rows):
        return False
    return all(rows[g][v]['metrics']['net_usd']+1e-7 >= baseline[g][v]['metrics']['net_usd']
               for g in ('raw','cent') for v in ('base','stress')) and all(
        rows[g][v]['risk'][k] <= baseline[g][v]['risk'][k]+1e-9
        for g in ('raw','cent') for v in VIEWS for k in RISK_FIELDS)


def reduced_risk(rows, baseline):
    return repair_eligible(rows,baseline) and any(rows[g][v]['risk'][k] < baseline[g][v]['risk'][k]-1e-9
        for g in ('raw','cent') for v in VIEWS for k in RISK_FIELDS)


def objective(rows, lane):
    raw = {v:rows['raw'][v]['metrics'] for v in VIEWS}
    if lane == 'profit':
        return score(raw)
    assert lane == 'repair'
    return tuple(max(rows[g][v]['risk'][k] for g in ('raw','cent') for v in VIEWS)
                 for k in RISK_FIELDS) + (-raw['base']['net_usd'],-raw['stress']['net_usd'])


def choose(current, names, summaries, lane, floors, baseline):
    accepted = [n for n in names if qualified(summaries[n],floors) and
                (lane=='profit' or repair_eligible(summaries[n],baseline))]
    assert current in accepted
    best = min(accepted,key=lambda n:(*objective(summaries[n],lane),n))
    return best if objective(summaries[best],lane) < objective(summaries[current],lane) else current


def run(out, workers):
    prior = read(PARENT/'protocol.json')
    old_result = read(PARENT/'results.json')
    for name,digest in read(PARENT/'COMPLETE.json')['artifacts'].items():
        assert sha(PARENT/name)==digest,name
    assert read(PARENT/'independent-verification.json')['status']=='PASS'
    assert sha(INPUT/'manifest.json')==prior['input_manifest_sha256']
    sources = dict(prior['sources'])
    for path in (Path(__file__),SPEC,ROOT/'scripts/research/c22_loop_store.py'):
        sources[str(path.relative_to(ROOT))] = sha(path)
    for name,digest in sources.items():
        assert sha(ROOT/name)==digest,name
    for name,digest in prior['input_hashes'].items():
        assert sha(INPUT/name)==digest,name
    protocol = dict(schema=1,algorithm='two_lane_block_closure_v1',sources=sources,
        input_hashes=prior['input_hashes'],input_manifest_sha256=prior['input_manifest_sha256'],
        parent_complete_sha256=sha(PARENT/'COMPLETE.json'),parent_results_sha256=sha(PARENT/'results.json'),
        broker=prior['broker'],views=prior['views'],start=prior['start'],end=prior['end'],
        original_floors=prior['original_floors'],benchmark_hashes=prior['benchmark_hashes'],
        domains={k:list(v) for k,v in DOMAINS.items()},blocks={k:list(v) for k,v in BLOCKS.items()},
        finite_domain=SPACE,initial=old_result['selected'],lanes=list(LANES),risk_fields=list(RISK_FIELDS),
        cost_status='COST_INCONCLUSIVE',holdout=False,claim='Conditional block closure; not global exhaustive optimum')
    if (out/'protocol.json').exists():
        assert read(out/'protocol.json')==protocol,'Protocol drift'
    else:
        write(out/'protocol.json',protocol)
        for name,digest in sources.items():
            target=out/'source_snapshot'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
            assert sha(target)==digest
    if (out/'COMPLETE.json').exists():
        for name,digest in read(out/'COMPLETE.json')['artifacts'].items():
            assert sha(out/name)==digest,name
        print('Already converged; hashes verified',flush=True)
        return
    cases,summaries,active = {},{},set()
    initial=protocol['initial']
    for name,case in old_result['cases'].items():
        cases[name]=dict(name=name,rules=case['rules'])
        summaries[name]={}
        for g in ('raw','cent'):
            for v in VIEWS:
                path=PARENT/'cells'/f'{name}-{v}-{g}.json'
                if path.exists():
                    key=f'{name}-{v}-{g}'
                    add_reference(out,key,path)
                    summaries[name].setdefault(g,{})[v]=load_summary(read_cell(out,key))
        active.add(name)
    baseline=summaries[initial]
    floors=protocol['original_floors']
    assert qualified(baseline,floors) and repair_eligible(baseline,baseline)
    phases=[]
    phase_number=0
    current={lane:initial for lane in LANES}
    closed={}
    context=multiprocessing.get_context('spawn')

    with ProcessPoolExecutor(max_workers=workers,mp_context=context,initializer=init_worker,
                             initargs=(protocol,str(out))) as pool:
        def jobs(items,phase):
            futures={}
            for rules,v,g,repeat in items:
                name=identity(Rules(**rules));key=f'{name}-{v}-{g}'
                folder='repeats' if repeat else 'cells'
                if (out/(folder+'-integrity')/f'{key}.json').exists():
                    cell=read_cell(out,key,folder)
                    if not repeat:
                        summaries[name].setdefault(g,{})[v]=load_summary(cell)
                    continue
                futures[pool.submit(execute_cell,(rules,v,g,repeat))]=(name,v,g)
            total=len(futures)
            for done,future in enumerate(as_completed(futures),1):
                name,v,g=futures[future]
                _,summary,_=future.result()
                if not items[0][3]:
                    summaries[name].setdefault(g,{})[v]=summary
                write(out/'progress.json',dict(phase=phase,done=done,new_jobs=total,
                    visited_cases=len(active),current=current))

        jobs([(cases[initial]['rules'],v,g,True) for g in ('raw','cent') for v in VIEWS],'initial-parity')
        # Both lanes repeatedly receive whole blocks, not only favorable single-factor changes.
        cycles=0
        while True:
            cycles+=1
            assert cycles<=2*SPACE+2,'Finite strict-promotion invariant broken'
            for lane in LANES:
                promoted=choose(current[lane],active,summaries,lane,floors,baseline)
                if promoted!=current[lane]:
                    current[lane]=promoted;closed.pop(lane,None)
                if closed.get(lane)==current[lane]:
                    continue
                started=current[lane]
                for block in BLOCKS:
                    phase_number+=1
                    before=current[lane]
                    candidates=catalog(cases[before]['rules'],block)
                    frozen=dict(number=phase_number,cycle=cycles,lane=lane,block=block,
                        incumbent=before,catalog=candidates,
                        downside_before={g:{v:summaries[before][g][v]['risk'] for v in VIEWS} for g in ('raw','cent')},
                        hypothesis='Exhaustive block trade-offs in payoff/holding/cooldown' if block=='core' else
                                   'Exhaustive stop/admission/protection trade-offs; global activation affects both sides')
                    cat_path=out/'phases'/f'{phase_number:03}-catalog.json'
                    if cat_path.exists():
                        assert read(cat_path)==frozen,'Frozen phase drift'
                    else:
                        write(cat_path,frozen)
                    for c in candidates:
                        cases.setdefault(c['name'],c);summaries.setdefault(c['name'],{})
                    jobs([(c['rules'],v,'raw',False) for c in candidates for v in VIEWS],f'{phase_number}-raw')
                    rawpass=[c for c in candidates if qualifies(
                        {v:summaries[c['name']]['raw'][v]['metrics'] for v in VIEWS},floors['raw'])]
                    jobs([(c['rules'],v,'cent',False) for c in rawpass for v in VIEWS],f'{phase_number}-cent')
                    active.update(c['name'] for c in candidates)
                    after=choose(before,active,summaries,lane,floors,baseline)
                    result=dict(number=phase_number,cycle=cycles,lane=lane,block=block,
                        incumbent=before,selected=after,improved=after!=before,
                        raw_qualified=[c['name'] for c in rawpass],
                        fully_qualified=[c['name'] for c in candidates if qualified(summaries[c['name']],floors)],
                        objective_before=list(objective(summaries[before],lane)),
                        objective_after=list(objective(summaries[after],lane)),visited_cases=len(active))
                    write(out/'phases'/f'{phase_number:03}-result.json',result)
                    phases.append(result);current[lane]=after
                    print('PHASE',phase_number,lane,block,'selected',after,'improved',after!=before,
                          'visited',len(active),flush=True)
                if current[lane]==started:
                    closed[lane]=current[lane]
            if all(closed.get(lane)==current[lane] and
                   choose(current[lane],active,summaries,lane,floors,baseline)==current[lane] for lane in LANES):
                break
        for name in sorted(set(current.values())):
            jobs([(cases[name]['rules'],v,g,True) for g in ('raw','cent') for v in VIEWS],'final-repeat')

    accepted=sorted(n for n in active if qualified(summaries[n],floors))
    strict=sorted(n for n in accepted if reduced_risk(summaries[n],baseline))
    diagnostics={
        'max_worst_net':min(accepted,key=lambda n:(-min(summaries[n][g][v]['metrics']['net_usd']
                            for g in ('raw','cent') for v in VIEWS),*objective(summaries[n],'profit'),n)),
    }
    for field in RISK_FIELDS:
        diagnostics['min_'+field]=min(accepted,key=lambda n:(max(summaries[n][g][v]['risk'][field]
                     for g in ('raw','cent') for v in VIEWS),*objective(summaries[n],'profit'),n))
    summary=dict(status='CONVERGED_BLOCK_SEARCH',initial=initial,selected=current,closed=closed,
        phases=phases,cycles=cycles,visited=sorted(active),cases=cases,summaries=summaries,
        qualified=accepted,strict_downside_improvers=strict,
        repair_status='STRICT_DOWNSIDE_IMPROVEMENT' if reduced_risk(summaries[current['repair']],baseline)
                      else 'NO_STRICT_DOWNSIDE_IMPROVEMENT',
        diagnostic_alternatives=diagnostics,cost_status='COST_INCONCLUSIVE',holdout=False,
        claim=protocol['claim'],finite_domain=SPACE)
    write(out/'results.json',summary)
    for lane,name in current.items():
        write(out/f'selected-{lane}-research.json',dict(status='RESEARCH_ONLY',rules_id=name,
            rules=cases[name]['rules'],lane=lane,protocol_sha256=sha(out/'protocol.json'),
            runtime_qualified=False,adapter_required=True,real_money='PROHIBITED'))
    paths=[p for folder in ('cells','cells-integrity','repeats','repeats-integrity','phases')
           for p in (out/folder).glob('*') if p.is_file()]
    paths += [out/n for n in ('protocol.json','results.json','selected-profit-research.json','selected-repair-research.json')]
    write(out/'COMPLETE.json',dict(status='CONVERGED_BLOCK_SEARCH',selected=current,cycles=cycles,
        visited_cases=len(active),new_economic_cells=len(list((out/'cells').glob('*.json.gz'))),
        reused_parent_cells=len(list((out/'cells-integrity').glob('*.json')))-len(list((out/'cells').glob('*.json.gz'))),
        fresh_repeats=len(list((out/'repeats').glob('*.json.gz'))),
        artifacts={str(p.relative_to(out)):sha(p) for p in paths}))
    print('CONVERGED',current,'visited',len(active),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/c22-learning-loop-2026-10-25')
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();out=(ROOT/args.output).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()) or args.workers not in (1,2,3,4):
        raise ValueError('Require runs/ output and1–4workers')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(out,args.workers)


if __name__=='__main__':
    main()
