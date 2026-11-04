# Pure B1 target refactor research

- Target: `scripts/strategy.py` pure M15 detection, new tick replay caller, then live runner only after replay review.
- Existing reference: `run_b1_breakdown.py` uses prior-30 Donchian, RSI14 EWM span14, EMA50 EWM span50, ATR14 simple rolling mean, strict RSI 30–70.
- Archived +342%: `scripts/research/b1_hybrid_six_month.py` uses `b1_final.reference_bars()` with Wilder RSI buy <=75 / sell >=25 and no EMA50. Preserve its source and outputs.
- Convention: `unittest`; `tests/test_strategy.py` covers legacy strategy, `tests/test_b1_hybrid_six_month.py` covers replay engine.
- Acceptance: deterministic target signals on completed UTC bars, strict thresholds, no lookahead, shared signal caller for replay, preserved old results, risk and cost accounting, no broker/notification side effects.

## Selected C22 adapter (2026-10-25)

Owner selects26b8 for shadow→Demo bot testing. Bounded new package
scripts/c22_selected; preserve all frozen research/currentDemo pins and existing
shared runtime changes. Accepted seams: strategy frame/geometry→public broker
cycle→CLI. Existing CandidateBroker/fake MT5 lifecycle fixtures provide broker
boundary injection. New tests cover native28Rules, BUY/SELL BE1R, daily2,
first-quote30minute negative-net cooldown across restart/UTC, no shadow sends,
ambiguous lifecycle, journal/cohort/source identity and execution-readiness gate.
Spec: specs/c22-selected-demo-adapter-2026-10-25.md. Test generation tooling
not separately available; bounded Research/Plan/Implement workflow runs inline.

## 2026-09-29 Pure B1 Shadow implementation

- Scope: read-only broker M15/tick capture, bar/index adapter, one shared Pure B1 decision, daily/exposure gates, append-only Shadow evidence.
- Pre-agreed seam from the approved plan: fake MT5 rates/ticks -> UTC adapter -> `pure_b1_bars` -> `check_fixed_lot_risk` -> JSONL; assert no `order_send` or Telegram.
- Existing helpers: `scripts/smc/broker_rates.py` returns RangeIndex; `scripts/strategy.py` requires UTC DatetimeIndex. `scripts/research/shadow_capture.py` captures bounded ticks with manifest. `scripts/ops/run_b1_d_wine.py` runs read-only scripts under Wine.
- Data contract: `CORE_STRATEGY.md`; archived input/source hashes in `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json`. Broker costs/fills remain unobserved.

## 2026-10-04 Reward156 paired tuning

# Reward156 paired tuning test research
Bounded sources: breakout_replay.py, new rollover model, new paired research harness.
Existing convention: unittest, synthetic UTC M15 and Bid/Ask arrays; no MT5 calls.
Requirements: identical data/account/costs for independent contracts; preserve trial30 and Reward156 logic; swap affects equity/admission; causal H4; reproducible outputs; unchanged defaults.
Existing tests: test_breakout_logic.py and test_reward156_strategy.py. Archived optional discovery helper exists; no installed generator agent available. Inline workflow.

## Profit/survival v2 (2026-10-04)
Focused extension targets: reward156_search policy/catalog/causal adapter, reward156_campaign checkpoints/rank/finalists, reward156_holdout pre-read lock; existing breakout replay covered by test_breakout_logic/test_reward156_tuning. New tests use deterministic UTC synthetic bars and temporary checkpoint directories. No external orders/notifiers in research imports.

## C22 frequency campaign (2026-10-06)

Bounded new research modules: c22_frequency adapter/policy/store/data/campaign.
Owner-preagreed TDD seams: adapter, qualification, monthly count, cost attribution,
resume. unittest deterministic UTC bar/tick fixtures, isolated temp outputs.
No optional generator agent installed; inline Research/Plan/Implement workflow.
Codegraph source lookup; existing breakout/Reward156 tests provide independent
canonical fill, BE, rollover, daily-state, fixed-lot and risk-cap regressions.
Spec/acceptance checklist: specs/c22-frequency-campaign.md. Existing Demo work
predates this task and stays excluded from its commit.

## SMC challenger implementation (2026-10-08)

# SMC challenger bounded test research

Scope: new signal, adapter and campaign modules only. Existing unittest/pandas/NumPy fixtures; no broker mocks inside economic logic. Public seams approved by owner instruction to implement the reviewed spec: causal frame, replay adapter, campaign CLI.

Acceptance checklist: UTC/coverage and causal session/pivot/CHoCH/FVG/retest timing; mirrored sides and setup expiry/dedup; quote-dependent SELL stop and cost-inclusive10% admission; mandatory modeled swap including calendar boundaries; full-result replay repeat, frozen comparator parity, manifests/resume/drift, output boundaries and descriptive status. Frozen C22/Trial30/pins unchanged. Full suite once at end.

Optional find-untested-sources, test-gap-analysis, assertion-quality tools/commands are unavailable (CLI/tool catalog checked); inline bounded discovery/quality review substitutes. No configured type checker in pyproject or available mypy/pyright command; syntax compilation and Ruff used, not claimed as type checking.

## C22 runtime corrections (2026-10-14)

Request: `$debug-mantra`, following C22 runtime scrutiny findings.

Scope: `Trial30DemoRunner` safety-close reconciliation/accounting and read-only
`scripts/ops/trial30_status.py` readiness reporting. Preserve C22/trial30 entry,
geometry, risk, daily baseline policy, frozen source pins, journal schema, and live
watcher state. Cost attestation is owner-reviewed; do not refresh its timestamp.

Existing conventions: unittest discovery under `tests`; public cycle fixtures in
`test_c22h4_demo.py` and `test_trial30_demo.py`; persistent temporary journals,
aware UTC clocks, broker mocks. No real MetaTrader5 initialization or sends.

Acceptance checklist:
- Confirmed partial safety close recovers only reconciled owned residual volume.
- Pending broker order or incomplete/mismatched ledger prevents resubmission.
- Timeout/placed/no response and legacy pending state never blindly retry.
- Restart retains request evidence; recovery emits no phantom FILLED event.
- Safety halt remains after closure; rejected close can be retried safely.
- Immediate and late safety closures use actual gross/cost/exit ledger values.
- Status separates execute mode from local cost readiness, even without signal.
- Default/explicit cost-policy source and expiry are visible without secrets.
- Existing source pins and C22/trial30 lifecycle/CLI behavior remain verified.

No named test-generation or gap-analysis tools are exposed in this environment;
the Research → Plan → Implement → assertion review workflow runs inline.


## Native frequency research (2026-10-14)

Native frequency research: MQL5 core + tester EA + no-order native/host harness. Owner-confirmed public signal/admission/order/report seams. Existing unittest, clang++ and bundled MetaEditor; no new dependency. Checklist: tester-only guard; complete UTC bars; causal pullback and retest/session consumption; C22 signal parity; fixed0.01/cost-inclusive10% cap; confirmed/ambiguous lifecycle; swap/commission attestation; monthly zero/partial/cash reports. Native economic evidence remains separate. Optional generator/gap/quality tools absent; inline bounded workflow.


## Shared native detector economic cases (2026-10-14)

Owner selected shared native MQL5 detector plus canonical tick execution. Five preregistered cases/two modeled swap+commission views. Native core/source pins unchanged. Existing canonical replay/SwapPolicy/audit reused; bound globals preserve native prepared geometry. Fixture risk2.6/fee0.4/triple swap−1.7022/net2.2978; absent swap blocks. No native Tester result label, no holdout, no Demo action.

## Oracle attended preparation (2026-10-24)

# Oracle final preparation, 2026-10-24

Bounded scope: explicit cost review helper, read-only readiness report and its
existing preparation command. No strategy, broker mutation or research pin change.

Owner requirement: “เราต้องการเตรียมให้พร้อมจนเหลือแค่ทดสอบเปิดใช้งานจริงตอนตลาดเปิดแล้วเท่านั้น”.
Owner decision: “เตรียม Demo trial บน feed นี้”, explicitly after shadow and
execution-time approval. Original failed parity evidence must remain unchanged.

Existing tests use unittest, temporary files and query-only SQLite fixtures.
New tests must reject stale/mismatched/unreviewed costs and unbound parity
exceptions. Reports never authorize execution. Run actual deployment-runtime
synthetic lifecycle tests separately from broker fill evidence.

Additional owner scope: “Demo trial แบบมีคนเฝ้า + backup บน Mac”. Add only a
manual SSH console and checksum/integrity-verified snapshot download; no scheduler,
sender control or unattended alerting claim.


## Selected26b8 verdict fixes (2026-10-26)

Owner: "$debug-mantra fix ตาม verdict". Bounded scope: shared lifecycle BE/no-resend and close reads; persistent selected terminal/boot registration; evidence-only UTC boundary sampling and dated closure diagnostics; independent read-only watchdog/private failure delivery. Native28 rules, fixed0.01/costinclusive10%, daily10%/loss2, cooldown and frozen research pins unchanged. Existing dirty edits preserved under runs/c22-fix-verdict-2026-10-26/before/.

Existing unittest native-MT5 fixtures, temporary persisted SQLite, aware UTC clocks; no HTTP replacement for MT5 native SDK. Optional find-untested-sources/gap-analysis/assertion-quality tools unavailable in catalog and command check. Use bounded manual pairing + independent agent assertions review.

Acceptance checklist: complete owned close reconciles without fresh quote/AutoTrading; incomplete evidence or real account blocks;10008 BE retains pending across restart and confirms broker SL before notification, no resend; valid boundary equity evidence persists before slow/stale-data gates, later/current-equity guessing blocked; boot returns exact financial manager from existing journal with one sender and persistent terminal; watchdog detects stopped/stale/UNKNOWN, deduplicates/retries, limits private payload and has explicit notification configuration; real VM source/identity/release/journal and rollback inspected before any flat cutover.


## C22 research risk closure (2026-10-26; owner confirmed Q6 via continue)

Scope broad: new research policy/event-loop/campaign/verifier and two new focused test files. Frozen101 sources/currentDemo/oldcampaign remain unchanged. Acceptance quote: “กันงบ SL ก่อนเปิดเพิ่ม โดยไม่เปลี่ยนกฎปิดไม้เดิม”, “หยุดเปิดเพิ่มก่อนความเสี่ยงถึง DD40%”, “เพิ่มพักอย่างน้อย24ชั่วโมง แล้วจึงตรวจว่าสัญญาณและงบความเสี่ยงผ่านครบ”, “Net BE ณครั้งแรกที่เลื่อน SL ก่อน”.12profiles/72matchedswapinclusivepaths. Existing unittest deterministic tick/bar fixtures plus real archived hashes. New files pair c22_risk_policy.py→test_c22_risk_policy.py and c22_risk_replay.py→test_c22_risk_replay.py. Optional find-untested-sources/gap-analysis/assertion-quality tools absent from catalog; inspect CLI availability once then use explicit new-file pairing.

Checklist: overlayoff exactparentledger/equityparity each6views; strictdaily/DDfloor equality; low/unknown/nonfinite inputs; independentD1P1; all-tickpeak;24helapsedfirsttrigger/noreset/exactdeadline/freshsignal/recurringpause; original1Rtrigger; signedaccruedswap B1price/currentSLmonotone/rounding/firstsuccessonly/geometryretry/latercost; explicitidentity/swap required; campaignhash/checkpoint/disk/exclusivelock/completedcellresume; full72coverage; independentcash/volume/time/nonoverlap/fulltickDD and eventaudit; unchangedfrozen/currentDemosources. No false brokerparity/newholdout/profitclaim.


## C22 root-cause closure first (2026-10-27)

Scope BROAD: user says “tuning strategy ให้ปิดช่องโหว่ลองไล่หา root cause ทั้งหมดของตอนนี้ก่อน”, invokes codebase-design/code-testing-agent/scrutinize. Bound audit to currentSelected26b8 market input, identity/connection admission, cost/review/daily/cooldown/UNKNOWN and watchdog. Root cause before parameter tuning. Preserve nativeRules/risk/frozen research/liveVM.

Existing unittest with SelectedBroker and persistent temporary SQLite; awareUTC clocks, Mock/patch; no SDK/network in tests. Smallest safe implementation may add identity-failure diagnostics using the SAME two existingSDK reads and existing publiccycle result, never a new reader/retry loop. Broker/runner diagnostic seam is the target; no new policy engine or strategy rewrite.

Acceptance checklist: R1 real sanitized VM/native logs and source trace distinguish confirmedcauses from unknowns; R2 disconnected and eachAlgo permission failure remainblocked but expose exact safe flags, successful nextcycle recovers withoutfreshcooldown, no stale diagnostics/secrets/extraSDKreads; R3 actual11/16H4 gap causes nativeNaN and restores onlyaftergenuinecompleteH4close/no futurecarry, RAWvsFULL distinguished; R4 policy/review/drift/manager interactions reproduced withoutautoattestation orriskweakening; R5 preserveactive/UNKNOWN/loss/daystate and pinnedsource/config, report remainingmaterial decisions; R6 independentassertionquality review and cleanfocused/full commands. No claim ofallpossibleunknownfuturebugs resolved ornewprofit/backtest.

Toolingdiscovery: dedicatedcode-testing-generator/find-untested-sources/test-gap-analysis/assertion-quality absent in toolcatalog; command-v find-untested-sources returned no path. ExecuteResearch→Plan→Implement inline with scopedagents and manualpairedinventory once: broker.py/runner.py→new test_c22_identity_diagnostics.py; selectedstrategy/frozenH4→new exactgaptestfile if existingcases do notalreadycover it; policy/cost/execution→new interactiontests proposed byreviewagent. Existingmetadata retained.

## 2026-10-27 Selected26b8 operability fixes
Broad bounded scope: existing watchdog, selected execution-review diagnostics, runner availability output and local read-only preflight. User requests fix the identified issue backlog. Prior dirty work preserved. No native strategy/risk changes, no new cost authority or automatic renewal, no broker forced order, no external delivery, no live VM mutation in implementation phase. Existing optional test-generator/pairing/gap/assertion tools unavailable; inline workflow plus independent agents. R1 intermittent failures must retain incident until stable recovery; R2 flat stale feed must expose unverified-session aging; R3 review diagnostic cause and policy expiry visibility without weaker approval; R4 separate process/protection/entry availability, known-vs-unevaluated gates, resumability; R5 preserve native rules, journal, UNKNOWN/no resend and frozen source pins. Root AP optimizer trigger requires actual evidence; historical/backtest changes remain separately qualified.

Operability outcome: existing status.py chosen as the observational seam; shared runner calls it after financial/protection outcome. No new module/dependency or broker reader. Safe review inspector reuses approval validator. Independent review uncovered malformed type and future/inconsistent timestamp counterexamples; all reproduced before fixes. Skill search found external monitoring options but none installed/required.


##2026-10-27 Selected26b8 debug-mantra verdict closure

Scope BROAD across existing selected runner/strategy, shared error and cost-admission/reporting boundaries. Requirements carried from owner: “ทุกอย่างถ้ามี error log ต้องมีเหตุผลบอกเสมอที่มาที่ไปของ issue” and close reproduced verdict gaps without modifying26b8 economics. Active tests use unittest, SelectedBroker and persistent temporary SQLite, awareUTC, no realSDK/network. Prior dirty files copied to runs/c22-debug-closure-2026-10-27/baseline. Frozen101/110 research files excluded; no currentbrokerconnection/VMwrite. Optional generator/pairing/gap/assertion tools not available (toolcatalog and command-v checked); bounded pairing inline.

Acceptance: R1 cost/spec generic refusal becomes safe field/stage diagnostic while exact allow/deny predicate unchanged; no guessed currentfield/automatic acceptance. R2 optional cache export/checkpoint cannot terminate owned cycle or erasevalidcache, preservesfinancialfailclosed. R3 unexpected identity/history failures retain distinct safe origin/stage and evidence without arbitraryexceptiontext, credentials or addedSDKreads. R4 concrete reason/resume mapping remains causal, UNKNOWN honest. R5 delivery/checkpoint operational outcomes durable and correlated without changing financialevent/replay semantics. R6 startup/reload/cleanup/journal failures have independent safe fallback; no addedorderretry or identity/risk bypass. R7 native/config bindings/pins and oldcorrectbehavior preserved; independentreview and clean focused/fulltests.


##2026-10-28 confirmed closure implementation
User: “ดำเนินการ fix ปิดช่องโหว่และสรุป logic,condition ทั้งหมด”. Scope: native trade decisions unchanged; R1 canonical refusal detail→public-cycle tests; R2 opt-in same-sender evidence request→fresh flat epoch/cash/sanitized packet tests and optional failure continuity; R3 offline grant/renewal planner→Q1/Q4/Q5/Q7/Q8 negative and boundary tests; R4 comprehensive source-cited native conditions and issue residual map; R5 targeted/full tests + immutable source-bound release, no VM deployment or runtime auto-renew. unittest fixtures from selected runner/costs; no additional dependencies. Optional test generator/pairing/gap tools not exposed; manual pairing + independent review. Reproduction/debugger/disproof ledger for actual bugs; missing feature RED labeled capability, not historical failure.


##2026-10-28 root-cause closure continuation
User: “continue until close all root cuse”. R1 durablecostgeneration/incidentcontinuity via existingJournalpublicseam;R2 immutablecoherentgenerationstore+crash/restart;R3 genuineofficial-sourcepacketdatedhash/contentclaims,notentitlement;R4 opt-inexisting-senderintegration/noadditionalSDK/ownedmanageruninterrupted/defaultoff;R5 freshread-onlyVM/APforensics and actualrootcauserepro;R6 fulltests/typechecks/Standards+Specreview/commitboundedcurrentbranch. Nativeparameters/frozen101/110pins unchanged; actualVMcutover/externalalerts/compoundingnotimplied. deterministicunittestverticals,root+agentassertionreview;exactacceptance mapsinreport. No newseamgrilling: interfaces/gates alreadyacceptedQ1-Q9+tickets. Unavailableoptionaltestgeneratortools manualpairing.

## C22 T20 joint-addon phase —28October2026

Bounded inventory: new c22_daily_addon.py (selector/attribution/daily MTM),
c22_daily_addon_campaign.py (frozen2profile/12path/6repeat CLI),
c22_daily_addon_verify.py (independent signal/cash/capacity/full-tick/daily math),
and tests/research/test_c22_daily_addon.py. Published#31 requirements preserved:
one frozen addon/sharedcapacity; swap-inclusive continuous joint accounting;
dailyMTM/distribution/noentrydays/coremissedidentities with coverage; matched
repeat/audit and noforcedwinner/autoDemo. Hypothesis/spec existed before module
implementation; this test-pipeline note was appended after initial seam tests,
not backdated. Existing repository unittest conventions retained.


## C22 session/feed continuation —29October2026

Bounded inventory: offline c22_session_gaps classifier/capture13tests already agent-implemented; root review source/UTC/missing-schedule negatives. New c22_forward_feed companion to sealed V2collector, existing paired-cache schema from selected/history.save_manifest. Agent left6public RED feature tests before quota ended; root continues implementation without modifying frozen collector/runtime. Requirements: original evidence bytes/hash/account/config/UTC chronology, no open bars/torn pair, rawM1/ticks NOT_CAPTURED, all-row daily denominators/excluded cohorts/partial days, no invented money or holds. Optional code-testing pairing tools unavailable; manual boundary pairing.


## 2026-10-30 Attended maintenance C-v2 local implementation

Broad scope: new attended_maintenance module, three closed AP/reboot/cost adapters, real read-only financial SQLite and separate durable operation store. Owner approved C-v2 local only. Existing campaigns and financial code remain unchanged. Helpers find-untested-sources/test-gap-analysis/assertion-quality unavailable; bounded manual inventory substitutes, no external calls. Agents attempted but hit usage limit; root research/review only. Requirements: exact plan/grant/cohort/backup; strict-zero/default and explicit OFF handoff; every row/schema/kind/payload/sent; critical review; quiescence/reader ownership; ambiguity/no redispatch; separate failure/recovery; budget/clock evidence; append-only/protected-key verification; durable same-handle/account serialization; preserve restored manager.


## 2026-10-30 Independent C-v2 corrections

Independent review reproduced6material defects after the prior39/1554green pass: real16character account identity mismatch; non-atomic terminalreceipt/account-release; permanently stuck conditional recovery; truthy UNKNOWN flags accepted; ownedprobe ignored after brokerproof; late reader ignored before sender start. All6pre-fix modules sealed by reviewer. Scope remains owner-approved local C-v2, not deployed. Use real SelectedDemoRunner + fake broker identity fixture. Preserve financial identity/schema/rules and all previous run receipts.

## 30 October approved midnight timing and H4 B continuation

Owner approved local #23 timing fix/tests without VM deployment, and H4 B bounded
carry age<8h offline first. Narrow methods use existing unittest/fake broker seams.
Root reproduced a missing held-management baseline reason and initial timing lost
by the second identity check. Requirement: original read interval and existing
baseline outcome public+persistent, no extra reads/gates, no exit-day overwrite.
H4 source/verifier preregister strict16H4/EMA200, M15close clock, all6modeled-swap
views, original $200 path/floors/DD40 and12cells+6fresh repeats before outcomes.

## Journal initialization diagnostic candidate (isolated, pending owner review)

Scope: original-source journal unchanged; prepare reviewed candidate+patch only.
Full disk run showed all BEGIN IMMEDIATE OperationalErrors relabelled writer.
Mock validation: structured BUSY/LOCKED extended codes retain legacy refusal;
FULL/IOERR/CANTOPEN/unknown/missing code retain original exception, FAULT and
sanitized metadata/hints. Initialization and cleanup failures remain fail closed;
no broker initialize/send. Preserve every existing SQL literal/connection flags.
Tests use mock connections or in-memory SQLite; no temp financial DB or VM.
Review source-binding impact and explicit owner boundary before applying patch.
