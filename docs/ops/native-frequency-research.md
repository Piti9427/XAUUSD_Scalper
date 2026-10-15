# Backtest frequency strategies directly in MT5 / Wine

Research only. EA rejects live/Demo chart attachment. It does not use the Python
sender, Telegram, account credentials or Python chart downloads. Keep the existing
`make bot-execute` process untouched. A CLI-launched second terminal must use a
separate data folder/prefix; do not close the Demo terminal to run this research.

## Compile and unit validation

In MetaEditor, place these four files together in a research folder under
`MQL5/Experts`: `FrequencyResearchEA.mq5`, `FrequencyResearchCore.mqh`,
`FrequencyResearchTests.mq5`, `FrequencyResearchCases.mqh` from repository `mql5/`.
Compile both `.mq5` files with F7; require0 errors. Run `FrequencyResearchTests`
in Strategy Tester first; Journal must show every named case PASS and
`FR_TEST_RESULT failures=0`. This harness submits no orders and is a unit fixture,
not an economic backtest. Host validation: `make native-frequency-check`; C++
compiles the actual shared header, then Python compares C22 signals/indicators
against the frozen contract. Host success is not MetaEditor or broker parity.

## Economic run settings

Select `FrequencyResearchEA` in **Strategy Tester** (Ctrl+R), not a chart.
Use XAUUSD broker symbol, USD deposit200, same account leverage/spec for all
strategies, **Every tick based on real ticks**, **Profit in pips OFF**.
Initially Optimization OFF, consistent evaluation dates and70-day M1 warmup
history. EA builds complete UTC M5/M15/H1/H4 from broker M1 bars; missing minutes
do not become filled bars. Date inputs are UTC epochs; Tester date range is
broker/server time. Align both explicitly and inspect actual first/last tick
epochs in output. A full observed UTC span is not proof of complete internal quote coverage.

Load one of six `.set` templates in `config/native-frequency/`:
pullback/session-breakout/c22-tuned, each base-swap/cost-stress-swap. Templates
intentionally fail initialization until actual assumptions are supplied:

- `CostsAttested=true` only after checking native Tester symbol swap mode **Points**,
  long/short rates, point/contract size and triple weekday. Enter exact
  `SwapLongPoints`, `SwapShortPoints`, `SwapTripleWeekday`, and named `CostSource`.
  Explicit short0 is valid; missing metadata is not0. Current-spec historical
  application remains COST_INCONCLUSIVE.
- `BaseCommissionUSDPerLotRoundTrip`: explicit base commission+fee in USD/lot/
  roundtrip, including0 when justified. Under **Advanced testing settings →
  Commission**, use instant per-volume USD/lot charges. For symmetric entry/exit,
  configure half the declared roundtrip rate on each side. Daily/monthly batch
  commission booking is unsupported; ledger/balance mismatch invalidates report.
- **Base+swap**: native roundtrip commission equals base declaration.
  **COST_SURCHARGE_STRESS+swap**: native roundtrip commission equals base+40USD/lot
  (add20USD/lot on each entry/exit, hence add0.40USD per0.01 roundtrip). The same
  base declaration stays in the EA input; selecting Stress adds40 internally for
  risk validation. EA verifies actual complete-ledger commission+fee. Setting
  `CostView` alone does not change Tester's fee table; mismatch invalidates run.
  This is cash-cost stress, not widened quotes/adverse fill/SL-trigger parity.
- `ServerOffsetAttested=true` and fixed `ServerUtcOffsetMinutes` only when correct
  over the whole tested period. Current offset cannot attest historical DST.
  Split periods with different offsets; each has its own capital/state and is
  not a continuous compound result. A variable-offset continuous replay is outside v1.
- `TesterEconomicsAttested=true` only after verifying real-tick mode, pips OFF,
  native instant fees, swap and correct Tester/evaluation windows.

Run all three strategies under both views, then freeze one candidate's parameters
and use Tester's Forward period on data not consumed by tuning. September2024–
October2026 data has already been used extensively; it is discovery, not a new
holdout. Optimizer objective is median full-observed-month net within requested scope, subject to
report validity; this is not an automatic profitability/selection gate. Session
UTC starts are fixed research windows, not DST-adjusted London/New York opens.

## Read results

Native Tester **Results / Graph / Report** reflect its actual orders, fees and
swap. Journal names a unique output prefix for each pass. Agent sandbox
`MQL5/Files` holds `<prefix>_events.csv`, `_deals.csv`, `_months.csv`, `_summary.csv`.
Save exported machine artifacts under ignored `runs/<campaign>/`; write only a
synthesized markdown verdict under `docs/reviews/`.

Summary: native net cash, every-observed-tick equity DD including final equity,
mean entries/full observed UTC month within requested scope, including zero/warmup months, profitable
month ratio, median monthly net, worst month, requested/actual tick scope and halt.
Monthly CSV distinguishes requested_full, observed_scope (0 unobserved,1 partial,
2 bracketed full span), and included_full_month. An entirely unobserved month
never enters the denominator; a first/last month lacking bracketing observed
ticks is conservatively partial, including market-closure boundary gaps.
Monthly cash is booked by deal month; a completed winning position belongs to its
entry month, after all opening/closing fees/swap. Partial months remain separate.
`INVALID` / ambiguous/partial fill / commission mismatch / unresolved exposure
cannot qualify. `COST_INCONCLUSIVE` is descriptive research, not approval.

No C22 Demo contract change, per-day baseline recovery, recovery baskets, topups,
lot resizing or real-money operation. Initial10% risk does not reserve future
swap or guarantee gap losses stay below10%. New strategies enforce one losing
completed exit/UTC day; C22 tuned reconstruction keeps its archived unlimited count.
Native first-tick daily baseline, warmup, fee stress and server swap calendar
differ from Python archived execution: only signal parity has a test contract.

Contract: [native research spec](../specs/2026-10-14-native-frequency-research.md).
MT5 [testing/real ticks/forward/commission settings](https://www.metatrader5.com/en/terminal/help/algotrading/testing).
