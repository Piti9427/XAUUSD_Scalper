# Selected26b8 — logic, conditions and closure status

สถานะ28ตุลาคม2026 (Asia/Bangkok): **LOCAL_IMPLEMENTED; VM_NOT_DEPLOYED**.
เอกสารนี้รวมเงื่อนไข native26b8 จาก source ปัจจุบัน และงานแก้ระบบรอบนี้
ไม่ได้รับรองว่าปิด23issuesแล้ว หรือกำไรในอนาคตจะเท่าผลย้อนหลัง
ผลตรวจและ source hashes อยู่ใน `runs/c22-closure-2026-10-28/`.

Checkpoint นี้เป็น predecessor ของงานต่อเนื่องใน
`docs/reviews/2026-10-28-c22-root-cause-closure.md` และ CORE6.63: coordinator,
cost-incident continuity และ atomic installer มี implementation/test ใน local แล้ว
แต่ grantจริง, source evidenceครบ, VMactivation และ AP/forward qualification
ยังไม่ผ่านทั้งหมด ใช้รายงานใหม่สำหรับสถานะ closure ล่าสุด

## สิ่งที่แก้รอบนี้

1. ปิดช่องโหว่การรายงานเหตุ: risk cap, margin, invalid stop และ M1ผิด/ไม่ครบ
   เคยถูกยุบเป็น `ValueError`; เพิ่ม11เหตุเฉพาะพร้อมวิธีกลับมาเทรดแบบมีเงื่อนไข
   รวมถึง16เหตุ lifecycle เช่นรอ fill/BE/close, ownership/volume ไม่ชัด
   ซึ่งเคยถูก availability ยุบเป็น `runtime_blocked`. ไม่เปลี่ยน gate หรือ clear UNKNOWN.
2. เพิ่ม opt-in evidence export ผ่าน senderเดิม โดยใช้ account/exposure/history/spec
   ที่รอบนั้นอ่านอยู่แล้ว ไม่มี SDK initialization/session/read เพิ่ม
   ทำ IO หลังจบ financial cycle; exportล้มไม่เปลี่ยนผล fill/manage/UNKNOWN
   ไม่มีการพักเทรดเพื่อเก็บ evidence. ส่ง order/ยังถือไม้/UNKNOWN/latched halt ให้ defer.
3. เพิ่ม offline renewal planner สำหรับ Q1/Q4/Q5/Q7/Q8: grantต้องมี trusted pin
   บัญชี/source/config/economicsตรง,72hเริ่มเตรียม,168hอายุเดิม,flat/noorders/noactive/noUNKNOWN
   จึงได้ review candidate. ทุกผลยัง `installation_authorized=false` และคง old policy/context.
   **ยังไม่มี scheduler, grantจริง, cost-incident migration หรือ atomic installer**.

แหล่ง source: `scripts/demo_runtime/diagnostics.py`, `scripts/c22_selected/evidence.py`,
`scripts/c22_selected/runner.py`, `scripts/c22_selected/renewal.py`.

## 1. ตัวตนและลำดับการทำงาน

- Rules ID `26b8bcd69e043653`, snapshot `RESEARCH-C22-SELECTED-20261025-26B8`;
  magic22261025. ใช้ `scripts/c22_selected` กับ `c22-selected-execution.service`.
- ตรวจ config/source → Demo identity/terminal → exposure/history → symbol/quote
  → M1/M15/H4 → signal → dailybaseline/halt/exposure/loss/cooldown/window
  → cost/daily/risk/margin/stops/order_check → ตรวจสดก่อนส่ง → journal SENDING
  → broker → reconcile. เมื่อมี active intent ให้เข้า owned manager ก่อน new admission.
- บัญชีต้องตรง expected login/server, Demo/USD/hedging, balance/equityเป็นบวกและfinite.
  Terminal connected; การส่ง/แก้/ปิดต้องมี AutoTrading/API/account/expert permissions.
- หนึ่ง account หนึ่ง sender; ไม่เปิด oldC22,main.py,webhookหรือEAอื่นร่วมบัญชี.
  `execute=true` คือ armed mode ไม่ได้หมายความว่าทุก gate ผ่านหรือมี order แล้ว.

Source: `scripts/c22_selected/__main__.py`, `scripts/demo_runtime/runner.py`,
`scripts/demo_runtime/broker.py`, `scripts/demo_runtime/admission.py`.

## 2. Graph และ indicator ที่ใช้

- ใช้ UTC Bid M15 ที่ประกอบจาก M1ครบ15แท่ง ปิดแล้วทั้งหมด ไม่ใช้แท่งกำลังก่อตัว
  ไม่เติมแท่งหายด้วยราคาสมมติ. ATR14ใช้ arithmetic mean True Range รวม gap.
- EMA50จาก M15; slopeเทียบ4แท่งก่อน. RSI7ใช้ arithmetic rolling gain/loss
  ไม่ใช่ Wilder RSI; gain/lossศูนย์ทั้งคู่ได้50 และ lossศูนย์/gainบวกได้100.
- H4ต้องมี M15ครบ16แท่งต่อbucket; EMA200ต้องมี201completeH4
  และมีค่า macro ของช่วงปัจจุบันที่พิสูจน์ได้. PartialH4ไม่ carry ค่าเก่ามาบังคับเปิด.
- Startupอ่าน broker historyจริงและ verifiedcacheได้ ไม่ต้องเริ่มนับ201H4ใหม่ทุกrestart.
  Cacheต้องตรงบัญชี/config/hash และ broker overlap; แหล่งข้อมูลไม่พอยัง block.

Source: `scripts/c22_selected/strategy.py`, `scripts/c22_selected/history.py`,
`scripts/demo_runtime/market_data.py`, `scripts/research/campaign_signals.py`,
`scripts/research/reward156_tuning.py`, `scripts/strategy.py`.

## 3. BUY / SELL

- BUY: RSI7ก่อนหน้า<30 และปัจจุบัน>=30; closeเพิ่มจากแท่งก่อน;
  close>EMA50; EMA50สูงกว่า4แท่งก่อน; close>closedH4EMA200.
- SELL: closeต่ำกว่า lowต่ำสุดของ48แท่งก่อนหน้า; close<EMA50;
  EMA50ต่ำกว่า4แท่งก่อน; close<closedH4EMA200. ถ้าชนกัน parentSELLมีลำดับก่อน.
- ไม่มี native dailyprofit target, newsfilter, sessionfilterหรือ max-spread filterเพิ่ม.
  Spreadกว้างยังทำให้ geometry/risk/broker checksไม่ผ่านได้.
- ต้องเป็น closed M15ใหม่; ไม่มีการย้อนเปิดสัญญาณเก่าเมื่อ windowหมด.

## 4. Lot, entry, SL, TP, RR และต้นทุน

- Fixed0.01lot,หนึ่งposition; ไม่ทบlot, martingale หรือ recoverybasket.
  กำไรเพิ่ม balance แต่ lotยังเท่าเดิม; risk%ของไม้เดิมจึงลดลงเมื่อequityเพิ่ม.
- BUYส่งที่ ask; SELLที่ bid. Geometryใช้ conservative entryเผื่อ declaredslippage
  และ symboltick rounding. SL2.5ATRทั้งสองฝั่ง ปัดออกด้านปลอดภัย.
- BUY TP3R; SELL TP1.35R โดย Rใช้ระยะSLหลังrounding; TPปัดเข้าตามtickgrid.
  RRนี้คือ price geometryก่อนต้นทุน ไม่ใช่ net realized RR ที่รับประกัน.
- Initial SL risk รวม declared slippage allowanceและround-trip commission
  ต้องไม่เกิน10%ของ currentequity ทั้งcanonicalและbroker profit check.
  ไม่ปัดlotขึ้นเพื่อให้เปิดได้; freemargin,lotgrid,stops/freeze/fillingและorder_checkต้องผ่าน.
- ยังไม่สำรอง future holding swapใน10%initialcap. Gap/slippage/ต้นทุนจริงอาจทำให้
  realizedlossเกินแบบจำลอง. ก่อนส่งตรวจราคา/capital/exposure/identity/windowซ้ำ.

Source: `scripts/research/breakout_entry.py`, `scripts/c22_selected/strategy.py`,
`scripts/demo_runtime/admission.py`.

## 5. BE และการออกไม้

- Broker SL/TPเป็นหลัก. BE1Rตรวจที่ firstquoteหลัง M15ใหม่ปิดหลังเข้าไม้
  ไม่ใช่ BEทุกtick และไม่ใช่ trailingstop.
- ต้องได้ executableprofit หลัง commission/slippage ถึง originalfillriskก่อน.
  SLใหม่อิงfill+/-commission/slippage ปัดtick,เลื่อนเฉพาะทิศที่tighten; TPเดิม.
- บันทึก pending mutationก่อนส่ง; BE_MOVEDต้องเห็นbrokerSLยืนยันจริง.
  ไม่ยืนยันให้คงpending/UNKNOWN ไม่ blind resend.
- Native BEยังไม่รวม accrued/futureswap; ปิดที่priceBEยัง netlossได้.
- พบfillผิดside/volume/risk/protection/costcontract ให้ใช้ owned safetycontainment
  พร้อมlatchedhalt. ไม่ปิดforeignposition. CLOSEDต้องมีledgerครบและnetvolumeศูนย์;
  netรวมprofit+commission+swap+fee.
- Broker SLTPอยู่ต่อเมื่อclientดับ; clientBEต้องมีmanager/connection/permissions.
  อ่านclosedledgerได้แม้ส่งคำสั่งไม่ได้ ถ้าidentity/exposure/historyพิสูจน์ได้.

Source: `scripts/demo_runtime/lifecycle.py`.

## 6. เสียเท่าไรพัก และกลับมาเมื่อไร

| เหตุ | พฤติกรรม native | กลับมาได้เมื่อ |
|---|---|---|
| ขาดทุนเทียบ UTCdaystartequity ถึง10% | หยุดเปิดใหม่ ไม่บังคับปิดไม้เดิม | dailybudgetพิสูจน์ได้และผ่านอีกครั้ง พร้อมfreshsignal/allgates |
| Closed owned netlossครบ2ไม้ในUTCวันนั้น | หยุดเปิดใหม่ | UTCวันใหม่ (07:00ไทย) มีbaselineพิสูจน์ได้และfreshsignal/allgates |
| เพิ่งปิดnetloss | Cooldown30นาทีตามเวลาจริง ข้ามวัน/restartก็ยังอยู่ | FIRSTquoteของสัญญาณใหม่ถึงexit+30นาทีและทุกgateผ่าน |
| สัญญาณเกิดก่อนcooldownครบ | consumeแท่งนั้น | ต้องรอสัญญาณใหม่ ไม่รอเวลาแล้วเปิดแท่งเดิม |
| 0.01lotเสี่ยงเกิน10%/marginไม่พอ | ไม่เปิด/ไม่เพิ่มทุนสมมติ | equity/ATR/price/marginจริงเอื้อและfreshsignalผ่าน |
| Quoteหาย/เก่า | ไม่เปิด; freshquoteต้องอายุ0..60วินาที | feedกลับมาและยังอยู่ในentrywindow90วินาที มิฉะนั้นรอสัญญาณใหม่ |
| H4/historyไม่ครบ | ไม่เปิด | genuine completehistory/macro และfreshsignal |
| UNKNOWN/ledger/ownershipไม่ชัด | reconcileต่อ ห้ามส่งซ้ำ | brokerproofครบ; ถ้าlatchedhaltต้องreviewresolutionด้วย |
| source/account/cost/reviewผิด | ไม่เปิดใหม่ | แก้หลักฐาน/ข้อผิดพลาดจริงและreviewที่ผูกตรง ไม่เปลี่ยนtimestampหลบ |

Daily10%เป็น **observed equity admission threshold** ไม่ใช่จองงบSLไม้ถัดไป.
DD40%เป็น **research selection gate** ไม่ใช่ liveDDbreaker.
ยังไม่มี native24hพักหรือ auto-resumeDD; เป็นcandidateแยกที่ไม่ได้promote.
จึงไม่ควรตีความว่าliveขาดทุนสูงสุด40%ถูกบังคับไว้แล้ว.

Dailybaselineต้องreconcile epochhistory/count/ticket/cash/positionvolume.
Flatที่midnight reconstructได้; ถือไม้ข้ามmidnightต้องมี genuineequityproof
ในfirstUTCsecond. ไม่มีproofไม่สร้างallowanceใหม่จากrestart.
Daily lossนับตามวันfinalexit; priceBEแต่swapติดลบนับเป็นloss.

## 7. Policy expiry และ renewal

- Current v2policyอายุ0..168ชั่วโมง inclusive; หลัง168ชั่วโมงไม่ผ่าน.
  ต้องมีhash-bound tariff/spec/datedswapcalendar; storedspecเทียบliveตรงทุกfield.
  **Spec driftไม่ใช่expiry**: ต่อเวลาอย่างเดียวแก้ไม่ได้.
- Actualcost guardตรวจledgerหลังreviewcutoff: swapตรงdatedmodelภายใน0.02USD
  และcommission/feeไม่เกินbudget; swapต่ำกว่าคาดก็ถือdrift.
- Swap-Free entitlementยังUNKNOWN; regularPOINTS/scheduleเป็นDemoassumptions,
  economicqualificationยังCOST_INCONCLUSIVE. ไม่รับรองholidayexceptions.
- Q1–Q9ที่ยืนยันแล้ว: เตรียมก่อนหมดอายุ72ชม. **ยังเทรดต่อได้** ถ้าoldvalidและallgates.
  Cost/spec/source/account/configต้องตรงscopeเดิม; installเฉพาะflat/noorders/noactive/noUNKNOWN.
  Newrenewalล้มให้เก็บoldgeneration/contextครบ; oldหมดอายุจึงblocknewentries.
- รอบนี้มีofflineplannerและsame-senderevidenceเท่านั้น. ยังไม่ติดตั้งstandinggrant,
  scheduler,sourcecollector,incidentcontinuityหรือatomicgenerationinstaller;
  จึง **ยังไม่ใช่ระบบauto-renewที่ใช้งานบนVMแล้ว**.
- Ownedmanagerแยกจากnewentryreview/expiry แต่ยังต้องผ่านbrokerprerequisitesที่เกี่ยวข้อง.
  ห้ามforcecloseเพื่อrenew/ลบjournal/เลื่อนcutoffข้ามunauditedexit.

Source: `scripts/demo_runtime/costs.py`, `scripts/c22_selected/execution.py`,
`scripts/c22_selected/trial_costs.py`, `scripts/c22_selected/renewal.py`.

## 8. Error และการเฝ้าระวัง

แต่ละfixedreasonมีresumecondition; failureมีstage,exceptiontype,sourceframes,
correlation/evidence reference. ไม่แสดงrawSDKsecret. Unknownexceptionยังบอกชนิดและ
originได้ แต่ไม่เดาว่าmechanicaloriginคือdeepestrootcause.
`KNOWN_BLOCKERS_ONLY` แปลว่ารู้เฉพาะchecksที่ถึงแล้ว/independentreview
ไม่ใช่ทุกdownstreamgateผ่าน. Processalive,entryready,positionprotectedเป็นคนละค่า.

Localwatchdog recovery180วินาทีเป็นmonitoring ไม่ใช่tradingcooldown.
ExternaldeliveryยังOFF; VMดับทั้งเครื่องไม่สามารถเตือนจากตัวเองได้.
APmaintenance≤15นาทีต่อรอบรวมrollback; ตรวจfix≥1ชม.และเฝ้ารวม24ชม.รวมrollover
เป็นเกณฑ์ปิดissue ไม่ใช่เพิ่มเวลารอก่อนเทรด.

## 9. Backtest ที่ยังอ้างได้และข้อจำกัด

Archived base+swapจากทุน200USD: net+1,945.334USD,final2,145.334USD,
DD34.275%,460trades. Worst6modeledpathsDD38.671%; lossstreak11;
completedclosing-balancerecoveryยาวสุด130.30วัน,ongoing60.78วันณข้อมูลสิ้นสุด.
ดู `docs/reviews/2026-10-25-c22-exhaustive-tuning.md` และ
`docs/reviews/2026-10-26-c22-risk-closure.md`.

รอบนี้ไม่ได้รันeconomicbacktestใหม่; nativefunctionASTและ101/110frozenpinsต้องตรง.
Operationalfixช่วยให้ทำตามกฎ/เห็นปัญหาจริง ไม่สร้างสถิติกำไรใหม่.
Data/geometryagreementไม่เท่ากับbrokerfill/cost/lifecycleparity;
ข้อมูลที่จูนไปแล้วไม่ใช่freshholdout. ผลย้อนหลังไม่รับประกันกำไรรายวันหรือปลายทาง.

## 10. Issue closure matrix

| Tickets | สถานะหลังงานlocalรอบนี้ | หลักฐาน/สิ่งที่ยังขาด |
|---|---|---|
| #12 | ยังเปิด: stagedlocal | ต้องapprovedsource-boundVMrolloutและruntimecheck |
| #13–14 | ยังเปิด: AProotcause | ต้องterminaltimeline/controlledrepro/fix/1h+24hrollover |
| #15 | Localcontractพร้อมreview | offlinegrant+pin+exactscope; ยังไม่มีgrantจริง/activation |
| #16 | Localimplementationพร้อมทดสอบ | opt-insenderreadexport; VMfreshpacketยังไม่observed |
| #17 | ยังเปิด | datedofficialsource packets/collector,ไม่ใช่timestamp-only |
| #18 | ยังเปิด | durableincident/costgeneration/cutoffcontinuity |
| #19–20 | Partialpreparation | offlineplanner; ยังขาดinstaller/scheduler/crash+restartintegration |
| #21/#34 | Deferred/OFF | ยังไม่เลือก/อนุมัติexternalchannelหรือoff-VMobserver |
| #22–23 | ยังเปิด: requiredevidence | datedsessions/held-midnightproofจริงและrestart/slowSDK |
| #24–27 | ยังเปิด: operational/forwardproof | UNKNOWNresolution,authenticlifecycle,reboot,prospectivecollector |
| #28–32 | ยังเปิด: distinctresearch | preregisteredmatchedswap-inclusivecampaigns+independentaudit/forward |
| #33 | PAUSED | lotcompoundingยังไม่ได้รับresume |

ไม่มีGitHubissueถูกปิดจากunit tests และไม่มีVM/SDK/order/alertactivationในงานรอบนี้.

## Requirement | Evidence

| Requirement | Evidence |
|---|---|
| “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด” — เหตุentryถูกต้องและกลับตามgateเดิม | `CanonicalRefusalDiagnosticsTests.test_real_native_geometry_refusals_keep_exact_cause_and_never_send`, `test_real_m1_refusals_keep_exact_cause_and_never_send`, `test_real_native_risk_refusal_recovers_only_when_original_geometry_passes` |
| “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด” — UNKNOWNมีเหตุเฉพาะ/noresend | `test_native_unknown_fill_keeps_specific_reason_and_never_resends`, `test_all_fixed_lifecycle_return_reasons_have_specific_resume` |
| “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด” — evidenceไม่เพิ่มSDK/ไม่ขัดmanager/ไม่refreshวันที่ | `SenderEvidenceTests.test_capture_adds_no_sdk_calls_compared_with_disabled_path`, `test_native_fill_and_unknown_defer_export_without_changing_send`, `test_bad_request_and_write_failure_are_optional_and_retryable`, `test_restart_retains_original_capture_time_and_never_turns_old_packet_fresh`, `test_changed_release_never_relabels_prior_packet_as_current_evidence` |
| “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด” — Q1–Q9contractไม่เปิดauthorityเอง | `RenewalContractTests.test_disabled_or_unpinned_grant_never_manufactures_authority`, `test_72_hour_boundary_prepares_without_cooldown`, `test_lower_swap_commission_slippage_or_spec_drift_requires_review`, `test_held_order_active_unknown_defers_install_but_preparation_can_start`, `test_failed_preparation_retains_complete_old_context_and_trading_eligibility` |
| “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด” — สรุปทั้งหมด/ไม่แอบเปลี่ยนกลยุทธ์ | เอกสารนี้, `logic-inventory.json`, `preservation.json`, `task-delta.diff`; source-coordinate auditแยกจากfreshVMproof |

## Validation และ local release

- New31tests: canonical/lifecycle6, same-senderevidence9, offline-renewal16.
- Focused54tests PASS32.310s. Fullrepository1,374tests PASS251.865s,skipped2,exit0.
- ScopedRuff/compile/whitespace/sourceverificationPASS. Coveragepercentageไม่ได้วัด.
- Frozenparent101/risk110sourcepinsไม่เปลี่ยน; nativeSelectedStrategy functionASTตรงเดิม.
  Sharedcycle/_cycle/sendASTตรงเดิมหลังตัดเฉพาะobservercall/attemptflagที่เพิ่ม.
- Configเปลี่ยนเฉพาะsourcebindings21รายการ; strategyparametersเดิม.
- Prepared `selected-7e55d89979d50b0d`:83manifestpayloadfiles,74Pythoncompile,85archivemembers;
  SHA256 `dc5259bf1865124c4e858045ea9e6af841c43e8228adb98a72c5ff4d2238f7bd`.
  ไม่รวมenv/financialDB; defaultshadow,executionstaged; ไม่deploy/activate.
- Source/diagnosticcross-auditsทำโดยfocusedagents; finalfollowupindependentreview
  ไม่สำเร็จเพราะagentusage limit. Rootตรวจsource/assertionsเองและเก็บROOT_REVIEW.md;
  ไม่อ้างว่าเป็นindependentend-to-endgeneration/VM audit.

Machineproof: `validation.json`, `preservation.json`, `financial-ast.json`,
`release-verification.json`, `current-conditions.json` (28rulegroups/170resume codes),
`source-coordinates.json`, `full-suite.log`, `focused-verified.log`, `task-delta.diff`
ใน `runs/c22-closure-2026-10-28/`. Historicalbeforepatchinventoryเก็บไว้แยก.

Nextoperationalstep: freshVMread-onlypreflightและreviewsource-boundrolloutของreleaseนี้
ก่อนowner-approvedcutover; ไม่ใช้เอกสารlocalเป็นหลักฐานว่าVMอัปเดตแล้ว.
APtrigger/costincidentcontinuity/atomicrenewal/realforwardproofยังต้องดำเนินต่อ
ตามmatrixข้างบน. ไม่มีissueถูกปิดโดยการคาดเดา.
