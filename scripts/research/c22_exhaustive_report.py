"""Checkpoint-bound exhaustive C22 matrix, provisional until full independent audit."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import time

from scripts.research.c22_performance_campaign import ROOT, INPUT, OLD, VIEWS, read, write, sha, diagnostics
from scripts.research.c22_loop_store import read_cell, load_summary
from scripts.research.c22_matrix_tuning import closing_recovery


TARGET = '/Users/nopparuj/.cursor/projects/Users-nopparuj-my-agents-XAUUSD-Scalper/canvases/C22-exhaustive-loop-2026-10-25.canvas.tsx'
RISK = ('dd','recovery','severity','streak')
FIELDS = ('net','balance','dd','streak','severity','completed_days','ongoing_days','recovery',
          'min_equity','trades','win_rate','profit_factor','max_initial_risk','net_excluding_top5','swap','commission')


def stable_snapshot(out):
    for _ in range(5):
        checkpoint = read(out/'checkpoint.json')
        binding = checkpoint['summaries_cache']
        path = Path(binding['path'])
        if not path.is_absolute():
            path = ROOT/path if path.parts[0]=='runs' else out/path
        path = path.resolve()
        assert path.is_relative_to(out), 'Summary cache escaped this run'
        digest = sha(path)
        if digest != binding['sha256']:
            time.sleep(.05)
            continue
        if path.name.endswith('.gz'):
            with gzip.open(path,'rt',encoding='utf-8') as stream:
                state=json.load(stream)
        else:
            state=read(path)
        if sha(path)==digest and read(out/'checkpoint.json')['summaries_cache']['sha256']==digest:
            return checkpoint,state,path,digest
        time.sleep(.05)
    raise RuntimeError('Checkpoint is changing; retry snapshot, no partial artifact written')


def packed(summary):
    m,r = summary['metrics'],summary['risk']
    return [m['net_usd'],m['final_balance'],r['dd'],r['streak'],r['severity'],r['completed_days'],
            r['ongoing_days'],r['recovery'],r['min_equity'],m['trades'],m['win_rate'],m['profit_factor'],
            m['max_admitted_risk_pct'],m['net_excluding_top5_winners'],m['swap_usd'],m['commission_usd']]


def reasons(paths, floors):
    failures = []
    for view in VIEWS:
        m = paths[view]['metrics']
        if view in ('base','stress') and m['net_usd']+1e-7 < floors[view]['net_usd']:
            failures.append(view+' net < original floor')
        if m['max_dd_pct'] > 40:
            failures.append(view+' DD>40%')
        if not m['survival'] or m['net_usd'] <= 0:
            failures.append(view+' survival/net fail')
    return failures


def build(out):
    proto = read(out/'protocol.json')
    for name,digest in proto['sources'].items():
        assert sha(ROOT/name)==digest,name
    assert sha(INPUT/'manifest.json') == proto['input_manifest_sha256']
    checkpoint,state,state_path,state_hash = stable_snapshot(out)
    assert checkpoint['protocol_sha256']==sha(out/'protocol.json')
    assert sha(out/'catalog.json')==proto['catalog_sha256']
    manifest = read(INPUT/'manifest.json')
    initial = proto.get('initial',checkpoint['initial'])
    axes = list(proto['domains']) if 'domains' in proto else read(out/'catalog.json')['axes']
    summaries = state['summaries']
    cases = state['cases']
    if isinstance(cases,list):
        cases={case['name']:case for case in cases}
    assert initial in summaries
    baseline = summaries[initial]
    assert all(set(baseline[g])==set(VIEWS) for g in ('raw','cent'))
    complete_path=out/'COMPLETE.json'
    audited=False
    if complete_path.exists():
        completion=read(complete_path)
        assert completion['status']=='EXHAUSTIVE_COMPLETE'
        audit_path=out/'independent-verification.json'
        if audit_path.exists():
            audit=read(audit_path)
            assert audit['status']=='PASS'
            assert audit['parent_completion_sha256']==sha(complete_path)
            for name,digest in completion['artifacts'].items():
                assert sha(out/name)==digest,name
            audited=True
    stage='AUDITED_EXHAUSTIVE_RESULT' if audited else 'SEARCH_COMPLETE_AUDIT_PENDING' if complete_path.exists() else 'PARTIAL_CHECKPOINT'
    selected=checkpoint['selected']
    if complete_path.exists():
        selected=read(out/'results.json')['selected']
    source_hashes={}
    rows=[]
    omitted=0
    for name in sorted(summaries,key=lambda n:(n!=initial,n)):
        paths=summaries[name]
        if set(paths.get('raw',{}))!=set(VIEWS):
            omitted+=1
            continue
        roles=[]
        if name==initial:roles.append('latest-before-search')
        if name=='c22654fea98da73e':roles.append('old-matrix-row20')
        roles += [lane+' checkpoint incumbent' for lane,identity in selected.items() if name==identity]
        for role,identity in checkpoint.get('diagnostic_alternatives',{}).items():
            if name==identity:roles.append(role)
        rule=cases[name]['rules']
        row=dict(id=name,roles=roles,reference=False,params=[rule[k] for k in axes],raw=[],cent=None,
                 main=False,repair=False,reduced=False,failures={},committed=name in checkpoint['visited'])
        for guard in ('raw','cent'):
            if set(paths.get(guard,{}))!=set(VIEWS):
                continue
            points=[]
            for view in VIEWS:
                proof=out/'cells-integrity'/f'{name}-{view}-{guard}.json'
                binding=read(proof)
                sealed=state['cell_bindings'][proof.stem]
                assert sha(proof)==sealed['proof_sha256']
                assert binding['path']==sealed['path'] and binding['sha256']==sealed['sha256']
                source=(ROOT/binding['path']).resolve()
                assert source.is_relative_to((ROOT/'runs').resolve())
                assert sha(source)==binding['sha256'],proof.name
                source_hashes[str(source.relative_to(ROOT))]=binding['sha256']
                points.append(packed(paths[guard][view]))
            row[guard]=points
            row['failures'][guard]=reasons(paths[guard],proto['original_floors'][guard])
        row['main']=row['cent'] is not None and not any(row['failures'].values())
        if row['main']:
            row['repair']=all(paths[g][v]['metrics']['net_usd']+1e-7>=baseline[g][v]['metrics']['net_usd']
                for g in ('raw','cent') for v in ('base','stress')) and all(
                paths[g][v]['risk'][field]<=baseline[g][v]['risk'][field]+1e-9
                for g in ('raw','cent') for v in VIEWS for field in RISK)
            row['reduced']=row['repair'] and any(paths[g][v]['risk'][field]<baseline[g][v]['risk'][field]-1e-9
                for g in ('raw','cent') for v in VIEWS for field in RISK)
        rows.append(row)
    assert rows and rows[0]['id']==initial
    ready=len(rows)
    if audited:
        assert ready==proto.get('finite_domain',5184)==5184,'Full-domain claim needs5184complete raw profiles'
        assert set(checkpoint['visited'])==set(summaries)==set(cases)
    for label,identity,key in [('Original research9e','646690b541405adf','original'),
                               ('C22 Demo multi-rule reference','58e12c454c623996','demo')]:
        row=dict(id=key,roles=[label],reference=True,params=[],raw=[],cent=[],main=False,repair=False,
                 reduced=False,failures={},committed=True)
        for guard in ('raw','cent'):
            for view in VIEWS:
                filename=f'{identity}-{view}'+('-cent' if guard=='cent' else '')+'.json'
                source=OLD/'cells'/filename;proof=OLD/'integrity'/filename
                assert sha(source)==read(proof)['sha256']
                source_hashes[str(source.relative_to(ROOT))]=sha(source)
                cell=read(source)
                cell['diagnostics']=diagnostics(cell['result'],manifest['last_quote_utc'])
                cell['diagnostics']['actual_closing_recovery']=closing_recovery(cell['result'],manifest['last_quote_utc'])
                row[guard].append(packed(load_summary(cell)))
                if not row['params']:row['params']=[cell['result']['rules'][k] for k in axes]
        rows.insert(0,row)
    witnesses={}
    for name in sorted(set(selected.values())|{initial}):
        if name not in summaries:continue
        witnesses[name]={}
        for guard in ('raw','cent'):
            witnesses[name][guard]={}
            for view in VIEWS:
                cell=read_cell(out,f'{name}-{view}-{guard}')
                assert load_summary(cell)==summaries[name][guard][view]
                d=cell['diagnostics']
                run=d['worst_run_by_loss_pct']
                witnesses[name][guard][view]=dict(
                    worst_run={k:run[k] for k in ('start','end','trades','net_usd','loss_pct_of_start_equity')} if run else None,
                    recovery=d['actual_closing_recovery'])
    batches=checkpoint.get('batches',[])
    learning=[]
    for batch in batches:
        rejected=Counter()
        for name in batch['candidates']:
            for guard in ('raw','cent'):
                if set(summaries[name].get(guard,{}))==set(VIEWS):
                    rejected.update(guard+'/'+reason for reason in reasons(
                        summaries[name][guard],proto['original_floors'][guard]))
        before=batch['selected_before']['profit'];after=batch['selected_after']['profit']
        learning.append(dict(number=batch['number'],tested=len(batch['candidates']),
            raw_pass=len(batch['raw_qualified']),reviewed6_pass=len(batch['fully_qualified']),
            visited=batch['visited_cases'],before=before,after=after,
            delta_base=summaries[after]['raw']['base']['metrics']['net_usd']-
                       summaries[before]['raw']['base']['metrics']['net_usd'],
            delta_stress=summaries[after]['raw']['stress']['metrics']['net_usd']-
                         summaries[before]['raw']['stress']['metrics']['net_usd'],
            improved=batch['improved'],strict_count=batch['strict_downside_improvers'],
            reasons=dict(rejected.most_common()),
            source=str(out/'batches'/f'{batch["number"]:03}-result.json')))
    progress=read(out/'progress.json') if (out/'progress.json').exists() else {}
    data=dict(stage=stage,created_utc=datetime.now(timezone.utc).isoformat(),rows=rows,axes=axes,
        fields=list(FIELDS),initial=initial,selected=selected,ready_profiles=ready,omitted_incomplete=omitted,
        committed_profiles=len(checkpoint['visited']),domain=proto.get('finite_domain',5184),
        cent_rows=sum(r['cent'] is not None for r in rows),qualified=checkpoint.get('qualified',[]),
        strict_improvers=checkpoint.get('strict_downside_improvers',[]),
        selected_repair_strict=checkpoint.get('selected_repair_strict',False),
        progress=progress,batches=batches,batch_learning=learning,batch_count=len(batches),witnesses=witnesses,
        source_hashes=source_hashes,state_path=str(state_path),state_sha256=state_hash,
        input_manifest_sha256=proto['input_manifest_sha256'],cost_status='COST_INCONCLUSIVE',
        first_quote_utc=manifest['first_quote_utc'],last_quote_utc=manifest['last_quote_utc'],
        audited=audited,economic_replays=0)
    write(out/'matrix.json',data)
    source=CANVAS.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')))
    for key,path in dict(OUT=out,MATRIX=out/'matrix.json',PROTOCOL=out/'protocol.json',
                         CHECKPOINT=out/'checkpoint.json',CATALOG=out/'catalog.json').items():
        source=source.replace('__'+key+'__',str(path))
    (out/'canvas-source.txt').write_text(source)
    proof=dict(status=stage,ready_profiles=ready,committed_profiles=data['committed_profiles'],
        cent_rows=data['cent_rows'],matrix_sha256=sha(out/'matrix.json'),canvas_source_sha256=sha(out/'canvas-source.txt'),
        builder_sha256=sha(Path(__file__)),state_sha256=state_hash,intended_canvas=TARGET,economic_replays=0)
    write(out/'MATRIX-COMPLETE.json',proof)
    print(json.dumps(proof,indent=2))


CANVAS='''import {Stack,Row,H1,H2,Text,Table,Select,Callout,Link,useCanvasState} from "cursor/canvas";
type Value=number|null;
type Experiment={id:string;roles:string[];reference:boolean;params:(string|number|null)[];raw:Value[][];cent:Value[][]|null;main:boolean;repair:boolean;reduced:boolean;failures:Record<string,string[]>;committed:boolean};
type Run={start:string;end:string;trades:number;net_usd:number;loss_pct_of_start_equity:number};
type Recovery={longest_completed:{start:string;end:string;days:number;[key:string]:unknown}|null;ongoing:{start:string;days:number;[key:string]:unknown}|null;[key:string]:unknown};
type Learning={number:number;tested:number;raw_pass:number;reviewed6_pass:number;visited:number;before:string;after:string;delta_base:number;delta_stress:number;improved:Record<string,boolean>;strict_count:number;reasons:Record<string,number>;source:string};
type Data={stage:string;created_utc:string;rows:Experiment[];axes:string[];fields:string[];initial:string;selected:Record<string,string>;ready_profiles:number;omitted_incomplete:number;committed_profiles:number;domain:number;cent_rows:number;strict_improvers:string[];selected_repair_strict:boolean;batch_count:number;batch_learning:Learning[];progress:Record<string,unknown>;witnesses:Record<string,Record<string,Record<string,{worst_run:Run|null;recovery:Recovery}>>>;first_quote_utc:string;last_quote_utc:string;audited:boolean;[key:string]:unknown};
const DATA:Data=__DATA__;
const usd=(n:number)=>"$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const f=(n:number)=>n.toFixed(2),d=(n:number)=>`${n>0?"+":""}${n.toFixed(2)}`;
const views=["base","stress","fee"],names=["NetUSD","BalanceUSD","DD%","Streak","Worst-runseverity%","CompletedDays","OngoingDays","RecoveryMaxDays","MinEquityUSD","Trades","WinRate","PF","MaxInitialRisk%","NetLessTop5USD","SwapUSD","CommissionUSD"];
const point=(r:Experiment,g:string,v:number)=>(g==="cent"?r.cent!:r.raw)[v];
const n=(a:Value[],i:number)=>Number(a[i]);
const money=[0,1,8,13,14,15],percent=[2,4,12],days=[5,6,7];
const fmt=(a:Value[],i:number)=>i===10?f(n(a,i)*100)+"%":money.includes(i)?usd(n(a,i)):f(n(a,i));
const diff=(a:Value[],b:Value[],i:number)=>i===10?d((n(a,i)-n(b,i))*100)+"pp":d(n(a,i)-n(b,i))+(percent.includes(i)?"pp":days.includes(i)?"days":money.includes(i)?"USD":[3,9].includes(i)?"trades":"ratio");
export default function ExhaustiveMatrix(){
 const [view,setView]=useCanvasState("c22-exhaustive-view","base");
 const [guard,setGuard]=useCanvasState("c22-exhaustive-guard","raw");
 const [filter,setFilter]=useCanvasState("c22-exhaustive-filter","all");
 const [sort,setSort]=useCanvasState("c22-exhaustive-sort","order");
 const [page,setPage]=useCanvasState("c22-exhaustive-page","0");
 const [detail,setDetail]=useCanvasState("c22-exhaustive-detail",DATA.initial);
 const vi=Math.max(0,views.indexOf(view)),g=guard==="cent"?"cent":"raw";
 const latest=DATA.rows.find(r=>r.id===DATA.initial)!;
 const visible=DATA.rows.filter(r=>(g!=="cent"||r.cent)&&(r.reference||r.roles.length>0||filter==="all"||filter==="qualified"&&r.main||filter==="repair"&&r.repair||filter==="failed"&&!r.main)).sort((a,b)=>sort==="profit"?n(point(b,g,vi),0)-n(point(a,g,vi),0):sort==="dd"?n(point(a,g,vi),2)-n(point(b,g,vi),2):sort==="severity"?n(point(a,g,vi),4)-n(point(b,g,vi),4):a.id.localeCompare(b.id));
 const pages=Math.max(1,Math.ceil(visible.length/100)),pi=Math.min(pages-1,Math.max(0,Number(page)||0)),shown=visible.slice(pi*100,(pi+1)*100);
 const options=[...new Map([latest,...shown].map(r=>[r.id,r])).values()];
 const chosen=options.find(r=>r.id===detail)??latest,p=point(chosen,g,vi),old=point(latest,g,vi);
 const witness=DATA.witnesses[chosen.id]?.[g]?.[views[vi]];
 const status=(r:Experiment)=>r.reference?"REFERENCE":r.main?"PASS reviewed6":r.failures[g]?.length?"FAIL":"Raw/counter pass only;cent pending/check";
 const progress=Object.entries(DATA.progress).filter(([,v])=>typeof v==="number"||typeof v==="string");
 return <Stack gap={18} style={{padding:24,maxWidth:1600,margin:"0 auto"}}>
 <H1>C22 exhaustive tuning — {DATA.audited?"ตรวจครบ5184profiles":"ค้นหา5184profiles"}ในdomainที่ตรึง</H1>
 <Callout tone={DATA.audited?"info":"warning"} title={DATA.stage}>{DATA.audited?"ค้นครบ5184และindependent auditผ่านแล้ว;ดีที่สุดเฉพาะdomainและข้อมูลย้อนหลังที่ตรึง":"กำลังรัน/รอaudit:ยังไม่มีfinalwinner. Checkpointincumbentsด้านล่างเป็นprovisional;การsortกำไรไม่ใช่คำตัดสินสุดท้าย"}. COST_INCONCLUSIVE · Demoยังไม่เปลี่ยน</Callout>
 <Text>Snapshot {DATA.created_utc} · evaluated checkpoint {DATA.committed_profiles}/{DATA.domain}profiles · raw3พร้อม {DATA.ready_profiles}profiles · ละ {DATA.omitted_incomplete}profilesที่rawยังไม่ครบ · completed batches {DATA.batch_count}</Text>
 <Text size="small" tone="secondary">171,171,013ExnessXAUUSDm Bid/Askquotes · {DATA.first_quote_utc}–{DATA.last_quote_utc}. $200ต่อเนื่อง/fixed0.01/cap10%/daily10%/count2/singleposition. ทุกviewรวมmodeledswap;historicalbroker rates/calendar/fillsยังไม่attest. ข้อมูลทั้งหมดเคยใช้ค้นแล้ว;domainoptimumไม่ใช่futureprofit guarantee</Text>
 {progress.length>0&&<Table headers={["Progress field","Value"]} rows={progress.map(([k,v])=>[k,String(v)])}/>}
 <H2>{DATA.audited?"Audited selections":"Checkpoint incumbents · provisional"}</H2>
 <Text size="small">Profitlaneยังrank rawbase→rawstress→lowerrawDD ภายใต้originalprofitfloorsและDD≤40%ครบ6. Repairเป็นทางเลือก:matchedlatestprofits+riskทุกpathไม่แย่ลง;rankworst6DD→recovery→severity→count. Strictdownsidealternativesในcheckpoint: {DATA.strict_improvers.length};selectedrepairลดriskจริง: {DATA.selected_repair_strict?"ใช่":"ยังไม่ใช่"}</Text>
 <Table headers={["Lane","RulesID","Raw base net USD","Raw stress net USD","Worst6 DD%","Worst6 severity%","Worst6 streak","Worst6 recovery/ongoing days"]} rows={Object.entries(DATA.selected).map(([lane,id])=>{const r=DATA.rows.find(x=>x.id===id)!;const all=[...r.raw,...(r.cent??[])];return[lane,id,usd(n(r.raw[0],0)),usd(n(r.raw[1],0)),f(Math.max(...all.map(x=>n(x,2)))),f(Math.max(...all.map(x=>n(x,4)))),Math.max(...all.map(x=>n(x,3))),f(Math.max(...all.map(x=>n(x,7))))]})}/>
 {DATA.batch_learning.length>0&&<Stack gap={8}><H2>Batch learning ledger — ผลเสีย/ข้อปรับปรุงที่พบจริง</H2><Text size="small" tone="secondary">Deltaเทียบprofitincumbentก่อน/หลังcompletedbatch. Rejectioncountsนับscenario-level reasonsจากfullaccountcase;ไม่ใช่causalผลแยกparameterและไม่ใช้ลบtradeย้อนหลัง</Text><Table headers={["Batch","Tested","Raw / full6 pass","Visited","Profitbefore→after","ΔrawbaseUSD","ΔrawstressUSD","Profit / repair improved","Strict alternatives","Concrete rejection reasons","Source"]} rows={DATA.batch_learning.map(b=>[b.number,b.tested,`${b.raw_pass}/${b.reviewed6_pass}`,b.visited,`${b.before}→${b.after}`,d(b.delta_base),d(b.delta_stress),`${b.improved.profit}/${b.improved.repair}`,b.strict_count,Object.entries(b.reasons).map(([reason,count])=>`${reason}:${count}`).join("; "),<Link href={b.source}>batch result</Link>])}/></Stack>}
 <Row gap={12} wrap><Text>Cost</Text><Select value={views[vi]} onChange={setView} options={[{value:"base",label:"Base + swap"},{value:"stress",label:"Price stress + swap"},{value:"fee",label:"Stress + hypothetical fee + swap"}]}/><Text>Counter</Text><Select value={g} onChange={setGuard} options={[{value:"raw",label:"Raw · complete3only"},{value:"cent",label:`Cent · ${DATA.cent_rows}actualcomplete rows`}]}/><Text>กรอง</Text><Select value={filter} onChange={setFilter} options={[{value:"all",label:"ทุกreadyprofile"},{value:"qualified",label:"Main6pass +refs"},{value:"repair",label:"Repairpass +refs"},{value:"failed",label:"ยังไม่ผ่าน6 +refs"}]}/><Text>เรียง</Text><Select value={sort} onChange={setSort} options={[{value:"order",label:"StableID"},{value:"profit",label:"Netมาก→น้อย"},{value:"dd",label:"DDน้อย→มาก"},{value:"severity",label:"Severityน้อย→มาก"}]}/></Row>
 <H2>Matrixทุกreadyprofile — แบ่งหน้าเพื่ออ่าน5krows</H2>
 <Text size="small" tone="secondary">Net3columnsเป็นUSD;risksใช้{views[vi]}/{g};severity=worst losing-run loss%startingequity. Recovery=max(actualcompleted,ongoingage);ongoingคือcensoredage ไม่ใช่เวลาฟื้นที่รู้แล้ว. Centที่ยังไม่ครบไม่แทนด้วยraw. OldDemoเป็นmulti-rule historicalreference ไม่ใช่actualbrokerPnLหรือone-factorcontrol</Text>
 <Select value={String(pi)} onChange={setPage} options={Array.from({length:pages},(_,i)=>({value:String(i),label:`Page${i+1} · ${i*100+1}–${Math.min((i+1)*100,visible.length)} /${visible.length}`}))}/>
 <Table stickyHeader headers={["Roles / ID","Base net USD","Stress net USD","Fee net USD",`${views[vi]} DD%`,"ΔDDpp vs latest","Min equity USD","Loss streak","Worst severity%","Completed days","Ongoing age days","Main screen","Repair / strict","Committed"]} rows={shown.map(r=>{const q=point(r,g,vi),points=g==="cent"?r.cent!:r.raw;return[(r.roles.join(" / ")||r.id),usd(n(points[0],0)),usd(n(points[1],0)),usd(n(points[2],0)),f(n(q,2)),d(n(q,2)-n(old,2)),usd(n(q,8)),n(q,3),f(n(q,4)),f(n(q,5)),f(n(q,6)),status(r)+(r.failures[g]?.length?" · "+r.failures[g].join("; "):""),`${r.repair?"PASS":"FAIL"} / ${r.reduced?"riskreduced":"no strict repair"}`,r.committed?"checkpoint":"ready;batchpending"]})}/>
 <H2>เจาะprofileจากหน้าที่เลือก</H2>
 <Select value={chosen.id} onChange={setDetail} options={options.map(r=>({value:r.id,label:(r.roles.join(" / ")||r.id)+" · "+r.id}))}/>
 <Text weight="semibold">{chosen.roles.join(" / ")||chosen.id} · {chosen.id}</Text>
 <Table headers={["Native axis","Chosen","Latest before search"]} rows={DATA.axes.map((axis,i)=>[axis,axis==="target_rr"&&chosen.params[i]===0?"3ATR (target_rr0)":String(chosen.params[i]),String(latest.params[i])])}/>
 <Text size="small" tone="secondary">Demo additionally usesRSI14cross25/SELL96/dailycount1;research usesRSI7cross30/SELL48/count2. Cooldown=elapsed15min. GlobalBEactivationaffectsBUY+SELL. StopwidthchangesriskUSD/TPdistance/admission atfixedlot;BEcanremainnetnegativeafterswap/gap</Text>
 <Table headers={["Metric",`${views[vi]}/${g}chosen`,"Latest","Δ"]} rows={[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15].filter(i=>p[i]!==null&&old[i]!==null).map(i=>[names[i],fmt(p,i),fmt(old,i),diff(p,old,i)])}/>
 {witness&&<Stack gap={6}><H2>Source witnessesของcheckpointincumbent / baseline</H2>{witness.worst_run&&<Text size="small">Worst losing-run: {witness.worst_run.start}→{witness.worst_run.end};{witness.worst_run.trades}trades;net{usd(witness.worst_run.net_usd)};loss{f(witness.worst_run.loss_pct_of_start_equity)}%starting equity</Text>}{witness.recovery.longest_completed&&<Text size="small">Completed closing recovery: {witness.recovery.longest_completed.start}→{witness.recovery.longest_completed.end};{f(witness.recovery.longest_completed.days)}days</Text>}{witness.recovery.ongoing&&<Text size="small">Ongoing closing drawdown starts{witness.recovery.ongoing.start};age{f(witness.recovery.ongoing.days)}days throughlastquote</Text>}</Stack>}
 <Text size="small" tone="secondary">Source:SHA-bound checkpoint/state summaries;ready economic payload hasheschecked;incumbent witnessesreadfullcells. Finalindependent audit:{DATA.audited?"PASS":"PENDING"}. Snapshotไม่อัปเดตเองระหว่างschedulerbatches. NetLessTop5เป็นledger attribution ไม่ใช่replayตัดtradeแล้วคำนวณใหม่. Pricecostsใช้recordedBid/Ask;stress+spread$0.20/oz/slippage$0.10/oz;fee+สมมติ$7/lot;static swaplong−567.4/short0pointmode1/UTCmidnightcalendarยังไม่brokerattested</Text>
 <Row gap={16} wrap>{!chosen.reference&&<Link href={`__OUT__/cells-integrity/${chosen.id}-${views[vi]}-${g}.json`}>Chosen full-cell source proof</Link>}<Link href="__MATRIX__">Fullmatrixdata+sourcehashes</Link><Link href="__CHECKPOINT__">Checkpoint</Link><Link href="__CATALOG__">Frozen5184catalog</Link><Link href="__PROTOCOL__">Protocol</Link></Row>
 </Stack>;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/c22-exhaustive-loop-2026-10-25')
    args=parser.parse_args();out=(ROOT/args.output).resolve()
    if not out.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Machine outputs must remain under runs/')
    build(out)


if __name__=='__main__':
    main()
