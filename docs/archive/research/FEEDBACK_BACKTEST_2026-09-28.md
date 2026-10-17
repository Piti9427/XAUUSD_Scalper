# Strategy comparison and tuning — 2026-09-28

## Scope correction after reading the YouTube transcript

The completed round covered B1 variants, reconstructed EMA variants, legacy MSS and native single-position SMC/GOLD_V2 diagnostics. It did **not** exercise `BasketManager`, the current two-leg Smart Zone Recovery configuration, or a faithful reproduction of the clip's four-leg RSI recovery. The earlier chat phrase “all strategies” overstated this scope. Zero native SMC fills and the B1 +7.19% result cannot be used as performance verdicts for the recovery family. See [transcript comparison](YOUTUBE_VS_B1_2026-09-28.md).

## Decision
B1_TP25 is the best observed trading candidate at the 0.10R scenario in this bounded retrospective tick comparison. It is not qualified: at 0.20R it loses money, development selection admitted no candidate, and all history has previously been exposed. No live configuration changed.

## Method
- Captured Exness XAUUSDm Bid/Ask ticks; continuous scoring 2026-05-14 through 2026-09-25 UTC.
- Hypothetical research equity $10,000; separate $100 admission checks. Neither amount asserts current account equity.
- Same tick engine, B1 drawdown risk tiers, one position, floor volume, no upward minimum-lot clamp.
- Entry immediately after completed M15 signal; exact chronological tick exits.
- Spread from captured quotes plus current swap-spec scenario. Extra 0/0.10/0.20R cost reserved in sizing and charged inside replay, so costs affect equity and subsequent admissions.
- Historical commission, margin approval and slippage remain unverified. This is Python replay, not MT5 execution certification.

## Continuous results at 0.10R extra cost
| Strategy | Trades | Return | PF | Tick equity DD |
|---|---:|---:|---:|---:|
| B1_TP25 | 164 | +7.19% | 1.082 | 6.93% |
| EMA_RSI_RECONSTRUCTED | 0 | +0.00% | N/A | 0.00% |
| LEGACY_MSS | 23 | -0.45% | 0.958 | 4.38% |
| B1 | 133 | -2.16% | 0.960 | 11.16% |
| LEGACY_MSS_TP2 | 23 | -5.23% | 0.562 | 6.92% |
| EMA_CROSS | 147 | -6.80% | 0.837 | 9.81% |
| B1_SL2 | 185 | -6.85% | 0.843 | 10.88% |
| EMA_CROSS_TP2 | 145 | -8.21% | 0.730 | 10.78% |

## Feedback and tuning
- Baseline B1: SL 2.5 ATR, TP 3.5R. B1_SL2 changes only SL; B1_TP25 changes only TP to 2.5R.
- B1_TP25: +25.90% at 0R, +7.19% at 0.10R, -6.32% at 0.20R. Cost fragility remains unresolved.
- EMA crossover alone and its TP2 variant failed continuous cost-adjusted comparison.
- Literal EMA crossover with RSI <=35 for buys / >=70 for sells produced zero signals. This is a declared README reconstruction, not verified historical intent.
- Actual legacy detector is wick rejection + MSS + EMA50, not EMA crossover. Production check_signals is called with its closed-bar-at-minus-two convention; EMA/ATR use research smoothing, not pandas_ta parity. Legacy spread admission is not reproduced; quote costs are replayed.
- Existing legacy OHLC backtester is not used for ranking because it tests TP before SL on ambiguous bars, has no single-position restriction and supplies zero spread.
- No risk increase, martingale, grid, or live promotion used to manufacture a winner.

## Selection discipline
Development May 14–31, validation June–August, confirmation September 1–25. Split chosen to respect SMC foundation window boundaries. Development is short: 11 baseline / 16 B1_TP25 trades at 0.10R. Frozen criterion requires >=20 trades, positive net, PF>1 at all costs, DD<12%, no stop. No candidate passed; selection_locked.json was written before later-window results. Later-window leader is descriptive, not an out-of-sample winner.
Each split resets capital/state. Do not sum split returns. Continuous results above carry equity/HWM/positions across month boundaries.

## Account feasibility
$100: zero trades in all 72 split/cost scenarios for that account (144 scenarios total across both capitals). Baseline continuous replay rejected 553 signals below minimum lot risk. Zero PnL is not a profitable or safer winning strategy.

## Verification
- 25 focused B1/reference tick tests passed.
- Full repository unittest suite: 603 passed (see tests.log).
- Prefix-causality checks at three cuts passed for all tick signal families.
- Every nonempty research ledger checked: risk plus cost reserve <= budget, and initial equity plus cumulative net equals balance.

## Artifacts
- `data/feedback_comparison_2026-09-28/contract.json`: predeclared candidates, windows and assumptions.
- `tick_metrics.csv`: 144 split scenarios.
- `continuous_metrics.csv`: 24 continuous scenarios.
- Per-run CSV ledgers; `selection_locked.json`.
- `data/feedback_round_2026-09-28/continuous_check.py`: continuous reproduction.

## Next research iteration
Keep B1_TP25 as research-only lead. Obtain a longer, genuinely unseen broker dataset plus measured costs before selecting or promoting another version. A new development round may test hypotheses, but already inspected validation/confirmation must not be relabelled untouched.


## SMC/GOLD_V2 native diagnostics and feedback round 2

All 18 window/profile/capital runs completed. SMC_NATIVE, GOLD_V2 and GOLD_V2_TP2 each produced zero fills in development, validation and confirmation. Zero-trade PF=1 from the native summary is a placeholder, not evidence of break-even performance.

Validation GOLD_V2 at research equity $10,000 detected 7 setups and admitted 7 simulated pending orders; all 7 expired (`NO_FILL_TTL`), none filled. Main detector rejections: no_sweep 4,835; no_mss_displacement 588; choch_required_not_met 449. Development also had 354 H1 warmup rejects. September produced no qualifying setups. Native SMC diagnostics use fixed 0.5% risk, OHLC fills and their own circuit breakers, so they are not ranked against B1 tick equity.

Follow-up hypothesis: four-bar TTL may expire before price returns to entry. Tested TTL 4/8/12 on the already inspected June–August period, $10,000, all other GOLD_V2 settings unchanged. Baseline TTL4 exactly reproduced the original funnel; all three yielded zero fills. Increasing TTL alone did not resolve entry scarcity. This is retrospective diagnosis, not new validation; live TTL unchanged.

`require_choch=True` selects opposing liquidity pool targets, so changing `tp_r` alone is inactive for that target path. GOLD_V2_TP2 is a control showing this parameter does not tune the current CHOCH target rule.

Native code also requires a separate causality audit before promotion: the backtester precomputes whole-day London pools, while pool target selection can consume those fields. This run does not certify absence of lookahead in native SMC; zero fills provide no execution-profit evidence either way.

Artifacts: `data/feedback_smc_2026-09-28/metrics.csv`, per-run funnels and input bars; `data/feedback_ttl_2026-09-28/results.json` and ledgers.

## Research runtime improvement and final checks

The first native SMC run was interrupted during validation after profiling found repeated whole-history structure replay. Completed tick outputs and original source snapshot were preserved. SMC was rerun to completion using process-local precomputed states; production modules were not edited.

- Same production `apply_close_break` transition, same exclusive pivot-confirmation boundary.
- 1,820 synthetic state-prefix comparisons across 20 seeded sequences: identical.
- 24 actual-data prefix comparisons: identical.
- Full final state for all three actual M5 windows: identical to original replay.
- Validation window, 18,120 bars: all states precomputed in 0.0484s; original final-state replay alone took 30.4953s on this run. This is a component measurement, not an end-to-end speedup claim.
- Final focused B1/tick/SMC tests: 38 passed. Syntax and `git diff --check` passed.
- Only research runners and evidence/report artifacts added. No live settings, risk budgets, production strategy or notifier changed.

## Reproduction

```bash
.venv/bin/python -m scripts.research.b1_final \
  --capture data/b1_d_exness_ticks_2026_full_retry \
  --output data/b1_feedback_baseline_NEW --initial-equity 100
.venv/bin/python -m scripts.research.feedback_round \
  --baseline data/b1_feedback_baseline_NEW \
  --output data/feedback_comparison_NEW
```

The updated round runner calls the checked SMC acceleration automatically. Continuous and TTL follow-up scripts in `data/feedback_round_2026-09-28/` retain exact experiment paths; change their output paths before a new run. Existing evidence directories are intentionally not overwritten.
