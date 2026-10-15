# Reward156 paired tuning code review

Starting revision: `ab4916c178ffb1ca926f74ae36742fd27af3c954`.
Spec: `.cursor/plans/long-term_macro_gate_99f085f3.plan.md`.
Scope: opt-in replay swap/telemetry, config-driven research harness/catalog and regression tests; current Demo untouched.

## Standards

Initial findings: required CORE_STRATEGY research record absent; resume fingerprint omitted public replay facade and numerical runtime. Resolved by CORE_STRATEGY6.30, transitive source hashes/snapshots and Python/NumPy/pandas versions in behavior fingerprint. Follow-up reviewer found no additional actionable Standards defect. UTC, fixed0.01, cap10%, daily20% and independent strategy execution preserved. No execution/notifier API added.

## Spec

Initial findings: ordinary CLI could emit COMPLETE without mandatory fresh repeats; replay dispatch omitted from resume fingerprint. Resolved by mandatory --repeat before artifact creation, per-proof behavior/result/status validation, proof-count check before COMPLETE and added facade hash. Follow-up reviewer found no additional actionable Spec defect. Traced detectors -> shared environment/replay -> swap equity/settlement -> admission -> verdict/artifacts; complete closed-H4 availability and baseline-before-tuning order verified by source review.

## Executed verification

- `.venv/bin/python -m unittest tests.test_reward156_tuning`: 9 tests passed.
- `.venv/bin/python -m unittest tests.test_reward156_tuning tests.test_breakout_logic`: 52 passed before final additional protocol test.
- `.venv/bin/python -m unittest discover -s tests`: 819 tests,20.881s,OK(skipped=2).
- `.venv/bin/ruff check scripts/research/rollover.py scripts/research/breakout_replay.py scripts/research/reward156_tuning.py tests/test_reward156_tuning.py`: passed.
- `.venv/bin/python -m compileall -q scripts/research/reward156_tuning.py scripts/research/rollover.py scripts/research/breakout_replay.py`: passed. Syntax compilation, not static typechecking; no configured typechecker found.
- `git diff --check`: passed before final generated-result/docs updates; repeated before commit.

Tests: `test_default_replay_unchanged` executes starting revision source against same synthetic base/stress inputs; `test_swap_changes_next_risk_admission` checks swap debit, finalbalance/DD, next cap rejection and timestamped telemetry; `test_h4_closed_boundary_and_future_invariance` / `test_h4_incomplete_bucket_and_warmup` check timing, future mutation, incomplete buckets and EMA200 warmup; `test_contracts_share_environment_but_keep_signals_and_exits` checks distinct detectors/targets/protection and shared risk pins; `test_comparison_rejects_loss_and_missing_metrics` checks fail-closed qualification; `test_risk_blocked_days_require_all_signals_and_no_position` checks observational freeze classification; `test_completion_requires_fresh_repeat_protocol` rejects unverified completion before writes.

Optional archived find-untested-sources helper attempted once; unavailable tree-sitter-language-pack. No dependency installed for optional discovery; bounded source/test inventory inspected directly.

Matrix results are separate evidence in `reward156-tuning-2026-10-04/`; reviewers did not claim measured profitability or live parity. See COMPLETE.json and report.md after execution.

Final test-quality pass strengthened shared-environment contract test to assert actual SELL detections and Reward156 BUY detections on deterministic mixed data. First proposed random fixture had zero BUY; replaced fixture seed42 and reran narrow plus full suite to clean exits. All120matrix cells/120freshmatches and source/checkpoint hashes audited; ledgers reconcile net to finalbalance, swaps reconcile attribution, risk<=10% and lot0.01 throughout. All candidates fail frozen qualification; holdout unopened.

Implementation/artifacts committed as8aacf22 on existing feature/smc-v2-hardening. Scoped active-file whitespace checks pass. Whole staged artifact check reports one existing extra EOF blank line in archived source_snapshot/scripts/strategy.py; preserved byte-for-byte because source hash is provenance, not edited to satisfy formatting. Owner webhook test and unrelated root-cause/scratch files excluded from commit. Final plan completion recorded after observed commit.
