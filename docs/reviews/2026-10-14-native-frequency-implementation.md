# Native MT5 frequency research implementation

Implemented tester-only EA for Trend Pullback M5, UTC Session Breakout and C22
tuned reconstruction, with six Base+swap / COST_SURCHARGE_STRESS+swap templates.
Both EA and native no-order harness compiled using actual MetaEditor under
isolated Wine: **0 errors,0 warnings**, matching source/binary hashes retained.
No Demo sender, broker cost file, frozen research pins or prior runtime fixes
were changed by this implementation. No economic backtest or native harness
execution was performed; no new profitability result or Demo promotion claimed.

Use [MT5 app workflow](../ops/native-frequency-research.md) and
[frozen research spec](../specs/2026-10-14-native-frequency-research.md).
Ignored handoff bundle: `runs/native-frequency-2026-10-14/FrequencyResearch-MT5.zip`
contains two compiled `.ex5` files, four sources, six safe `.set` templates and
README. Templates deliberately reject initialization until explicit cost/UTC/
Tester attestations are entered; changing a view alone does not configure fees.

## Behavior and scope

Shared deterministic MQL5 core consumes complete causal M1 aggregates. Pullback
uses closed H1 trend and two-bar M5 reclaim. Session uses a complete30-minute
UTC range, later breakout then distinct retest, bounded lifetime and one consumed
attempt. Warmup never reconstructs session eligibility. C22 tuned uses rolling
RSI7/ATR14, EMA50 slope/prior96 low, closed H4EMA200; only detector parity is proven.
Native warmup, first-tick daily equity baseline, fills, server swap calendar and
cash-cost stress are separate from frozen Python economic execution.

Fixed0.01, cost-inclusive10% initial cap, one position, native10% daily equity
circuit; one losing completed exit/day for new strategies, unlimited count for
C22 tuned reconstruction. No volume rounding/top-up, recovery, grid or live chart
attachment. Native broker position/history confirms fills/closures; partial,
ambiguous or over-risk fills halt admission and contain only owned residual.
No blind repeat after an ambiguous incident close. Unknown pending requests
invalidate terminal reports; no phantom FILLED event from a send response alone.

Owner selected commission-surcharge Stress: native instant fees add40USD/lot/
roundtrip above explicit base (0.40USD at0.01). Tester applies fees to real simulated
equity; complete native ledger verifies them. This is cash-cost stress, not a claim
of spread/slippage price-path parity. Both views require points swap and declared
long/short/triple-day provenance. Current-spec historical assumptions remain
COST_INCONCLUSIVE; missing metadata, fee/ledger mismatch or execution uncertainty
cannot qualify. Future swap/gap loss is not reserved by the initial10% risk cap.

Native deal/month/summary/event CSVs report cash by deal month and completed
winners by entry month. Requested-full scope remains separate from observed
unobserved/partial/full-span scope. Only observed full spans within requested
full months enter frequency/profit statistics, including zero/warmup months;
first/last market-closure boundary gaps are conservatively partial. Internal
quote coverage remains unverified. Median full-month net is a descriptive
optimizer score, not automatic strategy qualification.

## Requirement and exact test evidence

| Requirement | Evidence |
|---|---|
| Owner `$implement`: native tester research artifact | `FrequencyResearchEA.mq5`, two actual MetaEditor0-error/0-warning builds; six `.set` templates |
| Tester-only/no accidental live attachment; missing cost attestation fails | `test_live_chart_is_rejected`, `test_unattested_costs_are_rejected` |
| Fixed0.01/cost-inclusive10% cap and daily contracts | `test_exact_risk_cap_and_one_cent_over`, `test_minimum_lot_never_rounds_up`, `test_daily_equity_and_strategy_loss_count_contracts` |
| Mirrored causal pullback, swing stop, no missing-bar entry | `test_pullback_reclaim_has_literal_swing_stop`, `test_pullback_sell_is_mirrored`, `test_pullback_missing_bar_never_triggers` |
| Session later retest/complete range/consume/no warmup reconstruction | `test_session_requires_later_retest_and_consumes_attempt`, `test_incomplete_opening_range_never_trades`, `test_session_sell_retest_is_mirrored`, `test_session_consumed_setup_never_reenters`, `test_warmup_cannot_reconstruct_session_eligibility` |
| Complete M1 publication; incomplete bucket fails closed | `test_complete_M1_group_publishes_at_close`, `test_missing_M1_group_never_publishes` |
| C22 rolling indicators/closed macro and actual two-sided fixture parity | `test_c22_native_signals_indicators_and_macro_match_frozen_contract`:5000 bars,3BUY/93SELL, exact directions and macro availability, float indicator tolerances |
| Literal flat/all-gain RSI and SELL executable stop | `test_flat_rolling_RSI_and_mean_TR_literals`, `test_all_gain_RSI_is_100`, `test_c22_sell_precedence_and_closed_macro_gate`, `test_sell_structure_stop_uses_ask_spread` |
| No confirmation of partial/ambiguous/over-risk request | `test_partial_ambiguous_and_overrisk_never_confirm_fill`, `test_unresolved_request_invalidates_terminal_report` |
| Cash includes swap/commission/fee; zero/partial/unobserved monthly scope | `test_monthly_cash_includes_commission_swap_fee`, `test_zero_month_counts_and_partial_month_excludes_frequency`, `test_observed_month_scope_rejects_unobserved_zero_denominator` |
| Public actual-core harness | `test_public_native_cases_pass_without_order_api`:24 named C++-executed cases, same case header native-compiled |

The24 cases execute actual production header through a C++ compatibility shim,
not a duplicated Python trading engine. Same cases form the native test harness.
Host results do not establish native broker adapter lifecycle parity; actual
Tester execution and economic cost/window provenance remain required checks.

## Validation observed

- `make native-frequency-check`:2 tests OK. Strict C++17 build uses
  `-Wall -Wextra -Werror`;24 shared cases pass. Narrow tests ran during vertical
  RED→GREEN slices and review corrections; raw logs under ignored run directory.
- Full repository suite once at end: **`make test`:955 tests/77.569s/OK, skipped2**.
- `make compile deps lint`:PASS. Scoped Ruff format-check and diff whitespace PASS.
  No Python typechecker configured; no typechecking claim beyond C++/MetaEditor.
  Existing repository-wide formatting failures from the prior task were not
  changed or claimed fixed; no aggregate `make check` claim.
- Actual MetaEditor compiled both EA and harness with0 errors/0 warnings and
  fresh nonempty `.ex5` artifacts. Wine process returned1; success evidence is
  explicit compile log plus artifact/source checks, not a claimed exit0.
- Owner approved compiler outside sandbox after `server_mach_port` prevented
  the initial attempt. Only `/tmp/xau-frequency-build/prefix` used; no saved
  credentials, original registry or terminal process copied/launched. UI pipe
  was unavailable, so no app interaction/native Tester execution claimed.
- Nine frozen C22 source pins9/9 MATCH; task-start dirty worktree recorded and
  excluded from task commit. Machine build/validation/bundle files stay ignored.

## Standards

Initial1 finding: unresolved DONE response could remain pending while final report
looked usable. Public terminal report guard and RED→GREEN regression added.
Final independent Standards re-review: **0 remaining findings**; no additional
documented-standard violations or actionable heuristic smells.

## Spec

Initial3 findings: session reconstruction from warmup, unresolved pending report,
requested-only month labels. Each corrected with literal public-boundary
regression. Final independent Spec re-review: **0 remaining concrete findings**,
no material scope creep. Native compilation/runtime/economic evidence remain
separate from host detector parity.

Implementation ready for the documented MT5 app validation. Next: native
no-order harness, then actual paired economic runs with attested Tester settings
and untouched forward data. Existing discovery data must not become holdout.
