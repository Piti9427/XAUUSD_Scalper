# Selected26b8 — AP reconnect / policy renewal drill-down

Scope: owner asks to break down the two remaining issues. This is analysis and issue decomposition, not approval to deploy, renew policy, change terminal/network settings or place orders. No runtime source/config/VM mutation this turn. Latest recorded VM snapshot is **27Oct2026 12:58:59Thailand**, not a new live refresh.

AP=Access Point between MT5 and broker; not a strategy cooldown. Current evidence proves repeated native handoff/reconnect, not its deepest trigger. Local diagnostics/watchdog fixes are staged but not deployed. Current cost policy was valid in the latest recorded snapshot; expiry is **1Nov2026 20:25:18.050055Thailand**.

**Correction of ambiguity:** Swap-Free UNKNOWN, COST_INCONCLUSIVE and holiday-exceptions-unverified are explicitly allowed labels in the existing conservative armed Demo trial. They do not independently prohibit that trial or prove zero swap. Automatic renewal is missing authority, fresh collection, cost-incident continuity and atomic installation; CLI already reloads policy every loop.

## Priority and dependency

- AP-01 enables actual SDK flag attribution; AP-02 maps endpoints. AP-03/AP-04/AP-05 distinguish broker/native, transport and Wine/QEMU hypotheses. AP-06 measures execution/protection impact; AP-07 validates an actual fix.
- COST-02 defines standing authority if wanted; AP reliability enables COST-03 fresh broker evidence. COST-04/05 validate source/calendar, COST-07 preserves old incidents, COST-06 installs one coherent generation, COST-08 preserves active management. COST-09 guards drift. COST-10 handles operational visibility/delivery.
- Labels: LOCAL_READY=implemented/tested locally, not deployed; HYPOTHESIS=not a proven cause; GUARD=current intentional rule; OPEN=missing evidence/workflow; PARTIAL=some mechanism/tests exist; DECISION=owner scope required before automation.

## AP reconnect

### AP-01 · SDK flag ที่ล้มยังไม่ปรากฏบน VM

**P1 / LOCAL_READY / ช่องว่างการวัด**

- **Verified/current:** VM รุ่นเดิมรวม disconnected, terminal permissions และ account permissions เป็น algo_permissions_required. Local diagnostics พร้อมใน release3916d35b2d095b1a แต่ยังไม่ deploy.
- **Impact:** แยกสาเหตุราย cycle ไม่ได้ และยังยืนยันไม่ได้ว่าทุก failure เป็น connected=false.
- **Investigation/change:** ใช้ identity diagnostics จาก account_info/terminal_info reads เดิม: connected, trade_allowed, tradeapi_disabled, account trade_allowed/trade_expert; จับคู่ timestamp กับ native log โดยไม่เปิด SDK reader เพิ่ม.
- **Close when:** ทุก identity-blocked cycle มี finite blocker/flags หรือ explicit unreadable. เดิม reject เหมือนเดิม ไม่มี extra SDK read/secret/resend; ตรวจจริงหลัง rollout.
- **Depends on:** No issue dependency; preserve existing runtime gates.
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-27-c22-operability-fixes.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/correlation.json).

### AP-02 · ยังไม่รู้ว่า AP ที่สลับคือ endpoint ใด

**P1 / OPEN / หลักฐานขาด**

- **Verified/current:** Native log ระบุ AP#1 และ quality99% ก่อน/หลัง. ชื่อเดียวกับเปอร์เซ็นต์ที่ปัดแล้วไม่พิสูจน์ว่าเป็น endpoint/คะแนนเดียวกัน. มีเพียง passive socket snapshots สี่ครั้ง.
- **Impact:** อาจโทษ network หรือ config ผิดจุด; host-global retransmit ไม่ชี้ว่า MT5 เป็นผู้ได้รับผล.
- **Investigation/change:** เก็บ terminal-owned peer mapping แบบปกปิด endpoint, ช่วง scan→handoff→lost→authorized→sync และ per-socket latency/retransmit ที่มีจริง; ระบุ PID/build/profile/เวลาให้ตรงกัน.
- **Close when:** จับคู่ handoff กับ endpoint transition หรือ same-endpoint reconnect ได้โดยหลักฐานตรง; แยก socket อื่นออก. Unknown endpoint role ต้องคง UNKNOWN.
- **Depends on:** AP-01
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/FINDINGS.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/socket-state-evidence.json).

### AP-03 · เหตุที่ native optimizer สั่งย้ายซ้ำยังไม่พิสูจน์

**P1 / HYPOTHESIS / root trigger ยังไม่รู้**

- **Verified/current:** 759 disconnect intervals; handoff median16.836s; lost→trading-enabled median8.728s; 5850/5852 permission cycles ทับช่วง disconnect. ยืนยัน mechanism แต่ไม่ยืนยัน trigger.
- **Impact:** เพิ่ม retry/restart อาจกลบ loop หรือเพิ่มช่วงขาดการจัดการ โดยไม่แก้เหตุ.
- **Investigation/change:** ทดสอบสมมติฐานแยก: broker/AP quality/load decision, stale native profile/network metadata, และ transport failure. ใช้ build/account/ช่วงตลาดเดียวกัน เปลี่ยนครั้งละหนึ่งปัจจัยใน maintenance ที่ reviewed; ไม่แก้ binary config หรือ pin IP เดา.
- **Close when:** สมมติฐานอธิบาย event sequence และผ่าน disproof; controlled comparison แสดงผลต่างที่ทำซ้ำได้. ไม่ปิด issue เพราะเห็น healthy ชั่วคราว.
- **Depends on:** AP-01, AP-02
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/FINDINGS.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/native-log-evidence.json).

### AP-04 · ยังแยก network path กับ native handoff ไม่ได้

**P1 / HYPOTHESIS / สมมติฐาน transport**

- **Verified/current:** NTP ปกติ, proxy disabled, snapshot RAM/disk/CPU ไม่ชี้ resource exhaustion. สถิติ TCP เดิมเป็นทั้ง host ไม่ผูกเหตุของ terminal.
- **Impact:** การอ้างว่า Oracle network เสีย หรือเพิ่ม resource จะแก้ เป็นข้อสรุปที่ยังไม่มีหลักฐาน.
- **Investigation/change:** ดู loss/retransmit/RTT ของ connection ที่เป็น terminal โดยตรงก่อนและหลัง handoff; ตรวจว่า transport fail มาก่อน native switch หรือ switch ทำให้ connection ปิด. ใช้ passive evidence ก่อนเปลี่ยน network.
- **Close when:** ระบุลำดับเหตุและ process attribution ได้; ถ้า counters ไม่รองรับต้องตัด hypothesis ไม่สรุปจากผลรวมทั้ง VM.
- **Depends on:** AP-02
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/host-config-evidence.json), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/socket-state-evidence.json).

### AP-05 · Wine/QEMU กับ native timing ยังไม่ถูกแยกทดสอบ

**P1 / HYPOTHESIS / สมมติฐาน compatibility**

- **Verified/current:** Terminal รันผ่าน Wine/QEMU บน ARM; host UTC/NTP ถูกต้องไม่ได้พิสูจน์ Windows monotonic/performance timer หรือ native networking behavior. ยังไม่มี matched control runtime.
- **Impact:** ยังบอกไม่ได้ว่า loop เกิดจาก emulation, build/profile หรือฝั่ง broker.
- **Investigation/change:** เก็บ exact MT5/Wine/QEMU build และเปรียบเทียบ guest elapsed clocks กับ host; หากจำเป็นใช้สภาพแวดล้อมควบคุมที่มีอยู่แบบทีละตัว/ไม่มีสอง sender. ไม่ซื้อ infra หรือเปลี่ยน platform อัตโนมัติ.
- **Close when:** ได้ paired timing/control ที่แยก emulation จาก broker/network โดยตรึง account/build/input ที่เกี่ยวข้อง; ไม่มี control ต้องคง UNKNOWN.
- **Depends on:** AP-02, AP-04
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/FINDINGS.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-root-cause-2026-10-27/permissions/host-config-evidence.json).

### AP-06 · ต้องวัดผลต่อ entry window และ owned protection

**P1 / PARTIAL / ผลกระทบยังไม่ครบ**

- **Verified/current:** Audit111 observed complete M15: FULL0. ไม่พบ eligible trade ที่พิสูจน์ว่าพลาด. บาง cycle positions=null; ไม่มี owned intent ไม่เท่ากับ broker flat. Connected=true ก็ยังต้องมี synchronized/fresh data.
- **Impact:** ห้ามแปลงจำนวน disconnect เป็นจำนวนไม้/กำไรที่เสีย หรือสรุปถือไม้ปลอดภัยจาก service active.
- **Investigation/change:** จับคู่ causal FULL signal กับทุก cycle ภายใน90s, fresh quote<=60s, broker REQUEST/RESPONSE และ reconciled fill. ทดสอบ disconnect ก่อนsend/หลังsend/ตอนBE ด้วย fixture และ UNKNOWN/no-blind-resend; จริงรอ native signal.
- **Close when:** ไม่มี phantom fill/resend; ช่วงเข้า order ทุกช่วงชี้ได้ว่าผ่านหรือติด gate ไหน; active protection มี broker-confirmed evidence หรือ UNKNOWN ชัด. ไม่มี signal ให้รายงาน not observed.
- **Depends on:** AP-01
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-27-c22-missed-signal-audit.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_identity_diagnostics.py).

### AP-07 · เกณฑ์ปิดและ rollout ต้องตรวจที่ VM จริง

**P1 / OPEN / validation/deployment**

- **Verified/current:** Final capture27Oct12:58:59ไทยยังเป็น selected-9cfc54a3dc78f0ae, PIDs52912/34838,NRestarts0, latest algo_permissions_required. Release3916... เป็น local/staged เท่านั้น.
- **Impact:** Local tests1312ผ่านไม่ได้พิสูจน์ว่าตัว native reconnect ถูกแก้ หรือ VM ได้ใช้ diagnostics ใหม่.
- **Investigation/change:** Rollout ที่ review source/config จริง หลังตรวจ manager/flat/noUNKNOWN/backup. ทดสอบ candidate AP fix แบบเดียวทีละตัว และทบทวน failure pattern หลายรอบ/หลาย M15 boundaries; เฝ้าต่อข้าม rollover. เวลาเฝ้าต้องตกลงก่อนทดลอง ไม่เพิ่ม startup wait ลับ.
- **Close when:** Actual deployed hashes ตรง; repeated~17s loop ไม่เกิดจาก trigger ที่แก้ใน observation ที่กำหนดล่วงหน้า; quote/protection/admission measurements รองรับ. Legitimate handoff ไม่ถูกซ่อน. รายงาน residual outages.
- **Depends on:** AP-01, AP-03, AP-06
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-operability-fix-2026-10-27/vm-readonly-final.json), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-27-c22-operability-fixes.md).

## Policy renewal

### COST-01 · อายุ168hและ dated calendar เป็นคนละ gate

**P1 / GUARD / กฎตั้งใจ**

- **Verified/current:** v2 valid เมื่อ ageอยู่0..168h; exact expiryยังผ่าน,+1µsไม่ผ่าน. Policyที่บันทึกไว้หมด1Nov2026 20:25:18.050055ไทย. Restartไม่ต่ออายุ; today/holding calendar missing ยัง block แยก.
- **Impact:** ลบ expiry อย่างเดียวไม่ได้ทำให้ทำงานต่อได้ และอาจใช้อัตรา/วันเก่าต่อไปผิดสัญญา.
- **Investigation/change:** แสดง expires/due; สร้าง evidence generation ใหม่จริงก่อนหมดอายุ. รักษา independent validity/calendar/spec/drift checks.
- **Close when:** Boundary testsผ่าน; ไม่มีการเปลี่ยน reviewed_utc เดิมเพื่อหลบ gate; calendar ขาดยังไม่ผ่านแม้ ageสด.
- **Depends on:** No issue dependency; preserve existing runtime gates.
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_rootcause_policy_interactions.py).

### COST-02 · ยังไม่มี standing authority สำหรับ auto-renew

**P1 / DECISION / สิทธิ์และขอบเขต**

- **Verified/current:** Ownerอนุญาต armed Demo และ waiver เวลา shadow แต่ยังไม่ได้ให้อำนาจต่ออายุทุก generation. Reviewปัจจุบันผูก account/source/config/policy hash ตรงกัน.
- **Impact:** Cronที่สร้าง approvalใหม่หรือเปลี่ยน policy เองจะขยายสิทธิ์จากที่ตกลง และอาจยอมรับต้นทุนใหม่โดยไม่มีขอบเขต.
- **Investigation/change:** กำหนด immutable standing grant ถ้าต้องการ auto-refresh: exact Demo/source/config, fieldsที่เปลี่ยนได้, cost bounds, evidence freshness, revocation และเงื่อนไขต้องหยุดรอ review. ไม่สร้าง approved_utcเสมือนคนอนุมัติใหม่.
- **Close when:** เปลี่ยน account/source/config/assumptionsนอกgrantต้อง block; refreshที่อยู่ในขอบเขตต้อง trace ถึงgrantเดิมได้. ยังไม่ถือว่าตัดสินใจอนุญาตในงาน drill-down.
- **Depends on:** No issue dependency; preserve existing runtime gates.
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/specs/c22-continuous-demo-2026-10-27.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py).

### COST-03 · ยังไม่มี collector อัตโนมัติผ่าน sender เดิม

**P1 / OPEN / implementation gap**

- **Verified/current:** Builderต้อง broker export<=5min, connected, exactStandardDemoUSDhedging, flat0positions/0orders, epoch historyครบ countตรง และ cash reconcile<=0.02USD.
- **Impact:** ถ้า APหลุด, historyขาด หรือยังถือposition จะยังสร้าง renewal packetที่ผ่านไม่ได้. Scheduled timestampไม่แทนข้อมูล broker.
- **Investigation/change:** เก็บ safe account/spec/ledger packetผ่าน read seamของ senderเดิมพร้อม timestamps/hash; AP/UNKNOWN/ledger failureให้defer. ไม่เปิด SDKreaderคู่กับ armedsender.
- **Close when:** Freshครบจึงสร้างpacket; disconnected/stale/nonflat/historyไม่ครบต้องfailหรือdeferอย่างเจาะจง. No extra sender/forcedorder/journalreset.
- **Depends on:** AP-01, AP-07
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/trial_costs.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_selected_trial_costs.py).

### COST-04 · URL+checked_utc ยังไม่ใช่ unattended content verification

**P1 / OPEN / collector/evidence gap**

- **Verified/current:** Builderรับ official HTTPS URLs และ checked_utc<=24h จากผู้review; ไม่ได้ดาวน์โหลดหรืออ่านความหมาย tariff/swap/holiday เอง.
- **Impact:** การใส่วันใหม่หรือหน้าเว็บhashเท่าเดิมไม่พิสูจน์ว่าเงื่อนไขบัญชี/วันหยุดไม่เปลี่ยน.
- **Investigation/change:** เก็บ actual retrieval time/content/hash และผลreviewเนื้อหาเทียบ schema/ขอบเขตgrant. เนื้อหาเปลี่ยน/กำกวม/เก็บไม่ได้→explicit unresolved. คงlabelสิ่งที่ยังไม่attestedตามconservativecontract.
- **Close when:** Stale/missing/changed/unsupportedcontentไม่ถูกยอมรับเป็นreviewใหม่; ไม่มี timestamp-only attestation. Publicpageไม่ถูกใช้ยืนยันSwap-Freeรายบัญชี.
- **Depends on:** COST-02
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/trial_costs.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/specs/c22-continuous-demo-2026-10-27.md).

### COST-05 · Calendar8วันต้องต่อเนื่องข้าม DST/holding/generation

**P1 / PARTIAL / workflow coverage**

- **Verified/current:** Builderสร้าง8dateddaysจาก NY17:00, Wednesdaytriple, weekend0 และ SDKPOINTS mode1. Missing todayหรือวันในช่วงถือทำให้ cost_swap_calendar_missing.
- **Impact:** Policyใหม่มีแต่วันนับจากrenewอาจไม่มีวันของpositionที่เปิดก่อนหน้า; cost ageสดไม่รับรองcalendarครอบคลุม.
- **Investigation/change:** Preserve applicable datedcalendar ของgenerationเดิม; ให้closedledgerอ้างgenerationที่ใช้. ทดสอบDST, triple, holdingข้ามrenewและcalendarขาด. ไม่เติมswap0เมื่อข้อมูลหาย.
- **Close when:** ทุกrolloverของpositionที่ตรวจหาdatedrowได้; missing dayต้องblockชัด. Regularscheduleยังเป็นassumptionตามcontract ไม่อ้างhistoricaltariffจริง.
- **Depends on:** COST-03, COST-04, COST-07
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/trial_costs.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py).

### COST-06 · Policy/review ยังติดตั้งคนละไฟล์ ไม่ใช่ atomic generation

**P1 / OPEN / implementation gap**

- **Verified/current:** CLI reloadpolicyทุกloopอยู่แล้ว; reviewอ่านแยกและต้องpolicy hashตรง. เปลี่ยนpolicyอย่างเดียวทำให้ cost_policy_changed. Current codefailclosed ไม่ได้อนุญาตครึ่งชุด.
- **Impact:** Renewแบบreplaceสองไฟล์อาจหยุดเปิดเพราะช่วงกลาง/crash; restartไม่แก้ binding mismatch.
- **Investigation/change:** Package grant/evidence/policy/reviewเป็นvalidated generation เดียว; เปลี่ยนpointerหลังvalidateครบ; runnerอ่านsnapshotเดียว. เก็บชุดเดิม/rollbackโดยไม่ย้อนfinancialjournal.
- **Close when:** Crashก่อน/ระหว่าง/หลังinstall→ชุดเดิมหรือชุดใหม่ที่ครบเท่านั้น; mismatched/tamperedgenerationไม่เข้าorder. ไม่ลด exactbinding.
- **Depends on:** COST-02, COST-03, COST-04, COST-07
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/cli.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py).

### COST-07 · การขยับreview cutoff อาจซ่อน cost incident เก่า

**P1 / OPEN / renewal accounting hazard**

- **Verified/current:** validate_observed_costsข้ามclosedexitsที่เก่ากว่า reviewed_utc. ปัจจุบันไม่มีauto-renew จึงยังไม่ใช่เหตุที่พิสูจน์ว่าVMซ่อนincidentแล้ว.
- **Impact:** ถ้าauto-renewเลื่อนcutoffก่อนaudit ไม้ที่มีswap/feeผิดmodelอาจหลุดจากการตรวจ.
- **Investigation/change:** Auditทุกclosedexitใหม่ด้วยpolicy generationที่เกี่ยวข้องก่อนadvancecheckpoint; persist incident/resolutionและledger identity. ห้ามrenewเพียงเพื่อข้ามexitที่ไม่ผ่าน.
- **Close when:** Injectdriftก่อนrenew→ยังblockหลังrenew/restart. Duplicate/out-of-orderhistoryไม่advancecheckpoint. Cash totalsและจำนวนexitตรวจครบ.
- **Depends on:** COST-03
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/specs/c22-continuous-demo-2026-10-27.md).

### COST-08 · Renewขณะถือposition/UNKNOWN ยังไม่มี lifecycle workflow

**P1 / OPEN / implementation/scope gap**

- **Verified/current:** Current builderต้องflat. Existing managerยังreconcile/protectเมื่อreviewหาย/หมดอายุ แต่ยังต้องผ่านbrokerprerequisites. positionเก็บcostเดิม; expiryไม่ได้สั่งforceclose.
- **Impact:** Stopmanagerเพื่อrenewหรือแทนcostของไม้เดิมอาจกระทบprotection/accounting. APdisconnectยังกระทบclientmanagementได้.
- **Investigation/change:** เริ่มด้วยflat-onlygeneration install; nonflat/UNKNOWNให้deferเฉพาะnewgenerationและดูแลownedต่อ. Activeposition migrationต้องdesign/reviewแยก; ห้ามresend/resetloss/peak/day.
- **Close when:** Expired/revoked/renewfailureระหว่างownedtradeยังไม่หยุดreconciliation; no duplicateorder/phantomfill. หลังprovencloseจึงrenewตามgrant/evidence.
- **Depends on:** COST-02, COST-06, COST-07
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_entry_availability.py).

### COST-09 · Actual cost drift ต้องไม่ถูกยอมรับเองแม้ถูกลง

**P1 / GUARD / กฎตั้งใจ/decisionแยก**

- **Verified/current:** Closed actual swapต่างmodelมากกว่า0.02USDรวมกรณีต่ำกว่า หรือcommission/feeเกินassumption→cost_broker_deal_drift. Specต้องตรงด้วย. UNKNOWNswapfree/COST_INCONCLUSIVE/holidayunverifiedไม่ใช่standalonehardblockของarmedconservativeDemo.
- **Impact:** ยืนยันSwap-Freeอย่างเดียวไม่ใช่คำตอบทุกrenewal; actualchargeที่ต่างยังtriggerguard. ปิดdriftเพื่อให้เข้าไม้ได้จะเปลี่ยนcontract.
- **Investigation/change:** แยก actual incidentจาก entitlement label; review/resolveledgerและgenerationตามหลักฐาน. ยอมรับlowercostหรือขยายboundsเป็นownerdecisionแยก ยังไม่อนุญาตอัตโนมัติ.
- **Close when:** Higher/lower/missingcostdriftยังให้ผลตามcontract; no zero fallback; ไม่เพิ่มentitlement-knownเป็นprerequisiteใหม่โดยพลการ.
- **Depends on:** COST-07
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/costs.py), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/trial_costs.py).

### COST-10 · Due visibilityมีlocalแล้ว แต่ยังไม่มี delivered escalation

**P2 / LOCAL_READY / deployment/owner-deferred**

- **Verified/current:** Release3916...มีdue72/24/6hและknownblockers; ยังไม่deploy. External deliveryปิดตามowner; localoutboxไม่เท่ากับเจ้าของรับข้อความแล้ว.
- **Impact:** ยังปล่อยลืมได้ถ้าไม่เปิดดู; observerในVMเดียวกันไม่แจ้งtotalVMoutage.
- **Investigation/change:** นำdiagnosticsขึ้นด้วยexactreviewก่อน; ระบุผู้รับผิดชอบ/due/resume และDELIVERY_DISABLEDชัด. ช่องทางส่ง/observerนอกVMต้องเลือกและอนุญาตแยก ไม่เปิดเอง.
- **Close when:** อ่านdue/expired/owneractionได้แม้ติดquote/identity; เมื่อdeliveryOFFต้องไม่อ้างnotificationreceived. หากเปิดภายหลังต้องทดสอบreceipt/retryโดยไม่ส่งข้อมูลบัญชี.
- **Depends on:** AP-01, COST-01
- **Evidence:** [source](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-27-c22-operability-fixes.md), [support](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_c22_watchdog_continuity.py).

## Primary platform documentation and remaining limits

MetaQuotes documents that [connected does not establish synchronized quotes](https://www.mql5.com/en/book/common/environment/env_connectivity). Its retransmission metric is host-wide, so it cannot by itself attribute failure to this MT5 instance. [Platform startup/configuration documentation](https://www.metatrader5.com/en/terminal/help/start_advanced/start) explains custom configuration and server address fields; it does not establish a proven safe fix for this captured optimizer loop. Do not invent a disable-rescan flag or pin a guessed IP.

No AP candidate experiment, fresh tariff attestation, policy renewal, native forward fill, new economic replay or proof of lost profit is claimed. The earlier111observed-bar audit has0FULLsignals. Existing1312-test result refers to the staged operability fix, not this issue decomposition and not native AP resolution. Machine catalog: `runs/c22-issue-drilldown-2026-10-27/issues.json`.
