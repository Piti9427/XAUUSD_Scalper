# Selected26b8 — debug-mantra verdict closure

เริ่ม27ต.ค.2026; สรุป28ต.ค.2026ตามเวลาไทย

Status: LOCAL_VERIFIED_NOT_DEPLOYED. แก้เฉพาะ local; VM, broker orders, cost attestation และ financial rules ไม่ถูกเปลี่ยน

## ผลที่แก้และสาเหตุ

| Issue | Root cause ที่ reproduce ได้ | Local correction | ยังไม่ใช่หลักฐานอะไร |
|---|---|---|---|
| LIVE-01 cost/spec refusal | no-spec review ผ่าน แต่ exact live-spec comparison คืนboolean โดยทิ้ง field; หลายสาเหตุถูกรวมเป็น invalid_or_stale | เพิ่ม optional diagnostic output และ CostPolicyError carrying safe stage/code/field/expected/observed; raw reason/tuple/predicate เดิม | ไม่รู้ field ที่ต่างจริงในสอง SELL ของVM27ต.ค.; ไม่อนุมัติต้นทุนใหม่ |
| LOG-01 export exit after fill | selected runner เรียก optional export หลัง financial cycle โดยไม่มี isolation | catch เฉพาะ export/checkpoint หลัง super().cycle; supplemental failure audit; retryตามcycle; คงmanagerและvalidcacheเมื่อexportล้ม | ไม่ได้พิสูจน์ว่าเคยเกิดOSErrorนี้บนVM |
| LOG-02 exception origin collapse | shared catch เก็บเพียง exception class; ValueError เก็บข้อความ arbitrary | failure recordมีstage, bounded cause types/frame refs, correlation, evidence/ref และresume; rawmessageรับเฉพาะfixedcodes | ไม่อ้างว่ารู้ deepest root cause ของSDK/APทุกเหตุการณ์ |
| LOG-03 resume collapse | availability มีregistryไม่ครบ จึงทิ้ง concrete codeเป็นruntime_blocked | ใช้registryเดียว; history_unknown/first_quote_unknownและfixedcodesอื่นมีspecificresume | resume hintไม่ใช่permissionหรือสัญญาว่าnextentryผ่าน |
| LOG-04 delivery marker missing | persist financial resultก่อนnotify แล้วเติมpending_retryเฉพาะreturneddict | supplemental OPERATIONAL_FAILURE audit + observational last_result; failureไม่เข้าวง outboxซ้ำ | durableoutboxไม่ใช่deliveryreceipt; externaldeliveryยังOFF |
| LOG-05 checkpoint detail stale | checkpointกลืนexceptionและเปลี่ยนinternalstatusหลังresultpersistแล้ว | return caughtfailureให้optionalboundary; samecycle status/cause durable; retryคืนactual seed provenance | CSV/metaยังเป็นสองhash-boundfiles; tornpairต้องถูกloaderปฏิเสธ |
| CLI cleanup/startup | closeexceptionกลบprimaryและข้ามshutdown; read/reload errorsไม่แยกstage | structuredstartup/reloadfailures; close/shutdownแยกguard; cleanupfaultทำexitnonzeroโดยเก็บprimaryresult | ไม่ใช่VMdeploymentหรือbrokerreconnectfix |

## ทำตาม4ขั้นอย่างไร

1. **Reproduce:** public SelectedDemoRunner.cycle + synthetic SelectedBroker และ temporary SQLite; frozen awareUTC; ไม่มีMT5connection/realorders เริ่มจากsaved7witnessesและเพิ่มREDregressions
2. **Trace:** pdbหยุดที่sharedcatch, exportหลังFILLED/active/send1 และcostspeccomparison ก่อนปรับknobs; source traceผ่านcallerจริงและเก็บstageที่existingSDKreads ไม่มีreaderเพิ่ม
3. **Falsify:** healthy/no-export/equal-spec/no-spec controls; isolatedexpired/hashdrift/specdrift; lifecycleยังFILLEDเมื่อnotifyล้ม; privateValueErrorและcleanupoverrideเป็นcounterexamples ผลcostpredicate differential219กรณีตรงbaselineทั้งหมด
4. **Breadcrumbs:** ทุกrunมีinput/change/outcome/hypothesis dispositionใน [ledger](../../runs/c22-debug-closure-2026-10-27/LEDGER.md) พร้อมcost/optional/independentreview ledgers ไม่เขียนทับผลก่อนแก้

ข้อผิดพลาดระหว่างdebugเก็บไว้ด้วย: debugger display commandแรกใช้walk_tb tupleผิดแล้วแก้; ownedreloadtestแรกไม่ได้freezeCLIclockจึงเจอquote-stale แก้fixtureclockโดยไม่เปลี่ยนproductiontiminggate; reviewerพบcost_evidence_source_missingถูกsanitizerทิ้ง แก้พร้อมproducer→recordregression

## Requirement → evidence

| Requirement จากเจ้าของ / ขอบเขต | Exact regression หรือหลักฐาน |
|---|---|
| “ทุกอย่างถ้ามี error log ต้องมีเหตุผลบอกเสมอที่มาที่ไปของ issue” — cost | `CostDiagnosticsTests.test_public_admission_keeps_raw_reason_and_carries_same_read_spec_detail`; `test_exact_spec_field_failure_preserves_legacy_refusal_and_safe_numeric_facts` |
| ข้อความเดียวกัน — SDK origin/privacy | `RuntimeErrorContractTests.test_distinct_sdk_origins_keep_legacy_reason_and_safe_trace`; `test_unknown_sdk_valueerror_does_not_leak_message_or_become_known_gate`; `test_chained_causes_are_bounded_and_exclude_messages_and_locals` |
| ข้อความเดียวกัน — durable delivery/resume | `test_failed_notification_is_durable_without_recursive_outbox_event`; `test_concrete_history_and_first_quote_causes_keep_specific_resume`; `test_cost_diagnostic_codes_survive_shared_failure_record` |
| “เงื่อนไขต่าง ๆ ตอนนี้มันปิดช่องโหว่ไปหมดหรือยัง” — optional manager continuity | `test_export_fault_after_fill_retains_manager_and_no_resend_across_restart`; `test_export_fault_after_be_preserves_confirmed_protection_and_broker_close`; `test_financial_journal_failure_is_not_swallowed_as_optional_output_failure` |
| Checkpoint/cause/retry | `test_checkpoint_fault_is_durable_same_cycle_and_retry_restores_seed_provenance`; `test_failed_export_skips_checkpoint_and_preserves_previous_valid_cache` |
| Startup/reload/cleanup | `CliErrorContractTests.test_malformed_startup_config_has_safe_decode_cause_before_sdk`; `test_policy_reload_fault_still_runs_owned_manager_and_persists_cause`; `test_cleanup_failure_preserves_primary_error_and_still_shuts_down`; `test_shutdown_failure_sets_failure_exit_without_erasing_successful_cycle` |
| Financial fail-closed / independent sink | `test_financial_journal_failure_still_propagates_without_send`; `test_diagnostic_persistence_failure_uses_independent_safe_fallback` |
| “เพื่อให้สอดคล้องกับผล backtest” — native contract preservation |101parent+110riskpinszero drift; selectednativefunctionAST unchanged; confignonbindingfields unchanged; [preservation.json](../../runs/c22-debug-closure-2026-10-27/preservation.json) ไม่ใช่futureprofitguarantee |

Test sources: [runtime contract](../../tests/demo/test_c22_runtime_error_contract.py), [optional outputs](../../tests/demo/test_c22_optional_output_continuity.py), [cost diagnostics](../../tests/demo/test_c22_cost_diagnostics.py)

## Verification

- Costfocused11tests PASS1.134s; earlier43relatedregressions PASS14.875s
- Costbaseline differential219cases: noaccept/status/exception-class mismatch ทั้งdiagnosticsเปิด/ปิด
- Optional+existingcache/history35tests PASS17.490s
- Combinedfocused63tests PASS47.084s; finalruntime/release15tests PASS9.203s
- Independentreview5tests PASS1.157s; ไม่มีmaterialfindingคงค้างหลังแก้sanitizercode
- Boot/releasefixture9tests PASS0.048s หลังเติมrequireddependency โดยไม่ลดpackagervalidation
- Task-scoped whitespace/AST checks PASS; repo-wide diff checkมีpreexistingCRLFในdata/c22h4-demo-trades.md ซึ่งไม่แก้ในงานนี้
- Fullsuite: **1,343tests PASS226.676s, skipped2, exit0**; first fullrun226.517s had2missing-dependencyfixtureerrors, retained and corrected before finalrun
- Frozen101/110 sourcepins unchanged; selectedconfig binds20sources includingnewdiagnostics; nativeRules26b8bcd69e043653/fixed0.01/risk10%/daily10%loss2/cooldown30min/SLTPBE unchanged
- Packageprepared `selected-21ebb6f4bded8a67`,83files/72Pythoncompiled/20bindingsverified; archiveSHA256 `ec2d36ee65977e0ba04710c74f34a7fa5bd1c23933a9912134a329dc85c4a143`; execution_authorized=false, deployed=false ไม่มีenv/financialDBในarchive

## ขอบเขตที่ยังเปิด

- Exactspecfield/valueจากสองSELLบนoldVMยังไม่เคยcapture ตัวเลขในtestsเป็นsyntheticfixtures ต้องดูdiagnosticจากsenderเดิมเมื่อrolloutได้รับอนุมัติและมีfreshfailure
- APoptimizer deepesttriggerและcontrolledrepair/24hรวมrolloverยังไม่ปิด การแก้exception/logไม่ใช่การแก้network/AP
- Costrenewal/standingauthorityยังเป็นdraft ไม่ได้activate ไม่เปลี่ยนreviewed_utc/policyexpiryหรือยอมรับcostdrift
- Nativeforward fill→SLTP→BEเมื่อถึงtrigger→close→actualnetledgerยังต้องพิสูจน์ แยกmanualdeals/cashflowและcohort การปิดsoftwarebugsไม่รับประกันกำไรตามbacktest
- ResearchDD40ยังเป็นselectiongate ไม่ได้เพิ่มliveDDbreaker/netBE/MMrulesหรือเพิ่มlot งานนั้นต้องcandidateแยกตามข้อกำหนดเดิม
- Runtimeยังไม่ได้deploy รอบนี้ไม่มีVMwrite/SDKconnection/servicechange/order/externalnotification/ticketpublication

## Artifacts

- [Experiment ledger](../../runs/c22-debug-closure-2026-10-27/LEDGER.md)
- [Task-only diff from dirty baseline](../../runs/c22-debug-closure-2026-10-27/task-delta.diff)
- [Independent review](../../runs/c22-debug-closure-2026-10-27/error-review/FINAL_REVIEW.md)
- [Cost predicate differential](../../runs/c22-debug-closure-2026-10-27/cost/predicate-differential.json)
- [Release verification](../../runs/c22-debug-closure-2026-10-27/release-verification.json)
- [Prepared archive](../../runs/c22-debug-closure-2026-10-27/staged-release/release.tar.gz)

Next: local verification complete. Source-boundreview/rollbackและowner-approvedrolloutเป็นงานแยก ก่อนเก็บfreshdiagnostic/nativeforwardต่อ ไม่ส่งstaleSELLหรือบังคับorderเพื่อเติมหลักฐาน
