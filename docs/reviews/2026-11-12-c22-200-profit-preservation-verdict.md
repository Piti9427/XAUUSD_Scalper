# C22 $200 profit preservation: bounded tuning verdict

**Verdict: no qualifying improvement. Retain native; no runtime adoption.**
Both primary mechanisms and their single derived iterations were evaluated.
Both LOYO campaigns selected native in all seven folds. No new candidate meets
the owner's per-segment net/DD criteria. This is not evidence that native is
profitable on a continuous $200 account.

## Contract and evidence

- Reference: RulesID `26b8bcd69e043653`; native and candidate each start at $200.
- Fixed 0.01 lot, cost-inclusive 10% cap, daily 10%/loss2, cooldown and native
  signal generation retained. BUY hypotheses do not change SELL management;
  they can change later SELL eligibility through equity and position paths.
- Each of seven historical segments must have net >= native and Max DD <=
  native in both base+swap and stress+swap, with at least one strict net gain.
  Raw comparison tolerance: 1e-8. A lower loss somewhere cannot excuse a worse
  result elsewhere. Segment lengths differ; these are not seven calendar years.
- Continuous evaluation starts at $200 once, with no deposits/resets. Indicators
  are prepared once across combined bars. Open positions, swap from original
  entry, equity peak, daily losses, cooldown and polling state carry across
  boundaries. Only the final endpoint liquidates remaining exposure.
- Dates: 2020-01-01 through 2026-10-24 exclusive. All history has already been
  viewed; LOYO guards selection, not catalog-design bias or future profitability.
- COST_INCONCLUSIVE: archived POINTS swap long -567.4, short 0, point 0.001;
  UTC-midnight preceding-business-day calendar, Wednesday triple posts Thursday.
  These are declared sensitivity assumptions, not verified historical/current
  broker rates or Swap-Free entitlement. No new no-swap economic cells were run.
- Base uses recorded Bid/Ask; stress adds 0.20 spread and 0.10 adverse slippage.
  Both modeled commission rates are zero in the pinned archived scenario.

Artifacts (ignored, preserved locally):

- [Verified primary protocol](../../runs/c22-profit-preservation-200-2026-11-12/primary-verified/protocol.json),
  SHA256 `f86bcf6eca3ed2cae38d394b93d61a86668a08e0ee9f643bfcdb01de89001d8d`.
- [Derived protocol](../../runs/c22-profit-preservation-200-2026-11-12/derived/protocol.json),
  SHA256 `63659edaed2913e0e6649e2f9eae101da59fa129ddd1a21479744c8d848a2ae0`.
- Each phase contains result.json, per-cell full ledgers, attribution.json,
  run.log, input/source hashes and source snapshots. Derived protocol binds the
  primary attribution hash and the rationale before its economic evaluation.
- [Failed-cell event diagnosis](../../runs/c22-profit-preservation-200-2026-11-12/rejection-diagnostics/result.json)
  reproduces identical ledgers for all 20 regressing cells, then matches missing
  native entries to the candidate's actual admission events. No unmatched events.

## Results

Values below are **net USD**, after modeled swap, for independent $200 starts.
2024b25 covers 2024-09-01 through 2026-01-01 exclusive.

| Case | 2024b25 base / stress | 2026 base / stress | Regressing cells of 14 |
| --- | --- | --- | --- |
| Native | 927.80 / 773.91 | 699.21 / 24.92 | Reference |
| BUY intrabar BE 1R | 934.48 / 710.25 | 73.10 / 75.12 | 7 |
| BUY gate after any daily loss | 915.70 / 754.47 | 73.58 / 20.90 | 6 |
| Derived BUY intrabar BE 1.5R | 927.80 / 773.91 | 699.21 / 24.92 | 0; no strict gain |
| Derived BUY gate after BUY loss | 926.48 / 765.46 | 73.58 / 20.90 | 7 |

BE1.5R preserves every independent cell's net and DD exactly, but adds no strict
profit gain, so it fails improvement. Its occasional ledger protection metadata
differences do not establish an economic benefit.

Continuous accounts from $200 show why independent starts alone are misleading:

| Case | Final balance base / stress | Max DD base / stress |
| --- | --- | --- |
| Native | 17.30 / 16.59 | 94.35% / 94.45% |
| BUY BE 1R | 15.76 / 16.57 | 94.74% / 94.46% |
| BUY gate after any daily loss | 15.82 / 17.98 | 94.86% / 94.36% |
| Derived BUY BE 1.5R | 17.30 / 16.59 | 94.35% / 94.45% |
| Derived BUY gate after BUY loss | 15.96 / 16.76 | 94.81% / 94.54% |

All five native independent losing segments remain negative in both views.
Reducing some historical losses did not repair the continuous account.

## Rechecked failure mechanisms

Trade attribution reconciles every net difference into matched-trade changes,
removed native trades and replacement candidate trades, separately by side.

- **BE1R, 2026 base:** retained BUY net improves only $0.62. Removed native BUY
  contribution is -$103.95 and replacements contribute -$11.37. For SELL,
  110 missing native trades account for -$567.45 and replacements add $56.04.
  Total change is -$626.11. This is primarily path/admission damage, not a direct
  change to SELL management.
- Event reproduction confirms 163 missing native entries (both sides, including
  69 winners) were rejected by the candidate's risk cap; their native net was
  +$686.93. Total risk-cap rejections rise from 71 to 420. These counts include
  entry opportunities outside the native-trade set, so they are distinct metrics.
- **BUY gate, 2026 base:** only six missing native entries are directly
  suppressed by the daily gate; their native net was +$63.72. Another 148 missing
  entries are rejected by the changed risk-cap path, with native net +$597.73.
  Total risk-cap rejections rise from 71 to 395. Restricting the gate to prior BUY
  losses does not change that year's result.
- Derived BE1.5R tests a later trigger to reduce premature exits/displacement.
  Derived BUY-only-loss gating tests a narrower causal throttle. Both were
  frozen before execution; neither qualifies. The per-mechanism iteration
  budget is exhausted. No new grids, combinations or relaxed gates were added.
- The continuous native base path has a 1,193-day span of consecutive observed
  risk-cap rejection events. This is an **event-span proxy**, not proof that
  trading was impossible at every intervening instant. Full market availability
  and live execution parity are not established by this replay.

## Engineering checks and limitations

- Verified primary and derived adapters each match native ledger, admission
  events, final balance and all-tick Max DD in **14/14 independent control cells**.
  Every independent and continuous ledger reconciles to $200 + summed net.
- Earlier continuous research runners carried balance but closed positions and
  reset daily controls at segment boundaries. Their continuous results are not
  substituted for the new carry-aware paths.
- Review found a mid-poll-bucket carry bug: a new chunk could create an extra
  BUY poll. A synthetic RED regression reproduced $199.90 split versus $196.80
  whole. Persisting last observed tick fixes it; both now return $196.80.
- Initial primary execution failed while serializing numpy.bool_ after cells
  completed. Preserve that attempted run under primary/ as failed evidence.
  Use primary-verified/ for verdicts: it reran the same catalog after the polling
  and serialization fixes, with a fresh frozen protocol. This engineering rerun
  did not add candidates or consume an extra tuning iteration.
- Focused preservation suite: **7 tests passed**. Neighboring replay regressions
  also passed before the final regression addition. Full working-tree suite:
  **1,659 tests, OK, skipped 2**, using `.venv/bin/python -m unittest discover -s tests`.
  [Full log](../../runs/c22-profit-preservation-200-2026-11-12/full-tests.log).
- Mypy with `--check-untyped-defs --follow-imports=silent --ignore-missing-imports`
  passes the two new research modules. Standards and Spec review rechecked the
  polling fix; zero remaining blocking findings in the reviewed code.
- The full suite includes the owner's pre-existing uncommitted availability
  fixes. Those changes were preserved and are not part of this research commit.
- This is research-engine parity, not MT5 fill/latency, broker lifecycle,
  operational availability or Telegram verification. No VM access, manual MT5
  smoke test, deployment, new shadow observation or external publication occurred.
- Failed campaigns preserve outputs and require a fresh directory; automatic
  checkpoint resume is not implemented. Local ignored inputs and archived cells
  are prerequisites; source snapshots preserve the exact executed Python files.

## Next decision

Retain native under the existing Demo contract. No candidate is eligible for
forward adoption from this campaign. Another search requires a new, explicitly
bounded hypothesis/budget; do not relabel equality or a relaxed gate as success.
The Wayfinder tickets retain their HITL status pending owner review of these
findings; this report does not substitute for the owner's decision.

## Requirement / evidence checklist

All test names below belong to tests/research/test_c22_profit_preservation.py.

| Requirement | Evidence |
| --- | --- |
| Native parity, open-position/swap carry and ledger reconciliation | test_off_matches_native_and_split_carries_open_trade_swap_and_daily_state |
| Daily loss/cooldown carry | test_daily_losses_and_cooldown_survive_chunk_boundary |
| No extra poll at a chunk boundary | test_split_inside_poll_bucket_cannot_create_an_extra_buy_poll |
| BUY BE research leaves SELL management intact | test_buy_tick_be_saves_retracement_without_changing_sell_management |
| Strict net/DD gate rejects regression, equality and nonfinite metrics | test_strict_gate_rejects_one_bad_year_and_no_change |
| Train-only selection and native fallback | test_selection_uses_training_only_and_falls_back_to_native |
| Missing swap / noncontiguous carry fails closed | test_missing_swap_and_noncontiguous_carry_fail_closed |
| Economic checks and 20 failed-cell reproductions | Phase result.json, attribution.json and rejection-diagnostics/result.json |
| Full-suite validation | .venv/bin/python -m unittest discover -s tests: 1,659 tests, OK (skipped=2) |
