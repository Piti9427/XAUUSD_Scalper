# Historical review reproducers

Executable Python belongs here; human conclusions remain `docs/reviews/*.md`.
These programs were relocated from `docs/reviews` with repository/fixture paths
updated. They are historical diagnostics, outside the current Demo interface.

| Script | Scope |
| --- | --- |
| reproduce_master_pro_v6_review.py | Transcribed Pine branch counterexamples; not native Pine execution |
| reproduce_expansion_breakout_review.py | Frozen Git revision versus current detection and mutation checks |
| reproduce_backtest_readiness.py | Literal accounting/causality regression fixtures |
| reproduce_demo_auto_order_plan_review.py | Archived remediation-plan markers |
| compare_python_refactor.py | Historical detector/proxy performance comparison; `--help` is safe inventory |

Run from repository root, e.g.
`python scripts/debug/reviews/reproduce_master_pro_v6_review.py`.
Do not rerun historical proxy comparisons as a new economic evaluation: every new
economic campaign requires modeled swap in both base/stress and outputs in
`runs/<campaign>/`. Archived versions remain evidence, not current qualification.


## Validation on 2026-10-15

- Master Pro branch counterexamples:7 reproduced,exit0.
- Archived remediation-plan marker checks:PASS,exit0.
- Comparison CLI `--help`:PASS;no new proxy/economic benchmark executed.
- Accounting reproducer:historically stale fixture produces no trade (`IndexError`).
- Expansion reproducer:old detector revision rejects current fixture keyword
  `require_choch` (`TypeError`).

The last two failures were reproduced with pre-migration source and equivalent
fixture-path resolution. They predate this move; they are historical diagnostics,
not current acceptance commands. Current behavior is covered by grouped suites;
no strategy/default changes were made to force old counterexamples to pass.
