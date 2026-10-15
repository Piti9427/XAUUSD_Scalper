# Breakout logic tuning — 2026-09-30

**Status: NO_QUALIFIED_STRATEGY. Implementation completed; requested improvement across all metrics was not achieved.**

## Result

143 unique logic configurations tested. Every candidate earned less training net profit than the baseline, so none qualified. No candidate was selected, no candidate validation/final diagnostic was run, and the core trading contract was not replaced. No orders or notifications were sent.

User criterion: higher net profit, lower tick-equity drawdown, higher realized RR, and better cost-stress results, with fixed 0.01 lot and cost-inclusive 10% risk cap. No weighted score or relaxed fallback was used.

## Comparable training results

All rows below: 2026-03-28 inclusive to 2026-06-28 exclusive, independent $200 account; not six-month or live results. Realized RR is mean winning net USD divided by absolute mean losing net USD; it is not the configured TP/SL ratio.

| Trial / rules | Net USD | Return | Tick DD | Realized RR | Trades | Stress net USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline: immediate, ATR SL, fixed TP | 302.64 | +151.32% | 42.54% | 1.189 | 114 | 294.00 |
| 55: retest, atr SL, failed=0, reset=True, stagnant=16 | 173.49 | +86.75% | 23.09% | 2.172 | 22 | 129.33 |
| 24: confirm, atr SL, failed=0, reset=False, stagnant=0 | 158.07 | +79.04% | 33.82% | 1.140 | 50 | -45.68 |
| 114: confirm, structure SL, failed=2, reset=False, stagnant=8 | 154.91 | +77.45% | 64.17% | 3.282 | 98 | 155.73 |
| 106: confirm, structure SL, failed=1, reset=False, stagnant=8 | 151.54 | +75.77% | 60.09% | 3.805 | 105 | 143.66 |
| 98: confirm, structure SL, failed=0, reset=False, stagnant=8 | 151.19 | +75.60% | 64.87% | 3.217 | 97 | 97.13 |
| 43: confirm, atr SL, failed=2, reset=False, stagnant=16 | 134.16 | +67.08% | 54.28% | 1.905 | 86 | 96.16 |
| 8: immediate, atr SL, failed=1, reset=False, stagnant=0 | 130.78 | +65.39% | 31.97% | 3.183 | 83 | -57.84 |
| 63: retest, atr SL, failed=1, reset=True, stagnant=16 | 124.94 | +62.47% | 18.94% | 3.931 | 23 | 119.34 |

Trial 55 has the highest training profit among candidates: retest entry, reset required after exit, stagnant exit after 16 completed bars with no net progress, ATR SL. Its DD and realized RR improve, but net $173.49 loses to baseline $302.64; stressed net $129.33 loses to baseline $294.00. It is explicitly rejected, not a recommended replacement.

## Implementation and research sequence

- Entry logic: immediate breakout; next-bar confirmation; or retest/reclaim of the original boundary within four completed bars.
- Exit logic: first/two consecutive failed closes, or no-progress exit after 4/8/16 completed bars. All completed bars are considered, including bars with no entry signal.
- Optional reset: a later closed bar must re-enter the frozen range after the preceding exit before another entry. A bar closed before the stop fill cannot rearm.
- SL: baseline 2.5 ATR; structural alternative uses original breakout and entry candle extremes plus one broker tick. Stops and lots are never clamped to pass admission. TP remains 3 ATR.
- New entries require first quote <=90 seconds after close; quote age is zero when observed. Protective exits use first available quote even if late. Bid/Ask sides and SL/TP event ordering preserved.
- Ledger: entry/exit, reasons, fixed lot, admitted risk, net USD/net R, MFE/MAE, commission, modeled slippage, quoted/extra spread attribution. Risk and margin rejections are separate.
- Entry spread enters DD and MAE immediately. TP overshoot cannot inflate account equity or MFE. Commission reserved at entry; expected adverse exit slippage included in risk admission.
- Three disclosed training-guided batches: 23 immediate-entry variants; expanded to 71 with confirm/retest; expanded to 143 with structural SL. Earlier configurations were rerun, not counted as independent evidence. Candidate validation was never opened to guide expansion.
- Finite loop stops on an exhausted declared universe or evaluated selected candidate; no endless search, validation-based retries, or promise of eventual profitability. Source changes during a run prevent COMPLETE evidence. Existing output directories cannot be overwritten.

## Data, baseline and costs

- Saved Exness Demo XAUUSDm Bid/Ask: 45,671,201 raw ticks including warmup; hashes checked against daily capture, exact raw/tape equality, reconstructed 12,100 canonical M15 bars. Only complete 15-minute bars accepted.
- Six-month baseline reproduced: final $533.621, 266 trades, DD 56.8941%, matching archived rounded $533.62 / 266 / 56.89%. Calibration must pass before tuning. Reference hash and numeric deltas stored in results.
- Base: saved spread, Standard commission 0, no added slippage/swap. Tariff reference: https://www.exness.com/standard-accounts/ (verified in preceding session on September 29). No measured historical commission/fill ledger asserted.
- Stress: quotes widened by $0.20/oz plus adverse $0.10/oz per market fill; TP is a limit fill at target. These are declared scenarios, not measured broker costs. Spread attribution is a proxy already embedded in prices; never deduct it again. It is not a counterfactual PnL difference because trade admission/timing changes.
- Historical swap entitlement, actual fills, slippage and historical margin schedules remain unmeasured. Margin is a snapshot-based proxy. Neither fee improvement nor live readiness is proven.
- All six months had been inspected in earlier research. Training-only selection prevents new selection leakage but does not turn this reused history into an untouched holdout. Extra search increases selection bias.

## Verification and review

- Focused public-seam tests: 18 passed. Full suite: 679 ran, 677 passed, 2 skipped; exit 0.
- Ruff passed. Mypy passed for both source files with `--follow-imports=skip --ignore-missing-imports --check-untyped-defs`; external libraries/imported modules are outside this check. Checker installed only in `/tmp/xauusd-tuning-typecheck`, no project dependency edits.
- TDD failures observed and fixed: training selector absent; entry-spread MAE omitted; reset used pre-exit bar; NumPy boolean not JSON serializable; late protective exit skipped; TP MFE overshoot; confirmation/retest and structural-stop feature seams absent.
- Standards review versus develop, scoped to this implementation: 2 initial findings (late exits, MFE overshoot), fixed; final 0 actionable findings.
- Spec review versus develop: 3 initial findings (late exits, cost attribution, baseline comparator), fixed; final 0 blocking findings. Review covers this task, not all older branch changes relative to develop.
- `CORE_STRATEGY.md` updated with research evidence only; operational contract unchanged. Existing unrelated worktree modifications preserved.

| Requirement | Test / evidence |
| --- | --- |
| Completed-bar exit and quote timing | `test_failed_breakout_exits_on_next_quote_without_new_signal`, `test_late_quote_does_not_discard_failed_breakout_exit` |
| Risk, fees, fixed lot | `test_cost_inclusive_risk_rejects_instead_of_clamping_lot`, `test_commission_and_both_market_slippages_are_charged`, `test_structure_stop_uses_candle_extreme_and_still_rejects_excess_risk` |
| Realized RR / DD / ledger | `test_rr_and_dd_use_realized_tp_not_favorable_tick_overshoot`, `test_entry_spread_is_in_trade_mae_and_account_drawdown` |
| Daily halt / midnight | `test_daily_loss_gate_blocks_new_entry_after_losses`, `test_cross_midnight_position_requires_day_start_snapshot` |
| No selection fallback/leakage | `test_training_choice_ignores_validation_and_never_falls_back`, `test_gate_rejects_rr_regression_even_when_profit_increases` |

## Reproduce

```bash
.venv/bin/python -m scripts.research.tune_breakout_logic --output data/breakout_logic_NEW
.venv/bin/python -m unittest discover -s tests -p test_breakout_logic.py
.venv/bin/python -m unittest discover -s tests
```

Complete local run: `data/breakout_logic_tuning_2026_09_30_structural`. Every trial has base/stress ledger JSON. Summary copy: `data/research_output/review-fixtures/2026-09-30-breakout-logic-results.json`.
Results SHA-256: `6b828bd7c8820c7b5eaafca2336b0b55f131c7f2636f95207eb51f9fca24d524`.

## Remaining objective

The requested all-metric improvement remains unmet. The implemented loop produces an honest negative result for these hypotheses. The next justified experiment needs a new economic hypothesis or new independently collected history; repeated searching of this tape must not be presented as validation. No strategy promoted.
