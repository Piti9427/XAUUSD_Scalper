# B1-FINAL-v1 — simulated $100 deposit

User requested simulated capital $100 instead of current Demo $1,173.46. Explicit `--initial-equity 100` changes only the historical research deposit. Original Demo/account and symbol snapshots remain unchanged. No broker deposit, order, risk-tier or alpha change.

Frozen B1: Donchian30 + RSI14, M15, SL 2.5 ATR14, TP 3.5R, next-bar executable Bid/Ask, max one position. Equity-HWM DD risk tiers 1/0.75/0.5/0.25%; DD >=12% latches stop-new-entries; daily hard stop disabled.

Executed:

```sh
.venv/bin/python -m scripts.research.b1_final \
  --capture data/b1_d_exness_ticks_2026_full_retry \
  --initial-equity 100 \
  --output data/b1_final_backtest_usd100_2026-09-26
```

Actual broker capture: 31,780,274 Bid/Ask ticks, May 7–September 25, 2026. May 7–13 warmup; scoring May 14–September 25. This is Python real-tick replay, not MT5 Strategy Tester. Dataset exposed; commission/slippage/historical margin and rollover remain unverified.

| Window | Signals rejected below minimum lot | Trades | Ending simulated equity |
|---|---:|---:|---:|
| May 14–June | 194 | 0 | $100 |
| July–August | 258 | 0 | $100 |
| September 1–25 | 101 | 0 | $100 |
| Continuous May 14–September 25 | 553 | 0 | $100 |

Continuous and splits are separate accounts; do not double-count. Net $0, DD 0%; win rate/PF/expectancy undefined because no executed sample. These values do not demonstrate strategy safety or profitability.

## Why no entries

There are **553 signals**, not zero signals. At DD zero:

```text
risk budget = $100 × 1% = $1
XAUUSDm minimum volume = 0.01 lot
contract size = 100 oz/lot
minimum lot exposure = 1 oz
nominal SL risk = |entry − normalized SL| × 1 oz
```

Across the actual signals, minimum-lot SL risk is **$12.676–$59.927**; median **$21.034**. That is **12.676–59.927% of the simulated $100 portfolio**, before stop gaps/additional fees. Budget permits only $1. Raw lot is below 0.01 for all signals; round down gives zero. Every outcome is `RISK_BELOW_MINIMUM_LOT`, with no tick-gap, busy-position or hard-DD rejection and no duplicate signal ID.

Reducing the deposit reduces the allowed dollar risk; it does not reduce broker minimum exposure or the ATR stop distance. RR affects TP, not SL affordability. Forcing 0.01 lot would violate the frozen risk policy, so it is not done. No conclusion about the alpha's win rate/expectancy follows from this rejected sample.

Artifacts: `data/b1_final_backtest_usd100_2026-09-26/manifest.json`, `continuous_decisions.csv`, split decisions/ledgers, reference bars and checkpoints. Manifest separates simulated `initial_equity=100` / `hypothetical_capital_override=true` from actual `account_snapshot.equity=1173.46`. Source/input/output hashes checked; all 553 budgets exactly $1 and all 553 minimum-lot risks above budget.

Verification: 32 focused B1 tests PASS, 532 full-suite tests PASS. `test_explicit_simulated_deposit_preserves_broker_snapshot` checks the capital override, unchanged actual snapshot, defaults and invalid deposits. `test_decision_ledger_explains_rejections_without_changing_trades` checks admission traces and telemetry parity. Frozen strategy config hash unchanged.

Verdict: **ACCOUNT/SYMBOL/RISK POLICY INCOMPATIBLE FOR OBSERVED SIGNALS; no executable sample, NO-GO.** This does not justify raising risk or changing the frozen SL to manufacture trades.
