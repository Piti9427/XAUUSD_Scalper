"""Read-only snapshots; reuse existing Demo evidence without recomputing PnL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import make_report, read_json, source_ref


def build_dashboard(
    report_paths: list[Path],
    demo_report_path: Path | None = None,
) -> dict[str, Any]:
    panels: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    blockers: list[str] = []
    for path in report_paths:
        source = source_ref(path)
        if source["hash_status"] != "VERIFIED":
            raise ValueError("Dashboard consumes bounded report snapshots, not raw run dumps")
        evidence = read_json(path)
        if evidence.get("schema_version") != 1 or evidence.get("execution_authorized") is not False:
            raise ValueError("Expected a non-executing preparation report")
        kind = evidence["artifact_type"]
        cohort_class = {
            "observed_cost_reconciliation": "observed_broker_cost_sample",
            "forward_review": "prospective_observation_references",
            "forward_protocol": "prospective_protocol_draft",
            "forward_cohort": "prospective_definition_only",
            "data_quality": "historical_data_quality",
        }.get(kind, "research_preparation")
        panels.append({"cohort_class": cohort_class, "source": source, "evidence": evidence})
        sources.append(source)
        blockers.extend(f"{kind}: {reason}" for reason in evidence.get("reasons", []))
    if demo_report_path is not None:
        source = source_ref(demo_report_path)
        if source["hash_status"] != "VERIFIED":
            raise ValueError("Demo evidence export exceeds bounded snapshot size")
        demo = read_json(demo_report_path)
        if not isinstance(demo.get("cohorts"), list):
            raise ValueError("Expected scripts.demo_runtime.evidence report")
        for cohort in demo["cohorts"]:
            if not cohort.get("cohort_id"):
                raise ValueError("Demo evidence requires explicit cohort identities")
            panels.append(
                {
                    "cohort_class": "existing_demo_broker_evidence",
                    "source": source,
                    "evidence": {
                        "artifact_type": "existing_demo_evidence",
                        "status": "INCONCLUSIVE",
                        "cohort_id": cohort["cohort_id"],
                        "candidate_id": None,
                        "coverage": {
                            "from_utc": demo.get("since_utc"),
                            "until_utc": demo.get("until_utc"),
                        },
                        "reasons": demo.get("limitations", []),
                        "data": cohort,
                        "dd_definition": "observed sampled-equity DD; not full-tick DD",
                    },
                }
            )
        sources.append(source)
    if not panels:
        raise ValueError("Dashboard needs actual evidence; empty panels are not reports")
    return make_report(
        "preparation_dashboard",
        "PREPARATION_ONLY",
        sources=sources,
        coverage={"panels": len(panels)},
        reasons=list(dict.fromkeys(blockers)),
        panels=panels,
        profitability="INCONCLUSIVE",
        real_money="PROHIBITED",
        limitations=[
            "Observed account-cost samples are not attributed candidate forward returns",
            "Existing Demo cohorts remain separate from research and future replacement cohorts",
            "Sampled equity drawdown is not full-tick drawdown",
            "No evidence state authorizes strategy selection or execution",
        ],
    )


def canvas_source(dashboard: dict[str, Any]) -> str:
    """Render the same snapshot as a self-contained managed Canvas source."""
    if dashboard.get("artifact_type") != "preparation_dashboard" or not dashboard["data"]["panels"]:
        raise ValueError("Canvas needs an actual preparation dashboard")
    template = """import {H1,H2,Text,Stack,Table,Select,Callout,Link,useState,useHostTheme} from "cursor/canvas";
type Evidence={artifact_type:string;status:string;candidate_id?:string|null;cohort_id?:string|null;coverage:Record<string,unknown>;reasons?:string[];data:Record<string,unknown>;[field:string]:unknown};
type Panel={cohort_class:string;source:{path:string;sha256:string|null;[field:string]:unknown};evidence:Evidence};
type Snapshot={created_utc:string;status:string;data:{panels:Panel[];limitations:string[];[field:string]:unknown};[field:string]:unknown};
const DATA:Snapshot=__SNAPSHOT__;
const show=(value:unknown)=>value===null?"INCONCLUSIVE":typeof value==="object"?JSON.stringify(value):String(value);
export default function C22PreparationEvidence(){
 const theme=useHostTheme();const [index,setIndex]=useState("0");
 const selected=DATA.data.panels[Number(index)]??DATA.data.panels[0];
 return <div style={{background:theme.bg.editor,color:theme.text.primary,padding:24,maxWidth:1440,margin:"0 auto"}}><Stack gap={18}>
 <Text size="small" tone="secondary">Snapshot UTC · {DATA.created_utc}</Text><H1>C22 · Offline adoption evidence</H1>
 <Callout title={DATA.status} tone="warning">เครื่องมือเตรียม shadow → Demo พร้อมใช้; candidate adapter, broker/cost/feed qualification และเกณฑ์ forward ยังต้องผ่านหลักฐาน. ไม่มี execution authorization.</Callout>
 <H2>รายงานจริง แยก cohort และขอบเขต</H2><Text size="small" tone="secondary">แถว = source report · Coverage = counts / UTC intervals / explicit sampling ตามชื่อ field. Research, exported account costs และ prospective evidence แยกกัน.</Text>
 <Table stickyHeader headers={["Report","Status","Cohort class","Candidate / cohort"]} rows={DATA.data.panels.map(p=>[p.evidence.artifact_type,p.evidence.status,p.cohort_class,p.evidence.candidate_id??p.evidence.cohort_id??"Unattributed sample"])} />
 <H2>ตรวจรายละเอียดและ source</H2><Select value={index} onChange={setIndex} options={DATA.data.panels.map((p,i)=>({value:String(i),label:p.evidence.artifact_type+" · "+p.evidence.status}))}/>
 <Text weight="semibold">{selected.cohort_class}</Text><Link href={selected.source.path}>{selected.source.path}</Link><Text size="small" tone="secondary">SHA256 · {selected.source.sha256??"NOT VERIFIED"}</Text>
 <Table headers={["Coverage field","Observed value / declared limit"]} rows={Object.entries(selected.evidence.coverage).map(([key,value])=>[key,show(value)])}/>
 {selected.evidence.reasons&&selected.evidence.reasons.length>0&&<ul>{selected.evidence.reasons.map(r=><li key={r}>{r}</li>)}</ul>}
 <details><summary>รายละเอียด Rules / positions / issues / protocol จาก source</summary><pre style={{fontSize:12,whiteSpace:"pre-wrap",maxHeight:560,overflow:"auto",color:theme.text.secondary}}>{JSON.stringify(selected.evidence.data,null,2)}</pre></details>
 <H2>ข้อจำกัดของหลักฐาน</H2><ul>{DATA.data.limitations.map(item=><li key={item}>{item}</li>)}</ul>
 </Stack></div>;
}
"""
    return template.replace(
        "__SNAPSHOT__", json.dumps(dashboard, ensure_ascii=False, allow_nan=False)
    )
