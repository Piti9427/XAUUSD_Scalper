# SMC challenger implementation and validation — 2026-10-08

Outcome: isolated research prototype implemented; frequency/net-return hypothesis not supported by this frozen run. No Demo/config/source-pin change or core migration. `smc_m15_v1`, contract ID `dd80c871955d7422`. Owner requested implementation of the [reviewed plan](../specs/2026-10-08-smc-strategy-implementation-plan.md); [ops/CLI](../ops/smc-challenger.md), canonical contract `CORE_STRATEGY.md`6.37.

New modules: causal M15 signal state machine, prepared-entry adapter, hash-bound resumable campaign. Existing structure helpers, closed H4EMA, canonical tick replay, swap calendar and checkpoint Store reused. No legacy H1/M5 orchestrator, new tariff/risk engine or sender. Numeric risk and broker provenance remain separate.

## Decisive seam fixes

Canonical `_entry_signals` overwrites structure anchors even in immediate mode. Adapter binds exact replay bytecode to a private globals dictionary containing a prepared-entry transform. No engine source fork, shared-global mutation or frozen-file edit. Complete-result differential fixture proves canonical output unchanged when anchors agree. Actual sweep stop geometry tests exercise different anchors and scenario-specific SELL Ask spread.

Canonical float addition before adverse grid rounding sometimes adds an extra protective tick. Prototype retains this behavior, includes rounded risk in admission, and documents it. No volume clamp or silent10% escalation.

Code review found omitted `commission_per_lot` could reach default0, and custom input broker metadata could contaminate archived parity. Red regressions reproduced commission omission, then exact cost schema/unit gates fixed it. Distinct broker regression runs actual archived parity with original snapshot and new-input comparison with custom snapshot. Input/evaluation prefix coverage now separate; H4/ATR unavailable counts disclosed. Per-rollover debits independently reconcile to ledger.

## Validation observed

| Check | Evidence |
| --- | --- |
| New focused suite | `.venv/bin/python3 -m unittest tests.test_smc_challenger tests.test_smc_challenger_adapter tests.test_smc_challenger_campaign`:21 tests OK,6.080s |
| Repository regression | `.venv/bin/python3 -m unittest discover -s tests`:937 tests OK,71.884s, skipped2. Log `runs/smc-implementation-full-suite-20261008.log` |
| Static checks | Ruff check/format and Python syntax compilation passed for new modules/tests. No typechecker configured or available; no typechecking claim. |
| Review | Standards and Spec independent agents: initial findings corrected and re-reviewed; no remaining substantive finding. Fixed task-start commit `f5dba467936e14eba8cfcded98e99d59a662e7a9`, staged/worktree diff reviewed. |
| Frozen sources | `verify_sources` with current C22 config passed before/after;9 pinned files and contract preserved. |
| Synthetic CLI | Workers2 fixture completed4 cells and all fresh repeats, explicitly FIXTURE_COMPLETE; cannot substitute historical evidence. |
| Actual history | Archived C22 base-swap/stress-swap full-result parity passed. Four new comparison cells each repeated completely. Direct CLI resume exited0. |
| Artifact audit | All11 checkpoint artifact hashes, per-cell cashflow/swap attribution and reconstructed equity-checkpoint DD passed. |

Initial historical command used `/usr/bin/time -l`; campaign wrote COMPLETE, but timing wrapper exited1 because sandbox denied `sysctl kern.clockrate`. Re-ran same campaign directly, resumed successfully with exit0. Economic data/results unchanged; timing wrapper error is not a strategy failure.

## Actual frozen research run

Artifacts: ignored `runs/smc-challenger-history-20261008/`; protocol SHA256 `ee02157fa138926f26add3afa230aa901b284ba97bb6da57e92ce3fea57954f3`. Command:

```bash
.venv/bin/python3 -m scripts.research.smc_challenger_campaign --output runs/smc-challenger-history-20261008 --workers 1
```

Requested2024-09-01 through2026-10-04T11:19:48.476278UTC. Actual paired quotes2024-09-01T22:05:06.129UTC through2026-10-02T20:57:59.885UTC;167,366,065 ticks,48,367 M15 bars,552 bar gaps (no fill),12,219 H4-unavailable evaluation bars,13 ATR-unavailable bars. Reused discovery, not independent holdout.25 full requested UTC months; partial October excluded from frequency mean.

Both views include modeled points swap. Both use declared slippage0.10/oz, commission0 USD/lot/roundtrip from named archived assumption; stress adds total spread0.20/oz. C22 archived parity retains archived costs; table is the **new common-cost** comparison, not relabeled archived returns.

| Strategy/view | Net USD | Tick-equity DD | Trades | Entries/full month | Swap USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| C22 base+swap |335.2722 |39.8684% |120 |4.76 |-3.9718 |
| C22 stress+swap |278.7102 |37.8232% |116 |4.60 |-3.9718 |
| SMC base+swap |-43.6250 |24.2828% |5 |0.20 |0.0000 |
| SMC stress+swap |-44.7130 |24.7367% |5 |0.20 |0.0000 |

SMC funnel:2,494 sweeps,111 CHoCH,61 FVG publications,9 candidates after macro gate,5 admitted trades/view. Zero realized SMC swap charge is ledger exposure outcome; modeled swap policy and per-rollover accounting are present. Lower DD with only5 trades does not establish superiority. Strict conservative pool calendar may suppress PDH/PDL around ordinary market gaps; no post-result relaxation or retuning performed.

## Requirement evidence

| Reviewed requirement | Exact evidence |
| --- | --- |
| No lookahead, causal pivots/CHoCH/FVG/retest, mirrored sides | `test_prefix_future_mutation_and_chunk_cache_match`, `test_sweep_protected_choch_fvg_later_retest_buy_and_sell`, `test_pivot_publication_bos_not_entry_and_conflicting_sweep_rejects`, `test_fvg_requires_third_close_and_displacement` |
| Pool coverage, setup expiry/invalidation/dedup, macro warmup | `test_pools_publish_after_complete_session_missing_pool_stays_unavailable`, `test_wick_invalidation_retest_expiry_and_no_revived_setup`, `test_unwarmed_macro_blocks_candidate` |
| SELL executable stop,10% cost-inclusive cap, fixed lot, exposure/margin/timing | `test_sell_stop_uses_actual_ask_spread_and_adverse_grid`, `test_cost_inclusive_cap_equality_and_one_cent_over_are_distinct`, `test_busy_margin_and_midday_unknown_baseline_remain_canonical`, `test_no_quote_late_quote_fixed_volume_and_risk_rejections` |
| Mandatory swap/equity/debits and prepared replay parity | `test_missing_swap_or_invalid_tape_cannot_fall_back`, `test_swap_triple_midnight_changes_equity_and_no_global_replay_mutation`, `test_prepared_replay_matches_canonical_for_unchanged_anchors`; existing `SwapTests.test_swap_triple_day_and_weekend_gap` and replay circuit regressions in full suite |
| Explicit costs, frozen comparison, coverage | `test_missing_commission_in_either_view_blocks_without_default`, `test_archived_parity_uses_archive_broker_not_custom_broker`, `test_evaluation_coverage_excludes_tape_prefix_and_reports_warmup`; actual archived full-result parity |
| Repeat/resume/drift/output boundaries | `test_both_swap_views_comparator_repeat_and_resume`, `test_partial_resume_equals_fresh_and_artifact_drift_blocks_completion`, `test_input_drift_missing_cost_sources_and_no_fixture_shortcut`; actual direct resume exit0 |
| Documentation/scope | CORE6.37, config, ops and reviewed plans; no modifications to frozen sender, pins or Trial30. Pre-existing `CONTEXT.md` edit excluded from implementation commit. |

Limitations: retrospective model, current-spec swap/commission assumptions remain `COST_INCONCLUSIVE`; no independent holdout, broker parity, shadow, deployment or profitability qualification. Implementation complete; research prototype does not meet frequency/net-return objective on this run.
