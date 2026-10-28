# Selected26b8 — one-time cost install28October2026

**INSTALLED_AND_POST_REVIEW_BAR_VERIFIED.** Ownerตอบชัดเจน
“อนุมัติ one-time -490.0 ตามขอบเขตนี้”. Fresh brokerตรวจซ้ำแล้วต่างเพียง
swap_long -490.8→-490.0POINTS จึงติดตั้ง policy/spec/calendar/review ใหม่จริง
บน Demo12:50:38UTC /19:50:38Asia/Bangkok. Auto-renewยังOFF; ไม่เปลี่ยน26b8,
fixed0.01,source/config,risk/entry/exit gates,terminal/runtimeหรือส่งforcedorder

Private evidence: `runs/c22-cost-install-2026-10-28/`. Root-cause/PDBและcandidate
ก่อนอนุมัติยังอยู่ใน `runs/c22-cost-blocker-2026-10-28/`; ไม่แก้เวลาpacketเดิม

## Installed facts

| สิ่งตรวจ | Actual result |
|---|---|
| Sender/source | selected-1c0453dcf92db05d,PID126749,active/enabled,NRestarts0 ณ12:51:43UTC |
| New policy rawSHA256 | `70cdd46bfb9da53663150ef867a494f50d721c83e967036f4e8d8f2dd3e3b3cc` |
| New review rawSHA256 | `e3421d3d953173fa65da746171f6ded728e957a7fd9d55280652af40a8af454f` |
| PolicyreviewedUTC | 28Oct12:50:38.309115UTC |
| PolicyexpiryUTC | 4Nov12:50:38.309115UTC /19:50:38Thai; unchanged168hour lifetime |
| NewapprovedUTC | 28Oct12:50:38.324141UTC; originalMondayarmtime retained |
| Cost change | Onlyswap_long=-490.0; exact remaining economic_scopeตรงเดิม |
| Actual postbrokerpacket | 12:50:38.060430UTC; finalspec/exposure originaltimestampsตรวจ<=5secondsก่อนswitch/start |
| Exposure/history | Demo/USD/hedging,flat,noorders,43completecash/volume-reconcileddeals,zero nativeopeningmagic22261025 |
| Maintenance | 31.529765secondsรวมquiescence/probes/switch/start; senderunitไม่เปลี่ยน |
| Terminal | PID116183/start06:49:04UTCเดิม; fiveunaffectedunit/dropin hashesตรงเดิม |
| Controls | Probe/controlไม่เรียกorder_send; noforcedorder/nofinancialstate reset |

Current CYCLE release/config pairและpersistedreviewSHAตรงกับinstalledbytes
Runtime12:51:40UTCเป็นBLOCKED/armed_trial_new_closed_m15_required,
execute=true,reviewVALID,activefalse/haltfalse/outbox0. CompleteM15แรกหลังreview
คือ13:00UTC/20:00Thai ต้องรอตามcontractเดิม ไม่backdateapprovalหรือreplaystalesignal

## สิ่งที่แก้และสิ่งที่คงไว้

ใช้nativebuilderสร้างspec/calendarทั้งชุดจากactualfreshbroker ไม่แก้แค่rateแล้ว
rehashspecเพราะcalendarอาจไม่สอดคล้อง. Installedbytesผ่านvalidate_policy
กับfinalbrokerpacket, nativeeconomic_scope/formulaและobservedcostvalidator
Independentcomparisonยืนยัน economicsต่างเฉพาะapprovedswap_long

ModelBUY0.01lot:regular-$0.4908→-$0.4900 และWednesdaytriple-$1.4724→-$1.4700
ส่วนต่างนี้เป็นต้นทุนตามmodel ไม่ใช่ผลกำไรbacktestใหม่. Exactgateไม่ถูกผ่อน:
negativecontrolsค่ากลับ-490.8/แย่ลง-491/ดีขึ้น-489หรือSELLrateเปลี่ยนยังREFUSED
ดังนั้นone-timeapprovalไม่ให้สิทธิ์รับrateใหม่อัตโนมัติในอนาคต

OldpolicySHA247cf2…/oldrevieweea6168…/rawledger/journalและcutoffเดิม
25Oct13:25:18.050055UTCเก็บครบในprevious-policy.json/previous-review.json/
cost-transition-provenance.json. ตรวจoldpolicychargehistoryก่อนสร้างcutoffใหม่
และบังคับnativeopening=0; ถ้ามีnativeopeningเพิ่มจะDEFERเพื่อทำapplicable-generation
provenanceก่อน ไม่ข้ามchargeหรือclearincident. observedcostPASSในsampleนี้
ไม่มีnativepositionให้qualify จึงไม่ใช่หลักฐานactualnativeforwardcost/lifecycle

FinancialKVทั้งชุดและcache/sidecarhashตรงขณะsenderหยุด; noDBrestore/noHWM/
day/loss/haltreset/no cachemetadata migration. Policy/reviewสองpointerสลับขณะ
senderหยุดและoldreviewถูกquiesce; mismatchก่อนstartfailclosedและมีrollback
ไม่อ้างsinglefilesystemtransactionหรือhardpowerloss/fsyncatomicityที่ไม่ได้พิสูจน์
หลังstartห้ามrollbackทิ้งowned/UNKNOWNmanager และห้ามย้อนfinancialjournal

## Fresh source review และข้อจำกัด

Officialpagesถูกเปิดตรวจใหม่ก่อนinstallผ่านwebtool:
[Standard tariff](https://www.exness.com/standard-accounts/),
[swap](https://get.exness.help/hc/en-us/articles/360014709151-About-swap),
[DST/calendar](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours).
สนับสนุนpublishedStandardcommission0,MT5POINTS,metalsWednesdaytriple/weekend0
และUSDSTformulaเดิม RateจริงมาจากSDKsnapshotที่อ่านใหม่ ไม่ได้เดาจากpublicpage

Provenanceเป็นmanualofficial-page review พร้อมactualcheckedUTC ไม่ใช่rawHTTP
automatedsourcepacket. DirectHTTP403และเก่า200accessshellยังไม่ถูกเปลี่ยนเป็น
proofปลอม. Swap-Free/account-specifictariff/datedbrokerholidayexceptionsยัง
ไม่attested; labelsUNKNOWN/COST_INCONCLUSIVEยังอยู่ครบ

## Validation ก่อนและหลังinstall

- Backupก่อนเปลี่ยน:139272192rawbytes,gzip10344778; download/SHA/restore/
  quick_check/counts/identity/financialKV/maxaudit/outboxผ่าน audit111754/kv12/
  events0/deliveries0. Previousbackupไม่ถูกเขียนทับ
- Initialpreflightติดalgo_permissions_requiredจึงยังไม่ใช้unknownเป็นflatproof
  Read-onlypassivewindowพบfreshflat12:47:28UTCโดยไม่แตะAP/terminal
- Independentcontrollerreviewพบstalespecระหว่างhistorywait จึงแก้เฉพาะoperational
  probeให้re-readspecท้ายสุดพร้อมoriginaltimestampและ<=5secondgate. Initial
  filesretained; actualscope/freshnessnegativecontrolsผ่านก่อนใช้งาน
- Sourcecontroller8401b8eb…independentreviewPASSก่อนexecute; noSDK/services
  โดยreviewer. Currentruntimepackageไม่ได้ถูกแก้ source87payload/25bindingsเดิม
- IndependentactualVMverification12:52:37UTCผ่าน27checks:payload/binding/cohort/
  review/policy/expiry/formula/originalcutoff/provenance/financialstate/terminal/
  unaffectedunits/noautorenewe. Costvalidationใช้savedgenuinefinalpacketclock
  ไม่อ้างเป็นSDKreadใหม่หลังstart
- Postinstallbackup140500992rawbytes,gzip10416054,112076audit/kv12/events0/
  deliveries0 ทดลองrestoreจริงบนlocalแล้วnewacceptedreview/policy/CYCLEcohort/
  day/loss/boundary/identity/outboxตรงครบ beforebackupไม่ถูกทับ. เป็นpersisted
  recoverycontextproof ไม่ใช่actualVMrebootหรือnativeforward qualification
- Before/aftercontrolsไม่เรียกforcedorder; actualpoststartsignal→fill→BE→close,
  realizedcost/futureprofitและrebootยังไม่qualified. ไม่มีeconomicbacktestรอบนี้

APdeeptriggerยังเป็นอีกissue ไม่ถูกแก้ด้วยการรับcostใหม่ การhealthyชั่วคราวไม่ใช่
matchedfix/1hour+24hourrolloverproof. Senderalive+reviewvalidไม่รับประกันครบทุกgate
Post-reviewM15และpostinstallrestoreผลจริงอยู่ในส่วนถัดไปตามobservationเวลาใหม่

## Actual post-review M15

ต้นแท่ง13:00:00/13:00:01UTCติดalgo_permissions_requiredจริง เก็บauditเดิมครบ
ไม่ได้เปลี่ยนpermissionsหรือterminalเพื่อให้ผ่าน. ต่อมารอบcaptured
13:00:05.434786UTC/audit13:00:13.575856UTCประเมินM15เป็นWAIT/no_signal,
failure=null. Snapshot13:00:59UTCเป็นduplicate_bar,last_bar13:00UTC,
financialeventrows0. จึงพิสูจน์ว่าnew-reviewM15gateผ่านและประเมินแท่งจริงแล้ว
ไม่ได้พิสูจน์ว่าnativeFULLsignalผ่านcost/riskหรือมีfill/BE/close

Costfixproofคือfreshactualspec/calendarvalidationก่อนinstall และaccepted
policy/reviewhashหลังstart แยกจากno_signalของแท่งนี้. APยังflapได้และrate
เปลี่ยนภายหลังยังblockตามexactguardเดิม ไม่มีauto-renewหรือglobal-readyclaim
