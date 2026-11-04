"""Build the audited C22 learning-loop comparison matrix; never replay economics."""

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.research.c22_performance_campaign import ROOT, INPUT, OLD, VIEWS, read, write, sha, diagnostics
from scripts.research.c22_matrix_tuning import closing_recovery
from scripts.research.c22_loop_store import read_cell, load_summary


TARGET = '/Users/nopparuj/.cursor/projects/Users-nopparuj-my-agents-XAUUSD-Scalper/canvases/C22-learning-loop-2026-10-25.canvas.tsx'
ROW20 = 'c22654fea98da73e'
RISK_FIELDS = ('dd', 'recovery', 'severity', 'streak')
SIGNAL_KEYS = ('strategy', 'formula', 'rsi_period', 'rsi_threshold', 'buy_ema',
               'sell_lookback', 'sell_ema', 'macro_span', 'entry_session')


def point(cell, source, proof, origin, last_quote, months):
    result, metrics = cell['result'], cell['metrics']
    assert result['initial_balance'] == 200 and result['swap_policy'] is not None
    assert all(trade['volume'] == .01 for trade in result['ledger'])
    prepared = dict(cell)
    if 'diagnostics' not in prepared:
        prepared['diagnostics'] = diagnostics(result, last_quote)
    prepared['diagnostics'] = dict(prepared['diagnostics'])
    prepared['diagnostics'].setdefault('actual_closing_recovery', closing_recovery(result, last_quote))
    summary = load_summary(prepared)
    monthly = dict.fromkeys(months, 0.)
    for trade in result['ledger']:
        monthly[trade['exit_time_utc'][:7]] += trade['net']
    cash, curve = 200., [200.]
    for month in months:
        cash += monthly[month]
        curve.append(cash)
    assert abs(cash-result['final_balance']) < 1e-7
    risk = summary['risk']
    run = prepared['diagnostics']['worst_run_by_loss_pct']
    run_witness = ({key:run[key] for key in ('start','end','trades','net_usd',
                    'loss_pct_of_start_equity','start_equity','sides')} if run else None)
    dd_witness = max(result.get('context_dd_witnesses',[]),
                     key=lambda x:(x['peak']-x['trough'])/x['peak'],default=None)
    return dict(net=metrics['net_usd'], balance=metrics['final_balance'],
                dd=risk['dd'], streak=risk['streak'], severity=risk['severity'],
                completed_days=risk['completed_days'], ongoing_days=risk['ongoing_days'],
                recovery=risk['recovery'], min_equity=risk['min_equity'],
                longest_run_net=risk['longest_run_net'], longest_run_severity=risk['longest_run_severity'],
                trades=metrics['trades'], pf=metrics['profit_factor'], win_rate=metrics['win_rate'],
                max_initial_risk=metrics['max_admitted_risk_pct'], survival=metrics['survival'],
                net_excluding_top5=metrics['net_excluding_top5_winners'], swap=metrics['swap_usd'],
                commission=metrics['commission_usd'], source=str(source), proof=str(proof),
                origin=origin, curve=curve, witness=dict(worst_run=run_witness,
                recovery=prepared['diagnostics']['actual_closing_recovery'],dd=dd_witness,
                minimum=prepared['diagnostics']['minimum_observed_equity']))


def build(out):
    completion = read(out/'COMPLETE.json')
    assert completion['status'] == 'CONVERGED_BLOCK_SEARCH'
    for name, digest in completion['artifacts'].items():
        assert sha(out/name) == digest, name
    protocol = read(out/'protocol.json')
    for name, digest in protocol['sources'].items():
        assert sha(ROOT/name) == digest, name
    assert sha(INPUT/'manifest.json') == protocol['input_manifest_sha256']
    audit = read(out/'independent-verification.json')
    assert audit['status'] == 'PASS'
    assert audit['parent_completion_sha256'] == sha(out/'COMPLETE.json'), 'Audit completion binding'
    results = read(out/'results.json')
    assert results['status'] == completion['status']
    assert results['selected'] == completion['selected']
    manifest = read(INPUT/'manifest.json')
    last_quote = manifest['last_quote_utc']
    months = [f'{year}-{month:02}' for year in (2024,2025,2026) for month in range(1,13)
              if '2024-09' <= f'{year}-{month:02}' <= '2026-10']
    categories = ['Initial'] + months
    source_hashes = {}
    rows = []

    def historical(label, case_id, key):
        row = dict(id=key, order=len(rows), label=label, roles=['reference'], phases=[],
                   reference=True, paths={}, rules={}, signal={}, source_case_id=case_id)
        for guard in ('raw','cent'):
            paths = {}
            for view in VIEWS:
                filename = f'{case_id}-{view}' + ('-cent' if guard=='cent' else '') + '.json'
                path = OLD/'cells'/filename
                integrity = OLD/'integrity'/filename
                assert sha(path) == read(integrity)['sha256']
                if key == 'research-reference':
                    assert sha(path) == protocol['benchmark_hashes'][str(path.relative_to(ROOT))]
                source_hashes[str(path.relative_to(ROOT))] = sha(path)
                cell = read(path)
                assert cell['guard'] == guard and cell['view'] == view
                paths[view] = point(cell, path, integrity, 'historical-reference', last_quote, months)
                if not row['rules']:
                    row['rules'] = cell['result']['rules']
                    row['signal'] = {k:cell['case']['config'][k] for k in SIGNAL_KEYS}
            row['paths'][guard] = paths
        rows.append(row)

    historical('C22 Demo contract · multi-rule reference', '58e12c454c623996', 'demo-reference')
    historical('Research เดิม · 9e511d195c52ef3d', '646690b541405adf', 'research-reference')
    seed_config = read(ROOT/'config/research-c22-terminal-profit-9e511d195c52ef3d.json')
    signal = {k:seed_config[k] for k in SIGNAL_KEYS}
    membership = {name:[] for name in results['visited']}
    for phase in results['phases']:
        frozen = read(out/'phases'/f'{phase["number"]:03}-catalog.json')
        for case in frozen['catalog']:
            membership[case['name']].append(phase['number'])
    diagnostics_roles = {}
    for role, name in results['diagnostic_alternatives'].items():
        diagnostics_roles.setdefault(name, []).append(role)
    for name in results['visited']:
        case = results['cases'][name]
        roles = list(diagnostics_roles.get(name, []))
        if name == results['initial']:
            roles.append('latest-before-loop')
        if name == ROW20:
            roles.append('old-matrix-row20')
        roles += [lane+'-selected' for lane, identity in results['selected'].items() if name==identity]
        row = dict(id=name, order=len(rows), label=name, roles=roles, phases=membership[name],
                   reference=False, paths={}, rules=case['rules'], signal=signal)
        for guard in ('raw','cent'):
            paths = {}
            for view in VIEWS:
                key = f'{name}-{view}-{guard}'
                proof = out/'cells-integrity'/f'{key}.json'
                if not proof.exists():
                    continue
                binding = read(proof)
                source = ROOT/binding['path']
                cell = read_cell(out, key)
                source_hashes[str(source.relative_to(ROOT))] = binding['sha256']
                paths[view] = point(cell, source, proof, binding['origin'], last_quote, months)
            if paths:
                assert set(paths) == set(VIEWS), 'Partial cost scenario coverage'
                row['paths'][guard] = paths
        assert set(row['paths']['raw']) == set(VIEWS)
        rows.append(row)
    assert len(rows) == len(results['visited'])+2
    latest = next(row for row in rows if row['id']==results['initial'])
    benchmark = next(row for row in rows if row['id']=='research-reference')
    lookup = {row['id']:row for row in rows}
    for row in rows:
        changes = [f'{key}: {latest["rules"][key]} → {value}' for key, value in row['rules'].items()
                   if value != latest['rules'][key]]
        changes += [f'{key}: {latest["signal"][key]} → {value}' for key, value in row['signal'].items()
                    if value != latest['signal'][key]]
        row['changes'] = changes
        row['screen'] = {}
        for guard, paths in row['paths'].items():
            failures, repair_failures = [], []
            for view in VIEWS:
                p, original, old = paths[view], benchmark['paths'][guard][view], latest['paths'][guard][view]
                if view in ('base','stress') and p['net']+1e-7 < original['net']:
                    failures.append(view+' net < original floor')
                if p['dd'] > 40:
                    failures.append(view+' DD > 40%')
                if not p['survival'] or p['net'] <= 0:
                    failures.append(view+' survival/net fail')
                if view in ('base','stress') and p['net']+1e-7 < old['net']:
                    repair_failures.append(view+' net < latest')
                for field in RISK_FIELDS:
                    if p[field] > old[field]+1e-9:
                        repair_failures.append(view+' '+field+' > latest')
                for field in ('net','dd','streak','severity','completed_days','ongoing_days','recovery','min_equity'):
                    p['delta_'+field] = p[field]-old[field]
            row['screen'][guard] = dict(main_pass=not failures, reasons=failures,
                repair_pass=not failures and not repair_failures, repair_reasons=failures+repair_failures)
        row['fully_qualified'] = set(row['paths'])=={'raw','cent'} and all(
            screen['main_pass'] for screen in row['screen'].values())
        row['repair_eligible'] = row['fully_qualified'] and all(
            screen['repair_pass'] for screen in row['screen'].values())
        row['strict_risk_reduction'] = row['repair_eligible'] and any(
            row['paths'][g][v][k] < latest['paths'][g][v][k]-1e-9
            for g in ('raw','cent') for v in VIEWS for k in RISK_FIELDS)
        if set(row['paths']) == {'raw','cent'}:
            row['worst'] = {field:max(row['paths'][g][v][field] for g in ('raw','cent') for v in VIEWS)
                            for field in RISK_FIELDS}
            row['worst']['net'] = min(row['paths'][g][v]['net'] for g in ('raw','cent') for v in VIEWS)
        else:
            row['worst'] = None
        if not row['reference']:
            assert row['fully_qualified'] == (row['id'] in results['qualified'])
            assert row['strict_risk_reduction'] == (row['id'] in results['strict_downside_improvers'])

    phases = []
    seen = set(read(ROOT/'runs/c22-matrix-tuning-2026-10-25/results.json')['cases'])
    for item in results['phases']:
        number = item['number']
        frozen_path = out/'phases'/f'{number:03}-catalog.json'
        frozen = read(frozen_path)
        candidates = [case['name'] for case in frozen['catalog']]
        new = set(candidates)-seen
        seen.update(candidates)
        before, after = lookup[item['incumbent']], lookup[item['selected']]
        main_reasons, repair_reasons = Counter(), Counter()
        for name in candidates:
            row = lookup[name]
            for guard, screen in row['screen'].items():
                main_reasons.update(guard+'/'+reason for reason in screen['reasons'])
                if row['fully_qualified']:
                    repair_reasons.update(guard+'/'+reason for reason in screen['repair_reasons'])
        gain_counts = {}
        for view in ('base','stress'):
            changes = [lookup[name]['paths']['raw'][view]['net']-before['paths']['raw'][view]['net']
                       for name in candidates]
            gain_counts[view] = dict(higher=sum(x>1e-7 for x in changes),
                                    lower=sum(x < -1e-7 for x in changes),
                                    equal=sum(abs(x)<=1e-7 for x in changes))
        factorial = []
        for parameter in protocol['blocks'][item['block']]:
            groups = []
            for value in protocol['domains'][parameter]:
                names = [name for name in candidates if lookup[name]['rules'][parameter]==value]
                assert names
                base_nets = [lookup[name]['paths']['raw']['base']['net'] for name in names]
                stress_nets = [lookup[name]['paths']['raw']['stress']['net'] for name in names]
                raw_dds = [max(lookup[name]['paths']['raw'][v]['dd'] for v in VIEWS) for name in names]
                groups.append(dict(parameter=parameter,value=value,tested=len(names),
                    raw_pass=sum(name in item['raw_qualified'] for name in names),
                    reviewed6_pass=sum(name in item['fully_qualified'] for name in names),
                    base_min=min(base_nets),base_max=max(base_nets),
                    stress_min=min(stress_nets),stress_max=max(stress_nets),
                    raw_maxdd_min=min(raw_dds),raw_maxdd_max=max(raw_dds)))
            assert sum(group['tested'] for group in groups)==len(candidates)
            factorial.extend(groups)
        phases.append(dict(item, declared=len(candidates), new_profiles=len(new),
            candidates=candidates, hypothesis=frozen['hypothesis'], source=str(frozen_path),
            before_worst=before['worst'], after_worst=after['worst'],
            before_base=before['paths']['raw']['base']['net'], after_base=after['paths']['raw']['base']['net'],
            before_stress=before['paths']['raw']['stress']['net'], after_stress=after['paths']['raw']['stress']['net'],
            main_reason_counts=dict(main_reasons.most_common()),
            repair_reason_counts=dict(repair_reasons.most_common()),gain_counts=gain_counts,factorial=factorial))
    assert seen == set(results['visited'])
    role_rows = [('C22 Demo contract','demo-reference'),('Research เดิม','research-reference'),
                 ('Matrix #20',ROW20),('Latest before loop',results['initial']),
                 ('Profit lane selected',results['selected']['profit']),
                 ('Repair lane selected',results['selected']['repair'])]
    role_rows += [(role,name) for role,name in results['diagnostic_alternatives'].items()]
    strict_names = results['strict_downside_improvers']
    best_strict = min(strict_names,key=lambda name:(-lookup[name]['paths']['raw']['base']['net'],
        -lookup[name]['paths']['raw']['stress']['net'],max(lookup[name]['paths']['raw'][v]['dd'] for v in VIEWS),name)) if strict_names else None
    if best_strict:
        role_rows.append(('Best-base strict downside alternative',best_strict))
        lookup[best_strict]['roles'].append('best-strict-downside-alternative')
    data = dict(rows=rows, phases=phases, role_rows=[dict(label=label,id=name) for label,name in role_rows],
        initial=results['initial'], selected=results['selected'], repair_status=results['repair_status'],
        cycles=results['cycles'], visited_cases=len(results['visited']), finite_domain=results['finite_domain'],
        qualified=len(results['qualified']), strict_improvers=len(results['strict_downside_improvers']),
        selected_repair_strict=lookup[results['selected']['repair']]['strict_risk_reduction'],best_strict=best_strict,
        new_economic_cells=completion['new_economic_cells'], reused_cells=completion['reused_parent_cells'],
        fresh_repeats=completion['fresh_repeats'], source_hashes=source_hashes,
        categories=categories, raw_rows=len(rows), cent_rows=sum('cent' in r['paths'] for r in rows),
        first_quote_utc=manifest['first_quote_utc'], last_quote_utc=last_quote,
        completion_sha256=sha(out/'COMPLETE.json'), verification_sha256=sha(out/'independent-verification.json'),
        broker=protocol['broker'], views=protocol['views'], cost_status='COST_INCONCLUSIVE', holdout=False,
        source_economic_replays=0)
    write(out/'matrix.json',data)
    source = CANVAS.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')))
    for key, path in dict(PROTOCOL=out/'protocol.json', MATRIX=out/'matrix.json',
                          AUDIT=out/'independent-verification.json',
                          PROFIT=out/'selected-profit-research.json',REPAIR=out/'selected-repair-research.json').items():
        source = source.replace('__'+key+'__',str(path))
    (out/'canvas-source.txt').write_text(source)
    proof = dict(status='SOURCE_DATA_CHECKED',economic_replays=0,rows=len(rows),
        cent_rows=data['cent_rows'],source_cells=len(source_hashes),
        curve_points=sum(len(p['curve']) for row in rows for paths in row['paths'].values() for p in paths.values()),
        completion_sha256=sha(out/'COMPLETE.json'),verification_sha256=sha(out/'independent-verification.json'),
        matrix_sha256=sha(out/'matrix.json'),canvas_source_sha256=sha(out/'canvas-source.txt'),
        builder_sha256=sha(Path(__file__)),intended_canvas=TARGET)
    write(out/'MATRIX-COMPLETE.json',proof)
    print(json.dumps(proof,indent=2))


CANVAS = '''import {Stack,Row,H1,H2,Text,Table,Select,LineChart,Callout,Link,useCanvasState} from "cursor/canvas";
type Witness={worst_run:{start:string;end:string;trades:number;net_usd:number;loss_pct_of_start_equity:number;start_equity:number;sides:Record<string,number>}|null;recovery:{longest_completed:{start:string;first_underwater_exit:string;end:string;days:number;previous_peak:number;recovered_to:number}|null;ongoing:{start:string;first_underwater_exit:string;balance:number;days:number;previous_peak:number}|null;completed_count:number};dd:{time_utc:string;peak:number;trough:number}|null;minimum:{time_utc:string;equity_usd:number}|null};
type Point={net:number;balance:number;dd:number;streak:number;severity:number;completed_days:number;ongoing_days:number;recovery:number;min_equity:number;longest_run_net:number;longest_run_severity:number;trades:number;pf:number|null;win_rate:number;max_initial_risk:number;survival:boolean;net_excluding_top5:number;swap:number;commission:number;source:string;proof:string;origin:string;curve:number[];witness:Witness;delta_net:number;delta_dd:number;delta_streak:number;delta_severity:number;delta_completed_days:number;delta_ongoing_days:number;delta_recovery:number;delta_min_equity:number};
type Screen={main_pass:boolean;reasons:string[];repair_pass:boolean;repair_reasons:string[]};
type Worst={dd:number;recovery:number;severity:number;streak:number;net:number};
type Experiment={id:string;order:number;label:string;roles:string[];phases:number[];reference:boolean;rules:Record<string,string|number|boolean|null>;signal:Record<string,string|number|boolean|null>;changes:string[];paths:{raw:Record<string,Point>;cent?:Record<string,Point>};screen:{raw:Screen;cent?:Screen};fully_qualified:boolean;repair_eligible:boolean;strict_risk_reduction:boolean;worst:Worst|null;[key:string]:unknown};
type Phase={number:number;cycle:number;lane:string;block:string;incumbent:string;selected:string;improved:boolean;declared:number;new_profiles:number;raw_qualified:string[];fully_qualified:string[];candidates:string[];hypothesis:string;source:string;before_worst:Worst;after_worst:Worst;before_base:number;after_base:number;before_stress:number;after_stress:number;main_reason_counts:Record<string,number>;repair_reason_counts:Record<string,number>;gain_counts:Record<string,{higher:number;lower:number;equal:number}>;factorial:{parameter:string;value:string|number;tested:number;raw_pass:number;reviewed6_pass:number;base_min:number;base_max:number;stress_min:number;stress_max:number;raw_maxdd_min:number;raw_maxdd_max:number}[];[key:string]:unknown};
type Data={rows:Experiment[];phases:Phase[];role_rows:{label:string;id:string}[];initial:string;selected:{profit:string;repair:string};repair_status:string;selected_repair_strict:boolean;best_strict:string|null;cycles:number;visited_cases:number;finite_domain:number;qualified:number;strict_improvers:number;new_economic_cells:number;reused_cells:number;fresh_repeats:number;categories:string[];raw_rows:number;cent_rows:number;first_quote_utc:string;last_quote_utc:string;cost_status:string;holdout:boolean;[key:string]:unknown};
const DATA:Data=__DATA__;
const usd=(n:number)=>"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const f=(n:number)=>n.toFixed(2),delta=(n:number)=>`${n>0?"+":""}${n.toFixed(2)}`;
const label=(r:Experiment)=>r.roles.length?r.roles.join(" / "):"#"+r.order;
export default function LearningLoopMatrix(){
 const [view,setView]=useCanvasState("c22-learning-view","base");
 const [guard,setGuard]=useCanvasState("c22-learning-guard","raw");
 const [phase,setPhase]=useCanvasState("c22-learning-phase","all");
 const [filter,setFilter]=useCanvasState("c22-learning-filter","all");
 const [sort,setSort]=useCanvasState("c22-learning-sort","walk");
 const [detail,setDetail]=useCanvasState("c22-learning-detail",DATA.selected.profit);
 const v=["base","stress","fee"].includes(view)?view:"base",g=guard==="cent"?"cent":"raw";
 const latest=DATA.rows.find(x=>x.id===DATA.initial)!,profit=DATA.rows.find(x=>x.id===DATA.selected.profit)!,repair=DATA.rows.find(x=>x.id===DATA.selected.repair)!;
 const visible=DATA.rows.filter(x=>x.paths[g]&&(x.reference||x.roles.length>0||((phase==="all"||x.phases.includes(Number(phase)))&&(filter==="all"||filter==="qualified"&&x.fully_qualified||filter==="repair"&&x.repair_eligible||filter==="failed"&&!x.fully_qualified)))).sort((a,b)=>sort==="profit"?b.paths[g]![v].net-a.paths[g]![v].net:sort==="dd"?a.paths[g]![v].dd-b.paths[g]![v].dd:sort==="recovery"?a.paths[g]![v].recovery-b.paths[g]![v].recovery:a.order-b.order);
 const chosen=visible.find(x=>x.id===detail)??visible.find(x=>x.id===DATA.selected.profit)??visible[0];
 const p=chosen.paths[g]![v],old=latest.paths[g]![v];
 const selectedPhase=DATA.phases.find(x=>String(x.number)===phase);
 const status=(r:Experiment)=>r.reference?"REFERENCE":r.fully_qualified?"PASS reviewed6":r.screen[g]!.main_pass?"PASS current counter only":"FAIL";
 return <Stack gap={18} style={{padding:24,maxWidth:1600,margin:"0 auto"}}>
  <H1>C22 learning loop — profit กับ downside แสดงแยกชัด</H1>
  <Text weight="semibold">Profit lane: raw base {usd(profit.paths.raw.base.net)} · raw stress {usd(profit.paths.raw.stress.net)} · worst6 DD {f(profit.worst!.dd)}%</Text>
  <Text>Repair lane selected: {DATA.selected_repair_strict?"ลดriskจริงครบเงื่อนไข":"ยังไม่ลดriskแบบstrict"} · raw base {usd(repair.paths.raw.base.net)} · worst6 DD {f(repair.worst!.dd)}% · recovery/ongoing age {f(repair.worst!.recovery)}days</Text>
  <Text size="small">พบstrict downside alternativesทั้งหมด {DATA.strict_improvers}profiles. {DATA.best_strict?`ตัวbaseสูงสุดในกลุ่มนี้: ${DATA.best_strict}`:"ไม่มีprofileที่ผ่านเงื่อนไขลดriskแบบstrictในชุดที่ประเมิน"}. Selected-lane statusแสดงแยกจากการมีalternativeอื่น</Text>
  <Callout tone="warning" title="Converged conditional blocks; exposed-history research">
   ค้น {DATA.visited_cases}profiles จาก domain {DATA.finite_domain}ชุด. Core96และmanagement54ครบรอบรอบตัวนำทั้งสองlaneแล้วไม่ดีขึ้น. นี่คือblock closure ไม่ใช่ค้นครบglobal5184หรือพิสูจน์กำไรอนาคต. COST_INCONCLUSIVE · Demoยังไม่เปลี่ยน
  </Callout>
  <Text size="small" tone="secondary">171,171,013Exness XAUUSDm Bid/Ask quotes · {DATA.first_quote_utc}–{DATA.last_quote_utc} · $200ต่อเนื่อง/fixed0.01/singleposition/cap10%/daily10%/count2. ทุกscenarioรวมmodeledswap;historicalbroker rates/calendar/fillsยังไม่attest</Text>
  <Text size="small" tone="secondary">Profit: original9e base/stress floors +positive/survival/DD≤40%ครบ6;rank rawbase→rawstress→lowerrawmaxDD. Repairเป็นทางเลือกเพิ่ม: matchedlatestprofitsและDD/recovery/severity/countทุกpathไม่แย่กว่าlatest;rank worst6DD→recovery→severity→count→profit. ไม่ใช่เปลี่ยนเกณฑ์หลักเงียบ ๆ</Text>
  <Text size="small" tone="secondary">Baseใช้Bid/Askบันทึกจริง;stressเพิ่มspread$0.20/oz+adverse slippage$0.10/ozต่อmarketfill;feeเพิ่มสมมติ$7/lotroundtrip. Swap snapshot long−567.4/short0 pointmode1,point0.001,100oz/lot,prior-business-day UTCmidnight/Wednesday×3. ค่าเหล่านี้ยังเป็นmodeled assumptions</Text>
  <Row gap={12} wrap><Text>Cost view</Text><Select value={v} onChange={setView} options={[{value:"base",label:"Base + swap"},{value:"stress",label:"Spread/slippage stress + swap"},{value:"fee",label:"Stress + hypothetical fee + swap"}]}/><Text>Loss counter</Text><Select value={g} onChange={setGuard} options={[{value:"raw",label:`Raw · ${DATA.raw_rows} rows`},{value:"cent",label:`Cent · ${DATA.cent_rows} reviewed rows`}]}/></Row>
  <H2>เทียบรุ่นเก่า → ตัวนำล่าสุด → สองคำตอบจากloop</H2>
  <Text size="small" tone="secondary">Netด้านล่างใช้{g};riskworst6ใช้ทุกraw/cent costviewที่รันจริง. Demoเป็นreferenceหลายruleต่างกัน รวมRSI/SELLlookback จึงไม่ใช่one-factor control. ค่าDemoเป็นhistorical replay ไม่ใช่brokerPnLจริง</Text>
  <Table headers={["Version / role","Rules ID","Base net USD","Stress net USD","Fee net USD","Worst6 DD%","Worst6 severity%","Worst6 streak","Worst6 completed/ongoing days","Worst6 net USD","Main6 / repair6"]} rows={DATA.role_rows.map(role=>{const r=DATA.rows.find(x=>x.id===role.id)!,w=r.worst!;return [role.label,r.id,usd(r.paths[g]!.base.net),usd(r.paths[g]!.stress.net),usd(r.paths[g]!.fee.net),f(w.dd),f(w.severity),w.streak,f(w.recovery),usd(w.net),`${r.fully_qualified?"PASS":"REF/FAIL"} / ${r.repair_eligible?"PASS":"FAIL"}`]})}/>
  <H2>Learning ledger — ตรึงทางเลือก → ทดสอบ → เรียนรู้ผลเสียจริง</H2>
  <Text size="small">{DATA.cycles}cycles · {DATA.phases.length}slices · {DATA.new_economic_cells}new economic cells · {DATA.reused_cells}hash-bound reused cells · {DATA.fresh_repeats}fresh full-result repeats. All raw-qualifiedได้centครบ ไม่มีtop2 shortcut. Failed casesยังอยู่</Text>
  <Table headers={["Phase / cycle","Lane / block","Declared profiles","New profiles","Raw / full6 pass","Before → after","Δraw base USD","Δraw stress USD","Worst6 DD before→after%","Worst6 recovery before→after days","Decision"]} rows={DATA.phases.map(x=>[`${x.number} / ${x.cycle}`,`${x.lane} / ${x.block}`,x.declared,x.new_profiles,`${x.raw_qualified.length} / ${x.fully_qualified.length}`,`${x.incumbent} → ${x.selected}`,delta(x.after_base-x.before_base),delta(x.after_stress-x.before_stress),`${f(x.before_worst.dd)} → ${f(x.after_worst.dd)}`,`${f(x.before_worst.recovery)} → ${f(x.after_worst.recovery)}`,x.improved?"strict improvement":"คงตัวนำ"])} stickyHeader/>
  <H2>Outcome matrix — ทุกprofileและข้อเสียที่วัดได้</H2>
  <Row gap={12} wrap><Text>Slice</Text><Select value={phase} onChange={setPhase} options={[{value:"all",label:"ทุกphase +references/leaders"},...DATA.phases.map(x=>({value:String(x.number),label:`${x.number} · ${x.lane}/${x.block}`}))]}/><Text>กรอง</Text><Select value={filter} onChange={setFilter} options={[{value:"all",label:"ทั้งหมด"},{value:"qualified",label:"ผ่านหลักครบ6"},{value:"repair",label:"ผ่านrepairครบ6"},{value:"failed",label:"ยังไม่ผ่านครบ6"}]}/><Text>เรียง</Text><Select value={sort} onChange={setSort} options={[{value:"walk",label:"ลำดับคงที่"},{value:"profit",label:"Scenario net มาก→น้อย"},{value:"dd",label:"Scenario DD น้อย→มาก"},{value:"recovery",label:"Scenario recovery/age สั้น→ยาว"}]}/></Row>
  {selectedPhase&&<Stack gap={6}><Text size="small">Phase{selectedPhase.number}: {selectedPhase.hypothesis}. Complete catalog: <Link href={selectedPhase.source}>source</Link></Text><Text size="small">Rawbaseสูง/ต่ำ/เท่ากับincumbent: {selectedPhase.gain_counts.base.higher}/{selectedPhase.gain_counts.base.lower}/{selectedPhase.gain_counts.base.equal};rawstress: {selectedPhase.gain_counts.stress.higher}/{selectedPhase.gain_counts.stress.lower}/{selectedPhase.gain_counts.stress.equal}. เป็นผลเปรียบเทียบfullaccount ไม่ใช่isolated causal attribution</Text>{Object.keys(selectedPhase.main_reason_counts).length>0&&<Table headers={["Main rejection · scenario-level reason","Occurrences"]} rows={Object.entries(selectedPhase.main_reason_counts).map(([reason,count])=>[reason,count])}/>} {Object.keys(selectedPhase.repair_reason_counts).length>0&&<Table headers={["Repair rejection among fully-qualified profiles","Occurrences"]} rows={Object.entries(selectedPhase.repair_reason_counts).map(([reason,count])=>[reason,count])}/>}<H2>ค่าแต่ละfactorในsliceนี้ให้ช่วงผลแบบไหน</H2><Text size="small" tone="secondary">Descriptive rangesจากทุกconditional combinationในsliceเดียวกัน;ยึดrawcounterและครบ3costviews. ไม่ใช่causalผลแยกfactorหรือforecast. Base/stressเป็นnetUSD;DDเป็นworstraw3viewsของแต่ละprofile</Text><Table headers={["Parameter","Value","Tested","Raw / reviewed6 pass","Base net range USD","Stress net range USD","WorstrawDD range %"]} rows={selectedPhase.factorial.map(x=>[x.parameter,String(x.value),x.tested,`${x.raw_pass}/${x.reviewed6_pass}`,`${usd(x.base_min)} → ${usd(x.base_max)}`,`${usd(x.stress_min)} → ${usd(x.stress_max)}`,`${f(x.raw_maxdd_min)} → ${f(x.raw_maxdd_max)}`])}/></Stack>}
  <Text size="small" tone="secondary">Risk columnsใช้{v}/{g};ΔDDหน่วยpercentage pointsเทียบlatest26b8. Recovery=max(actualcompleted,ongoingage);ongoingคือcensored ageถึงlastquote ไม่ใช่เวลาฟื้นที่รู้แล้ว. Severity=worst losing-runloss%starting equity ไม่ใช่runที่countยาวสุด. Centที่ไม่ได้รันไม่ถูกแทนด้วยraw</Text>
  <Table stickyHeader headers={["Row / roles","Rules ID","Δvs latest","Base net USD","Stress net USD","Fee net USD",`${v} DD%`,"ΔDD pp","Min equity USD","Loss streak","Worst-run severity%","Completed days","Ongoing age days","Main screen","เหตุผลmain","Repair screen / เหตุผล"]} rows={visible.map(r=>{const q=r.paths[g]![v],s=r.screen[g]!;return [label(r),r.id,r.changes.join("; ")||"ไม่เปลี่ยน",usd(r.paths[g]!.base.net),usd(r.paths[g]!.stress.net),usd(r.paths[g]!.fee.net),f(q.dd),delta(q.delta_dd),usd(q.min_equity),q.streak,f(q.severity),f(q.completed_days),f(q.ongoing_days),status(r),s.reasons.join("; ")||"ตรงprofit/DD",r.repair_eligible?"PASS reviewed6":s.repair_reasons.join("; ")||"currentcounter pass only"]})}/>
  <H2>เจาะทีละข้อ — matched cost/counterเทียบlatestก่อนloop</H2>
  <Select value={chosen.id} onChange={setDetail} options={visible.map(r=>({value:r.id,label:`${label(r)} · ${r.id}`}))}/>
  <Text weight="semibold">{label(chosen)} · {chosen.id}</Text>
  <Text>เปลี่ยนจากlatest: {chosen.changes.join("; ")||"ไม่เปลี่ยน"}. Phases: {chosen.phases.join(", ")||"historical/cache reference"}</Text>
  <Table headers={["Metric",`${v}/${g} chosen`,"Latest26b8", "Δchosen−latest"]} rows={[["Net USD",usd(p.net),usd(old.net),delta(p.delta_net)+"USD"],["Equity DD %",f(p.dd),f(old.dd),delta(p.delta_dd)+"pp"],["Minimum equity USD",usd(p.min_equity),usd(old.min_equity),delta(p.delta_min_equity)+"USD"],["Longest loss streak · trades",p.streak,old.streak,delta(p.delta_streak)+"trades"],["Worst-run severity · %starting equity",f(p.severity),f(old.severity),delta(p.delta_severity)+"pp"],["Longest-count-run net · USD",usd(p.longest_run_net),usd(old.longest_run_net),usd(p.longest_run_net-old.longest_run_net)],["Longest-count-run severity · %",f(p.longest_run_severity),f(old.longest_run_severity),delta(p.longest_run_severity-old.longest_run_severity)+"pp"],["Completed closing recovery · days",f(p.completed_days),f(old.completed_days),delta(p.delta_completed_days)+"days"],["Ongoing closing drawdown age · days",f(p.ongoing_days),f(old.ongoing_days),delta(p.delta_ongoing_days)+"days"],["Max completed/ongoing · days",f(p.recovery),f(old.recovery),delta(p.delta_recovery)+"days"],["Net less top5 winner attribution · USD",usd(p.net_excluding_top5),usd(old.net_excluding_top5),usd(p.net_excluding_top5-old.net_excluding_top5)],["Swap USD",usd(p.swap),usd(old.swap),usd(p.swap-old.swap)],["Trades / win rate",`${p.trades} / ${f(p.win_rate*100)}%`,`${old.trades} / ${f(old.win_rate*100)}%`,`${p.trades-old.trades}trades`]]}/>
  <Text size="small" tone="secondary">Negative protected/swap exitsยังเป็นloss. Severityเทียบกันอาจเป็นคนละepisode;netที่หักtop5เป็นledger attribution ไม่ใช่replayตัด5tradeแล้วคำนวณใหม่. Profit/feesเปลี่ยนadmission/holding pathได้ จึงไม่แปลว่าต้นทุนเพิ่มทำให้กำไรดีขึ้นโดยตรง</Text>
  {(p.witness.worst_run||p.witness.recovery.longest_completed||p.witness.recovery.ongoing||p.witness.dd)&&<Stack gap={8}><H2>Source witnesses — จุดเสียหายจากledger/tickจริง</H2><Table headers={["Witness",`${v}/${g} chosen`]} rows={[
   ...(p.witness.worst_run?[["Worst losing-run",`${p.witness.worst_run.start} → ${p.witness.worst_run.end}; ${p.witness.worst_run.trades}trades; ${usd(p.witness.worst_run.net_usd)} / starting ${usd(p.witness.worst_run.start_equity)} = ${f(p.witness.worst_run.loss_pct_of_start_equity)}%; sides ${JSON.stringify(p.witness.worst_run.sides)}`]]:[]),
   ...(p.witness.recovery.longest_completed?[["Actual completed closing recovery",`${p.witness.recovery.longest_completed.start} → ${p.witness.recovery.longest_completed.end}; ${f(p.witness.recovery.longest_completed.days)}days`]]:[]),
   ...(p.witness.recovery.ongoing?[["Ongoing closing drawdown · censored",`${p.witness.recovery.ongoing.start} → lastquote ${DATA.last_quote_utc}; age ${f(p.witness.recovery.ongoing.days)}days`]]:[]),
   ...(p.witness.dd?[["Observed tick DD witness",`${p.witness.dd.time_utc}; peak ${usd(p.witness.dd.peak)} → trough ${usd(p.witness.dd.trough)}`]]:[])
  ]}/><Text size="small" tone="secondary">Witnessเป็นเหตุการณ์ที่เกิดภายใต้แต่ละstrategy;การกรองจุดนั้นภายหลังไม่ได้พิสูจน์ว่าผลfullpathจะดีขึ้น. ใช้ตรวจสมมติฐานรอบใหม่ก่อนตรึงcatalog ไม่เพิ่มกฎอ้างอิงวันที่แพ้ย้อนหลัง</Text></Stack>}
  <H2>Parameter matrix — native management + signal contract</H2>
  <Table headers={["Parameter","Chosen","Latest before loop"]} rows={[...Object.keys(chosen.signal),"buy_stop_atr","buy_target_rr","stop_atr","target_rr","cooldown_bars","protect_after_r","buy_protect_mode","protect_mode","risk_cap","daily_loss_limit","max_daily_losses","sizing_mode"].map(k=>[k,String(k in chosen.signal?chosen.signal[k]:chosen.rules[k]),String(k in latest.signal?latest.signal[k]:latest.rules[k])])}/>
  <Text size="small" tone="secondary">Cooldown=elapsed15minหลังnetloss รวมmarketclosure. GlobalBEactivationเปลี่ยนทั้งBUY/SELL;SELLTPต่ำกว่าactivationอาจจบก่อนactivate. Stopระยะกว้างเปลี่ยนriskUSD/target/admissionที่fixedlot. BEราคาไม่รับประกันnet≥0หลังswap/gap</Text>
  <H2>Initial $200 + cumulative net attributed to exit month</H2>
  <Text size="small" tone="secondary">X=exitmonthUTC;Y=USD. Source:savedExnessreplayledgers,2024-09–2026-10. Monthlyclosing-tradeattribution ไม่ใช่tickequity/MT5chart;ไม่แสดงfloatingDDหรือentryfee timingของไม้ข้ามเดือน. Legendแยกchosen/latest/profitlane</Text>
  <LineChart categories={DATA.categories} series={[{name:`Chosen · ${chosen.id}`,data:p.curve},{name:"Latest before loop · 26b8",data:old.curve},{name:`Profit lane · ${profit.id}`,data:profit.paths[g]![v].curve}]} height={300} valuePrefix="$" fill={false} referenceLines={[{value:200,label:"Initial $200"}]}/>
  <Row gap={16} wrap><Link href={p.proof}>Chosen source hash proof</Link><Link href={p.source}>Chosen full saved cell</Link><Link href="__MATRIX__">Matrix data</Link><Link href="__PROTOCOL__">Frozen protocol</Link><Link href="__AUDIT__">Independent audit</Link><Link href="__PROFIT__">Profit research descriptor</Link><Link href="__REPAIR__">Repair research descriptor</Link></Row>
  <Text size="small" tone="secondary">Descriptorเป็นresearch-only ต้องทำadapter/broker/forwardreviewก่อนDemo. ข้อมูลทั้งหมดเคยถูกใช้ค้นแล้ว;การรันซ้ำและตรวจบัญชีไม่สร้างข้อมูลตลาดอิสระ. DD40เป็นhistoricalqualification ไม่รับประกันfutureDD</Text>
 </Stack>;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/c22-learning-loop-2026-10-25')
    args = parser.parse_args()
    out = (ROOT/args.output).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Machine outputs must remain under runs/')
    build(out)


if __name__ == '__main__':
    main()
