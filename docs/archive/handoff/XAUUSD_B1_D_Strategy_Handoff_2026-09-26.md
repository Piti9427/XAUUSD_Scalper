# XAU/USD EA Strategy Handoff
## Primary Focus: B1 — Donchian30 + RSI
### Secondary: D — ATR Expansion1.5 + RSI + FVG

**Status:** Strategy selection closed; validation/engineering phase active  
**Primary priority:** Validate and production-engineer B1 first  
**Real-money status:** **NO-GO**  
**Last consolidated context:** 2026-09-26

---

# 0. TL;DR

The strategy discovery phase is considered closed.

Final shortlist:

1. **Primary EA — B1: Donchian30 + RSI**
2. **Secondary EA — D: ATR Expansion1.5 + RSI + FVG**

Everything else is removed from the primary production path unless future evidence justifies reopening research.

Current focus is **B1 only**.

B1 has encouraging recent results across Dukascopy and OANDA, but fails the 2012–2022 long-history robustness test. Therefore the correct interpretation is:

> **B1 appears to be a regime-dependent breakout strategy, not a timeless always-on gold strategy.**

The next phase is not “find more strategies”. The next phase is:

```text
Freeze B1 specification
        ↓
Implement reproducibly
        ↓
Exness MT5 real-tick backtest
        ↓
Realistic transaction-cost validation
        ↓
Walk-forward / out-of-sample
        ↓
Regime segmentation
        ↓
Monte Carlo / robustness
        ↓
Demo forward test
        ↓
Backtest-vs-live execution reconciliation
        ↓
Only then consider small real-money deployment
```

---

# 1. Project Objective

Build a production-grade automated XAU/USD trading system for MT5 that:

- is deterministic and reproducible;
- avoids discretionary interpretation;
- uses risk-controlled entries/exits;
- can survive realistic spread, commission, swap, slippage and execution constraints;
- can be validated using multiple independent market-data sources;
- can be monitored and debugged in production;
- does not rely on hidden look-ahead or data leakage;
- can recover safely from terminal/VPS/network restarts;
- has explicit evidence before any real-money deployment.

The current architecture has two retained candidates:

```text
                        XAU/USD
                           │
                           ▼
                    REGIME / RISK
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       BREAKOUT / TREND             VOL EXPANSION
             │                           │
             ▼                           ▼
     B1: Donchian30 + RSI       D: ATR Expansion1.5
                                  + RSI + FVG

                  SIDEWAYS / NO EDGE
                         │
                         ▼
                      NO TRADE
```

**Important:** the regime router is only a future hypothesis. It must not be hardcoded into production until separately validated.

---

# 2. Final Strategy Decision

| Strategy | Role | Current status |
|---|---|---|
| **B1 — Donchian30 + RSI** | Primary alpha / main EA | **KEEP — Final #1** |
| **D — ATR Expansion1.5 + RSI + FVG** | Volatility specialist | **KEEP — Final #2** |
| B4 — B1 + H4 BOS | Context experiment | HOLD / not production |
| B5 — B1 + FVG + H4 BOS | Hybrid | DROP |
| B2 — B1 + FVG | Filter | DROP |
| B3 — B1 + Sweep | Filter | DROP |
| H4 HH/HL structure | Filter | DROP |
| Pure SMC | Standalone alpha | DROP from production |

## Decision

### Primary EA

```text
B1 — Donchian30 + RSI
```

This is the first strategy to:

- fully specify;
- reproduce;
- implement in MQL5;
- validate on Exness real ticks;
- forward-test on demo.

### Secondary EA

```text
D — ATR Expansion1.5 + RSI + FVG
```

Keep D frozen as the second candidate, but **do not split current effort**. Complete the B1 validation path first.

---

# 3. Why B1 Is Primary

B1 is not selected because it wins every dataset. It does not.

It is selected because its current evidence package is cleaner for production engineering:

- more trades than D;
- simpler logic;
- fewer moving parts;
- deterministic structure;
- easier debugging;
- easier MQL5 implementation;
- lower implementation-drift risk;
- positive recent Dukascopy Bid/Ask evidence;
- positive independent OANDA evidence;
- historically positive recent GetData evidence;
- no need to interpret OB/FVG/CHOCH state across many layers.

The main weakness is equally important:

> **B1 does not show a stable edge over the full 2012–2022 history.**

This must remain visible in all future decision-making.

---

# 4. B1 — Existing Backtest Evidence

## 4.1 Dukascopy 2026 — Recent Real Bid/Ask

Reported result:

| Metric | B1 |
|---|---:|
| Trades | **287** |
| Win Rate | **34.15%** |
| Expectancy | **+0.185R** |
| Profit Factor | **1.278** |
| Total | **+53.23R** |
| Max Drawdown | **$1,108.67** |

Interpretation:

- recent performance is positive;
- sample is materially larger than D in the same shortlist;
- expectancy is positive;
- PF is positive but not extremely high;
- result is encouraging, not enough for production approval.

---

## 4.2 Dukascopy Equal-N Test

Reported:

```text
Trades    55
WR        40%
PF        1.822
Exp      +0.374R
Total    +20.6R
```

Purpose:

- reduce the chance that B1 looked better only because it produced more trades;
- confirm that recent edge is not purely an artifact of trade count.

Result:

> B1 remained positive in the equal-N sample.

---

## 4.3 Independent OANDA 2025

Dataset window:

```text
OANDA XAU/USD M15
2025-10-09
→ 2025-11-21
```

Reported result:

| Metric | B1 |
|---|---:|
| Trades | **45** |
| Win Rate | **37.78%** |
| Expectancy | **+0.322R** |
| Profit Factor | **1.518** |
| Total | **+14.5R** |
| Drawdown | **7.5R** |

Interpretation:

- independent feed remained positive;
- this materially reduces the chance that the recent result exists only on one provider;
- sample is still relatively small, so it is evidence, not proof.

---

# 5. B1 — Cost Stress Evidence

OANDA recent sample with generic transaction-cost stress:

## Cost = 0.05R / trade

```text
Expectancy   +0.272R
PF            1.417
```

## Cost = 0.10R / trade

```text
Expectancy   +0.222R
PF            1.325
```

Interpretation:

- recent OANDA edge remained positive after generic cost stress;
- actual Exness costs are still required;
- generic R-cost stress must not be treated as a substitute for broker-specific spread, commission, swap, slippage, stop levels and execution behavior.

---

# 6. B1 — Long-History Failure

Frozen logic was reportedly run without retuning over:

```text
XAU/USD M15
2012-05-15
→ 2022-03-04

Bars     230,400
Trades     3,765
```

Result:

| Metric | B1 long history |
|---|---:|
| Trades | **3,765** |
| Win Rate | **28.18%** |
| Expectancy | **-0.0137R** |
| Profit Factor | **0.981** |
| Total | **-51.5R** |
| Max Drawdown | **106R** |

This is a major negative result and must not be hidden by recent performance.

Correct classification:

```text
NOT:
timeless / always-on gold strategy

CURRENT HYPOTHESIS:
regime-dependent breakout strategy
```

---

# 7. B1 — Year-by-Year Behavior

| Year | Expectancy | Total R |
|---|---:|---:|
| 2012 | -0.030R | -6.5R |
| 2013 | -0.074R | -27.5R |
| 2014 | 0.000R | 0R |
| 2015 | -0.058R | -23.5R |
| 2016 | -0.059R | -23.5R |
| **2017** | **+0.050R** | **+19R** |
| **2018** | **+0.078R** | **+28.5R** |
| 2019 | -0.047R | -19.5R |
| 2020 | +0.010R | +3.5R |
| 2021 | -0.017R | -6.5R |

Key observation:

> Edge changes materially across market regimes.

Therefore this statement is invalid:

```text
"PF 1.278 in 2026 means B1 works permanently."
```

The future validation question is instead:

> **Which observable market conditions explain when B1 has or loses its edge?**

---

# 8. D — Secondary EA Evidence

D remains the secondary candidate.

## 8.1 Dukascopy 2026

| Metric | D |
|---|---:|
| Trades | **85** |
| Win Rate | **32.94%** |
| Expectancy | **+0.285R** |
| Profit Factor | **1.677** |
| Total | **+24.19R** |
| Drawdown | **$361.95** |

Compared with B1:

```text
B1
Exp     +0.185R
PF       1.278
Trades     287

D
Exp     +0.285R
PF       1.677
Trades      85
```

D showed better quality per trade in this recent sample, but much lower trade frequency.

---

## 8.2 D — Frozen Reconstruction Used in OANDA Test

The documented deterministic reconstruction is:

```text
ATR expansion >= 1.5 ATR
Body / Range >= 50%

Opposing pullback = 1–2 bars
Rebreak <= 6 bars

RSI guard
FVG >= 0.05 ATR

SL = 2 ATR
TP = 3R
```

**Important limitation:** the older D implementation was not fully preserved. The current D definition is a deterministic reconstruction and cannot be assumed to reproduce every old backtest 1:1.

---

## 8.3 D — OANDA Independent Test

| Metric | D |
|---|---:|
| Trades | 26 |
| Win Rate | 30.77% |
| Expectancy | **+0.231R** |
| Profit Factor | **1.333** |
| Total | +6R |
| Drawdown | 9R |

Cost stress:

```text
0.05R / trade
Exp +0.181R
PF  1.249

0.10R / trade
Exp +0.131R
PF  1.172
```

Recent evidence remained positive.

---

## 8.4 D — Long-History Result

2012–2022:

| Metric | D |
|---|---:|
| Trades | **2,189** |
| Win Rate | **24.81%** |
| Expectancy | **-0.0078R** |
| Profit Factor | **0.990** |
| Total | **-17R** |
| Drawdown | **53R** |

At 0.05R generic cost stress:

```text
Exp    -0.0578R
PF      0.927
Total -126.45R
```

Conclusion:

> D has the same fundamental issue as B1: recent evidence is positive, long-history stability is not.

---

# 9. B1 vs D — Current Evidence Matrix

| Test | B1 | D |
|---|---:|---:|
| Dukascopy 2026 Bid/Ask | **PASS** | **PASS** |
| Recent GetData | **PASS** | Historically promising |
| OANDA independent | **PASS** | **PASS** |
| 2012–2022 long history | **FAIL** | **FAIL** |
| Long-term cost robustness | **FAIL** | **FAIL** |
| Exness real tick | **NOT TESTED** | **NOT TESTED** |
| Walk-forward / OOS | **NOT COMPLETE** | **NOT COMPLETE** |
| Monte Carlo robustness | **NOT COMPLETE** | **NOT COMPLETE** |
| Demo forward | **NOT TESTED** | **NOT TESTED** |
| Small real account | **NO** | **NO** |
| Production real money | **NO** | **NO** |

---

# 10. Strategies / Features Already Investigated and Removed

The project tested enough strategy combinations to close the broad discovery phase.

| Component / Strategy | Result |
|---|---|
| FVG standalone | Weak |
| FVG hard filter on B1 | Worse than B1 |
| Sweep → MSS | Negative |
| Sweep → CHOCH | Negative |
| Sweep → MSS → FVG | Negative |
| Pure SMC CE50 M15 | Weak |
| H4 SMC CE50 | Edge in some periods only |
| Liquidity Sweep + B1 | Recent sweep subset worse |
| H4 HH/HL structure | Worse than B1 |
| H4 BOS | Small contextual information |
| B4 — B1 + H4 BOS | Long-history gross positive but cost-fragile |
| B5 — B1 + FVG + H4 BOS | Drop |
| B2 — B1 + FVG | Drop |
| B3 — B1 + Sweep | Drop |

## Liquidity Sweep Observation

Reported B1 subset:

### Sweep <= 5 bars

```text
Exp -0.213R
PF   0.726
```

### No recent sweep

```text
Exp +0.364R
PF   1.597
```

Potential research interpretation:

```text
Sweep may be more useful as:
risk / chop warning

rather than:
entry confirmation
```

This is **not production logic yet**. It requires independent validation before use.

---

# 11. B4 / H4 BOS Context Finding

B4 long-history result:

```text
Trades   2,398
Exp     +0.010R
PF       1.014
Total   +24R
DD       52.5R
```

But with 0.05R/trade cost stress:

```text
Exp     -0.040R
PF       0.947
Total   -95.9R
```

Conclusion:

- H4 context may contain some information;
- edge is too thin after costs;
- do not promote B4 into production.

---

# 12. Current Project Phase

Previous phase:

```text
strategy discovery
```

Current phase:

```text
strategy validation
+
production engineering
```

Do **not** keep generating combinatorial strategy variants unless B1/D validation produces a specific evidence-based reason to reopen discovery.

---

# 13. Critical Missing Artifact Before B1 Rerun

The current consolidated source preserves the strategy name:

```text
B1 — Donchian30 + RSI
```

but does **not** fully preserve the exact B1 implementation contract.

The following exact values/rules must be recovered from the original backtest code/config before claiming reproducibility:

- Donchian calculation source:
  - High/Low?
  - Close?
  - Bid or Ask?
- Donchian lookback behavior:
  - confirmed `30`, but exact indexing must be verified;
  - whether current bar is excluded;
- breakout definition:
  - intrabar cross;
  - close above/below;
  - next-bar entry;
- RSI period;
- RSI thresholds;
- RSI role:
  - momentum confirmation;
  - overbought/oversold guard;
  - direction filter;
- long rule;
- short rule;
- initial stop-loss;
- take-profit;
- trailing stop, if any;
- breakeven logic, if any;
- time/session filter;
- one-position-only / pyramiding behavior;
- cooldown logic;
- re-entry behavior;
- risk-per-trade;
- lot normalization;
- minimum stop-distance handling;
- spread filter;
- news filter, if any;
- exit on opposite signal, if any;
- handling of gaps;
- Bid/Ask side used for stop/TP trigger;
- bar-close vs tick-level evaluation.

## Blocking rule

> Do not rerun “B1” from memory or reconstruct missing parameters casually.

First recover the original implementation/config and create an immutable **B1 Strategy Specification**.

---

# 14. Required B1 Strategy Specification

Create a versioned document/config, for example:

```text
strategy_id: B1
strategy_version: 1.0.0
symbol: XAUUSD
timeframe: M15
donchian_period: 30

# Remaining fields must be copied from the real source implementation.
rsi_period: TBD
rsi_long_rule: TBD
rsi_short_rule: TBD

entry_model: TBD
sl_model: TBD
tp_model: TBD

risk_per_trade: TBD
session_filter: TBD
spread_filter: TBD

source_commit: TBD
config_hash: TBD
```

Every future backtest must record:

- strategy version;
- git commit;
- config hash;
- dataset name;
- dataset checksum if possible;
- broker/data provider;
- timezone;
- symbol metadata;
- date range;
- spread/cost model;
- execution model;
- random seed if stochastic logic exists;
- code/compiler/runtime version.

---

# 15. Next-Step Validation Pipeline — B1 First

## Phase A — Reproducibility Gate

### Goal

Reproduce at least one already-known B1 result using frozen code/config.

### Tasks

- recover exact B1 source code/config;
- pin dependencies;
- freeze parameter manifest;
- identify dataset used for known result;
- rerun;
- compare:
  - trades;
  - timestamps;
  - entry price;
  - exit price;
  - direction;
  - SL/TP;
  - R result;
  - aggregate metrics.

### Required outcome

The rerun should match the historical run within explicitly documented tolerance.

If not:

```text
STOP
↓
Find divergence
↓
Do not continue to Exness validation yet
```

---

## Phase B — Exness MT5 Real-Tick Backtest

### Goal

Validate B1 under the target broker environment.

### Must capture

- XAUUSD exact symbol name;
- contract size;
- digits;
- point/tick size;
- tick value;
- minimum lot;
- lot step;
- maximum lot;
- stop level;
- freeze level;
- margin mode;
- trading hours;
- Bid/Ask ticks;
- variable spread;
- commission;
- swap long;
- swap short;
- rollover behavior.

### Output

Store at least:

```text
run_id
strategy_version
account_currency
symbol
timeframe
from
to
tick_model
spread_model
commission_model
swap_model

trades
wins
losses
win_rate
gross_profit
gross_loss
profit_factor
expectancy_R
total_R
max_drawdown_R
max_drawdown_money
max_consecutive_losses
avg_trade_R
median_trade_R
```

---

## Phase C — Cost / Slippage Stress

Do not validate only against “perfect” execution.

Test:

- observed spread;
- widened spread;
- commission;
- swap;
- positive and negative slippage scenarios;
- stop execution around fast markets;
- rollover periods.

The critical question is:

> Does B1 remain positive after costs representative of actual Exness execution?

---

## Phase D — Walk-Forward / Out-of-Sample

Purpose:

- detect overfitting;
- test stability without reusing future information.

Rules:

- split chronology, never shuffle time series;
- define train and OOS windows before running;
- avoid repeated tuning on OOS;
- record every parameter change;
- once OOS is inspected, treat it as consumed.

Possible pattern:

```text
TRAIN → OOS
TRAIN → OOS
TRAIN → OOS
```

Exact window lengths should be decided from available history and trade frequency before testing, not optimized after seeing results.

---

## Phase E — Regime Segmentation

This is likely the most important research question for B1.

Evaluate B1 performance across independently defined regimes such as:

- trend strength;
- realized volatility;
- ATR percentile;
- Donchian width percentile;
- directional persistence;
- range/chop;
- session;
- spread regime.

For every regime output:

```text
trades
WR
PF
expectancy_R
total_R
DD_R
```

Do not add a regime filter merely because one historical slice looks good.

Process:

```text
Discover regime hypothesis
        ↓
Freeze regime definition
        ↓
Test on independent period
        ↓
Only then consider router/filter
```

---

## Phase F — Monte Carlo / Sequence Robustness

At minimum evaluate trade-sequence risk using the frozen trade distribution.

Questions:

- expected drawdown range;
- tail drawdown;
- losing streak distribution;
- probability of breaching risk limits;
- sensitivity to trade ordering;
- sensitivity to missed trades;
- sensitivity to slippage/cost perturbation.

Do not use Monte Carlo to manufacture profitability. It is for risk robustness.

---

## Phase G — Demo Forward Test

B1 should run unchanged on Exness Demo.

Capture:

- signal timestamp;
- intended entry;
- actual entry;
- intended SL/TP;
- actual accepted SL/TP;
- spread;
- slippage;
- broker result code;
- fill type;
- rejected/modified orders;
- latency if available;
- actual exit;
- actual P/L;
- expected backtest outcome for the same event.

Primary deliverable:

```text
BACKTEST vs DEMO EXECUTION RECONCILIATION
```

---

## Phase H — Small Real Account

Only consider after:

- reproducibility passes;
- Exness real-tick backtest is acceptable;
- OOS/walk-forward remains positive;
- cost robustness passes;
- demo execution is stable;
- operational error handling is proven.

Use the smallest practical risk.

No automatic promotion from demo to real.

---

# 16. Production Acceptance Gates

These gates are principles to freeze **before** final validation.

Avoid changing thresholds after seeing the result.

## Mandatory

- positive expectancy after actual modeled broker costs;
- PF > 1 after costs;
- drawdown within predefined account risk budget;
- no material look-ahead/data leakage;
- reproducible run;
- OOS not structurally broken;
- no dependence on one narrow month/provider;
- demo behavior consistent with backtest logic;
- no unresolved duplicate-order/state-recovery defects;
- execution errors fail safely.

## Numeric thresholds

The project has **not yet frozen final numeric production thresholds** for:

- minimum PF;
- minimum expectancy;
- maximum drawdown;
- minimum trade count;
- maximum consecutive losses;
- maximum live-vs-backtest divergence.

These must be agreed **before** the final go/no-go run.

Do not invent thresholds retrospectively to make B1 pass.

---

# 17. Backtest Integrity Rules

## 17.1 No Look-Ahead

Never use:

- current candle high/low before the candle closes if the strategy assumes bar-close signals;
- future swing confirmation without delayed availability;
- future session high/low;
- future ATR/RSI values;
- revised data unavailable at decision time.

Every feature must have an explicit availability timestamp.

---

## 17.2 Bid/Ask Correctness

For XAU/USD:

- long entries normally execute at Ask;
- long exits/SL normally resolve against Bid;
- short entries normally execute at Bid;
- short exits/SL normally resolve against Ask.

The engine must model this consistently.

Do not backtest all fills against mid-price and call it realistic execution.

---

## 17.3 Warm-Up

Indicators must not trade before sufficient history exists.

At minimum:

```text
warmup >= maximum required lookback
```

Prefer an additional safety buffer.

If RSI/Donchian/ATR values are NaN or not ready:

```text
NO TRADE
log reason
```

---

## 17.4 Timezone / Session Integrity

Persist:

- raw data timezone;
- broker server timezone;
- UTC conversion;
- DST handling;
- session definition.

Never mix:

```text
UTC
broker server time
Thailand time
New York time
London time
```

without explicit conversion.

---

## 17.5 Data-Gap Detection

Before each run:

- verify timestamps are monotonic;
- detect duplicate bars/ticks;
- detect missing intervals;
- detect zero/negative prices;
- detect impossible Bid > Ask inversions unless provider format explains it;
- verify spread is non-negative;
- verify OHLC invariants.

If a material gap exists:

```text
mark run INVALID
do not silently interpolate execution-critical ticks
```

---

# 18. EA Runtime Error Handling

## 18.1 Duplicate Order Prevention

Risk:

- same signal evaluated multiple ticks;
- terminal reconnect;
- EA restart;
- delayed response causes resubmission.

Required design:

```text
signal_id =
strategy_version
+ symbol
+ timeframe
+ direction
+ signal_bar_time
```

Before submitting:

- check existing position;
- check pending orders;
- check persisted last processed signal;
- ensure idempotency.

Default behavior:

> If uncertain whether an order already exists, reconcile broker state first. Do not blindly resend.

---

## 18.2 Broker Disconnect / Network Failure

On disconnection:

```text
do not assume order failed
```

Recovery:

1. reconnect;
2. query open positions;
3. query pending orders;
4. query recent trade history;
5. reconcile against local state;
6. only then resume new entries.

Existing risk-management logic should prioritize managing open exposure over opening new trades.

---

## 18.3 Order Rejection

Capture MT5 trade result information.

Handle cases such as:

- invalid volume;
- invalid stops;
- market closed;
- not enough money;
- price changed;
- off quotes;
- trade disabled;
- symbol not tradable;
- unsupported filling mode.

For entry rejection:

```text
log
→ classify transient/permanent
→ bounded retry only when safe
→ never infinite retry
```

For protective SL/TP rejection:

```text
HIGH SEVERITY
```

If a position exists without intended protection, the EA must enter a fail-safe management path rather than continue normally.

---

## 18.4 Partial Fill / Volume Mismatch

After every execution:

- query actual filled volume;
- do not assume requested volume == filled volume;
- calculate protection from actual position state;
- log residual/unfilled quantity;
- avoid duplicate compensation orders.

---

## 18.5 Slippage / Price Drift

Before retrying:

- recompute whether the setup is still valid;
- enforce max allowed deviation;
- do not chase price indefinitely.

If price moves outside allowed execution tolerance:

```text
SKIP TRADE
```

A missed trade is safer than uncontrolled execution drift.

---

## 18.6 Stop-Level / Freeze-Level Errors

Before placing/modifying SL/TP:

- read broker stop level;
- read freeze level;
- normalize to tick size;
- validate distance.

If intended stop violates broker constraints:

- do not silently widen risk without recalculating position size;
- either:
  - recompute size using the valid stop, if strategy rules explicitly allow it; or
  - skip the trade.

---

## 18.7 Invalid Indicator State

If:

```text
RSI = NaN
Donchian = unavailable
ATR = unavailable
buffer copy failed
insufficient bars
```

Then:

```text
NO ENTRY
log error
retry next evaluation cycle
```

Never convert missing data to zero.

---

## 18.8 State Persistence / Restart

Persist enough state to recover:

- strategy version;
- current symbol;
- last processed bar;
- last processed signal ID;
- open trade attribution;
- initial risk R;
- original SL;
- original TP;
- trailing/breakeven state if used;
- session/day counters;
- kill-switch state.

On restart:

```text
broker state = source of truth for actual exposure
local state = source of strategy metadata
```

Reconcile before trading again.

---

## 18.9 Position Attribution

Every order/position must be attributable.

Use:

- Magic Number;
- strategy ID;
- strategy version;
- run/environment;
- structured comment if supported.

B1 and D must never share indistinguishable positions.

---

# 19. Risk Error Handling

## Hard Safety Checks Before Entry

Reject new order if any required condition fails:

- invalid symbol;
- market closed;
- no fresh price;
- spread outside allowed bound;
- insufficient free margin;
- lot below minimum;
- lot above maximum;
- lot not aligned to lot step;
- SL invalid;
- risk calculation invalid;
- duplicate signal;
- current exposure exceeds cap;
- daily/strategy kill-switch active.

Fail closed:

```text
unknown state → NO NEW TRADE
```

---

# 20. Risk Calculation Safety

Position sizing must be based on monetary risk, not assumed pip values.

Validate using broker symbol metadata:

- tick size;
- tick value;
- contract size;
- account currency;
- volume step.

If risk calculation returns:

- NaN;
- infinity;
- zero unexpectedly;
- negative value;
- lot beyond configured cap;

then:

```text
reject trade
log HIGH severity
```

---

# 21. Spread / Market-Abnormality Guard

At each signal capture:

```text
spread_points
spread_price
spread_as_R
```

Do not only log the final trade.

Potential guard behavior should be validated before enabling:

```text
spread > configured maximum
→ skip new entry
```

Do not retroactively tune the spread threshold on the same dataset used to discover it.

---

# 22. Daily / Catastrophic Kill Switch

Production EA should support configurable protection such as:

- max daily realized loss;
- max daily total R loss;
- max consecutive execution errors;
- max consecutive rejected orders;
- maximum open risk;
- unexpected position detected;
- strategy-state corruption;
- repeated data errors.

On trigger:

```text
disable NEW entries
retain/reconcile protection for existing positions
emit high-severity log
require explicit recovery rule
```

Exact numeric thresholds remain to be frozen.

---

# 23. Logging / Observability

Every evaluation should be traceable.

Recommended structured log:

```json
{
  "timestamp_utc": "...",
  "strategy": "B1",
  "version": "1.0.0",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "bar_time": "...",
  "signal_id": "...",
  "donchian_upper": 0,
  "donchian_lower": 0,
  "rsi": 0,
  "bid": 0,
  "ask": 0,
  "spread": 0,
  "decision": "ENTER_LONG|ENTER_SHORT|SKIP",
  "reason": "...",
  "risk_R": 0,
  "requested_volume": 0,
  "actual_volume": 0,
  "sl": 0,
  "tp": 0,
  "broker_retcode": 0
}
```

The exact B1 fields must match the recovered strategy specification.

---

# 24. Required Trade Ledger

Every completed trade should have one row containing at minimum:

```text
trade_id
signal_id
strategy
strategy_version
symbol
direction

signal_time
request_time
fill_time
exit_time

signal_bid
signal_ask
entry_requested
entry_filled
exit_price

spread_at_signal
spread_at_fill
slippage

initial_sl
initial_tp
final_sl
exit_reason

volume
risk_money
risk_R
pnl_money
pnl_R

broker_retcode
data_provider
environment
```

This ledger becomes the source for:

- performance reports;
- backtest/demo comparison;
- Monte Carlo;
- execution-quality analysis;
- debugging.

---

# 25. Backtest vs Demo Reconciliation

For every demo trade, attempt to match a backtest signal by:

```text
strategy_version
symbol
direction
signal_bar_time
```

Classify divergence:

| Type | Meaning |
|---|---|
| SIGNAL_MISSING | Backtest signal exists, demo did not |
| LIVE_ONLY_SIGNAL | Demo signaled but backtest did not |
| ENTRY_PRICE_DIFF | Same signal, materially different fill |
| EXIT_DIFF | Different stop/TP/exit behavior |
| SIZE_DIFF | Different lot/risk |
| TIMING_DIFF | Different evaluation time |
| COST_DIFF | Spread/commission/slippage explains result |
| STATE_DIFF | Restart/position state changed behavior |
| DATA_DIFF | Broker feed created different signal |

Do not treat divergence as random noise without classification.

---

# 26. File / Report Error Handling

Backtest/report generation must not silently succeed when output fails.

Required behavior:

- write to temporary file first;
- flush/close;
- verify file exists;
- verify non-zero size;
- validate expected columns;
- then rename/move into final report path.

If CSV/report write fails:

```text
run status = FAILED_REPORT
metrics must not be treated as finalized
```

Never overwrite the only previous valid report without a backup/versioned run directory.

---

# 27. Run Directory Standard

Suggested:

```text
runs/
  B1/
    1.0.0/
      2026-09-26_exness_real_tick_001/
        config.yaml
        manifest.json
        trades.csv
        equity.csv
        metrics.json
        errors.log
        execution.log
        report.md
```

`manifest.json` should contain:

```text
run_id
strategy_id
strategy_version
source_commit
config_hash
dataset
dataset_hash
provider
symbol
timezone
date_range
cost_model
execution_model
runtime_version
created_at_utc
```

---

# 28. Parameter Drift Protection

Once B1 validation begins:

```text
parameter change
=
new strategy version / experiment
```

Do not quietly change:

- RSI threshold;
- Donchian indexing;
- stop;
- target;
- session;
- spread rule;
- re-entry;
- risk model;

and still call the result “B1 baseline”.

Examples:

```text
B1 v1.0.0 = frozen baseline

B1 v1.1.0 = explicit intentional logic change
```

All comparisons must name the version.

---

# 29. Data Leakage / Overfitting Controls

Do not:

- tune on the full history and report the same history as validation;
- repeatedly inspect OOS and retune until it passes;
- choose regime boundaries after seeing profits and call them causal;
- select only favorable years;
- remove losing trades manually;
- optimize transaction costs unrealistically;
- ignore unavailable historical broker conditions.

Maintain an experiment log:

```text
hypothesis
parameter change
reason
dataset used
result
decision
```

---

# 30. Reproducibility Failure Protocol

If a known historical B1 result cannot be reproduced:

1. do **not** average the two results;
2. freeze both outputs;
3. compare trade-by-trade;
4. find the first divergent signal;
5. inspect:
   - data timestamp;
   - OHLC/tick;
   - Donchian buffer/index;
   - RSI value;
   - spread;
   - execution side;
   - position state;
6. identify root cause;
7. fix implementation or documentation;
8. rerun from scratch;
9. create regression test.

The first divergence is usually more useful than comparing final PF.

---

# 31. Regression Tests Required for B1

Once exact B1 logic is recovered, create tests for:

- Donchian upper/lower calculation;
- exclusion/inclusion of current bar;
- RSI calculation;
- long signal boundary;
- short signal boundary;
- exact equality at thresholds;
- first valid bar after warm-up;
- spread handling;
- SL/TP rounding;
- lot-step normalization;
- duplicate signal prevention;
- restart recovery;
- order rejection;
- missing tick/bar;
- timezone/session edge;
- end-of-day / rollover behavior.

Keep golden test fixtures for known signals.

---

# 32. Environment Separation

Explicitly separate:

```text
RESEARCH
BACKTEST
DEMO
REAL
```

Use different configuration files and clear environment labels.

Real-money execution must never be enabled merely by changing account credentials if safety configuration is missing.

Recommended:

```text
ALLOW_LIVE_TRADING=false
```

by default.

Promotion to live should require explicit configuration.

---

# 33. Current Go / No-Go Matrix

| Area | Status |
|---|---|
| Strategy discovery | **DONE** |
| Primary strategy selected | **DONE — B1** |
| Secondary strategy selected | **DONE — D** |
| B1 recent Dukascopy | **PASS** |
| B1 independent OANDA | **PASS** |
| B1 long history | **FAIL** |
| B1 exact spec frozen | **BLOCKED / must recover exact implementation** |
| B1 reproducibility gate | **TODO** |
| Exness real tick | **TODO** |
| Actual broker costs | **TODO** |
| Walk-forward / OOS | **TODO** |
| Regime validation | **TODO** |
| Monte Carlo | **TODO** |
| Demo forward | **TODO** |
| Execution reconciliation | **TODO** |
| Small real | **NO-GO** |
| Production | **NO-GO** |

---

# 34. Immediate Work Queue

## P0 — Must do first

- [ ] Locate original B1 source code/config.
- [ ] Recover exact RSI rule and all entry/exit rules.
- [ ] Freeze `B1 v1.0.0`.
- [ ] Save parameter manifest.
- [ ] Save source commit/hash.
- [ ] Reproduce a known B1 backtest result.
- [ ] Build trade-level reconciliation.

## P1 — Broker validation

- [ ] Export/check Exness XAUUSD symbol specification.
- [ ] Run MT5 real-tick B1 backtest.
- [ ] Include spread/commission/swap.
- [ ] Record trade ledger.
- [ ] Compare with Dukascopy/OANDA.

## P2 — Robustness

- [ ] Walk-forward.
- [ ] Out-of-sample.
- [ ] Year/month breakdown.
- [ ] Regime segmentation.
- [ ] Cost/slippage stress.
- [ ] Monte Carlo.

## P3 — Forward execution

- [ ] Deploy to Exness Demo VPS.
- [ ] Enable structured logs.
- [ ] Verify restart recovery.
- [ ] Verify duplicate-order prevention.
- [ ] Reconcile demo vs backtest.
- [ ] Run long enough to collect meaningful forward samples.

## P4 — Only after all gates

- [ ] Define small-real risk budget.
- [ ] Explicit live approval.
- [ ] Use minimal practical risk.
- [ ] Keep kill switch enabled.
- [ ] Review live-vs-demo execution continuously.

---

# 35. Definition of Done — B1 Validation

B1 validation is not “done” when one backtest is profitable.

It is done when all of the following are true:

- exact strategy definition is preserved;
- previous result is reproducible;
- Exness real-tick result is known;
- actual transaction-cost model is known;
- OOS/walk-forward result is known;
- regime behavior is understood;
- Monte Carlo risk is known;
- demo forward behavior is known;
- backtest-vs-demo divergence is explained;
- error/restart/duplicate-order protections are tested;
- all run artifacts are stored;
- numeric production acceptance gates were frozen before the final decision.

Only then make a separate:

```text
GO / NO-GO for small real
```

decision.

---

# 36. What Not To Do Next

Do not:

- add more SMC layers because the recent backtest looks weak;
- add random indicators;
- optimize B1 against the same test period repeatedly;
- combine B1 + D without attribution;
- hardcode a regime router before validating it;
- use only recent 2026 performance as production evidence;
- ignore the 2012–2022 failure;
- start real-money trading before Exness and demo validation;
- reconstruct missing B1 rules by guessing;
- change parameters without versioning.

---

# 37. Final Project State

```text
FINALISTS

#1 PRIMARY
B1 — Donchian30 + RSI

#2 SECONDARY
D — ATR Expansion1.5 + RSI + FVG
```

Current operational decision:

```text
FOCUS = B1
```

Current evidence:

```text
Recent Dukascopy       PASS
Independent OANDA      PASS
Generic cost stress    PASS on recent sample
Long history           FAIL
Exness real tick       NOT TESTED
Walk-forward / OOS     NOT COMPLETE
Demo forward           NOT TESTED
```

Therefore:

> **B1 is the primary research/engineering candidate, not yet a real-money production EA.**

The immediate objective is to prove or disprove B1 under **reproducible, broker-realistic, out-of-sample and forward execution conditions** before any further strategy expansion.

---

# 38. Handoff to Next Agent / Developer

Start here:

1. **Do not invent B1 parameters.**
2. Find the original B1 implementation/config.
3. Create `B1 Strategy Specification v1.0.0`.
4. Reproduce a known historical result.
5. If reproducibility fails, stop and debug the first divergent trade.
6. Once reproduced, implement/verify MQL5 behavior.
7. Run Exness MT5 real-tick backtest.
8. Add broker-realistic costs.
9. Perform walk-forward/OOS.
10. Segment by regime to understand long-history failure.
11. Run Monte Carlo.
12. Deploy unchanged version to Exness Demo.
13. Reconcile every forward trade against expected logic.
14. Only after all evidence is stable, evaluate small-real deployment.
15. Leave D frozen until B1 validation is complete.

---

## Source-of-Truth Note

This handoff consolidates the supplied project summary and current conversation.

Historical numbers above are **reported prior backtest results**. They are not newly rerun in this handoff.

A critical limitation is that the supplied summary does not contain the complete exact B1 implementation contract. That missing specification must be recovered before claiming reproducibility or running a final production validation.

