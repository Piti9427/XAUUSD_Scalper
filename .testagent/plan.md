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
