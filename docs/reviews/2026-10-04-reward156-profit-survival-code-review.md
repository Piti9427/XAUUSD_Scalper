# Reward156 profit/survival v2 code review

Fixed point: `88bd849ac5286dec441f5e0146a093af382e86d2`. Spec: appended profit/survival v2 section in `.cursor/plans/long-term_macro_gate_99f085f3.plan.md`. Review includes untracked new research modules/config/tests and modified offline cooldown contract. Owner's webhook/scratch edits excluded.

## Standards

Initial findings: interrupted checkpoint result without proof could not resume; protected-exit diagnostic label included unprotected losing SL/end exits. Fixed: unproved result recomputed, proved hash mismatch rejected; metric renamed `swap_on_losing_non_tp_exits`. Six targeted review/checkpoint regressions passed. Reviewer confirmed no remaining Standards findings in reviewed implementation. Small duplicated macro/metric assembly judged acceptable at research scope.

## Spec

Initial findings: global execution dedup removed per-seed factor alternatives; mutable final results invalidated pre-holdout selection hash; parity fixture had insufficient H4 warmup and compared all-zero directions. Fixed: canonical execution catalog plus complete per-seed references; immutable `discovery-results.json` hash; raw nonzero BUY/SELL and warmed H4 signals compared. Reviewer executed10new tests, all passed; no remaining Spec findings in revised implementation.

Backtest/full acceptance require current campaign artifacts and independent verifier; code review alone does not prove performance. Full suite observed829tests/33.668seconds/OK(skipped2). Changed-Python Ruff checks and syntax compilation pass; compilation is not static typechecking.

## Runtime serialization regression

First campaign stopped after104cells before seed-matrix completion: fresh NumPy balance comparisons emitted `numpy.bool_`, rejected by JSON writer. New actual-replay→Campaign.cells→atomic_json regression reproduced failure. Fix casts policy flags to native bool without changing predicates. Test verifies fresh/resumed persisted matrices identical; additional integrated BE-price-zero/swap-negative loss triggers same-day loss circuit and next-day reset. Both reviewers rechecked fix, no new findings. Twelve new tests pass; final full suite831tests/21.448seconds/OK(skipped2). Original source/hash/cells preserved separately; fresh canonical campaign never imports their attestation.

## Artifact verifier review

Standards findings in helper scripts: optimized Python disabled assertions; consumed artifacts and helper sources were not bound to validation manifest; summary test evidence was hardcoded. Fixed: reject `-O`, hash consumed root JSON/verifier/summarizer, read hash-bound checks/log evidence. Both optimized invocations observed RuntimeError/exit1 as intended. Re-review found no remaining Standards finding.

Spec findings: row metrics were not recomputed from cells; input audit could drift from frozen manifests; adaptive catalogs, candidate aggregates and no-qualifier selection lacked full recomputation. Fixed: bind source archives/tapes/bars to frozen manifest; recompute frame/rules/cost/swap/window/metrics, exact seed/variant/reference/combination catalogs, rank/aggregates, finalist budget and complete cell coverage. Ledger verifies cashflow, initial-stop cost risk, admission equity/cap, lot and non-overlap. Re-review found no remaining Spec finding.

Canonical campaign completed exit0. Independent verifier completed exit0:584 cells,64 fresh matches,51,010 reconciled trades,48 exact v1 control comparisons; validation statusVERIFIED. Summary completed exit0. No candidate qualified; conditional candidate half/additional-swap validation and holdout were not run. Detailed acceptance map: `reward156-profit-survival-2026-10-04/completion-audit.md`.

Final Standards and Spec passes reviewed measured outcome, completion map and config SHA/object/behavior digest checks. Both reported no further blocker. Latest verifier rerun completed exit0 with unchanged584/64/51,010/48 counts. Owner concurrently added Git ignore rules for campaign outputs; preserve them unstaged, retain raw cells/proofs/diagnostics locally and commit only source/config/curated reports and exact source snapshots.
