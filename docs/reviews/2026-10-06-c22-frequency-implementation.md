# C22 frequency campaign implementation review

Research CLI, strict challenger adapter, qualification/accounting, atomic artifact
store and fresh-month acquisition implemented separately from frozen Demo code.
Owner spec: `specs/c22-frequency-campaign.md`; operations:
`docs/ops/c22-frequency-campaign.md`; strategy documentation: CORE_STRATEGY6.35.
Economic result is published separately after the 300-variant campaign completes.

## Standards

Independent read-only reviewer: **No findings.**

Reviewed task-only patch against AGENTS.md, pyproject.toml, CORE_STRATEGY6.35 and
campaign specification. Traced canonical replay/accounting reuse, fixed-lot/risk
checks, UTC handling, swap enforcement, artifact hashing, pending checkpoint
recovery, resume validation and research-only output boundaries. No documented
standard violations or actionable baseline smells identified. Frozen Demo
contracts remain outside changed execution paths.

## Spec

Independent reviewer identified one actionable issue before its service hit a
usage limit: CLI accepted budgets1–300 and could finalize a reduced search,
contrary to "Stop at300 unique challenger variants or exhaustion."

Fixed: CLI config requires exactly300. `--max-cells` paces PARTIAL execution
without changing total budget. Regression first failed for1/3/299, then passed:
`ContractTests.test_public_campaign_cannot_finalize_reduced_search_budget`.
Primary agent completed the remaining spec pass and reviewed final diff. Separate
Spec sub-agent did not produce a completed final report because of service limit;
this limitation is retained, not represented as an independent pass.

Primary review also tightened candidate scalar types (reject float RSI period
before rolling-window construction), verified COMPLETE pointer integrity on
resume, and persisted BLOCKED with selected=null on validation failure.

Standards:0 findings, none worst. Spec:1 confirmed finding, reduced-budget finalization,
fixed; independent final Spec review incomplete.

## Verification

Red-before-green observed at adapter, policy/accounting, Store/resume and
budget/type-validation seams. Synthetic integration runs actual candidate frames,
nonzero trade ledgers, both swap views, full-result repeats and partial resume.
No generated tests call broker execution APIs.

| Owner requirement | Evidence |
|---|---|
| baseline parity, config เปลี่ยน signal จริง | `AdapterTests.test_baseline_parity_and_buy_ema_changes_real_signals`; full archived base/stress result parity |
| reject unknown keys | `AdapterTests.test_reject_unknown_keys_and_out_of_domain_values`; `ContractTests.test_adapter_rejects_float_period_before_signal_generation` |
| future invariance, H4 unavailable | `SignalBoundaryTests.test_future_invariance_and_h4_diagnostics` |
| เฉลี่ย ≥15 entries/เดือนเต็ม รวมเดือนศูนย์ไม้/warmup; partial month รายงานแยก | `PolicyTests.test_monthly_entry_count_includes_zero_warmup_and_excludes_partial` |
| ทุก candidate ต้องผ่านทั้ง base+swap และ stress+swap | `PolicyTests.test_qualification_requires_both_views_all_gates`; `SearchTests.test_real_cells_partial_resume_repeat_and_both_swap_views` |
| Cost proxy ไม่บวก extra spread ซ้ำ; swap debit/credit แยก | `PolicyTests.test_cost_proxy_never_counts_extra_spread_twice` |
| metadata ขาด/ไม่รองรับ → BLOCKED | `SearchTests.test_missing_or_unsupported_swap_blocks_worker` |
| freeze catalog; deduplicate; 300 unique variants | `SignalBoundaryTests.test_catalog_round_one_covers_each_value_and_deduplicates`; `RankingTests.test_three_hundred_unique_variants_without_early_stop`; reduced-budget regression above |
| Search ranking; ผู้ผ่านจัดอันดับ | `RankingTests.test_rank_survival_gates_frequency_and_worst_case_ties` |
| terminal gate; no-signal/mixed reasons แยก | `RankingTests.test_terminal_all_risk_without_exposure_only_and_utc_required` |
| lock/checkpoint/resume | `ResumeTests.test_resume_rejects_config_or_artifact_drift`; `ResumeTests.test_pending_commit_recovery_and_unknown_artifacts`; `LockTests.test_second_writer_cannot_change_existing_artifacts`; real-cell integration above |
| UTC midnight, swap/triple rollover, BEสุทธิติดลบ | Existing `SwapTests.test_swap_triple_day_and_weekend_gap`; `SwapCircuitTests.test_break_even_swap_loss_counts_for_daily_circuit_before_next_admission`; `test_cross_midnight_position_requires_day_start_snapshot` |
| DD floating และ cap/fixed lot | `test_entry_spread_is_in_trade_mae_and_account_drawdown`; `test_local_peak_trough_survives_compressed_equity_trace`; `test_cost_inclusive_risk_rejects_instead_of_clamping_lot`; `test_drawdown_steps_reject_high_risk_entry_after_two_losses`; every cell independent reconciliation |
| machine artifacts runs/; update CORE_STRATEGY; preserve Demo | CLI restricted to runs/; CORE_STRATEGY6.35 only; initial Demo working changes excluded from task diff/commit |

Final configured environment command: `source .venv/bin/activate`, then
`python3 -m unittest discover -s tests`: **909 tests OK, skipped2**.
System Python's first full-suite attempt failed13 imports because yaml/fastapi
were absent; `.venv` already had required dependencies, so no installation or
lockfile change was needed. New Python lint/format, compile and diff whitespace
checks pass. No repository typecheck command is configured in Makefile/pyproject.
MT5 smoke test not run: no credentials, connector or runtime timeframe changes.

Campaign uses separately pinned system runtime Python3.14.6/NumPy2.4.5/Pandas3.0.3;
full suite uses existing `.venv` NumPy2.5.3/Pandas3.0.5. Archived whole-result parity
passed on campaign runtime; resume rejects runtime changes.
