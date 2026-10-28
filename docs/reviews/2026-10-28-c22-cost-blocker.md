# Selected26b8 cost blocker — diagnosis and prepared correction

**ROOT_CAUSE_CONFIRMED; CANDIDATE_VERIFIED_NOT_INSTALLED.**
ปัญหาคือ SDK swap rate เปลี่ยนจริง แต่ policy ที่อนุมัติยังตรึงค่าเดิม
Exact-spec gate ทำงานตาม Q4; ไม่ใช่ float error, expiry หรือ bug ที่ควรถอด gate
Evidence: `runs/c22-cost-blocker-2026-10-28/` (ignored/private)

Later owner approval and actual one-time installation supersede this preparation
checkpoint: `2026-10-28-c22-one-time-cost-install.md`, CORE6.65. Original diagnosis
and candidate bytes remain retained; they were not re-dated into fresh evidence.

## Reproduce → debugger → disproof

ใช้ policy เดิม SHA
`247cf2a51d96beb5c805aba2daba9e9c45d49cbff5645514e76811c5fd1babd0`
และ actual broker packet28Oct08:46:31UTC โดย freezeเวลาเฉพาะ repro
ไม่ได้เปลี่ยนข้อมูลเก่าเป็น fresh evidence. `reproduce.py` ให้
`cost.spec / cost_spec_mismatch / swap_long` ซ้ำได้

PDB หยุด `scripts/demo_runtime/costs.py:166` และเห็น key=`swap_long`,
expected=-490.8,observed=-490.0. Source trace:
ExecutionReview ตรวจ source/account/policy hash → SelectedAdmission → shared
admission → validate_policy → validate_evidence เปรียบทุก storedspec ด้วย exact
equality. ดังนั้น review_valid/no_signal ไม่ได้พิสูจน์ livecost admissionผ่าน
Whole-policy spec gate ใช้ก่อนทั้ง BUY และ SELL

Disproofก่อนสรุป: policy/calendarผ่านเมื่อไม่ส่ง livespec, mode1/point/contract
ตรงกัน, Decimalยืนยันต่าง0.8POINTSจริง, เปลี่ยนเฉพาะ observedrate กลับค่าเก่าแล้ว
ผ่าน. จึงหักล้าง expiry, unit mismatch และ serialization/float artifact สำหรับ
snapshotนี้. ไม่ย้อนอ้างว่า fieldนี้คือสาเหตุของrefusals27Octที่ไม่ได้เก็บค่าไว้

## Actual fresh capture และ candidate

อ่าน brokerแบบexclusiveอีกครั้ง28Oct09:37:08.993420UTC /16:37:08Thai:

| สิ่งตรวจ | ผลจริง |
|---|---|
| SDK spec | ยังต่างเพียงswap_long: -490.8→-490.0POINTS |
| Account/exposure | Demo/USD/hedging,positions0,orders0,43deals; cash/volumeครบ |
| Native openings | magic22261025/entry0 จำนวน0; ไม่อ้าง observed-chargePASSเป็นnativeforwardproof |
| Snapshot/candidate | candidateสร้าง09:37:09.259784UTC,หลังcapture0.266364seconds |
| Candidate SHA256 | `9f1f19334fd31ffa6e52dec790895da15ad2dff434ccabd6109d8038ba3b0650` |
| Validation | Native policy/spec/charge checksผ่าน ณเวลาสร้าง และ independent economic_scope/calendarformulaผ่าน |
| Preparation pause | 9.876839seconds; admissionquiescence→senderstop→exclusiveprobe→คืนoriginalreview/startsender |
| Preservation | Originalpolicy/review bytes,stoppedfinancialKV/cache,terminalPID116183 และ5unaffectedunitsตรงเดิม |

Candidateอยู่ `candidate-policy.json` คู่กับ `candidate-review.json` และ
`candidate-validation.json`. เป็นข้อเสนอที่ตรวจได้ **ยังไม่ติดตั้งและไม่มีสิทธิ์
execute**; brokerpacketนี้อายุเกิน5นาทีแล้ว ต้องเก็บใหม่ก่อนใช้งานจริง
ห้ามเปลี่ยน captured_utc/reviewed_utc เพื่อทำให้packetเดิมดูใหม่

## สิ่งที่จะเปลี่ยนเมื่อยอมรับ candidate

| ข้อ | เดิม | Candidate |
|---|---:|---:|
| swap_long,POINTS | -490.8 | -490.0 |
| BUY regular swap ต่อ0.01lot,USDตามmodel | -0.4908 | -0.4900 |
| BUY Wednesday triple ต่อ0.01lot,USDตามmodel | -1.4724 | -1.4700 |
| ส่วนต่างregular/triple | — | +0.0008 / +0.0024USD |

ใช้ actualpoint0.001×contract100×rate×lot. ส่วนต่างนี้คือmodelต้นทุนต่อrollover
ไม่ใช่กำไรbacktestใหม่หรือการรับประกันต้นทุนจริง. SELLrate/commission0/
slippage0.1/specอื่นไม่เปลี่ยน; native26b8lot/risk/entry/exitไม่เปลี่ยน

ต้อง rebuild spec และdatedswapcalendarด้วย nativebuilderทั้งชุด แล้ว bind
executionreviewกับpolicyhashใหม่ การแก้แค่storedswap_longและrehashspecอาจผ่าน
structuralvalidatorแต่ยังเหลือcalendarเก่า; negativecontrolพิสูจน์ว่า independent
economic_scope ปฏิเสธshortcutนั้น Candidateนี้ไม่ได้ใช้shortcut

Rebuildใช้ timestampที่ตรวจใหม่จริง,168hour lifetimeเดิมและ8dateddaysตามformula
เดิม; นับเป็น **manual one-time changed-cost review** ทำให้ expiryย้ายตามเวลา
reviewจริง เช่นcandidate09:37มี expiry4Nov09:37UTC แทน policyเดิม1Nov13:25UTC
ไม่ใช่auto-renew และไม่ใช้วันหมดอายุใหม่ซ่อนoldcostincident/cutoff

## Source proof และข้อจำกัด

ตรวจ official Standard account page ผ่านweb toolพบ Standard commissionเป็น0;
[Standard account](https://www.exness.com/standard-accounts/) ยืนยันpublishedtariff
เท่านั้น ไม่พิสูจน์account entitlement. [About swap](https://get.exness.help/hc/en-us/articles/360014709151-About-swap)
ระบุ MT usesPOINTS,metalsWednesdaytriple/weekendzero,ratesอาจเปลี่ยนและholidays
อาจมีexceptions. [Trading hours](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours)
ระบุsummer/winterตามUSDST ใช้ประกอบformulaเดิม

DirectHTTPครั้งนี้403Cloudflareทั้ง3URL ส่วนrawtariff200ครั้งก่อนเป็นaccess/sign-in
shellไม่มีterms การแก้parserให้ผ่านจากbodyนั้นจะเป็นการเติมข้อเท็จจริงเอง
จึงคงautomatedsourcepacketDEFERRED. Candidateใช้ **manual official-page review**
พร้อมURL/checkedUTCจริงตามinterfaceเดิม ไม่ปลอมว่าwebtextคือoriginalHTTPbody
ไม่ลดguard ไม่ใส่missing=zero และไม่อ้างautomatedcollectorพร้อมใช้งาน

Swap-FreeยังUNKNOWN, datedbrokerholidayexceptionsยังไม่attested,
economicqualificationยังCOST_INCONCLUSIVE. Builder/validationPASSไม่ใช่broker
historicalswapproofหรือaccount-specifictariffattestation

## Installation protocol ที่เตรียมไว้

1. รับ specific decision ตามQ4สำหรับค่าswap_long=-490.0ครั้งเดียว พร้อมactual
   review/calendarlifetime168h; สิทธิ์source-onlycutoverก่อนหน้าไม่รวมcostacceptance
2. เก็บsource reviewและbrokerใหม่จริง; account/source/configต้องตรง1c0453
   newratespecต้องตรงcandidateทุกfield ถ้าค่าอื่นเปลี่ยนให้defer ไม่ขยายขอบเขต
3. Fresh brokerflat/noorders และ journalnoactive/noUNKNOWN/nohalt/emptyoutbox
   ก่อนพักsender; budget<=15minutes,terminal/runtime/watchdog/backupคงเดิม
4. Retainoldpolicy/review/ledger/cutoff ตรวจhistoryทั้งหมดด้วยoldpolicyก่อน
   ถ้ามีnativeopeningเพิ่มจากproof0เดิมหรือoldincident ให้deferเพื่อจัดgeneration
   provenanceก่อน ห้ามเลื่อนcutoffข้ามchargeที่ยังไม่ตรวจ
5. Rebuildทั้งpolicy/spec/calendarจากfreshbytes ตรวจexactscope+formula+old/new
   history charges แล้วทำnewpolicy-bound reviewตามdecisionจริง ไม่fabricateapproval
6. Switchขณะsenderหยุด/flatพร้อมbackup/rollback; restartรุ่น1c0453เดิม
   คงone sender/riskcap/UNKNOWN/noresend; newcompleteM15หลังreviewตามcontract
7. หลังstartตรวจactualcohort/rawreview/policyhash/expiry/financialstate/terminal
   และcostgateจากfactsจริง; ไม่มีsignalไม่forceorder ไม่อ้างfinancialqualification

หากrateเปลี่ยนอีกภายหลัง exactguardยังบล็อกตามเดิม one-timefixนี้ไม่ใช่สิทธิ์
ยอมรับrateใหม่ทุกครั้ง นโยบายปรับrateอัตโนมัติเป็นmaterialdecisionคนละเรื่อง

## Validation และสถานะล่าสุด

- Repro/PDB/disproof artifactsครบ;31existingcost/builder/ledger testsผ่าน1.476s
- Candidateformula,fullstoredspecdifference,oldcostcheckและsubsequenthigher/lower
  rate negativecontrolsผ่าน; ไม่มีeconomicbacktestใหม่
- Source/runtime/configไม่มีการแก้; ไม่มีtestfixtureหรือapprovalปลอมเข้าVM
- Follow-uptraceagentsติดusage limit จึงไม่อ้างindependentfinalPASS; rootตรวจ
  candidateformula/hash/scopeและlivepreservationเอง
- Runtime11:50:30UTC /18:50Thai:sender121664 activeบน1c0453,execute=true,
  WAITduplicate_bar,activefalse/haltfalse/outbox0,review/policyเดิม,terminal116183

**ยังไม่ปิดruntimecostblocker**: correctionพร้อมreview แต่ต้องยอมรับcostเปลี่ยน
ตาม [confirmed Q4](../../specs/c22-continuous-demo-2026-10-27.md) ก่อนติดตั้งจริง
