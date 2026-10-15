# Pure B1 Shadow test status — 2026-09-29

Scope: canonical broker M1 to M15 adapter, pure decision/risk gate, read-only MT5 Shadow JSONL, bounded capture, bar/signal parity.

| Requirement | Evidence |
| --- | --- |
| Complete 15/15 UTC M1 bar adapter | `tests/test_pure_b1_broker_data.py` |
| Fixed 0.01 lot, 10% cap, quote/day/exposure rejection, broker trade mode and stop distance | `tests/test_pure_b1_decision.py` |
| Read-only Shadow, one record per bar, balance/foreign exposure rejection, zero order API | `tests/test_pure_b1_shadow.py` |
| Target Demo identity before bars and after ticks; immutable manifest | `tests/test_pure_b1_capture.py` |
| OHLC and signal mismatch detection | `tests/test_pure_b1_parity.py` |
| Full suite | `make test`: 641 tests, OK, 2 skipped |
| Static and dependency checks | `ruff check`, `ruff format --check`, `compileall`, `pip check`: passed |

Review found remaining evidence gaps: per-bar SL/TP/risk parity lacks historical account/cost snapshots; one-hour ticks cannot qualify six-month strategy; no measured fills, slippage or historical swap entitlement. `main.py` and EA remain outside Pure B1 Shadow path. Demo and real-money execution remain NO-GO.

## 2026-10-04 Reward156 paired tuning

Inline test pipeline plus independent Standards/Spec code-review. Initial provenance/repeat gaps fixed and reviewed again. Nine new seam tests passed; full suite819 tests,2skips,OK. Changed Python lint passed; syntax compilation passed (no configured static typechecker). Existing test metadata preserved and current research/plan appended. Complete-result matrix repeats remain independent acceptance evidence, recorded by research harness.

## Profit/survival v2 implementation review
Focused unit/regression scope; inline Research→Plan→Implement plus Standards/Spec code-review agents. Narrow63tests passed; full829tests33.668seconds OK(skipped2). Assertions strengthened after review: frozen raw directions contain both sides; warmedH4 directions nonzero; dedup preserves full per-seed choice sets; immutable discovery lock remains verifiable after final verdict changes; interrupted unproved result recomputed; hash corruption fails. Cooldown2 executes two rejects then admits on elapsed boundary. Existing replay directional exit/roundedRR/BE/cost-inclusive rejection/swap/H4 tests remain passing. Performance acceptance waits for complete campaign and independent artifact audit.

### Demonstrated runtime fix
Fresh-replay NumPy gate serialization failed after104cells. Red `SerializationTests.test_fresh_and_resumed_replay_matrix_serializes_native_boolean_gates` reproduced real Campaign.cells→atomic_json path. Pythonbool boundary fixed serialization; test checks all flags native and fresh/resumed full matrix equality. `SwapCircuitTests.test_break_even_swap_loss_counts_for_daily_circuit_before_next_admission` verifies BE price-zero/-3swap loss/circuit two rejects/nextday admit. Added explicit zero-trades/nonpositive-equity policy inputs. Final narrow65tests pass; full831tests21.448seconds OK(skipped2). Standards and Spec reviewers verified fix, no new findings. Performance acceptance remains pending canonical COMPLETE/audit.

### Completed campaign and artifact audit
Canonical COMPLETE observed:65 configurations,584 cells,64 fresh complete-result control matches. Independent verifier recomputed all row metrics/gates, adaptive catalogs, finalist selection and reconciled51,010 ledger trades;48 main control results match v1 completely. SelectedNONE, finalistsNONE, holdoutNOT_OPENED_NO_QUALIFIER. Strongest measured candidate is profitable above both controls in all8 continuous scenarios, worstnet29.74/worstDD35.60; A32trades fails60 and all A profits fail50. No conditional validation reported as executed. Full requirement/test map: `docs/reviews/reward156-profit-survival-2026-10-04/completion-audit.md`. Final test log and checks are hash-bound; verifier rejects optimized Python assertions. Implementation complete does not mean profit qualification achieved.

## C22 frequency campaign (2026-10-07)

Completed inline test-quality review and requirement mapping in
`docs/reviews/2026-10-06-c22-frequency-implementation.md`. Added17 focused tests,
including actual nonzero replay executions, not only all-zero signal assertions.
Red/green reproduced adapter/policy/Store absence and reduced-budget/type defects.
Final full suite in existing .venv:909 tests OK, skipped2; new Python lint/format,
compile and diff whitespace pass. Initial system Python failed13 dependency imports;
no dependency change required. No configured repository typecheck.

Standards agent:0 findings. Spec agent:1 confirmed reduced-budget finalization
finding fixed with failing-then-passing regression; service quota prevented its
final report. Primary agent completed remaining spec/final-diff pass. No independent
Spec completion claimed. Research result NO_QUALIFIER after300 challengers/602cells,
81304 trades independently reconciled; baseline parity/repeats and696-hash resume pass.

## SMC research challenger (2026-10-08)

Implemented reviewed isolated research plan with inline Research → Plan → Implement
and independent Standards/Spec agents. Preserved existing test metadata and frozen
C22/Trial30 sources. Commission-default, archive-broker provenance and evaluation
coverage findings fixed with focused regressions; both reviewers report no remaining
substantive findings. Full requirement mapping:
`docs/reviews/2026-10-08-smc-challenger-implementation.md`.

Focused21 tests OK; full937 tests OK, skipped2. New Python Ruff check/format and
syntax compilation passed. No configured/available typechecker. Historical four-cell
swap-inclusive campaign COMPLETE, archived parity and complete fresh repeats passed;
direct CLI resume exit0. Independently audited11 artifact hashes, ledger cashflow,
swap debits and reconstructed equity-checkpoint drawdown. SMC stress net -44.713 USD,
5 trades: frequency/net-return hypothesis unsupported. COST_INCONCLUSIVE; descriptive
research only, no holdout/qualification/live readiness or Demo deployment claimed.

## C22 runtime corrections (2026-10-14)

User requested `$debug-mantra`, then selected “คง policy เดิม แสดง blocker ให้ชัด”.
Baseline policy, frozen strategy/risk pins, live watcher and cost attestation kept.
Local shared safety-close recovery/accounting and read-only status corrected.
Existing research/plan/status history preserved; current plan appended.

Permanent public-cycle regressions:10 safety-recovery cases; status suite8 cases
(including2 existing). Exact acceptance-to-test mapping and inline quality review:
`docs/reviews/2026-10-14-c22h4-runtime-debug-fixes.md`. Negative controls assert no
resend with incomplete/pending/ambiguous/legacy evidence; positive cases assert
actual residual/ticket, restart, no phantom FILLED, cash components and exit price.
Status tests verify readiness/expiry/history semantics and no journal/policy write.

Final make test:953 tests/85.085s/OK, skipped2. Compile/deps/lint PASS; four changed
Python files Ruff check/format PASS. Whole-repository format-check still fails13
pre-existing out-of-scope files; no aggregate make check or typecheck claim.
C22 source pins9/9 match. Red/green/debugger/status artifacts in ignored runs.
No MT5 broker initialization/orders, economic replay, cost renewal or rollout.
Daily continuity limitation remains under owner-selected process-scoped policy;
deployment acceptance and fresh owner attestation remain separate next gates.
