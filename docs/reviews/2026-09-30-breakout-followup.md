# Profit protection and entry quality follow-up — 2026-09-30

**NO_QUALIFIED_STRATEGY. Added 48 unique hypotheses after the earlier 143, total 191. User objective remains unmet.**

## What changed

- Added cost-covering break-even, candle trailing, and runner logic. Protection activates at a completed bar when executable net PnL reaches half the initial admitted risk. Stop only tightens and applies to subsequent ticks. Runner removes TP only after a valid protective stop update.
- Added BUY-only and SELL-only controls, body-dominant and outer-quarter close filters, and previous UTC calendar-day direction. These are research hypotheses, not adopted trading rules.
- Admission still fixed 0.01 lot, 10% cost-inclusive equity cap and 40% UTC daily-loss admission gate. No recovery, order API, notifier or runtime configuration changes.
- Existing default original batch retained. New CLI `--batch protection` runs18 candidates and `--batch entry_quality` runs30. Protocol is persisted before trials; every trial records base/stress metrics and trade ledger.

## Evidence motivating hypotheses

Training baseline ledger, March28–June28 exclusive:56 losers;19 first reached >=0.5R MFE then lost $443.705 in total. Baseline SELL63 trades net +$346.821; BUY51 trades net -$44.185. These observations motivated additional training-guided search. They do not prove profit protection or directional filtering will work. Both directional controls were tested; direction was not silently changed to SELL-only.

## Comparable training results

Each row starts with $200 on March28–June28 exclusive. These are training results, not full six-month returns. Realized RR is average winning net USD divided by absolute average losing net USD.

| Strategy | Net USD | Return | DD | Realized RR | Trades | Stress net USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline48 / SL2.5 / TP3 | 302.64 | +151.32% | 42.54% | 1.189 | 114 | 294.00 |
| Protection, trial4 | 94.99 | +47.49% | 56.88% | 3.389 | 98 | 48.77 |
| Entry quality, trial11 | 330.00 | +165.00% | 20.41% | 0.832 | 47 | 290.11 |
| SELL-only control, trial7 | 249.10 | +124.55% | 28.87% | 1.103 | 59 | 263.63 |

Protection trial4: confirm entry + structural initial stop + break-even. Entry-quality trial11: immediate SELL-only + ATR stop + candle-trail runner. Trial7: immediate SELL-only with fixed TP, no protection. Rows are explanatory examples selected after training, not qualified winners.

Entry-quality trial11 improves profit ($330.004 vs $302.636) and DD (20.412% vs42.537%), but realized RR deteriorates (0.832 vs1.189) and stressed net is lower ($290.115 vs$293.996). It fails the user-selected all-metric criterion. No trial qualified; no candidate validation/final diagnostic was evaluated. No runner-up or relaxed gate used.

## Costs, calibration and research limits

- Base: archived Bid/Ask spread, commission0 assumption for Standard, no added slippage or swap. Stress: extra spread$0.20/oz plus adverse$0.10/oz per market fill. TP fills at target; runner exits are market fills. No actual tariff or cost improvement claimed.
- Modeled spread attribution is a quote proxy embedded in execution prices, not an additional debit or counterfactual profit difference. Historical swap entitlement and broker fills/slippage remain unmeasured.
- Both final runs independently reproduced full baseline $533.621 /266 trades and validated capture/tape/bar identity. Source hashes stayed unchanged throughout each completed run.
- Expansions were based on training-only evidence. All six-month history was previously inspected; no untouched holdout claim. The greater search count increases selection bias.
- Earlier intermediate runs are preserved; final authoritative folders end `_v2` below. The first entry-quality run used bar-open date for previous-day mapping at midnight; corrected results supersede it. The correction did not produce a passing candidate.

## Fix and verification

- Review versus `develop`, scoped to this follow-up, found one shared issue:00:00 entry from23:45 bar used the wrong previous day. Fixed mapping to completed-bar timestamp. RED test reproduced0 trades when1 was expected; GREEN verifies the just-completed previous day. Current/future-day prices cannot affect that guard; missing calendar day rejects.
- Focused suite:26 passed. Full suite after fix:687 ran,685 passed,2 skipped; exit0. Ruff passes. Mypy passes for two source files with `--follow-imports=skip --ignore-missing-imports --check-untyped-defs`; imported library internals are excluded.
- Standards and Spec reviews both rechecked the fix; final findings recorded separately by reviewers. No broad review of unrelated historical branch changes implied.

| Requirement | Regression evidence |
| --- | --- |
| Protective stop after closed bar, no widening | `test_protection_does_not_apply_to_earlier_ticks_or_widen_stop` |
| Net cost-covered SELL break-even | `test_sell_break_even_covers_commission_and_slippage` |
| Runner TP removal and immutable risk | `test_runner_disables_target_only_after_protection_and_retains_initial_risk` |
| Prior-day midnight/future safety | `test_midnight_admission_uses_day_that_just_completed`, `test_prior_day_guard_uses_only_previous_calendar_day` |
| Strict all-metric gate | `test_gate_rejects_rr_regression_even_when_profit_increases` |

## Reproduce

```bash
.venv/bin/python -m scripts.research.tune_breakout_logic --batch protection --output data/protection_NEW
.venv/bin/python -m scripts.research.tune_breakout_logic --batch entry_quality --output data/entry_quality_NEW
```

Local final ledgers: `data/breakout_protection_2026_09_30_v2/` and `data/breakout_entry_quality_2026_09_30_v2/`. Tracked summaries and hashes: `data/research_output/review-fixtures/2026-09-30-breakout-followup-results.json`.

No replacement adopted. Research implementation complete for these batches; strategy-improvement objective remains unmet. Additional work needs a distinct testable hypothesis or independent history, not a claim that repeated search guarantees success.
