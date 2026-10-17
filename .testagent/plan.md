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
