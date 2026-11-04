"""Source-bound comparison matrix/Canvas from completed offline risk cells."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.research.c22_performance_campaign import read, sha, write
from scripts.research.c22_risk_campaign import DEFAULT_OUT, GUARDS, ROOT, VIEWS, read_cell


def points(result, limit=300):
    marks = result["equity"]
    if not marks:
        return []
    indices = {0, len(marks) - 1,
               min(range(len(marks)), key=lambda i: marks[i]["equity_usd"]),
               max(range(len(marks)), key=lambda i: marks[i]["equity_usd"])}
    step = max(1, len(marks) // limit)
    indices.update(range(0, len(marks), step))
    return [[marks[i]["time_utc"], marks[i]["equity_usd"]] for i in sorted(indices)]


def report(out):
    out = Path(out).resolve()
    assert out.is_relative_to((ROOT / "runs").resolve())
    protocol = read(out / "protocol.json")
    assert protocol["algorithm"] == "c22_risk_closure_v1"
    catalog = read(out / "catalog.json")
    saved = read(out / "results.json") if (out / "results.json").exists() else {}
    audit_path = out / "independent-verification.json"
    verified = False
    if audit_path.exists():
        audit = read(audit_path)
        verified = (audit["status"] == "PASS" and audit["cells"] == 72 and audit["fresh_repeats"] == 6
                    and audit["independent_full_tick_dd_cells"] == 72
                    and audit["protocol_sha256"] == sha(out / "protocol.json")
                    and audit["completion_sha256"] == sha(out / "COMPLETE.json"))
        assert verified, "Existing audit is not bound to this completed campaign"
    rows = []
    coverage = 0
    for profile in catalog["profiles"]:
        row = dict(profile, paths={})
        for guard in GUARDS:
            for view in VIEWS:
                key = f'{profile["name"]}-{view}-{guard}'
                if not (out / "cells-integrity" / (key + ".json")).exists():
                    continue
                cell = read_cell(out, key)
                overlay = cell["result"].get("overlay", {})
                row["paths"][view + "-" + guard] = dict(metrics=cell["metrics"], risk=cell["summary"]["risk"],
                    equity_points=points(cell["result"]), sampled_equity_points=True,
                    overlay_state=overlay.get("state"), overlay_rejections=overlay.get("rejections", {}),
                    net_be_adjustments=len(overlay.get("be_adjustments", [])))
                coverage += 1
        if row["paths"]:
            rows.append(row)
    assert coverage <= 72
    baseline_id = protocol["baseline_overlay_id"]
    baseline = next((x for x in rows if x["name"] == baseline_id), None)
    for row in rows:
        row["qualified"] = row["name"] in saved.get("qualified", [])
        row["strict_matched_profit_nonregression"] = False
        if baseline and len(row["paths"]) == 6 and len(baseline["paths"]) == 6:
            row["strict_matched_profit_nonregression"] = all(
                row["paths"][v + "-" + g]["metrics"]["net_usd"] + 1e-7 >= baseline["paths"][v + "-" + g]["metrics"]["net_usd"]
                for g in GUARDS for v in ("base", "stress"))
            row["matched_deltas"] = {k:dict(
                net_usd=value["metrics"]["net_usd"] - baseline["paths"][k]["metrics"]["net_usd"],
                dd_pp=value["metrics"]["max_dd_pct"] - baseline["paths"][k]["metrics"]["max_dd_pct"])
                for k,value in row["paths"].items()}
    value = dict(schema=1, status="VERIFIED" if verified else "AWAITING_AUDIT" if coverage == 72 else "PARTIAL",
        captured_utc=datetime.now(timezone.utc).isoformat(), evaluated_paths=coverage, required_paths=72,
        profiles_in_catalog=12, native_rules_id=protocol["native_rules_id"], baseline_id=baseline_id,
        selected_profit=saved.get("selected", {}).get("profit") if verified else None,
        provisional_leader=saved.get("selected", {}).get("profit"), rows=rows,
        source=dict(protocol_sha256=sha(out / "protocol.json"), input_manifest_sha256=protocol["input_manifest_sha256"],
                    start=protocol["start"], end_exclusive=protocol["end"], cost_status="COST_INCONCLUSIVE", holdout=False),
        notes=["All paths include modeled swap; six cost/accounting paths reuse the same market history.",
               "Fixed0.01 and native26b8 signal/SL/TP/activation remain; overlay policies are separate research versions.",
               ("DD and minimum equity audited on full source ticks; chart samples actual persisted checkpoints." if verified else
                "Engine DD/minimum await independent full-tick audit; chart samples actual persisted checkpoints."),
               "Admission budgets do not guarantee realized daily/DD limits through gaps/outages.",
               "NetBE covers accrued costs at first successful adjustment; later swap may make final net negative.",
               "No forward-profit, historical broker-cost parity, real-money or Demo-adoption qualification."])
    write(out / "matrix.json", value)
    if rows:
        (out / "canvas-source.txt").write_text(canvas(value), encoding="utf-8")
    print(json.dumps({k:value[k] for k in ("status", "evaluated_paths", "required_paths", "selected_profit", "provisional_leader")}, indent=2))
    return value


def canvas(value):
    template = r'''import {useHostTheme,useState} from "cursor/canvas";
const D:any=__DATA__;
const money=(n:number)=>n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
export default function RiskMatrix(){
 const t=useHostTheme();const [view,setView]=useState("base");const [guard,setGuard]=useState("raw");
 const [chosen,setChosen]=useState(D.selected_profit||D.provisional_leader||D.baseline_id);
 const key=view+"-"+guard;const rows=D.rows.filter((r:any)=>r.paths[key]);
 const current:any=rows.find((r:any)=>r.name===chosen)||rows[0];
 const base:any=rows.find((r:any)=>r.name===D.baseline_id);
 const lines=[base&&{name:"Native26b8",data:base.paths[key].equity_points,color:t.text.tertiary},
  current&&current.name!==D.baseline_id&&{name:current.label,data:current.paths[key].equity_points,color:t.accent.primary}].filter(Boolean) as any[];
 const pts=lines.flatMap(s=>s.data.map((p:any)=>[Date.parse(p[0]),p[1]]));
 const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(200,...ys),maxY=Math.max(201,...ys);
 const x=(v:number)=>65+805*(v-minX)/Math.max(1,maxX-minX),y=(v:number)=>240-200*(v-minY)/Math.max(1,maxY-minY);
 const cell={padding:"9px 12px",borderBottom:`1px solid ${t.stroke.tertiary}`,textAlign:"right" as const,whiteSpace:"nowrap" as const};
 const select={background:t.bg.editor,color:t.text.primary,border:`1px solid ${t.stroke.primary}`,padding:"7px 10px",borderRadius:4};
 return <main style={{color:t.text.primary,background:t.bg.editor,padding:24,fontFamily:"inherit",fontSize:14,maxWidth:1400,margin:"0 auto"}}>
  <div style={{display:"flex",justifyContent:"space-between",gap:18,alignItems:"baseline"}}><h1 style={{fontSize:24,margin:"0 0 8px"}}>C22 · Risk closure matrix</h1><strong style={{color:t.accent.primary}}>{D.status} · {D.evaluated_paths}/72 paths</strong></div>
  <p style={{color:t.text.secondary,marginTop:0}}>12 profiles · fixed0.01 · Daily10% / DD40% budgets · Net BE first adjustment · pause24h</p>
  <div style={{borderTop:`1px solid ${t.stroke.primary}`,borderBottom:`1px solid ${t.stroke.primary}`,padding:"14px 0",display:"flex",gap:28,flexWrap:"wrap"}}>
   <span><b>Rules</b> {D.native_rules_id}</span><span><b>Data</b> {D.source.start.slice(0,10)} → {D.source.end_exclusive.slice(0,10)} exclusive</span><span><b>Economic evidence</b> COST_INCONCLUSIVE · reused history</span>
  </div>
  <section style={{marginTop:20}}><div style={{display:"flex",gap:12,alignItems:"center",flexWrap:"wrap"}}>
   <label>Cost + swap <select style={select} value={view} onChange={e=>setView(e.target.value)}><option value="base">Base + swap</option><option value="stress">Stress + swap</option><option value="fee">Fee stress + swap</option></select></label>
   <label>Accounting <select style={select} value={guard} onChange={e=>setGuard(e.target.value)}><option value="raw">Raw net loss flag</option><option value="cent">Cent-rounded admission loss flag</option></select></label>
  </div>
  <h2 style={{fontSize:18,marginBottom:7}}>Profit and risk · initial $200 · {view} / {guard}</h2>
  <div style={{overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontVariantNumeric:"tabular-nums"}}><thead><tr>{["Profile · click to plot","Final USD","Net USD","Δ net vs native","Max DD %","Loss streak","Min equity USD","Recovery completed days","Recovery ongoing days","Trades"].map((s,i)=><th key={s} style={{...cell,textAlign:i===0?"left":"right",color:t.text.secondary,fontSize:12}}>{s}</th>)}</tr></thead>
   <tbody>{rows.map((r:any)=>{const c=r.paths[key],m=c.metrics,k=c.risk;return <tr key={r.name} onClick={()=>setChosen(r.name)} style={{cursor:"pointer",background:r.name===current?.name?t.fill.tertiary:"transparent"}}>
    <td style={{...cell,textAlign:"left",fontWeight:r.name===D.baseline_id?600:400}}>{r.label}{r.name===D.selected_profit?" · verified profit leader":""}</td>
    <td style={cell}>{money(m.final_balance)}</td><td style={cell}>{money(m.net_usd)}</td><td style={cell}>{r.matched_deltas?money(r.matched_deltas[key].net_usd):"—"}</td><td style={cell}>{m.max_dd_pct.toFixed(2)}</td><td style={cell}>{k.streak}</td><td style={cell}>{money(k.min_equity)}</td><td style={cell}>{k.completed_days.toFixed(1)}</td><td style={cell}>{k.ongoing_days.toFixed(1)}</td><td style={cell}>{m.trades}</td></tr>})}</tbody></table></div>
  <p style={{fontSize:12,color:t.text.tertiary}}>Source: immutable cells, shared hashed Exness Bid/Ask tape. Daily/DD guards reserve planned loss; gaps can exceed modeled budgets. Raw/cent are two classification paths, not independent samples.</p></section>
  {pts.length>0&&<section style={{marginTop:24}}><h2 style={{fontSize:18}}>Observed equity checkpoints · USD · {current?.label}</h2>
   <svg viewBox="0 0 900 290" role="img" aria-label="Observed equity checkpoints over UTC time" style={{width:"100%",maxHeight:360}}>
    {[0,1,2,3,4].map(i=>{const v=minY+(maxY-minY)*i/4;return <g key={i}><line x1="65" x2="870" y1={y(v)} y2={y(v)} stroke={t.stroke.tertiary}/><text x="56" y={y(v)+4} textAnchor="end" fontSize="11" fill={t.text.secondary}>{Math.round(v)}</text></g>})}
    {lines.map(s=><polyline key={s.name} fill="none" stroke={s.color} strokeWidth="1.7" points={s.data.map((p:any)=>`${x(Date.parse(p[0]))},${y(p[1])}`).join(" ")}/>)}
    <text x="65" y="263" fontSize="11" fill={t.text.secondary}>{new Date(minX).toISOString().slice(0,10)}</text><text x="870" y="263" textAnchor="end" fontSize="11" fill={t.text.secondary}>{new Date(maxX).toISOString().slice(0,10)}</text><text x="465" y="282" textAnchor="middle" fontSize="11" fill={t.text.secondary}>UTC date</text><text x="9" y="20" fontSize="11" fill={t.text.secondary}>Equity USD</text>
   </svg><div style={{display:"flex",gap:24}}>{lines.map(s=><span key={s.name} style={{color:s.color}}>{s.name}</span>)}</div>
   <p style={{fontSize:12,color:t.text.tertiary}}>Sampled actual saved checkpoints; connecting lines are visual guides. {D.status==="VERIFIED"?"Full-tick DD/minimum independently audited.":"Engine DD/minimum await independent audit."} Source window: {D.source.start.slice(0,10)}–{D.source.end_exclusive.slice(0,10)} exclusive.</p></section>}
  {current&&<section style={{marginTop:22,borderTop:`1px solid ${t.stroke.primary}`,paddingTop:14}}><h2 style={{fontSize:18}}>Policy evidence · {current.label}</h2><p>Flags: Daily {String(current.overlay.daily_budget)} · DD {String(current.overlay.drawdown_budget)} · Net BE {String(current.overlay.net_be_first)} · DD pause {current.overlay.dd_pause_hours}h</p><p>Rejected budgets: {JSON.stringify(current.paths[key].overlay_rejections)} · Net BE adjustments: {current.paths[key].net_be_adjustments}</p>{current.paths[key].overlay_state&&<p>Pause episodes {current.paths[key].overlay_state.episodes} · resumes {current.paths[key].overlay_state.resumes} · final pause active {String(current.paths[key].overlay_state.pause_started_ms!==null)}</p>}</section>}
  <section style={{marginTop:20,color:t.text.secondary,fontSize:12}}>{D.notes.map((n:string)=><p key={n}>{n}</p>)}<p>Protocol SHA256 {D.source.protocol_sha256}</p><p>Input manifest SHA256 {D.source.input_manifest_sha256}</p></section>
 </main>
}
'''
    return template.replace("__DATA__", json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report(args.out)


if __name__ == "__main__":
    main()
