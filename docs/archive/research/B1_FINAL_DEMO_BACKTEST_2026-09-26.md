# B1-FINAL-v1 — current Demo backtest, 2026-09-26

**Result: 553 valid strategy signals; zero admitted trades.** All signals exceed the nominal 1% equity budget at the exact Demo symbol's minimum 0.01 lot. Strategy profitability cannot be assessed for this account from this run. No capital override, risk increase, alpha change, or order submission.

User selected only current Demo $1,173.46; no hypothetical-capital scenario executed.

## Frozen run

- Contract `config/B1-FINAL-v1.yaml`: M15 Donchian30 + RSI14, SL 2.5 ATR14, TP 3.5R, next-bar Ask/Bid entry, one position, equity-HWM risk tiers 1/0.75/0.5/0.25%, stop new entries at DD >=12%, no daily hard stop.
- Actual Exness Demo Bid/Ask capture: 31,780,274 ticks, May 7–September 25, 2026. Warmup May 7–13; scoring May 14–September 25. Broker returned no history before May 7 in the original January-onward request; no earlier-year validation claimed.
- Fresh read-only Demo verification: Exness-MT5Trial7, XAUUSDm, USD equity/balance $1,173.46, contract 100, minimum/step 0.01 lot, tick size 0.001, tick loss/profit value 0.1.
- Executed mode: **Python actual Bid/Ask tick replay**, not MT5 Strategy Tester. Current-spec swap/UTC rollover is a scenario; actual historical commission, slippage, margin/stop rules and rollover are not certified.
- Historical data already exposed. Diagnostic splits are not untouched OOS.

## Account results

| Run | Signals rejected at minimum lot | Trades | Net USD | Ending equity USD | Max equity DD |
|---|---:|---:|---:|---:|---:|
| May 14–June 30 | 194 | 0 | 0 | 1,173.46 | 0% |
| July–August | 258 | 0 | 0 | 1,173.46 | 0% |
| September 1–25 | 101 | 0 | 0 | 1,173.46 | 0% |
| Continuous May 14–September 25 | 553 | 0 | 0 | 1,173.46 | 0% |

Each split starts at the selected Demo equity. Continuous run is separate; do not add it to the split totals. Win rate, PF and expectancy are undefined. Zero DD does not pass acceptance or prove the strategy safe.

## Why every order is rejected

At initial DD zero, base risk is 1%:

```text
risk_budget = 1173.46 × 0.01 = $11.7346
minimum_lot_stop_risk = abs(entry_reference − normalized_SL) × 100 × 0.01
```

Observed minimum-lot nominal SL risk:

| Statistic | USD |
|---|---:|
| Minimum | 12.676 |
| 25th percentile | 18.418 |
| Median | 21.034 |
| 75th percentile | 24.734 |
| Maximum | 59.927 |

All 553 raw requested volumes fall below 0.01; rounding down yields zero lot. No forced minimum lot. RR changes TP, not this fixed SL sizing constraint.

Continuous signal counts: May 64, June 130, July 127, August 131, September 101. Every decision is `RISK_BELOW_MINIMUM_LOT`; tick-gap, busy-position and hard-DD rejection counts are zero. Duplicate deterministic signal IDs: zero. This validates recorded admission decisions, not real broker order idempotency/restart handling.

## Reproduce / artifacts

```sh
.venv/bin/python -m scripts.research.b1_final \
  --capture data/b1_d_exness_ticks_2026_full_retry \
  --output data/b1_final_backtest_demo_2026-09-26_verified
```

Use a new output directory when reproducing; existing artifacts are not overwritten.

Artifacts under `data/b1_final_backtest_demo_2026-09-26_verified/`:

- `manifest.json`: source/config/input/output hashes, actual account snapshot, explicit no hypothetical capital override.
- `continuous_decisions.csv`: all 553 signal IDs, UTC times, direction, ATR, entry quote, normalized SL/TP, budget, raw/floored volume, minimum-lot SL risk and outcome.
- Split decision files, empty trade ledgers with schema, risk-state checkpoints and pinned reference bars.
- `admission_audit.json`: independently checked outcomes, uniqueness, affordability and source/output hashes; links fresh probe hash.
- `COMPLETE`: completed research replay only, not production qualification.

Fresh probe: `data/b1_final_demo_backtest_probe_2026-09-26.json`. Credentials remain in `.env`, absent from artifacts.

## Verification

Focused B1 regression: 31 tests PASS. Full suite: 531 tests PASS. New test `test_decision_ledger_explains_rejections_without_changing_trades` verifies rejected minimum-lot decisions and exact trade-ledger parity with telemetry enabled/disabled. Frozen config hash remains unchanged. No indicator/signal/exit/risk-tier retuning.

**Verdict: INSUFFICIENT_EXECUTABLE_SAMPLE / NO-GO.** No PF, expectancy, Monte Carlo or OOS success claim. MT5 real-tick tester, EA trade parity and forward gates remain pending. Handoff's GetData/OANDA positive figures and 2012–2022 negative history remain unverified external evidence, not results of this run. See [implementation gate status](B1_FINAL_V1_VALIDATION_STATUS_2026-09-26.md).
