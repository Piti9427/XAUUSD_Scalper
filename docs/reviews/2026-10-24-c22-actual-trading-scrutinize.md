# C22 actual trading readiness — outsider review, 2026-10-24

**Goal:** determine whether the existing Oracle deployment can be left running to open/manage/close Demo orders from real broker quotes, and whether profitable performance is established.

**Verdict: fix-then-ship for Demo execution; shadow may continue.** Biggest reason: the deployed Oracle stack has no observed C22 signal/request/fill/close lifecycle yet. Profitable future performance is unproven, independently of operational readiness. Real money remains prohibited.

## Smaller alternative

Keep the frozen C22 sender and prove its real Demo lifecycle under the approved rollout. Do not add another strategy/sender or treat additional service/reporting code as evidence of profitability. Strategy selection, software correctness, broker execution and profitable outcomes are different claims. Increasing lot size, forcing a signal, changing frozen parameters or enabling an execution flag does not close the missing evidence.

## Blocker — current deployment cannot send orders

**Finding:** the active unit deliberately starts shadow with gate0/no `--execute`; the execution template is not installed, and the latest exclusive terminal probe observed AutoTrading disabled.

**Why:** a real BUY/SELL signal on Monday still cannot produce an order under this deployment. This is more than the market being closed.

**Evidence:** [shadow unit](../../deploy/c22-demo/c22-oracle-shadow.service#L16) → [CLI execution flag](../../scripts/demo_runtime/cli.py#L119) → [shadow return before sending](../../scripts/demo_runtime/admission.py#L142). If execution were selected, [strict broker identity/permissions](../../scripts/demo_runtime/broker.py#L45) would reject disabled AutoTrading. Separately, [admission cost validation](../../scripts/demo_runtime/admission.py#L61) rejects the current COST_INCONCLUSIVE file on a signal. Live read-only inspection at07:07:50UTC/14:07:50Asia/Bangkok confirmed execute=false, positions0, no active journal position/halt, empty pending outbox, shadow active and execution units inactive/uninstalled. Terminal permission evidence is from06:34:45UTC, not a newly queried SDK state during this review.

**Suggested change:** retain shadow until rollout review passes; obtain supported fresh costs and execution-time owner approval, then perform one explicit Demo cutover with the dedicated terminal and one sender. Do not flip permissions/gates as a substitute for review.

## Blocker — tests/checks do not establish an actual Oracle fill/close cycle

**Finding:** the Oracle journal contains6799 CYCLE events but zero SIGNAL, REQUEST, RESPONSE or LIFECYCLE events at this inspection. There is no C22 broker-confirmed Oracle fill or close to assess.

**Why:** startup/IPC/cache/backup and order_check success cannot prove the deployed emulator will execute a live C22 request, protect it, recover a timeout or reconcile its final costs. Zero observed trades is not a zero-loss profitable result.

**Evidence:** actual path is [CLI cycle](../../scripts/demo_runtime/cli.py#L148) → [identity/exposure/history/spec/quote](../../scripts/demo_runtime/runner.py#L198) → complete M1/M15 → [frozen candidate/cache](../../scripts/c22h4/runner.py#L75) → [admission and risk/margin/order_check](../../scripts/demo_runtime/admission.py#L22) → durable SENDING at[192](../../scripts/demo_runtime/admission.py#L192) → audited [order_send](../../scripts/demo_runtime/runner.py#L229) → [opening-ledger/stable-ID reconciliation](../../scripts/demo_runtime/lifecycle.py#L16) → broker-confirmed FILLED at[135](../../scripts/demo_runtime/lifecycle.py#L135) → [SELL BE](../../scripts/demo_runtime/lifecycle.py#L176) or BUY management → complete closing ledger/[cash event](../../scripts/demo_runtime/lifecycle.py#L311). The actual journal has reached only pre-admission cycles because quotes are stale. The latest prepared window had0 prospective completed bars. Its diagnostic readiness file is timestamped06:35:35UTC and is historical, not a current live approval.

The public-cycle tests use [CandidateBroker](../../tests/demo/test_c22h4_demo.py#L28) and synthetic bars. This is appropriate correctness coverage, not real fills. MetaQuotes likewise states that [order_check success does not establish successful execution](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercheck_py).

**Suggested change:** complete the real market-data shadow/cache/latency review, then an owner-approved Demo trial using genuine C22 signals, preserving request/response, position ID, stop/BE observations, closing deals and actual profit/commission/swap/fee. Do not create a forced signal merely to record a trade. The48h/96bar gate is operational validation, not an extra strategy entry rule and not profit qualification.

## Major — real broker data can produce a different C22 decision from the profitable archive

**Finding:** the unchanged original history/parity result remains failed:40 signal bars include3direction/admission differences and8geometry differences.

**Why:** software may execute the frozen formulas correctly while opening different trades on the actual account feed. Archive returns cannot then be assumed to transfer unchanged.

**Evidence:** the actual [probe gate](../../scripts/ops/c22h4_history_probe.py#L183) requires zero direction/admission differences. [Controlled diagnosis](2026-10-24-c22-market-open-preparation.md#L30) reduced3differences to1 by giving the archive the sameJuly15 start; identical-input controls produced0differences. This attributes two decisions to EMA initialization/history depth. The remainingSep11 03:45UTC close4304.146 is below archive prior96low4304.149 but above broker prior96low4304.044: the raw breakout itself differs. The diagnostic common-start experiment does not change the original gate or authorize production history trimming.

**Suggested change:** review/resolve the causal-prefix basis and accept or reject the actual feed differences explicitly; replay the exact exported live cache. Do not retune thresholds, seed from a different feed silently or change assertions to manufacture parity.

## Major — unattended critical alerts currently have no configured delivery path

**Finding:** the runtime can persist protection-uncertain critical events, but no Telegram or Healthchecks keys are configured in the active service environment.

**Why:** a running process can lose broker protection visibility without reaching the owner. A persistent SQLite event is not an external alert, and a live process is not evidence of healthy position management.

**Evidence:** [180-second critical event](../../scripts/demo_runtime/runner.py#L135) → [optional CLI notification clients](../../scripts/demo_runtime/cli.py#L105) → [flush returns immediately without notifier](../../scripts/demo_runtime/journal.py#L147). The latest inspection found all three notification configuration keys absent. This respects the owner's Telegram deferral; it does not establish unattended readiness. Nine unknown-protection cycles in the last inspected hour were specifically06:35:38–06:35:48UTC, immediately after a deliberate preparation restart; do not label them unexplained spontaneous failures. Earlier startup/uptime experiments remain historical qualification evidence.

**Suggested change:** before unattended execution, configure and test an owner-reachable critical/dead-man channel and the agreed recovery path. If Telegram remains deferred, review a concrete alternative rather than silently treating notification delivery as passed. Local cumulative backup/restore is verified; scheduled private-cloud recovery remains a separate open gate.

## Major — profitable research is not verified profitable operation

**Finding:** positive saved simulations support selecting C22 for a Demo experiment; they do not establish positive expectancy on this Oracle account or guarantee profit after activation.

**Why:** the selected history was already used for research, feed parity is unresolved and actual target-account costs/fills/latency are not established. Operational gates cannot convert those simulations into forward profit evidence.

**Evidence:** [canonical active contract](../../CORE_STRATEGY.md#L500) explicitly labels base+swap net+291.55USD and stress+swap+278.71USD as retrospective modeled results from200USD, with modeled drawdown about39.28%/37.82%. Existing saved summary/protocol/result artifacts were inspected and completion protocol/result hashes plus15source hashes verified in this review; no new economic replay was run. [The saved comparison](2026-10-18-dobby-vs-c22-comparison.md#L46) also contains an earlier negative subwindow and no untouched holdout. The research account begins200USD; the latest actual Demo evidence was1812.21USD and fixed0.01lot, so percentage returns/admission paths cannot simply be scaled. [The prospective evidence module](../../scripts/demo_runtime/evidence.py#L25) correctly starts data/cost/profitability as INCONCLUSIVE and separates actual net costs; no C22 Oracle lifecycle samples exist to replace that status.

**Suggested change:** retain the profitable-history claim at its measured scope. After technical cutover, collect forward broker fills and report net PnL, expectancy, profit factor, count, observed drawdown and data completeness. Any new economic comparison must include base+swap and stress+swap with supported metadata. Seven Demo days and48hshadow are operational gates, not evidence that future trades must win. No strategy or infrastructure can promise profit from those checks.

## Operational distinction — readiness is a review, not an execution interlock

The staged [execution unit](../../deploy/c22-demo/c22-oracle-execution.service#L7) checks approved-file existence/source hashes and invokes execution; it does not run the48h/parity review as ExecStartPre. The [report](../../scripts/ops/c22h4_readiness.py#L171) always returns execution_authorized=false and lists manual reviews. The [runtime cost validator](../../scripts/demo_runtime/costs.py#L18) retains v1 compatibility and C22v2's168hour admission age; neither automatically enforces the stricter<=24hour cutover review. These controls were documented as manual operational gates. A filename, successful unit parse or clean report must not be represented as proof that every gate was machine-enforced. Keep the template uninstalled until the actual owner-approved review; no new approval subsystem is required to answer the current readiness question.

## Verification performed in this review

- Live read-only VM journal/unit/configuration inspection; no account login/order/terminal switch, restart, cost renewal or execution activation.
- All8inspected deployed runtime source files matched local reviewed files; deployed58-file source/config manifest check returned0; all9frozen source pins matched.
- Existing economic protocol/result hashes and15pinned research sources matched; saved metrics inspected. Economic replay calls0, strategy changes0.
- Traced CLI → identity/data → detector → admission → persisted intent/send → stable-ID fill → BUY/SELL protection → complete close/cash → durable notes/optional delivery.
- Fresh focused regression command: `.venv/bin/python -m unittest tests.demo.test_c22h4_cli tests.demo.test_c22h4_demo tests.demo.test_c22h4_safety_recovery tests.demo.test_demo_containment`:64tests in67.303s, OK. Covers real shared code with synthetic broker, including BUY/SELL, timeout/restart, partial residual safety, stops/TP/BE, account switches, persistence and daily/cost gates. This review adds no tests or runtime changes.
- Earlier final140Demo/1022fullsuite runs remain recorded in the preparation report; they were not rerun as broker or profit proof.

Raw inspection/test/hash artifacts: ignored `runs/c22-scrutinize-readiness-2026-10-24/`. User's pending Dobby/research/trade notes were not changed.

**Verdict: fix-then-ship for a controlled Demo trial, not unattended profitable trading — the Oracle C22 fill/protection/close lifecycle and live profitability are still unproven.**
