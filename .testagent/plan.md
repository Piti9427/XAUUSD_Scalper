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
