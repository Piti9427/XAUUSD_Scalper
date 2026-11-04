# Pure B1 target test plan

1. Add synthetic M15 tests for Donchian exclusion, RSI and EMA gates, ATR/levels, invalid UTC data, and causal prefix invariance.
2. Implement pure target detection in `scripts/strategy.py` while retaining legacy class under its existing name.
3. Add new target replay caller using saved baseline/ticks and existing `Replay` execution engine. Verify output provenance and results.
4. Review target metrics against archived +342% before connecting runner to order execution.

## 2026-09-29 Pure B1 Shadow test plan

1. Test closed-M15 conversion rejects RangeIndex/duplicate/stale data and matches reference indicator signal on deterministic bars.
2. Test pure decision through public seam for fixed 0.01/10% cost cap, quote age, single position/pending, day-start 40%, missing policy and tick rounding.
3. Test injected fake MT5 cycle to JSONL, restart/dedupe behavior, account mismatch, and zero order/notification calls.
4. Test bounded M15/tick capture manifest/hash and comparison to reference; run focused files, then full suite once.

## 2026-10-04 Reward156 paired tuning

# Verification plan
- test_swap_changes_next_risk_admission: overnight debit changes subsequent cap admission.
- test_swap_triple_day_and_weekend_gap: explicit research calendar convention, entry/exit boundaries.
- test_default_replay_unchanged: disabled swap matches original output exactly.
- test_h4_closed_boundary_and_future_invariance: no unfinished H4/future leakage.
- test_h4_incomplete_bucket_and_warmup: fail closed; span200 cannot admit with150bars.
- test_contracts_share_environment_but_keep_signals_and_exits: same tape/costs, differing detector and protection.
- test_comparison_rejects_loss_and_missing_metrics: no negative profit winner or null RR qualification.
- test_risk_blocked_days_require_all_signals_and_no_position: distinguish no-signal/mixed rejection days.
Run narrow tests, then repository unittest discovery. Review assertions and complete status artifact.

## Profit/survival v2 test map
- Owner policy45%/$50/-$20, undefinedRR, trade/risk/terminal/survival: test_policy_boundaries_and_undefined_rr.
- <=27onefactor/seed, <=4combinations, dedup/risk invariants: test_finite_catalog_single_factor_and_dedup.
- Frozen detector and archived oscillator parity, future invariance: test_frozen_default_and_archived_seed_parity.
- New cooldown2 interface: test_cooldown_two_bars_is_supported; execution test to verify elapsed boundary.
- Full-result repeat and altered-result rejection: test_checkpoint_integrity_repeat_and_corruption.
- Source/config/input resume drift: test_config_and_source_drift_rejected.
- Stable ranking and holdout locked before price reads: test_deterministic_rank_and_holdout_requires_lock.
- Existing closedH4/swap equity-path/cost-inclusive cap/directional exits/BE tests remain required; run narrow then full suite after changes.
- Fresh/resumed actual replay result matrix JSON seam: test_fresh_and_resumed_replay_matrix_serializes_native_boolean_gates (red reproduced campaign failure; nativebool fix preserves policy).
- BE price-zero plus swap loss counted before circuit admission/day reset: test_break_even_swap_loss_counts_for_daily_circuit_before_next_admission.

## C22 frequency campaign (2026-10-06)

- Adapter baseline full-frame/rules parity; BUY EMA real signal change; strict
  keys/domains; future invariance and distinct H4 unavailable diagnostics.
- Policy tests: both views/all hard gates, full-month denominator including zeros
  and warmup, partial separation, entry UTC vs exit cash attribution, no double
  spread cost and separate swap credit/debit.
- Store tests: protocol/input/result binding; pending commit recovery; unrecognized
  artifacts; process lock. Search integration: actual replay cells, immutable
  rounds, bounded partial/resume and full-result repeats, missing swap blocks.
- Existing canonical tests: midnight reset, triple/weekend rollover, BE negative
  after swap, tick floating DD and fixed0.01/risk. Economic verification uses
  frozen full-result parity then current input baseline/top5 fresh repeats.
- Final focused tests, lint/format and repository unittest discover. No typecheck
  command configured in Makefile/pyproject; report this explicitly.

## SMC challenger implementation (2026-10-08)

# Sequential test slices

1. `test_smc_challenger.py`: reject naive/unordered/bad OHLC; prefix/future mutation and real BUY/SELL setup; session coverage, pivot/CHoCH/FVG publication, invalidation/TTL/dedup and chunk append.
2. `test_smc_challenger_adapter.py`: public replay with literal expected SELL Ask-side rounded stop/risk, swap debit/equity/circuits, late/no quote/busy, missing swap/cost metadata and unsupported volume.
3. `test_smc_challenger_campaign.py`: fixture input bundles, both swap views + C22 comparison, complete-result repeat, resume and hash drift, invalid output path, frozen parity prerequisite.
4. Regression, lint/syntax, full suite; two-axis code review; exact test evidence and limitations in status report. Economic smoke artifacts under runs only; no current profitability/selection claim.

## C22 runtime corrections (2026-10-14)

1. Re-run existing invariant witness to RED; inspect real pending/cash branches
   with pdb before modifying knobs. Store breadcrumbs under ignored `runs/`.
2. Add `tests/test_c22h4_safety_recovery.py` using public `cycle()` and existing
   CandidateBroker. Cover partial completion/restart, pending orders, incomplete
   and mismatched ledger, definitive rejection, ambiguous response, legacy
   pending compatibility, and immediate/late cash attribution. Run RED first.
3. Persist additive safety-close attempt metadata before send. Reconcile fresh
   residual position, complete ledger and no pending orders before retrying only
   confirmed partial completion. Preserve UNKNOWN for ambiguous/legacy requests.
   Use complete closing ledger for SAFETY_CLOSED result/event.
4. Add status regressions before status changes. Keep broker access absent;
   report execution mode independently of cost validation and heartbeat.
5. Run narrow tests during fixes, focused integration checks, then one repository
   unit suite. Verify source pins and final scoped diff. Author compact fix record
   with exact test names and remaining owner decisions; do not deploy/restart.

Daily-baseline contract change is excluded pending owner selection. Durable
per-bar funnel is a separate observability follow-up; no journal migration here.


## Native frequency research (2026-10-14)

Vertical slices: (1) host/native guard+fixed-risk RED→GREEN, (2) pullback mirrored causal bars, (3) session completeness/retest/expiry/consume, (4) C22 rollingRSI/EMA/H4 differential, (5) monthly accounting and execution state, (6) native adapter and compile, (7) scoped lint/types, two-axis review, full suite once, task-only commit. Exact test names recorded in final report. Native compile/run unavailability reported as blocker, never replaced with host success claims.


## Shared native detector economic cases (2026-10-14)

RED→GREEN public replay fee+swap fixture, missing metadata; monthly fee cash attribution and negative selection controls. Build actual C++ native detector bridge, verify real M15 and C22 against frozen Python; hash source/input. Run all10 cells, cash/lot/risk/swap audit, fresh all10 full-result repeats. Rank only both-view strict improvements; NO_IMPROVEMENT if none. Report all candidates/diagnostic champion and costs/execution differences; focused/full tests and assertion review, no native UI/commit escalation inferred.


Economic completion:7adapter/checkpoint regressions mapped in final report;
report-seam bankruptcy bug reproduced thenfixed without frozenengine edits.
Incomplete resume replaced by explicit refusal/freshdirectory; fullrepeat and
hashproof mandatory. All10cells+10repeats+independentaudit completed,strict
NO_IMPROVEMENT. Fullsuite962OKskip2; currentDemounchanged.

## Oracle attended preparation (2026-10-24)

# Verification plan

1. Cost review: exact input hashes, explicit confirmations, fresh capture,
   unchanged spec, complete dated calendar, historical charges, no overwrite.
2. Feed review: explicit owner decision bound to original parity/account/cohort;
   original strict default and every other readiness gate remain enforced.
3. Integration: preparation forwards optional review explicitly; dry run on actual
   VM restores shadow and produces blocked market-open prerequisites.
4. Run focused tests, Demo suite, full discovery, compile/deps/lint and changed
   file format checks. Verify deployment hashes and final read-only VM state.
5. Attended console: distinguish closed-market admission from stale/unknown
   protection, halt, service ownership and SSH loss. Prove off-VM restoration live.
# Selected C22 adapter — 2026-10-25

New-package plan: strategy/nativeRules+causalcache tests; public fake-broker
cycle tests for BUY/SELL BE, shadow/no sends, daily2 and persisted firstquote
cooldown; CLI reject send before newreadiness and preserve olddefault. Run
focused files during TDD, Pyright/Ruff, oldDemo regressions and full suite once
after final review. Actual VM shadow observation remains distinct from synthetic
cycle validation and historical parity. Never turn missing cost/feed evidence
into a test pass.


## Selected26b8 verdict fixes (2026-10-26)

1. Reproduce archived four public-cycle failures, retain ledger and pre-edit hashes. Offline pdb then source trace; disproof controls before implementation.
2. Lifecycle agent owns runner/lifecycle and new lifecycle recovery tests. Root owns broker baseline integration/boundary module/journal audit key/CLI scheduling/new boundary tests. Boot agent owns persistent terminal/units/boot helper/builder + packaging tests. Health agent owns independent watchdog + tests; no external sends until destination evidence.
3. Acceptance-to-test mapping will be exact names in final status after implementation. Cover both sides, persisted restart/UNKNOWN, stale/missing/wrong identity/malformed boundary proof, UTC edge scheduling, boot journal binding and service drift, notification delivery retry/dedupe and stopped heartbeat.
4. Run targeted RED/GREEN per seam, scoped lint/type checks, frozen101 source audit, full repository suite once, independent diff/test-gap review. Build immutable bundle, restore-check backup, bind current exact cohort using existing owner Demo approval and unchanged cost policy; cut over only after actual flat/empty unknown/exposure checks. Preserve prior evidence/releases.
5. Update CORE strategy operational/risk evidence description, ops runbook and synthesized report; record actual deployment versus locally verified preparation and any missing external evidence.


## C22 research risk closure (2026-10-26)

1. Root owns campaign/control/report/schema+spec/docs; implementation agent owns newpolicy+newreplay; testsagent owns two testfiles; independentauditagent owns verifier. No shared-file editing collisions.
2. Freeze12profiles plus6views/newsource/input/parentcells/cost/window before economicresults. Newloop is an explicit narrowly changed copy of frozen engine; no monkeypatch of frozen sources/Rules. Offparity gates all overlay economics.
3. Tests red/green at purepolicy+publicreplay seams cover checklist in research.md. Map exact names in status.md after qualityreview. Run scopedtests/lint then fullrepository once, only repeat after material changes/failures.
4. Resumable hashed cell campaign workers2, sameinputmaps/costswap eachworker; no midcellresume claim. Independentcheckall72cells+freshrepeats+fulltickDD; account minimum/recovery/streak/severity/stoppedintervals remainvisible.
5. Buildpartial/finalMatrix from raw evidence, include original26b8/oldDemo originalresearch/row20/latest references where available; neverforcewinner/profitDDgates. UpdateCORE/report. NativeDemo untouched.


## C22 root-cause closure first (2026-10-27)

1. Research first: rootcapturesexistingartifacts; permissionagent reads native/logswithoutSDK; H4agent checks canonicalgapand officialschedule; policyagent tracesindefiniteblockers. No VM mutations.
2. R1→sanitizedevidence+reproledger+humanrootcauseMatrix. R2→test_disconnected_cycle_reports_specific_flags_and_recovers_without_resend, test_each_permission_denial_preserves_gate_and_whitelists_evidence, test_identity_diagnostics_are_reset_before_next_cycle, test_active_close_read_does_not_require_trading_permission. Names maybespecializedduringphase with exactfinalmapping. Writebehavioraltests andretainRED beforeminimalproductiondiagnosticaddition.
3. R3→actual11of16gap/04Zcausalrecovery exactcase onceagentconfirmsmissingcoverage. R4→costdrift/refreshedpolicywithoutmatchingreview andactiveprotection intersection onceagentconfirmsmissingcoverage. Agents awaitGO beforeeditingtestfiles. No editingfrozenresearch orselectedsourcepins.
4. Rootownsbroker/runnerdiagnostics+identitytests; H4agent owns only newgaptests; policyagent owns only newpolicyinteractiontests. Keep phases sequentialpertestfile; productionedits rootonly.
5. Run narrowtargets duringrepair; root/independentreviewer readassertions againstpublicseams withnegativecontrols. Reviewfinaldeltaagainstbeforecopies. Onefullrepo unittestdiscover afterallnewtests/diagnosticchanges pass; appropriateRuff/compileandpinscheck. No falsecoverageclaimifnocoveragemeasurement.
6. R5/R6→appendstatuswithactualnames/commands/testcounts and confirmed/unknownrootcauseboundaries. FinalRequirement|Evidencequotesuserrequest and exacttests. Anyserverdiagnosticrollout is separateconcretereview, notinferredfromrootcause-firstrequest.

Root-cause phase exactH4mapping approvedbeforetestwrite: R3→test_rollover_sized_gap_drops_partial_m15_without_claiming_scheduled_closure, test_partial_rollover_h4_blocks_until_exact_next_complete_h4_close, test_future_complete_h4_does_not_backfill_unavailable_prior_decisions in tests/demo/test_c22_h4_gap_rootcause.py. NativepartialH4semantics preserved; sessionnormalitynotfabricated.

Root-cause phase policytestmapping approvedbeforewrite: R4/R5→test_accepted_review_exact_expiry_blocks_even_after_successful_restart, test_policy_calendar_missing_masks_daily_limit_until_policy_restored, test_resolved_unknown_latched_halt_still_blocks_fresh_entry_after_restart in tests/demo/test_c22_rootcause_policy_interactions.py. Watchdogflapping/flatstaleblindspot reproduceasignoredrunsproof rather thanpinningdefectacceptanceorchoosingnewgracethreshold. No policybehaviorchanges.

## 2026-10-27 Selected26b8 operability implementation plan
1. Snapshot bounded files and frozen pins; reproduce public watchdog failures before mutation.
2. Agent watchdog owns scripts/ops/c22_selected_watchdog.py and its tests: use existing grace period for stable recovery and stale wait escalation, no financial writes/sends.
3. Agent review owns scripts/c22_selected/execution.py and new review diagnostics tests: preserve exception text/gates, expose finite safe causes and read-only inspection with no approval write.
4. Root integrates runner read-only availability through existing captured data; specific reasons, expires/due, operator/resume visibility, no extra broker reads or financial gates.
5. Independent review, focused regressions then full suite once, frozen101 parity and source verification. Produce bounded issue closure report and deployable release only after validation; VM changes require concrete source/review-compatible rollout.

Operability completion mapping: R1=WatchdogContinuityTests alternating/rotating/exact stable recovery; R2=day-old/missing/invalid age witnesses; R3=ReviewDiagnosticsTests read-only armed inspection/exact expiry and40-case prior/new write parity; R4=EntryAvailabilityTests stacked connection/review/halt, conditional cooldown/day/arm/newbar, activeBE with revokedreview; R5=63focused/1312full/sourceconfig/archive and101parent+110risk pins. Actual VM cutover/AP comparison remain separate; no automatic renewal, native economic rule or delivery authorization inferred.


##2026-10-27 debug-mantra closure plan

1. Re-run saved public witnesses into NEW run directory; eachdebugagent creates deterministicrepro beforeedit. Usepdb beforeknobs thenrank3–5hypotheses anddisprooffirst. Retain ledgerperrun.
2. R1 costs.py/admission.py→new test_c22_cost_diagnostics.py: exactfieldvariation, missing/nonfinite/specgetter, policytime/hash failures, noSDKadditionalcalls, unchangedlegacytuplepredicate and canonicalrejection.
3. R2 selectedrunner/strategy→new test_c22_optional_output_continuity.py: export/checkpoint faults afterfill/manage/BE/close/restart, validcachepreservation, financialjournalfailurestillraises.
4. R3/R4 sharedrunner/broker/status→new test_c22_runtime_error_contract.py: origin-separated exceptions, correlatedsafecontext, detailedknownresumes, unknownsafe fallback and manager/loss/daystate unaffected.
5. R5/R6 sharedrunner/CLI/journal→public faultprobes fordurableoperationaldelivery/checkpoint, startup/reload/cleanup failures and independentstderr fallback. Reusenarrowhelpers; nosecondengine orfinancialschema rewrite.
6. Coordinate disjointfileownership, source-bound selectedconfig onlyafterallcodefinished. Run focusedslices thenonefullunittestsuite. Review generatedassertions/diff and frozen/configpins. Write .testagent/status.md + synthesizeddebugreport with requirement→exacttestname and residualVM/AP/cost/forwardlimits. Prepare concrete localrelease if checks pass; do not deploy.


##2026-10-28 confirmed closure implementation
User: “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด”. Scope: native trade decisions unchanged; R1 canonical refusal detail→public-cycle tests; R2 opt-in same-sender evidence request→fresh flat epoch/cash/sanitized packet tests and optional failure continuity; R3 offline grant/renewal planner→Q1/Q4/Q5/Q7/Q8 negative and boundary tests; R4 comprehensive source-cited native conditions and issue residual map; R5 targeted/full tests + immutable source-bound release, no VM deployment or runtime auto-renew. unittest fixtures from selected runner/costs; no additional dependencies. Optional test generator/pairing/gap tools not exposed; manual pairing + independent review. Reproduction/debugger/disproof ledger for actual bugs; missing feature RED labeled capability, not historical failure.


##2026-10-28 root-cause closure continuation
User: “continue until close all root cuse”. R1 durablecostgeneration/incidentcontinuity via existingJournalpublicseam;R2 immutablecoherentgenerationstore+crash/restart;R3 genuineofficial-sourcepacketdatedhash/contentclaims,notentitlement;R4 opt-inexisting-senderintegration/noadditionalSDK/ownedmanageruninterrupted/defaultoff;R5 freshread-onlyVM/APforensics and actualrootcauserepro;R6 fulltests/typechecks/Standards+Specreview/commitboundedcurrentbranch. Nativeparameters/frozen101/110pins unchanged; actualVMcutover/externalalerts/compoundingnotimplied. deterministicunittestverticals,root+agentassertionreview;exactacceptance mapsinreport. No newseamgrilling: interfaces/gates alreadyacceptedQ1-Q9+tickets. Unavailableoptionaltestgeneratortools manualpairing.

## C22 T20 joint-addon test plan —28October2026

Public seams joint_frame/attribute_joint/daily_mtm plus independent_selector/
audit_daily. Verify causal prior48/EMA/H4 and disablednativeidentity; native
priority/no fallback; oneaccount/heldaddonblocks referencecore/cashcontributions;
BUYbid/SELLask/signedswap/fee/daypartial/stale/flatnoquote; independent day-vector
reconciliation and tampered-net rejection.13focusedtests currentlyPASS; realbar
signalparity preflight before economics. Freeze allnewsource/catalog/input pins
before12primary cells; audit all12full-tick paths and6fresh selected repeats.
Run fullsuiteonce after final code; record root-vs-independentreview limits.


## C22 session/feed continuation —29October2026

Feed tests: pairedcachehash/reusedlabel; identity/hash/rows/tornpair; future/naive/duplicate bars; during-read change; everyUTCday/excluded/unknownmoney; publicCLI/verificationtamper. Add explicit fields/config/symbol/aggregation/nonfinite negative controls and original-artifact immutability. New companion only, no financial calculation or VMchange; source-bound verify existing batch against consistent backup. Focused final tests then one fullsuite after all new source stable. Root final review after agentquota; do not claim independent final review.


## 2026-10-30 Attended maintenance C-v2 local implementation

RED public interface first. Implement typed contract and readonly journal proof; separate durable operation/effect receipts; orchestrate three closed action families through recording-only effects. Add behavioral cases for all requirement intersections; assert independent SQL and host call order/counts. Run narrow suite per slice, compile/lint, full repository suite once after local review. No commit or VM activity.


## 2026-10-30 Independent C-v2 corrections

Add public-seam RED regressions for all6findings before fixes; then correct typed identity and host flags, atomic operational transaction, fresh exclusion proofs and bounded conditional recovery retries. Every irreversible work action remains once-attempt; retain primary/cleanup/recovery evidence and attempts. Re-run narrow until green, await independent re-review, then freeze allapplication source and run full suite once after final corrections. No financial policy/VM/SDKreal/GitHub/commit change.

## 30 October approved continuation regression map

#23 fast/slow actual account interval: test_c22_boundary_account_timing.py.
Held Selected management, 197vs150 restart, public/persistent reason, new-cycle
reset and no additional calls: test_held_selected_position_keeps_management_and_uses_only_genuine_restart_proof.
Closure validity: test_exit_day_validity_is_not_relabelled_by_current_cycle_diagnostics.
Existing diagnostics reset now asserts request/null return and no old fields;
rollback/direct parity pins observation clock and keeps full state/event equality.
H4: producer16+independent verifier18synthetic cases before source freeze.
Keep first failedfull1615/2fixtures; final full only after all327app sources stable.

## Journal initialization diagnostic candidate (isolated, pending owner review)

Scope: original-source journal unchanged; prepare reviewed candidate+patch only.
Full disk run showed all BEGIN IMMEDIATE OperationalErrors relabelled writer.
Mock validation: structured BUSY/LOCKED extended codes retain legacy refusal;
FULL/IOERR/CANTOPEN/unknown/missing code retain original exception, FAULT and
sanitized metadata/hints. Initialization and cleanup failures remain fail closed;
no broker initialize/send. Preserve every existing SQL literal/connection flags.
Tests use mock connections or in-memory SQLite; no temp financial DB or VM.
Review source-binding impact and explicit owner boundary before applying patch.
