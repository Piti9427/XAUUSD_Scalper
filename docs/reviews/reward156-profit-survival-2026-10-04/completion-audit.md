# Profit/survival v2 completion audit

Implementation and finite experiment complete; **profit qualification unmet**.
Policy `profit_survival_v2`; fixed review point `88bd849ac5286dec441f5e0146a093af382e86d2`.
Plan: `.cursor/plans/long-term_macro_gate_99f085f3.plan.md`, appended v2 section.
V1 evidence remains immutable. No new threshold relaxation after inspecting results.

## Outcome

65 configs =5 seeds +52 deduplicated one-factor configs +8 combinations.
584 cells =64 control cells +65 candidates ×8 continuous cells.
64 fresh complete-result control matches;48 main control cells match v1 exactly.
No continuous qualifier, no finalist, no selected config, no holdout opening.
Candidate reset-half and swap0.5x/1.5x stages cancelled by prerequisite, not executed.

Best measured candidate `variant_1af968e9ac6a26ea` (circuit22 +H4EMA200) earns positive net above both controls in all8 cells; worst net +USD29.74, worst DD35.60%. Four A cells fail net>=50 and trades>=60 (32 actual fills); four B cells pass. This result supports discovery improvement, not full replacement qualification. A covers10 months; B12 months. Each result starts USD200 independently; profits never summed across reset accounts.

## Requirement and evidence

Behavior names below are exact unittest methods; existing replay tests intentionally reused. Artifact verification complements tests with actual full-history evidence.

| Requirement | Evidence |
|---|---|
| “เน้นผลลัพว่าต้องได้ performance ที่ดีกว่าเดิม” | `SearchTests.test_policy_boundaries_and_undefined_rr` requires full profit>=50 and strictly above controls; `results.json`/`summary.md` show measured improvement but no complete qualifier. |
| “ปรับให้ relax ได้” | Frozen v2 policy in plan/config; `SearchTests.test_policy_boundaries_and_undefined_rr` exercises DD45, half net-20, report-only undefined WR/RR and full-only both sides. |
| “ยังต้องเน้นได้ profit หรือกำไรที่ดีไม่พอร์ตแตก” | Same boundary test rejects nonpositive equity, bankruptcy, excessive DD/risk and terminal blockage; `validation.json` recomputes gates from584 cells. Qualification unmet, no guarantee of future survival. |
| “ใช้ทุกเงื่อนไขหรือสภาพแวดล้อมที่เหมือนกันมาทำการ backtest” | `TuningTests.test_contracts_share_environment_but_keep_signals_and_exits`; `contract.json`, `input-A.json`, `input-B.json`; verifier recomputes identical account/window/cost/broker inputs per cell. |
| “logic,strategy ของแต่ละอันก็ใช้งานแยกกัน” | `SearchTests.test_frozen_default_and_archived_seed_parity`, `TuningTests.test_contracts_share_environment_but_keep_signals_and_exits`; each cell independent account, directional rules and detectors explicit. |
| Archived/frozen RSI formula and nonzero BUY/SELL parity | `SearchTests.test_frozen_default_and_archived_seed_parity` compares directions and warmedH4 output, future-modified suffix leaves past unchanged. |
| Causal completed H4, full indicator prefix for reset accounts | `TuningTests.test_h4_closed_boundary_and_future_invariance`, `TuningTests.test_h4_incomplete_bucket_and_warmup`; verifier reconstructs candidate frame from discovery prefix before applying window. |
| Independent side exits, rounded targets and BE timing | `BreakoutLogicTests.test_buy_exit_profile_preserves_sell_parent_and_cost_inclusive_cap`, `BreakoutLogicTests.test_buy_protection_off_keeps_sell_break_even_lifecycle_identical`, `BreakoutLogicTests.test_rr_and_dd_use_realized_tp_not_favorable_tick_overshoot`, `BreakoutLogicTests.test_break_even_activates_after_closed_bar_and_covers_costs`. |
| Swap changes actual equity/admission; research rollover calendar | `SwapTests.test_swap_changes_next_risk_admission`, `SwapTests.test_swap_triple_day_and_weekend_gap`; `cost-path-divergence.json` records independent path differences. |
| BE price-zero/swap-loss triggers daily loss circuit before next entry | `SwapCircuitTests.test_break_even_swap_loss_counts_for_daily_circuit_before_next_admission`: -USD3 swap, two same-day rejects, next-day admission. |
| Fixed0.01/10% cost-inclusive cap, no upward clamp | `BreakoutLogicTests.test_cost_inclusive_risk_rejects_instead_of_clamping_lot`, `SearchTests.test_finite_catalog_single_factor_and_dedup`; verifier checks51,010 fills, initial-stop risk, costs, admission equity/cap and single-position non-overlap. |
| UTC-aware windows and daily state | `BreakoutLogicTests.test_naive_window_rejected`, `BreakoutLogicTests.test_cross_midnight_position_requires_day_start_snapshot`; every saved equity checkpoint verified UTC. |
| Distinguish risk-only blocked days from no-signal inactivity | `TuningTests.test_risk_blocked_days_require_all_signals_and_no_position`; row metrics recomputed from actual events and positions. |
| Cooldown2 supported with exact elapsed boundary | `SearchTests.test_cooldown_two_bars_is_supported`, `ReviewRegressionTests.test_cooldown_two_bars_rejects_then_admits_on_boundary`. |
| Finite5 seeds/top2/<=27 factors each/3pairs+1triple/<=62 new | `SearchTests.test_finite_catalog_single_factor_and_dedup`, `ReviewRegressionTests.test_dedup_retains_all_per_seed_factor_choices`; verifier reproduces `chosen-seeds.json`,52 one-factor configs/references and8 combinations exactly. |
| Controls saved first, same independent inputs, repeat complete results | `CampaignTests.test_checkpoint_integrity_repeat_and_corruption`; `baseline-matrix.json`64 cells precedes seed/search catalog in campaign code;64 hash-attested fresh matches,48 v1 whole-result matches. |
| Atomic checkpoints, source/config/input/runtime drift rejection | `CampaignTests.test_config_and_source_drift_rejected`, `CampaignTests.test_checkpoint_integrity_repeat_and_corruption`, `ReviewRegressionTests.test_interrupted_result_recomputed_and_lock_immutable`; frozen contract/snapshots and verifier. |
| Fresh/resumed matrices serialize native JSON boolean gates | `SerializationTests.test_fresh_and_resumed_replay_matrix_serializes_native_boolean_gates`; demonstrated RED before nativebool fix, GREEN with fresh/resumed whole matrices equal. Interrupted104-cell run preserved separately. |
| Stable rank, <=6 finalists, immutable selection before holdout access | `CampaignTests.test_deterministic_rank_and_holdout_requires_lock`, `ReviewRegressionTests.test_interrupted_result_recomputed_and_lock_immutable`; verifier recomputes rank/selection/matrix coverage. Actual eligible count0. |
| Conditional24 main cells plus8 extra-swap cells per finalist, fresh repeats | `reward156_campaign.py:Campaign.validate_finalists`; verifier enforces exact coverage/repeats for eligible finalists. Cancelled: no continuous qualifier, no candidate validation claimed. Controls alone executed full/halves/extra-swap. |
| Conditional historical holdout4 views/winner+controls/no retune | `reward156_holdout.py:verify_lock`/`run_holdout`; missing/changed lock tests above. Cancelled: `NOT_OPENED_NO_QUALIFIER`; verifier checks no selection lock or holdout input. Actual heldout replay untested by campaign because prerequisite failed. |
| Report JSON/CSV/Markdown, side attribution/loss clusters/MAE/MFE, fee caveats | `results.json`, `report.csv`, `report.md`, `summary.md`, `diagnostics/`, `cost-path-divergence.json`; source hash and metrics/selection recheck before summary. Commission0/current-spec swap calendar remain assumptions: COST_INCONCLUSIVE. |
| “แล้วอันไหนที่ทำไปแล้วก็ติ๊กใน todo ของ plan ไปด้วย” | Plan frontmatter marks observed steps completed and conditional unexecuted stages cancelled; final review/commit todo completed only after observed commit. |
| CORE_STRATEGY update and existing Demo unchanged | `CORE_STRATEGY.md`6.31 measured protocol/results; scoped diff excludes Demo runners/config/execution/notifications. No broker/MT5 call or live smoke test required by offline changes. |
| Narrow tests, full suite, changed-Python lint/syntax | Narrow65 tests passed; `.venv/bin/python -m unittest discover -s tests`:831tests/21.448s/OK(skipped2), exit0; hash-bound `checks.json`/`unittest.log`, readable `test-results.txt`; Ruff and compileall exit0. No configured static typechecker. |
| Two-axis final review | `../2026-10-04-reward156-profit-survival-code-review.md`: Standards0 remaining, Spec0 remaining; discovered checkpoint/dedup/lock/parity/serialization/audit gaps fixed and re-reviewed. |
| Independent full-artifact verification | `verify_campaign.py` exit0; `validation.json`:584 cells,64 matches,51,010 ledger trades, full metrics/gates/adaptive catalog/finalist selection recomputed,48 v1 parity matches. `-O` rejected before verification/publication. |
| Current branch scoped commit; unrelated owner work preserved | Branch `feature/smc-v2-hardening`; implementation/evidence commit pending final scoped staging. Follow-up completion record adds observed commit SHA. |

## Reproduction

From repository root, with original archived data available:

```bash
.venv/bin/python -m scripts.research.reward156_campaign
.venv/bin/python docs/reviews/reward156-profit-survival-2026-10-04/verify_campaign.py
.venv/bin/python docs/reviews/reward156-profit-survival-2026-10-04/summarize_campaign.py
```

Default output resumes only the exact frozen source/config/input/runtime contract. Do not overwrite producer cells/results/COMPLETE to relabel a failing run. Raw `cells/`, `integrity/`, `diagnostics/` and execution logs are retained locally, excluded from scoped Git commit; full campaign directory is approximately434MB. Committed root reports/catalogs/contracts/validation, exact source snapshots and test-results excerpt preserve the decision and provenance without importing raw backtest dumps. Independent verification requires retained local raw results/log plus archived input data. Concurrent owner's `.gitignore` changes remain unstaged. Essential source config and curated report files are explicitly staged despite namespace ignore rules.

`unittest.log` is retained locally; test-results excerpt and checks record observed summary plus full log SHA. Archived tapes remain under ignored data directory and their hashes under contract/manifests. Source snapshots retain exact bytes, including pre-existing whitespace.

Completion scope is implementation plus finite experiment, not a claim that superior production strategy was found. No prospective test, actual broker fee/fill validation or Demo transition occurred.
