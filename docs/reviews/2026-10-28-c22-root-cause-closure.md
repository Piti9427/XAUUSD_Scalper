# Selected26b8 root-cause closure —28October2026

**LOCAL_VERIFIED_PARTIAL; VM_NOT_ACTIVATED.** แก้ช่องโหว่ renewal/provenance/
restart ใน local แล้ว แต่ยังปิดทุก root cause ไม่ได้: AP trigger, หลักฐาน tariff
ที่อ่านได้จริง, source-bound rollout และ native forward lifecycle ยังมีงานค้าง
ไม่มีการรับรองกำไรอนาคตจาก test ระบบเหล่านี้

Run evidence: `runs/c22-root-closure-2026-10-28/`. Baseline:
HEAD `53312a0783c8424a2ecb8760acafd8d5a71e32e0` พร้อม snapshot ของ dirty workspace
ก่อนเริ่มงาน (`baseline.json`, `before/`); ไม่ถือว่างานเก่าทั้งหมดเป็น delta รอบนี้
สเปก: `specs/c22-continuous-demo-2026-10-27.md`, confirmed Q1–Q9
Native contract: CORE6.54/6.63; เงื่อนไข entry/exit ทั้งหมดอ่านคู่กับ
`2026-10-28-c22-complete-conditions-and-closure.md`

## Root cause → correction → proof

| ช่องโหว่/สาเหตุ | สิ่งที่แก้และผลที่ตรวจจริง | สถานะ |
|---|---|---|
| ต่อ policy โดยย้าย cutoff อาจข้ามต้นทุนของ exit เก่า | Ledger เก็บ original review cutoff, immutable policy และ position binding; ตรวจ epoch/count/cash/volume ก่อน applicable-generation costs; late exit ยังถูกตรวจ | Local verified |
| Restart/new review อาจซ่อน drift รวม swap ที่ต่ำกว่าเดิม | Incident คงอยู่; reference การตัดสินใจไม่ล้าง incident; KV ถูกลบ/ย้อนตรวจเทียบ append-only audit hash | Local verified |
| เปลี่ยน policy/review/evidence ทีละไฟล์ทำ context ปน | Seven-document sealed generation, writer guard, atomic pointer/CAS, semantic validation; failed candidate คง old context ทั้งชุด | Local verified |
| Pointer A→B→A ยังผ่านขณะ A ไม่หมดอายุ | เทียบ durable adoption/lineage; รับเฉพาะรุ่นปัจจุบันหรือ authorized direct child หลัง crash; deleted adopted pointer ไม่ fallback | Reproduced, fixed |
| อ่าน exposure แล้ว history ช้า180วินาที แต่ประทับเวลาใหม่ตอนจบ | เก็บเวลาเริ่ม exposure จริง; install ต้องอายุ<=5วินาที จึง defer เมื่อมี pending order ใหม่ระหว่างอ่าน | Reproduced, fixed |
| Legacy file reload เป็น `{}` ทำ expired generation ฟื้นไม่ได้ | Reload คืน sealed historical context ทั้งชุดสำหรับ planning/CAS; expiry ยังห้าม entry; startup opt-in ฟื้นได้แม้ legacy fileหาย | Reproduced, fixed |
| Cost KVเสีย/grantถูกถอนทำ manager เริ่มไม่ได้ | Lazy auxiliary ledger; owned reconciliation/BE/close ยังเดิน; admission ใหม่ยังถูกปิดตามเหตุ | Local public-sender tests |
| แค่ HTTP200/เวลาใหม่ถูกใช้แทน source proof | ตรวจ actual bytes/hash/URL/เวลา/visible account section/terms; hidden text, wrong-account clause, changed/missing terms defer; hash ติดเข้า policy | Local verified; actual tariff still missing |
| เก็บข้อมูล broker ด้วย processใหม่เสี่ยงสอง SDK readers | ใช้ read seam ของ senderเดิม; automatic watcher อ่านเฉพาะ local source bundle; same-cycle send/held/UNKNOWN defer | Local verified; OFF on VM |
| Wrapper error กลบสาเหตุ generation | เพิ่ม finite codes พร้อม stage/resume; unknown SDK text ไม่สะท้อนออก log; deeper trigger ที่ไม่รู้คง UNKNOWN | Local verified |

หลักฐาน RED/debugger/disproof อยู่ใน `review/`, `cost-generations/`,
`generations/`, `coordinator/` และ source RED/GREEN logs ไม่ใช้ test ผ่านอย่างเดียว
อ้างว่าต้นเหตุ AP หายแล้ว ส่วน initial source-parser debugger ที่เข้าผิด frame
เก็บไว้ตามจริง ไม่ใช้เป็น debugger proof; negative controls/source trace ใช้ยืนยันแทน

## ลำดับ renewal ที่ implement

1. Default OFF; opt-in ต้องครบ grant path, trusted pin, generation directory,
   local source bundle และ original execution review ที่ journal เคยรับจริง
2. เก็บ authority เดิมแยก renewable evidence; ไม่สร้าง owner approval/grant
   ไม่เปลี่ยน approved_utc, account/source/config หรือ commission/slippage/swap/spec
3. เมื่อ policy อายุ96ชั่วโมง เริ่มเตรียมก่อน expiry72ชั่วโมง ระหว่างนี้ old-valid
   ยังรับ native signal ได้ตาม gates เดิม ไม่มี72ชั่วโมง cooldown
4. ตรวจ actual source packet<=24ชั่วโมง และ same-sender broker evidence<=5นาที
   พร้อม complete ledger/cost receipt; HTTPสำเร็จอย่างเดียวไม่ผ่าน
5. Install เฉพาะ actual exposure observation<=5วินาที, flat/noorders/noactive/
   noUNKNOWN/nohalt/no same-cycle send; คง168ชั่วโมง lifetime
6. Switch sealed policy/broker/sources/review/grant/context/cost_audit ทั้งชุด
   เก็บ final-flat install intent ก่อน pointer switch และ durable adoption หลัง switch
7. ก่อน pointer switch ล้มให้เก็บ old context; หลัง replace แล้ว fsyncไม่ชัดให้
   รายงาน ambiguity และตรวจ complete generation ตอน restore ไม่อ้าง rollbackสำเร็จ
8. ต่อใหม่ไม่สำเร็จใช้รุ่นเดิมได้เฉพาะยัง valid และ gates ผ่าน หมดอายุให้หยุดเปิดใหม่
   owned manager ยังดูแลไม้เดิมตาม broker prerequisites; ไม่ force closeเพื่อ renew

ไม่มี operational collector schedule/grant/auto-renew activation ติดตั้งจริง
Source watcher ไม่ fetch เว็บ จึงต้องมี genuine capture supplier ก่อนใช้งาน
POSIX concurrent-read/crash tests ไม่พิสูจน์ Windows directory fsync หรือ hard
power-loss durability บนทุก filesystem

## Native26b8 ยังเหมือนเดิม

Rules `26b8bcd69e043653`, magic22261025. BUY RSI7 arithmetic cross30 + closeขึ้น
เหนือ EMA50 ที่ slope4ขึ้น + closed H4 EMA200 filter; SELL prior48-low breakout
ต่ำกว่า EMA50 ที่ slope4ลงและ closed H4 EMA200. ใช้ closed Bid M15 จาก M1ครบ15
และ H4ครบ16 M15; ไม่เติม missing bars หรือ carry partial H4 เพื่อบังคับเข้า

Fixed0.01, SL2.5ATR, BUY TP3R/SELL TP1.35R, native BE1R ที่จังหวะ M15เดิม;
initial cost-inclusive cap10%, daily10% observed-equity admission/loss2 ต่อ UTC day,
post-loss30minute cooldown, quote<=60วินาที/entry90วินาที, one sender/position,
source/identity/exposure/history/cost/margin/stops/order_check และ UNKNOWN/noresend
ยังอยู่ครบ. ไม่มี lot compounding, daily-profit addon, live DD40 breaker หรือ Net-BE
ที่รวม swapเพิ่มเข้ามา. Daily10% ไม่ใช่การสำรอง SL ถัดไป; BEเดิมยังไม่รวม swap

101 frozen parent pins และ110 risk pins ไม่เปลี่ยน; native strategy function AST
และ config ที่ไม่ใช่ source bindings ตรง baseline. Config bindings เพิ่มเป็น25
ไม่มี economic backtest ใหม่รอบนี้; synthetic accounting/broker tests ไม่ใช่ผลกำไรจริง

## Requirement | Evidence

ชื่อ method ด้านล่างอยู่ใน `tests/demo/`; ใช้ public sender ร่วมกับ deterministic
broker fixtures จึงพิสูจน์การเรียก/ไม่เรียก order API ใน fixture ไม่ใช่ broker fillจริง

| Requirement | Evidence |
|---|---|
| “continue until close all root cuse” — ไม่ย้าย cutoffเพื่อซ่อน drift | `test_c22_cost_generations.py::CostGenerationTests.test_higher_lower_swap_and_excess_fee_incidents_survive_new_review_and_restart`; `test_late_out_of_order_exit_is_audited_even_before_previous_checkpoint` |
| Cost state ต้องไม่ถูกล้าง/ย้อนโดยไม่รู้ | `test_c22_cost_generations.py::CostGenerationTests.test_append_only_cost_audit_detects_incident_reset_or_deleted_state` |
| ไม่มี fabricated approval/source และ lower cost acceptance | `test_c22_renewal_runtime.py::RenewalRuntimeTests.test_matching_renewal_and_restart_keeps_original_approval_after_base_expiry`; `test_changed_candidate_or_incomplete_receipt_retains_old_valid_policy` |
| Q5 flatต้องเป็นข้อมูลที่เพิ่งอ่านจริง | `test_c22_renewal_sender.py::RenewalSenderTests.test_slow_history_cannot_relabel_cached_flat_exposure_as_fresh_for_install`; `test_c22_generation_store.py::GenerationStoreTests.test_slow_validation_or_pointer_write_does_not_reuse_old_flat_observation` |
| Generation rollback/crash ต้องไม่เพิ่ม authority | `test_c22_renewal_runtime.py::RenewalRuntimeTests.test_repointing_to_still_valid_ancestor_blocks_instead_of_readopting_it`; `test_direct_child_with_durable_final_flat_intent_recovers_after_replace_crash`; `test_known_precommit_failure_cancels_intent_and_cannot_be_manually_installed` |
| Q7 old contextและ expired planning ต้องไม่หาย | `test_c22_renewal_runtime.py::RenewalRuntimeTests.test_expired_derived_context_recovers_when_legacy_input_reload_failed`; `test_c22_renewal_sender.py::RenewalSenderTests.test_cli_restart_can_read_complete_generation_when_legacy_policy_file_is_missing` |
| ถือไม้/revoked grant/corrupt cost ไม่ทิ้ง manager | `test_c22_renewal_sender.py::RenewalSenderTests.test_real_fill_and_owned_be_continue_after_standing_grant_is_revoked`; `test_corrupt_auxiliary_cost_state_on_restart_cannot_abandon_owned_protection` |
| Q8 prepareไม่พักเทรด; ไม่มี SDK readerใหม่ | `test_c22_renewal_sender.py::RenewalSenderTests.test_optional_preparation_failure_keeps_old_valid_admission_and_context`; `test_watching_local_source_bundle_installs_due_generation_without_sdk_side_reader`; `test_partial_cli_opt_in_never_initializes_a_second_broker_reader` |
| Source claims ต้องอ้าง visible terms บัญชีถูกและ hashไม่หาย | `test_c22_official_source_packets.py::OfficialSourcePacketTests.test_hidden_or_other_account_terms_cannot_prove_standard_commission`; `test_source_content_hash_survives_into_policy_and_changes_its_bound_identity` |
| Unknown/raw secret error ไม่หลุด; finite causeยังอยู่ | `test_c22_renewal_runtime.py::RenewalRuntimeTests.test_wrapped_generation_failures_preserve_only_known_finite_cause`; `test_c22_runtime_error_contract.py` |

## ผลตรวจ

- Full suite: **1439 tests,257.987seconds,OK,skipped2**, exit0
  (`full-suite.log`). เพิ่ม65 tests: cost13/store17/source7/coordinator20/sender8
- Final focused integration/diagnostic/CLI:83PASS; related review52PASS
  (`review/recheck-related.log`, `review/final-focus.log`)
- Scoped Ruff PASS โดยคง existing `scripts/demo_runtime/cli.py:E402` bootstrap
  exception; raw Ruffพบ existing E402 จริง ไม่อ้างว่า cleanโดยไม่มี exception
- Release `selected-1c0453dcf92db05d`:87 payloads/89 archive members,
 78 Python compile/25 source bindings,ทุก hashตรง ไม่มี env/financialDB
 SHA256 `11a8792f05d453664cf33c00f1e0bbfc4c8451ce4f0491152ea9fa1b4eb66a00`
- ไม่มี configured/available static typechecker; compile/test ไม่ใช่ typecheck
  Coverage% ไม่ได้วัด

### Standards

Independent initial review พบ1hard finding: pointer rollback และ1heuristicเรื่อง
store-layout coupling. Rollback reproduced/fixed พร้อม durable lineage/intent;
historical loading ย้ายเข้า public store method. ยังใช้ internal validation helpers
ภายใน packageร่วมกัน เป็น maintainability trade-off ไม่ใช่ข้อพิสูจน์ gate bypass
Root final source/assertion review ไม่พบ hard finding เพิ่ม

### Spec

Independent initial review พบ2findings: stale-flat timestamp และ legacy reload
context loss; ทั้งคู่ reproduced/fixed. Cross-reviewพบ H3 wrong-account terms;
rootพบ missing legacy startup fileเพิ่ม จึงเพิ่ม negative controlsก่อนแก้
Final independent follow-up ถูก usage limit จึง **ไม่อ้าง independent final PASS**
Root final review +83focused/full suiteเป็นหลักฐานหลังแก้ แยกจาก initial review
AP/source evidence/VM activation/actual forward ยังไม่ใช่ spec completionทั้งหมด

## VM/AP และหลักฐานจริงที่ยังขาด

| เวลา observation | ข้อเท็จจริง | ขอบเขตข้อสรุป |
|---|---|---|
| 27Oct18:34–18:38UTC /28Oct01:34–01:38Thai | AP loopกลับหลัง18:00:12; reconnect median16.842s; lost→enabled median8.741s;1066/1066 permission failuresตรง133disconnect intervals | ยืนยัน proximate mechanism; peer role/quality และ deeper triggerยัง UNKNOWN |
| เทียบ12:00กับ18:00 scan | 12:00ไม่ loop แต่18:00loop | หักล้างว่า scanทุกครั้งเป็นสาเหตุเพียงตัวเดียว; ไม่ใช่ fix |
| 28Oct00:56:20UTC /07:56Thai | Old9cfc, macro_latest_h4_incomplete, activefalse/haltfalse/outbox0; APเงียบตั้งแต่midnightประมาณ56นาที | ช่วงดีขึ้นเองไม่ใช่ before/afterfix หรือครบ24ชั่วโมง |
| 28Oct06:55:04UTC /13:55Thai | Old9cfc, sender116202/terminal116183 เริ่ม06:49:04UTC, NRestarts0; WAITduplicate_bar | PIDเปลี่ยนจากก่อนหน้าโดยภายนอกงานนี้; NRestarts0ไม่พิสูจน์ว่าไม่มี manualrestart |
| 28Oct07:04:07UTC /14:04Thai หลัง staging | Old9cfc/PID116202, execute=true, WAITduplicate_bar, observedpositions0; policy hashเดิม | ไม่มี service activation โดยงานนี้; cachedflatไม่ใช่ fresh broker noorders proofสำหรับ cutover |

Cost policy hashยังเป็น
`247cf2a51d96beb5c805aba2daba9e9c45d49cbff5645514e76811c5fd1babd0`;
expiry1Nov2026 13:25:18UTC /20:25:18Thai ไม่ต่ออายุหรือแตะ reviewed_utc
สอง FULL SELL refusals27Oct08:15/08:30UTCเคยแยกถึง live-spec mismatch แต่ exact
fieldเก่าไม่ถูกเก็บ จึงยังย้อนพิสูจน์ fieldไม่ได้ ไม่เดาค่าหรือปล่อย mismatchผ่าน

Official source capturesจริง3หน้า HTTP200 เก็บ27Oct18:36UTC; packetตรวจ18:39:50UTC
เป็น **DEFERRED tariff/source_claims_missing**. Raw HTMLไม่มี clauseที่ parserต้องใช้
ไม่แทนด้วย fixture/web-renderข้อความคนละชุด ไม่อ้าง Standard fee/Swap-Free entitlement
ใหม่ และไม่ถือว่า missing=zero. Published modelยัง COST_INCONCLUSIVE

VM prep มีเฉพาะ extracted `selected-7e55d89979d50b0d` ใน private preparation
directory และ consistent SQLite backupจาก source read-only; quick_checkok,
audit105354/kv12/events0/deliveries0. Backup SHA256
`aff5c8c0ab23f9c647a086e8be450bdc348d1a290a21503b1be1cf6a06d1c535`.
ดาวน์โหลด124248064bytesครบ, SHAตรง และ local SQLite backup→restore round trip
ผ่าน quick_check/counts/identity/max-audit/outboxเทียบ snapshotต้นทาง
SCPครั้งแรก timeout240วินาที เก็บ partialไว้; resumeผ่าน compressed read-only SSH
หลังตรวจ prefix hash ไม่รัน remote staging/backupซ้ำ และไม่ restoreลง VM
ไม่ติดตั้ง units/review/grant, ไม่เปลี่ยน terminal/env/cost/journal, ไม่เรียก SDK
แพ็กเกจ1c0453ล่าสุดยัง local และต้อง review cutoverของรุ่นนั้นโดยตรง

## Remaining closure gates

1. Actual official tariff captureที่มี relevant terms และ dated scheduleครบ;
   ตรวจ same economic spec/costจากsenderจริง ห้ามเติมข้อเท็จจริงที่ยังไม่มี
2. [T01/#12](https://github.com/Piti9427/XAUUSD_Scalper/issues/12) explicit
   execution-time approvalสำหรับ concrete source-bound Demo cutover;
   fresh flat/noorders/noUNKNOWN/empty-outbox, backup/rollback,หนึ่งsender
   การยืนยัน Q1–Q9ไม่ใช่การสร้าง machine grantหรือapproved_utc
3. AP controlled one-factor maintenanceที่อนุมัติแยก งบพักรวม<=15นาทีต่อรอบ;
   reproduceก่อน/หลัง,1ชั่วโมงrepeatและรวม24ชั่วโมงรวมrollover; ไม่เพิ่มเวลารอก่อนเทรด
4. Native signal→fill→BE→close,held-midnight/restart และ actual charge/slippage
   proofต่อเนื่องหลัง rollout; ไม่มี signalให้คง NOT_OBSERVED ไม่ force order
5. External channel/off-VM observerยัง OFFตามowner; VMดับทั้งเครื่องจึงไม่มี
   external delivery assuranceจาก local watchdogอย่างเดียว

ผลย้อนหลัง26b8ไม่กลายเป็นผล forwardโดยอัตโนมัติ งานนี้รักษา native logic และทำ
operational failuresตรวจสอบได้ ไม่ได้ยืนยันว่าจะได้กำไรรายวันหรือเท่า backtest
