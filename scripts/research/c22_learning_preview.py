"""C22 partial matrix."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from scripts.research.c22_performance_campaign import ROOT, INPUT, OLD, VIEWS, read, write, sha, diagnostics
from scripts.research.c22_loop_store import read_cell, load_summary
from scripts.research.c22_matrix_tuning import closing_recovery

TARGET = '/Users/nopparuj/.cursor/projects/Users-nopparuj-my-agents-XAUUSD-Scalper/canvases/C22-learning-loop-2026-10-25.canvas.tsx'
KEY = re.compile(r'([0-9a-f]{16})-(base|stress|fee)-(raw|cent)\Z')


def screen(paths, floor):
    reasons = [v+' net < original floor' for v in ('base','stress')
               if paths[v]['net']+1e-7 < floor[v]['net_usd']]
    for view, p in paths.items():
        if p['dd'] > 40:
            reasons.append(view+' DD>40%')
        if not p['survival'] or p['net'] <= 0:
            reasons.append(view+' survival/net fail')
    return dict(passed=not reasons,reasons=reasons)


def point(cell, source, proof, last_quote):
    c = dict(cell)
    if 'diagnostics' not in c:
        c['diagnostics'] = diagnostics(c['result'],last_quote)
    c['diagnostics'] = dict(c['diagnostics'])
    if 'actual_closing_recovery' not in c['diagnostics']:
        c['diagnostics']['actual_closing_recovery'] = closing_recovery(c['result'],last_quote)
    summary = load_summary(c)
    m, risk = summary['metrics'], summary['risk']
    assert c['result']['swap_policy'] is not None and c['result']['initial_balance']==200
    return dict(net=m['net_usd'],balance=m['final_balance'],dd=risk['dd'],streak=risk['streak'],
        severity=risk['severity'],completed_days=risk['completed_days'],ongoing_days=risk['ongoing_days'],
        recovery=risk['recovery'],min_equity=risk['min_equity'],survival=m['survival'],
        trades=m['trades'],source=str(source),proof=str(proof))


def build(out):
    assert not (out/'COMPLETE.json').exists(), 'Use final report after completed independent audit'
    proto = read(out/'protocol.json')
    assert sha(INPUT/'manifest.json') == proto['input_manifest_sha256']
    progress = read(out/'progress.json')
    manifest = read(INPUT/'manifest.json')
    groups = {}
    proofs = sorted((out/'cells-integrity').glob('*.json'))
    for proof in proofs:
        match = KEY.fullmatch(proof.stem)
        assert match,proof.name
        name,view,guard = match.groups()
        groups.setdefault(name,{}).setdefault(guard,{})[view] = proof
    rows, hashes = [], {}
    for name in sorted(groups,key=lambda n:(n!=proto['initial'],n)):
        coverage = groups[name]
        if set(coverage.get('raw',{})) != set(VIEWS):
            continue
        row = dict(id=name,reference=False,label='Latest before loop' if name==proto['initial'] else name,
                   rules={},paths={})
        for guard in ('raw','cent'):
            if set(coverage.get(guard,{})) != set(VIEWS):
                continue
            paths = {}
            for view in VIEWS:
                proof = coverage[guard][view]
                binding = read(proof)
                cell = read_cell(out,proof.stem)
                source = ROOT/binding['path']
                hashes[str(source.relative_to(ROOT))] = binding['sha256']
                paths[view] = point(cell,source,proof,manifest['last_quote_utc'])
                if not row['rules']:
                    row['rules'] = cell['result']['rules']
            row['paths'][guard] = paths
        rows.append(row)
    assert rows and rows[0]['id']==proto['initial'] and 'cent' in rows[0]['paths']
    for label,name,key in [('C22 Demo · multi-rule reference','58e12c454c623996','demo'),
                           ('Research original9e','646690b541405adf','original')]:
        row = dict(id=key,reference=True,label=label,rules={},paths={})
        for guard in ('raw','cent'):
            row['paths'][guard] = {}
            for view in VIEWS:
                filename=f'{name}-{view}'+('-cent' if guard=='cent' else '')+'.json'
                source,proof=OLD/'cells'/filename,OLD/'integrity'/filename
                assert sha(source)==read(proof)['sha256']
                hashes[str(source.relative_to(ROOT))]=sha(source)
                cell=read(source)
                row['paths'][guard][view]=point(cell,source,proof,manifest['last_quote_utc'])
                row['rules']=cell['result']['rules']
        rows.insert(0,row)
    latest = next(r for r in rows if r['id']==proto['initial'])
    for index,row in enumerate(rows):
        row['order']=index
        row['changes']=[f'{k}: {latest["rules"][k]} → {v}' for k,v in row['rules'].items()
                        if v!=latest['rules'][k]]
        if row['id']=='demo':
            row['changes'].insert(0,'Signal contract differs: RSI14cross25/SELL96 vs RSI7cross30/SELL48')
        row['screen']={g:screen(paths,proto['original_floors'][g]) for g,paths in row['paths'].items()}
        row['reviewed6']=set(row['paths'])=={'raw','cent'}
        row['qualified6']=row['reviewed6'] and all(s['passed'] for s in row['screen'].values())
        for guard,paths in row['paths'].items():
            for view,p in paths.items():
                for field in ('net','dd','streak','severity','recovery','min_equity'):
                    p['delta_'+field]=p[field]-latest['paths'][guard][view][field]
    catalogs=[]
    for path in sorted((out/'phases').glob('*-catalog.json')):
        c=read(path);rp=path.with_name(path.name.replace('-catalog','-result'))
        catalogs.append(dict(number=c['number'],lane=c['lane'],block=c['block'],declared=len(c['catalog']),
            completed=rp.exists(),source=str(path)))
    data=dict(status='PARTIAL_NOT_A_FINAL_RESULT',created_utc=datetime.now(timezone.utc).isoformat(),
        progress=progress,rows=rows,catalogs=catalogs,initial=proto['initial'],
        ready_profiles=len(rows)-2,omitted_incomplete_profiles=len(groups)-(len(rows)-2),
        cent_rows=sum('cent' in r['paths'] for r in rows),source_hashes=hashes,
        first_quote_utc=manifest['first_quote_utc'],last_quote_utc=manifest['last_quote_utc'],
        protocol_sha256=sha(out/'protocol.json'),cost_status='COST_INCONCLUSIVE',
        independent_final_audit=False,economic_replays=0)
    write(out/'interim-matrix.json',data)
    source=CANVAS.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')))
    source=source.replace('__MATRIX__',str(out/'interim-matrix.json')).replace('__PROTOCOL__',str(out/'protocol.json'))
    (out/'interim-canvas-source.txt').write_text(source)
    proof=dict(status=data['status'],ready_profiles=data['ready_profiles'],cent_rows=data['cent_rows'],
        omitted_incomplete_profiles=data['omitted_incomplete_profiles'],economic_replays=0,
        matrix_sha256=sha(out/'interim-matrix.json'),canvas_source_sha256=sha(out/'interim-canvas-source.txt'),
        builder_sha256=sha(Path(__file__)),intended_canvas=TARGET)
    write(out/'INTERIM-COMPLETE.json',proof)
    print(json.dumps(proof,indent=2))


CANVAS='''import {Stack,Row,H1,H2,Text,Table,Select,Callout,Link,useCanvasState} from "cursor/canvas";
type Point={net:number;balance:number;dd:number;streak:number;severity:number;completed_days:number;ongoing_days:number;recovery:number;min_equity:number;survival:boolean;trades:number;source:string;proof:string;delta_net:number;delta_dd:number;delta_streak:number;delta_severity:number;delta_recovery:number;delta_min_equity:number};
type Experiment={id:string;order:number;reference:boolean;label:string;changes:string[];rules:Record<string,string|number|boolean|null>;paths:{raw:Record<string,Point>;cent?:Record<string,Point>};screen:{raw:{passed:boolean;reasons:string[]};cent?:{passed:boolean;reasons:string[]}};reviewed6:boolean;qualified6:boolean};
type Data={status:string;created_utc:string;progress:{phase:string;done:number;new_jobs:number;visited_cases:number;[key:string]:unknown};rows:Experiment[];catalogs:{number:number;lane:string;block:string;declared:number;completed:boolean;source:string}[];initial:string;ready_profiles:number;omitted_incomplete_profiles:number;cent_rows:number;first_quote_utc:string;last_quote_utc:string;[key:string]:unknown};
const DATA:Data=__DATA__;
const usd=(n:number)=>"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const f=(n:number)=>n.toFixed(2),d=(n:number)=>`${n>0?"+":""}${n.toFixed(2)}`;
export default function LearningPreview(){
 const [view,setView]=useCanvasState("c22-learning-preview-view","base");
 const [guard,setGuard]=useCanvasState("c22-learning-preview-guard","raw");
 const [sort,setSort]=useCanvasState("c22-learning-preview-sort","order");
 const [detail,setDetail]=useCanvasState("c22-learning-preview-detail",DATA.initial);
 const v=["base","stress","fee"].includes(view)?view:"base",g=guard==="cent"?"cent":"raw";
 const latest=DATA.rows.find(r=>r.id===DATA.initial)!;
 const visible=DATA.rows.filter(r=>r.paths[g]).sort((a,b)=>sort==="profit"?b.paths[g]![v].net-a.paths[g]![v].net:sort==="dd"?a.paths[g]![v].dd-b.paths[g]![v].dd:a.order-b.order);
 const chosen=visible.find(r=>r.id===detail)??latest,p=chosen.paths[g]![v],old=latest.paths[g]![v];
 return <Stack gap={18} style={{padding:24,maxWidth:1550,margin:"0 auto"}}>
 <H1>C22 tuning loop — Matrixระหว่างรัน</H1>
 <Callout tone="warning" title="PARTIAL · ยังไม่มีผู้ชนะรอบสุดท้าย">นี่คือsnapshotจากcasesที่รันครบ3costviewsแล้ว. Loopและindependentfinalauditยังไม่จบ;การเรียงกำไรไม่ใช่การเลือกstrategy. ห้ามใช้เป็นคำยืนยันผลสุดท้ายหรือเปลี่ยนDemo</Callout>
 <Text>Snapshot {DATA.created_utc} · phase {DATA.progress.phase}: {DATA.progress.done}/{DATA.progress.new_jobs}newjobs ในphaseนี้. พร้อมเทียบ {DATA.ready_profiles}researchprofiles +2historicalreferences;ละ {DATA.omitted_incomplete_profiles}profilesที่ยังไม่ครบraw3views</Text>
 <Text size="small" tone="secondary">171,171,013Exness Bid/Ask quotes · {DATA.first_quote_utc}–{DATA.last_quote_utc} · initial$200/fixed0.01/cap10%/daily10%/count2. ทุกeconomicviewรวมmodeledswap;COST_INCONCLUSIVE/ข้อมูลเคยใช้ค้นแล้ว/ไม่มีfreshholdout. Demoเดิมยังไม่เปลี่ยน</Text>
 <Table headers={["Phase","Lane / block","Declared profiles","Status","Catalog"]} rows={DATA.catalogs.map(c=>[c.number,`${c.lane}/${c.block}`,c.declared,c.completed?"slice complete; loopยังไม่final":"IN PROGRESS",<Link href={c.source}>frozen source</Link>])}/>
 <Row gap={12} wrap><Text>Cost view</Text><Select value={v} onChange={setView} options={[{value:"base",label:"Base + swap"},{value:"stress",label:"Price stress + swap"},{value:"fee",label:"Stress + hypothetical fee + swap"}]}/><Text>Counter</Text><Select value={g} onChange={setGuard} options={[{value:"raw",label:"Raw · ทุกreadyprofile"},{value:"cent",label:`Cent · ${DATA.cent_rows}rowsที่รันครบจริง`}]}/><Text>เรียง</Text><Select value={sort} onChange={setSort} options={[{value:"order",label:"ลำดับคงที่"},{value:"profit",label:"Net scenario มาก→น้อย"},{value:"dd",label:"DD scenario น้อย→มาก"}]}/></Row>
 <Text size="small" tone="secondary">Net3columnsหน่วยUSD;DD/streak/severity/recoveryเป็น{v}/{g}. ΔDDเป็นpercentagepointsเทียบlatest26b8. Severity=worst losing-run loss%starting equity;recovery=max(actualcompleted,ongoingage). Ongoingเป็นcensoredage ไม่ใช่เวลาrecoveryที่รู้แล้ว. Centที่ยังไม่ครบถูกละ ไม่มีrawแทนค่า</Text>
 <Table stickyHeader headers={["Profile","Rules ID","ΔnativeRules vs latest","Base net USD","Stress net USD","Fee net USD",`${v} DD%`,"ΔDD pp","Min equity USD","Loss streak","Worst-run severity%","Completed days","Ongoing age days","Qualification snapshot","Failure reasons"]} rows={visible.map(r=>{const q=r.paths[g]![v],s=r.screen[g]!;return[r.label,r.id,r.changes.join("; ")||"Latest unchanged",usd(r.paths[g]!.base.net),usd(r.paths[g]!.stress.net),usd(r.paths[g]!.fee.net),f(q.dd),d(q.delta_dd),usd(q.min_equity),q.streak,f(q.severity),f(q.completed_days),f(q.ongoing_days),r.reference?"REFERENCE · replay":r.qualified6?"PASS reviewed6 · provisional":s.passed?"PASS counter only · cent pending/othercounter check":"FAIL",s.reasons.join("; ")||"ตรงprofit/DDในcounterนี้"]})}/>
 <H2>เจาะทีละprofileเทียบlatestก่อนloop</H2>
 <Select value={chosen.id} onChange={setDetail} options={visible.map(r=>({value:r.id,label:r.label}))}/>
 <Text>{chosen.label} · {chosen.id}. {chosen.reference?"Historicalreferenceหลายrule ไม่ใช่singlefactorcontrolหรือactualbrokerPnL":"ผลย้อนหลังจากcaseที่พร้อมในsnapshotนี้ ยังไม่ใช่finalwinner"}</Text>
 <Table headers={["Metric",`${v}/${g} chosen`,"Latest26b8","Δ"]} rows={[["Net USD",usd(p.net),usd(old.net),d(p.delta_net)+"USD"],["Equity DD %",f(p.dd),f(old.dd),d(p.delta_dd)+"pp"],["Minimum equity USD",usd(p.min_equity),usd(old.min_equity),d(p.delta_min_equity)+"USD"],["Loss streak trades",p.streak,old.streak,d(p.delta_streak)],["Worst-run severity%",f(p.severity),f(old.severity),d(p.delta_severity)+"pp"],["Completed recovery days",f(p.completed_days),f(old.completed_days),d(p.completed_days-old.completed_days)+"days"],["Ongoing drawdown age days",f(p.ongoing_days),f(old.ongoing_days),d(p.ongoing_days-old.ongoing_days)+"days"]]}/>
 <Text size="small" tone="secondary">NegativeBE/swapยังเป็นloss. Fullpathเปลี่ยนตามadmission/holding/equity จึงไม่ใช่กำไรที่บวกแยกparameterได้. Costmodel baseบันทึกBid/Ask;stressเพิ่มspread$0.20/oz+slippage$0.10/oz;feeเพิ่มสมมติ$7/lot. Swaplong−567.4/short0 pointmode1/UTCmidnightcalendarยังไม่brokerattested</Text>
 <Row gap={16} wrap><Link href={p.proof}>Chosen hash proof</Link><Link href={p.source}>Chosen saved cell</Link><Link href="__MATRIX__">Partial matrix data</Link><Link href="__PROTOCOL__">Frozen loop protocol</Link></Row>
 </Stack>;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/c22-learning-loop-2026-10-25')
    args=parser.parse_args();out=(ROOT/args.output).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Machine outputs must remain under runs/')
    build(out)


if __name__=='__main__':
    main()
