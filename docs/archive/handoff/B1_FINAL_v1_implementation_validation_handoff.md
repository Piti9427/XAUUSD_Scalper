# BotTradeGold — B1-FINAL-v1 Implementation Validation Handoff

**Project:** BotTradeGold  
**Strategy:** B1-FINAL-v1 — Donchian30 + RSI  
**Symbol:** XAU/USD  
**Primary timeframe:** M15  
**Document purpose:** Implementation validation and production-readiness handoff  
**Status:** Strategy/research logic frozen; implementation/broker validation active  
**Real-money status:** **NO-GO until all mandatory gates pass**  
**Last consolidated:** 2026-09-26

---

# 0. Executive Summary

The strategy-discovery and strategy-tuning phase is considered closed for the current primary candidate.

The frozen primary candidate is:

```text
B1-FINAL-v1
XAU/USD M15
Donchian30 breakout
+ RSI14 overextension guard
+ ATR14 stop
+ fixed 3.5R target
+ fixed-fractional risk with drawdown de-risking
```

The next phase is **not** to search for more indicators, add SMC layers, add Martingale, or retune RR.

The next phase is:

```text
Freeze exact contract
        ↓
Build deterministic reference engine
        ↓
Implement MQL5 EA
        ↓
Reference ↔ EA signal/trade reconciliation
        ↓
Exness MT5 Every tick based on real ticks
        ↓
Actual broker-cost validation
        ↓
Multi-period OOS / walk-forward
        ↓
Regime analysis
        ↓
Monte Carlo on broker-realistic ledger
        ↓
Exness Demo forward test
        ↓
Trade-by-trade reconciliation
        ↓
Small-live validation at reduced risk
        ↓
Separate GO / NO-GO production decision
```

The existing long-history evidence must remain visible:

- B1 has shown positive recent evidence.
- B1 previously failed the 2012–2022 long-history robustness test.
- Therefore B1 must currently be treated as a **regime-dependent breakout candidate**, not as a proven always-on strategy.
- Passing implementation validation does **not** automatically prove long-term profitability.

---

# 1. Source-of-Truth Hierarchy

When two artifacts disagree, use this priority order:

1. **This document — `B1-FINAL-v1` frozen contract**
2. Latest project conversation that explicitly changes `B1-FINAL-v1`
3. `XAUUSD_B1_D_Strategy_Handoff_2026-09-26.md`
4. `BotTradeGold_chat_handoff_2026-09-23(1).md`
5. Older experiments/research logs

Important:

- Older handoffs used `TP = 2.5R`.
- `B1-FINAL-v1` now uses **`TP = 3.5R`**.
- Older files are still useful for historical evidence, Bid/Ask execution semantics, and prior failures, but must not silently override the latest frozen contract.

---

# 2. Frozen Strategy Contract

## 2.1 Strategy identity

```yaml
strategy:
  id: B1-FINAL-v1
  family: breakout_trend
  symbol: XAUUSD
  signal_timeframe: M15
  max_concurrent_positions: 1
```

## 2.2 Indicators

```yaml
indicators:
  donchian:
    period: 30
    source:
      high: M15 high
      low: M15 low
    include_signal_bar_in_channel: false

  rsi:
    period: 14
    price: close

  atr:
    period: 14
```

Implementation requirement:

- RSI14 and ATR14 must match the reference implementation numerically.
- Do not replace Wilder-style indicator behavior with a different smoothing implementation without a version change.
- Indicator values must use **completed bars only** for signal generation.

## 2.3 Donchian breakout rule

For signal bar `t`, use the previous 30 **completed** M15 bars:

```text
HH30(t) = max(High[t-30 ... t-1])
LL30(t) = min(Low [t-30 ... t-1])
```

### Long

```text
Close[t] > HH30(t)
AND
RSI14[t] <= 75
```

### Short

```text
Close[t] < LL30(t)
AND
RSI14[t] >= 25
```

No equality shortcut:

```text
Long requires >
Short requires <
```

Do not convert this to:

```text
>=
<=
```

without creating a new strategy version.

## 2.4 Signal timing

Signal is evaluated only after M15 bar `t` is closed.

The EA must not use:

- current unfinished candle High/Low;
- current unfinished RSI/ATR;
- future bar values;
- future revised data.

Entry is attempted on the **first valid tick of the next M15 bar**.

Reference behavior:

```text
signal = closed bar t
entry  = first executable quote of bar t+1
```

## 2.5 Entry side

### Buy

```text
Reference entry quote = Ask
```

### Sell

```text
Reference entry quote = Bid
```

Actual fill price must be recorded independently from the reference quote.

## 2.6 Stop Loss

```text
ATR = ATR14 from the completed signal bar
Initial stop distance = 2.5 × ATR
```

### Long

```text
SL = entry_reference - 2.5 × ATR
```

### Short

```text
SL = entry_reference + 2.5 × ATR
```

The production implementation must explicitly choose and preserve one fill policy:

**Recommended production policy**

1. calculate intended SL/TP using the executable quote immediately before `OrderSend`;
2. calculate volume from that intended entry/SL;
3. send the order;
4. record actual fill;
5. if actual fill differs materially, reconcile the effective risk and log the deviation;
6. do not silently change strategy logic.

If the implementation chooses to re-anchor SL/TP to the actual fill, the reference engine and all validation runs must use the same rule. This is an implementation-contract decision and must be frozen before the final Exness run.

## 2.7 Take Profit

```text
Reward = 3.5R
```

Where:

```text
R = initial entry-to-SL risk distance
```

Therefore:

```text
TP distance = 3.5 × initial stop distance
            = 3.5 × (2.5 ATR)
            = 8.75 ATR
```

### Long

```text
TP = entry + 3.5R
```

### Short

```text
TP = entry - 3.5R
```

## 2.8 Exit management — intentionally disabled

The following have been tested/researched and are **not part of B1-FINAL-v1**:

```yaml
partial_take_profit: false
move_to_break_even: false
atr_trailing_stop: false
structure_trailing: false
martingale: false
averaging_down: false
grid_recovery: false
fixed_ratio_growth_ladder: false
```

Do not reintroduce them during implementation validation.

Latest controlled exit tests showed that Partial/BE/Trailing variants reduced robustness on the primary GetData test, particularly the untouched holdout.

---

# 3. Position Sizing Contract

## 3.1 Sizing model

```text
Fixed Fractional
+
Equity High-Water-Mark Drawdown De-risking
```

Growth ladder is disabled.

Risk percentage must never be increased after a loss.

## 3.2 Equity drawdown

Use equity high-water mark:

```text
HWM = maximum observed account equity since strategy start/reset

DD% = (HWM - Current Equity) / HWM × 100
```

Use **equity**, not balance-only drawdown.

## 3.3 Risk tiers

```yaml
drawdown_risk:
  dd_0_to_3:
    risk_per_trade: 1.00%

  dd_3_to_6:
    risk_per_trade: 0.75%

  dd_6_to_9:
    risk_per_trade: 0.50%

  dd_9_to_12:
    risk_per_trade: 0.25%

  dd_ge_12:
    action: STOP_NEW_ENTRIES
    auto_restart: false
    manual_review_required: true
```

Boundary convention must be deterministic.

Recommended:

```text
0.00% <= DD < 3.00%   => 1.00%
3.00% <= DD < 6.00%   => 0.75%
6.00% <= DD < 9.00%   => 0.50%
9.00% <= DD < 12.00%  => 0.25%
DD >= 12.00%           => STOP
```

## 3.4 Risk amount

```text
risk_money = current_equity × risk_percent
```

Do not use initial balance for normal position sizing.

## 3.5 Lot sizing

Do not hardcode:

- contract size;
- tick value;
- tick size;
- minimum lot;
- volume step;
- maximum volume.

Read symbol properties from MT5 at runtime.

At minimum capture:

```text
SYMBOL_TRADE_CONTRACT_SIZE
SYMBOL_TRADE_TICK_SIZE
SYMBOL_TRADE_TICK_VALUE
SYMBOL_TRADE_TICK_VALUE_PROFIT
SYMBOL_TRADE_TICK_VALUE_LOSS
SYMBOL_VOLUME_MIN
SYMBOL_VOLUME_MAX
SYMBOL_VOLUME_STEP
SYMBOL_VOLUME_LIMIT
SYMBOL_POINT
SYMBOL_DIGITS
SYMBOL_TRADE_STOPS_LEVEL
SYMBOL_TRADE_FREEZE_LEVEL
SYMBOL_SWAP_LONG
SYMBOL_SWAP_SHORT
```

Preferred volume calculation:

1. compute entry quote;
2. compute intended SL;
3. use `OrderCalcProfit()` for a 1-lot entry → SL loss estimate in account currency;
4. calculate raw lot:

```text
raw_lot = risk_money / abs(loss_for_1_lot)
```

5. round **down** to `SYMBOL_VOLUME_STEP`;
6. do not round up and exceed the risk budget;
7. clamp to broker maximum;
8. if normalized volume `< SYMBOL_VOLUME_MIN`:

```text
SKIP TRADE
```

Never force minimum lot if doing so breaches the risk budget.

## 3.6 Margin check

Before sending:

- call `OrderCalcMargin()`;
- call `OrderCheck()` or equivalent preflight;
- verify free margin;
- verify the resulting order does not breach risk constraints.

A valid signal is not permission to ignore margin safety.

---

# 4. Daily Risk Policy

Automatic daily hard stop is currently **disabled**.

Reason:

The recent controlled test found that a `-3R` daily hard stop materially reduced total return without improving Max DD on the primary test set.

Current behavior:

```yaml
daily_loss:
  hard_stop: false

  telemetry:
    alert_minus_2R: true
    alert_minus_3R: true

  automatic_strategy_change: false
```

A losing day or two losing days may trigger:

- alert;
- review;
- regime telemetry;

but must not automatically cause strategy retuning.

---

# 5. Broker / Execution Semantics

## 5.1 Final validation platform

```text
Exness MT5
Strategy Tester:
Every tick based on real ticks
```

MetaTrader documents that real-tick testing uses broker-accumulated ticks from exchanges/liquidity providers and is the closest tester mode to real trading conditions.

Do not use:

```text
Open prices only
1 Minute OHLC
generated Every Tick
```

as the final production gate.

They may be used for fast regression tests only.

## 5.2 Bid / Ask semantics

Expected market semantics:

### Long

```text
Entry uses Ask
SL/TP exit condition uses Bid
```

### Short

```text
Entry uses Bid
SL/TP exit condition uses Ask
```

This matches the Bid/Ask execution model already used in the prior Dukascopy validation work.

## 5.3 Costs

Final validation must include broker-realistic:

```text
spread
commission
swap
slippage
order filling behavior
minimum stop distance
volume constraints
margin requirements
```

Do not treat a generic:

```text
0.10R / trade
0.15R / trade
```

stress assumption as a substitute for broker costs.

Those generic costs are research stress tests only.

## 5.4 Exness symbol assumptions

Do not hardcode values copied from a website.

Before every validation run, export the actual MT5 symbol specification from the exact account/server being tested.

Public Exness documentation currently lists XAUUSD with contract size 100 troy ounces and minimum Standard volume 0.01 lot, but the EA must still read the live symbol properties from MT5 because account type, symbol suffix, server, and specification can differ.

---

# 6. Time, Bar, and Data Contract

## 6.1 Canonical timestamps

All logs must include UTC timestamps.

Recommended fields:

```text
event_time_utc
broker_server_time
broker_utc_offset
signal_bar_open_utc
signal_bar_close_utc
entry_time_utc
exit_time_utc
```

## 6.2 M15 bar alignment

Before validation:

- verify Exness M15 boundaries map consistently to the reference M15 boundaries;
- confirm bars occur at `00/15/30/45` minute boundaries after UTC conversion;
- document server timezone/DST behavior.

If bars do not align with the reference data, do not silently accept the difference.

## 6.3 Data readiness

Do not generate a signal until:

```text
>= 30 completed Donchian bars
AND
RSI14 ready
AND
ATR14 ready
```

Recommended warmup:

```text
>= 100 M15 bars
```

to eliminate startup ambiguity.

---

# 7. Deterministic Reference Engine

Before validating the MQL5 EA, maintain a broker-independent deterministic reference engine.

Purpose:

```text
Known data
   ↓
Known indicators
   ↓
Known signals
   ↓
Known intended entries
   ↓
Known SL / TP
   ↓
Expected trade ledger
```

This is the oracle for implementation parity.

The reference engine must freeze:

```text
strategy version
input dataset hash
timezone
bar aggregation rules
indicator formulas
Donchian indexing
entry timing
same-bar ambiguity policy
cost model
risk model
```

---

# 8. Regression Baselines From Latest Research

These values are **reference reconstruction targets**, not production-profit guarantees.

## 8.1 GetData M15 — generic cost stress 0.10R

Fixed trade logic before equity sizing:

```text
Trades       169
Win Rate     29.59%
Expectancy  +0.2314R
Profit Factor 1.299
Total       +39.10R
R-curve DD   15.30R
```

With DD de-risk sizing:

```text
Start $100
End   $130.09
Return +30.09%
Max Equity DD 9.93%
```

## 8.2 GetData M15 — generic cost stress 0.15R

```text
Trades       169
Expectancy  +0.1814R
PF            1.224
Total       +30.65R
```

Portfolio reconstruction:

```text
Start $100
End   $122.42
Return +22.42%
Max Equity DD 10.22%
```

## 8.3 Untouched GetData holdout — 0.15R stress

```text
Trades       59
WR           27.12%
Expectancy  +0.0703R
PF            1.084
Total        +4.15R
```

DD-sized portfolio reconstruction:

```text
Start $100
End   $106.01
Return +6.01%
Max DD 10.22%
```

## 8.4 Independent OANDA sample — 0.15R stress

```text
Trades       33
WR           33.33%
Expectancy  +0.3791R
PF            1.514
```

These numbers must not be used as expected future returns.

They exist to detect implementation drift.

---

# 9. Known Negative Evidence

Do not hide this section.

Prior long-history test:

```text
XAU/USD M15
2012-05-15 → 2022-03-04

Bars       ~230,400
Trades       3,765
WR           28.18%
Expectancy  -0.0137R
PF            0.981
Total       -51.5R
Max DD      106R
```

Therefore:

```text
Recent success != permanent edge
```

Production approval must explain this failure through evidence, not ignore it.

Possible outcomes:

1. recent market regime genuinely favors B1;
2. old implementation/data differs materially;
3. execution/cost model changed;
4. B1 is regime-dependent;
5. recent sample is favorable noise.

Validation must distinguish these possibilities.

---

# 10. Signal Parity Validation

## Gate A — Indicator parity

For a fixed dataset compare, bar by bar:

```text
ATR14
RSI14
HH30
LL30
```

Required:

```text
No unexplained mismatches
```

Recommended numerical tolerance for double-precision calculations:

```text
<= 1e-8 in normalized internal values
```

Price-level comparisons should ultimately be normalized to symbol tick size.

## Gate B — Signal parity

For every M15 closed bar compare:

```text
timestamp
long_signal
short_signal
reason
RSI
HH30
LL30
Close
```

Required:

```text
Signal timestamps: 100% match
Directions:        100% match
Extra signals:     0
Missing signals:   0
```

Anything else is a bug or a documented data difference.

## Gate C — Intended trade parity

For deterministic reference data compare:

```text
entry_bar
direction
entry_reference
ATR
SL
TP
risk tier
risk money
requested lot
normalized lot
```

Required:

```text
Trade count: exact
Direction: exact
SL/TP: exact to symbol normalization
Risk tier: exact
```

---

# 11. Same-Bar / Same-Tick Ambiguity

Historical bar-based regression must use a conservative ambiguity policy.

If both SL and TP are reachable inside the same unresolved bar/minute:

```text
count SL first
```

For real-tick tests:

```text
tick ordering decides naturally
```

Do not artificially apply SL-first when actual tick order is available.

---

# 12. MQL5 Implementation Requirements

## 12.1 One signal evaluation per new M15 bar

Use a new-bar guard.

Persist:

```text
last_processed_m15_bar
```

Do not evaluate/send repeatedly on every tick for the same closed bar.

## 12.2 Position uniqueness

Do not rely blindly on `PositionSelect(symbol)`.

Account modes differ:

```text
netting
hedging
```

The strategy must identify its own exposure by:

```text
symbol
magic number
strategy version/comment
```

Recommended:

- iterate open positions/orders;
- filter by symbol + magic;
- enforce `max_concurrent_positions = 1`.

## 12.3 Order idempotency

Define deterministic signal ID:

```text
signal_id =
  strategy_id
  + symbol
  + signal_bar_close_utc
  + direction
```

Before sending an order:

```text
if signal_id already submitted/executed:
    DO NOT SEND AGAIN
```

Required to prevent duplicate trades after:

- terminal restart;
- reconnect;
- timeout;
- repeated OnTick calls;
- ambiguous OrderSend result.

## 12.4 `OrderSend()` handling

A boolean `true` return from `OrderSend()` does **not** prove the order was filled.

Always inspect:

```text
MqlTradeResult.retcode
request_id
order
deal
price
volume
comment
```

Use `OnTradeTransaction()` to reconcile actual server events.

---

# 13. Trade Error Handling Policy

Classify failures.

## 13.1 Transient / retryable

Examples:

```text
TRADE_RETCODE_REQUOTE
TRADE_RETCODE_TIMEOUT
TRADE_RETCODE_PRICE_CHANGED
TRADE_RETCODE_PRICE_OFF
TRADE_RETCODE_CONNECTION
TRADE_RETCODE_LOCKED
```

Policy:

1. do not immediately duplicate the request;
2. inspect broker state and transaction history;
3. obtain fresh Bid/Ask;
4. re-run all safety checks;
5. ensure signal is still valid for the same entry window;
6. retry with a strict bounded retry count;
7. log every attempt.

Recommended default:

```text
max retries: 2
```

No infinite retry loop.

## 13.2 Permanent / configuration errors

Examples:

```text
TRADE_RETCODE_INVALID_VOLUME
TRADE_RETCODE_INVALID_PRICE
TRADE_RETCODE_INVALID_STOPS
TRADE_RETCODE_TRADE_DISABLED
TRADE_RETCODE_MARKET_CLOSED
TRADE_RETCODE_NO_MONEY
TRADE_RETCODE_INVALID_FILL
TRADE_RETCODE_LIMIT_VOLUME
```

Policy:

```text
NO blind retry
LOG
ALERT
SKIP signal
```

`INVALID_VOLUME`, `INVALID_STOPS`, or `NO_MONEY` should be treated as implementation/risk defects until proven otherwise.

## 13.3 Partial fill

If:

```text
TRADE_RETCODE_DONE_PARTIAL
```

the EA must:

- reconcile actual filled volume;
- compute actual risk;
- not blindly send the full original volume again;
- decide whether remainder is canceled or retried according to a frozen execution policy;
- log the resulting exposure.

---

# 14. State Persistence and Restart Recovery

Persist at minimum:

```text
strategy_id
strategy_version
build_hash
magic_number

last_processed_bar
last_signal_id
last_order_request_id

equity_high_water_mark
current_drawdown
current_risk_tier

open_position_ticket
position_identifier

last_known_balance
last_known_equity

manual_stop_flag
hard_dd_stop_flag
```

On startup/restart:

```text
1. Disable new entries temporarily.
2. Read actual broker positions/orders/deals.
3. Reconcile broker state against persisted state.
4. Rebuild HWM/risk state.
5. Restore last processed M15 bar.
6. Confirm no duplicate signal/order exists.
7. Only then enable new entries.
```

Broker state wins over stale local state.

Never assume:

```text
"the previous OrderSend failed because the client timed out"
```

until broker state has been checked.

---

# 15. High-Water Mark Persistence

Equity HWM must survive:

```text
EA restart
terminal restart
VPS restart
network outage
```

It must not reset to current equity after a restart, because that would erase drawdown and incorrectly increase risk.

Resetting HWM is a **manual versioned operational action**, not automatic behavior.

---

# 16. Logging / Telemetry Schema

Every decision cycle should be reconstructable.

Recommended trade-decision log:

```text
event_time_utc
broker_server_time

strategy_id
strategy_version
ea_build
git_commit
config_hash
magic_number

symbol
timeframe
signal_id
signal_bar_time

bid
ask
spread

close
hh30
ll30
rsi14
atr14

signal_long
signal_short
signal_reason

equity
balance
equity_hwm
drawdown_pct
risk_tier
risk_pct
risk_money

entry_reference
intended_sl
intended_tp

raw_lot
normalized_lot
volume_min
volume_step
volume_max

margin_required
free_margin

request_id
retcode
retcode_external
order_ticket
deal_ticket
position_ticket

fill_price
fill_volume
slippage_price
slippage_R

commission
swap

exit_time
exit_price
exit_reason
realized_pnl
realized_R
```

Logs must be machine-readable:

```text
CSV / JSONL / database
```

Do not rely only on human-readable Experts log output.

---

# 17. Dataset and Run Manifest

Every backtest must save a manifest.

Example:

```yaml
run:
  run_id: <uuid>
  date_utc: ...
  strategy: B1-FINAL-v1
  ea_build: ...
  git_commit: ...
  config_hash: ...

broker:
  name: Exness
  server: ...
  account_type: ...
  currency: ...
  leverage: ...

symbol:
  actual_name: ...
  digits: ...
  point: ...
  contract_size: ...
  tick_size: ...
  tick_value_loss: ...
  volume_min: ...
  volume_step: ...
  stops_level: ...

tester:
  mode: Every tick based on real ticks
  start: ...
  end: ...
  deposit: ...
  leverage: ...

data:
  bars: ...
  ticks: ...
  missing_tick_intervals: ...
```

If the manifest changes, the run is not directly comparable.

---

# 18. Unit Tests

Required unit-test groups:

## Indicators

- RSI14 known vector
- ATR14 known vector
- Donchian previous-30 indexing
- warmup behavior
- NaN/missing bars
- gap bars

## Signal rules

- exact long breakout
- exact short breakout
- equality does not trigger
- RSI 75 exactly is allowed long
- RSI >75 blocks long
- RSI 25 exactly is allowed short
- RSI <25 blocks short

## Risk tiers

Test boundaries:

```text
2.9999%
3.0000%
5.9999%
6.0000%
8.9999%
9.0000%
11.9999%
12.0000%
```

## Volume normalization

- below minimum lot → SKIP
- exact minimum
- one step above minimum
- round down
- max volume
- zero/invalid tick value
- invalid SL distance

## High-water mark

- new equity high
- DD increases
- DD recovers partially
- DD recovers to HWM
- new HWM
- restart persistence

## Idempotency

- same tick repeated
- same signal after reconnect
- timeout then broker fill
- restart with position already open

---

# 19. Integration Tests

Required integration scenarios:

1. clean BUY signal → order → fill → SL
2. clean BUY signal → order → fill → TP
3. clean SELL signal → SL
4. clean SELL signal → TP
5. spread widens before order
6. price changes during send
7. insufficient margin
8. invalid stop level
9. invalid lot step
10. terminal disconnect
11. restart with open position
12. restart after request but before response
13. manual position accidentally exists
14. account switched from expected server/account
15. hard DD reached while position is open
16. hard DD reached while flat
17. symbol trading disabled/market closed

---

# 20. Hard DD Behavior

At:

```text
DD >= 12%
```

Required behavior:

```text
STOP NEW ENTRIES
```

Do **not** automatically liquidate an existing valid B1 trade unless that is separately specified and validated.

Existing trade should continue under its original SL/TP unless an emergency operational kill command is explicitly invoked.

Reason:

```text
hard DD stop
!=
panic-close all positions
```

Manual re-enable required.

Before re-enable:

- reconcile broker state;
- review DD source;
- verify no implementation fault;
- review recent trade ledger;
- record operator approval.

---

# 21. Reference ↔ EA Trade Reconciliation

For every trade compare:

```text
signal time
direction
entry reference
actual fill
ATR
RSI
Donchian level
SL
TP
risk %
risk $
lot
exit
P/L
R
```

Classify every difference:

```text
DATA
SIGNAL_LOGIC
INDICATOR
BAR_ALIGNMENT
BID_ASK
SPREAD
SLIPPAGE
COMMISSION
SWAP
VOLUME_ROUNDING
BROKER_RULE
IMPLEMENTATION_BUG
EXPECTED_EXECUTION_VARIANCE
```

Never use unexplained differences.

---

# 22. Reproducibility Gate

Before broker optimization/forward testing:

### Mandatory

- [ ] source code committed
- [ ] strategy manifest frozen
- [ ] config hash stored
- [ ] reference dataset stored/hashed
- [ ] reference trade ledger stored
- [ ] EA trade ledger stored
- [ ] same build reproduces the same tester output
- [ ] no unexplained signal differences
- [ ] no unexplained risk-tier differences

A code change after this gate requires:

```text
new build hash
new regression run
```

A strategy-rule change requires:

```text
new strategy version
```

---

# 23. Exness Real-Tick Validation

## Required tester mode

```text
Every tick based on real ticks
```

MetaTrader documentation notes that when real tick history is available, the tester uses broker-accumulated real ticks; if real ticks are missing for a minute, generated ticks may be substituted.

Therefore record:

- tick coverage;
- missing-tick intervals;
- tester journal warnings;
- data synchronization status.

## Required periods

Do not validate only one favorable period.

Use:

```text
recent trend regime
recent choppy regime
high-volatility period
low-volatility period
multiple calendar years if broker history allows
```

Where Exness history is insufficient, use the existing Dukascopy Bid/Ask dataset as an external long-history execution cross-check.

---

# 24. Walk-Forward / OOS Validation

B1 must remain frozen during this phase.

Do not tune:

```text
Donchian
RSI threshold
ATR multiplier
RR
entry timing
exit management
```

Suggested structure:

```text
Train/discovery: only for historical context
Validation:      no tuning
OOS/holdout:     no tuning
Rolling windows: no tuning within the frozen B1 version
```

The purpose is not to find a better parameter.

The purpose is to answer:

```text
Does B1-FINAL-v1 survive market changes?
```

---

# 25. Production Acceptance Metrics

These thresholds are **engineering gates**, not guarantees of future profit.

Freeze them before the final run.

## 25.1 Implementation gates — hard requirements

```text
Signal parity               = 100%
Direction parity            = 100%
Duplicate strategy trades   = 0
Unexplained missing trades  = 0
Unexplained extra trades    = 0
Critical trade errors       = 0 unresolved
State-loss after restart    = 0
HWM reset bugs              = 0
```

## 25.2 Broker backtest minimum gates

Proposed initial gates:

```text
Net expectancy after actual costs > 0
Profit Factor after actual costs > 1.00
Max Equity DD < 12%
Hard-DD stop not triggered in the selected acceptance run
```

Because PF barely above 1 can be fragile, also report:

```text
PF 1.00–1.10 = fragile
PF >=1.10    = preferable
```

Do not retroactively weaken thresholds to make B1 pass.

## 25.3 Sample-size gate

Recommended:

```text
>= 100 closed OOS trades across non-overlapping validation periods
```

If unavailable:

```text
extend the test period
```

Do not substitute more in-sample optimization.

## 25.4 Regime-concentration gate

Report P/L by:

```text
year
quarter
volatility regime
trend/chop proxy
long vs short
```

If essentially all profit comes from one narrow period while most other periods are negative:

```text
NO-GO as always-on production
```

This is especially important because B1 historically failed 2012–2022.

---

# 26. Monte Carlo Gate

Run Monte Carlo on the **final broker-realistic trade ledger**, not on the old generic-cost ledger.

Required methods:

```text
1. reshuffle without replacement
2. bootstrap with replacement
```

Recommended:

```text
>= 50,000 paths
```

Report:

```text
ending equity distribution
median return
5th percentile return
median Max DD
90th percentile Max DD
95th percentile Max DD
probability DD >= 12%
probability ending below initial equity
max consecutive losses
recovery duration
```

Important:

If the 1% base risk causes unacceptable tail DD:

```text
DO NOT change entry logic
DO NOT increase hard-DD limit
```

Permitted action:

```text
lower the base risk scalar
```

Then rerun Monte Carlo and all risk-tier tests.

Risk may be reduced without changing B1 alpha logic.

Risk must not be increased merely to improve backtest growth.

---

# 27. Demo Forward Validation

Use the exact same:

```text
EA binary/build
strategy version
parameters
magic number
risk engine
broker/server
```

that passed the final tester gate.

Recommended minimum observation:

```text
>= 8 weeks
AND
>= 50 closed trades
```

If 50 trades are not reached:

```text
continue until 50+
```

Do not change parameters mid-test.

## Demo success is primarily implementation validation

Measure:

```text
expected signal ↔ actual signal
expected order ↔ actual order
spread
slippage
commission
swap
fill latency
retcodes
restart behavior
duplicate prevention
risk sizing
DD tier changes
```

Do not demand that a 50-trade sample reproduce the exact backtest PF.

---

# 28. Forward Trade Reconciliation Gate

For each demo trade:

```text
Expected signal?
Correct direction?
Correct next-bar timing?
Correct ATR?
Correct RSI?
Correct Donchian level?
Correct risk tier?
Correct lot?
Correct SL/TP?
Correct exit?
```

Required:

```text
Logic mismatch = 0
```

Execution variance is allowed only when explained by:

```text
spread
slippage
broker fill
swap
commission
market gap
```

---

# 29. Small-Live Gate

Only after:

```text
real-tick PASS
OOS PASS
Monte Carlo PASS
Demo PASS
Reconciliation PASS
```

Start a separate small-live validation.

Recommended live-validation risk override:

```text
0.25%–0.50% base risk
```

This does not change B1 signal logic.

Purpose:

```text
validate real execution
not maximize profit
```

Do not immediately deploy the full 1% research risk.

Only scale toward the validated risk profile after the live execution ledger is consistent with demo/tester assumptions.

---

# 30. VPS / Operational Validation

Production EA should run on a stable Windows/MT5 VPS environment.

Validate:

- MT5 auto-start;
- EA attached after reboot;
- Algo Trading enabled;
- account/server identity verified;
- no duplicate terminal instance running the same magic;
- persistent state loaded;
- logs rotated;
- disk space monitored;
- time synchronization healthy;
- network reconnect tested.

Mac/Wine may be acceptable for development but should not be the only production runtime if 24/7 reliability is required.

---

# 31. Duplicate-Bot Protection

The system must prevent:

```text
local MT5
+
VPS MT5
```

from both trading the same strategy/account unintentionally.

Recommended:

```text
one approved deployment instance per account + magic
```

On startup detect:

- existing B1 position;
- existing recent B1 order/deal;
- conflicting deployment marker if implemented.

---

# 32. Manual Controls

Required operator controls:

```text
PAUSE_NEW_ENTRIES
RESUME
EMERGENCY_STOP
EXPORT_STATE
EXPORT_LEDGER
RESET_HWM (protected/manual only)
```

`RESET_HWM` must require explicit confirmation and audit logging.

---

# 33. Versioning Rules

Example:

```text
Strategy: B1-FINAL-v1.0.0
EA:       btg-b1-ea 1.0.0
```

### Patch

Allowed:

```text
logging fix
non-behavioral bug fix
telemetry
UI/comment
```

### Minor/Major

Required if behavior changes:

```text
indicator formula
signal condition
entry timing
SL
TP
RR
position sizing rule
DD tiers
exit management
```

A behavior change invalidates prior validation unless explicitly proven equivalent.

---

# 34. Configuration Drift Protection

At EA startup print/store:

```text
strategy_version
config_hash
EA build
git commit
symbol spec hash/snapshot
```

If required production parameters differ from the approved manifest:

```text
REFUSE TO TRADE
```

unless the deployment is explicitly marked as a new validation run.

---

# 35. What Is Frozen — Do Not Tune Further

```text
M15
Donchian 30
RSI14
Long RSI <= 75
Short RSI >= 25
ATR14
SL 2.5 ATR
TP 3.5R
next-bar entry
max concurrent 1
no partial
no BE
no trailing
no Martingale
no grid
no Fixed Ratio growth ladder
```

Do not:

- add SMC because one forward period is weak;
- add FVG/CHOCH/Sweep filters;
- add EMA filters;
- optimize parameters per year;
- change RR after seeing OOS results;
- change signal logic after demo losses;
- remove losing historical periods.

---

# 36. What May Change Without Alpha Retuning

Allowed only when versioned and regression-tested:

```text
broker adapter
symbol suffix handling
lot normalization
retry policy
logging
telemetry
state persistence
VPS operational code
performance optimization
```

Risk scalar may be **reduced** if Monte Carlo/execution risk requires it.

Increasing risk requires a new risk-validation decision.

---

# 37. Error / Incident Runbook

## EA stops sending trades

Check:

1. manual pause?
2. DD >= 12%?
3. Algo Trading disabled?
4. market closed?
5. wrong symbol?
6. invalid volume/stops?
7. no margin?
8. disconnected?
9. stale state?
10. already-open B1 position?

## Duplicate trade

Immediate:

```text
PAUSE NEW ENTRIES
```

Then:

- inspect signal ID;
- inspect request IDs;
- inspect OnTradeTransaction ledger;
- reconcile position exposure;
- do not auto-close blindly;
- classify incident;
- patch only after reproducing.

## HWM/state corruption

Immediate:

```text
PAUSE NEW ENTRIES
```

Never guess HWM.

Recover from:

```text
persisted state
+
account equity history / deployment records
```

If reliable recovery is impossible:

```text
manual review required
```

---

# 38. GO / NO-GO Matrix

## Strategy / implementation

| Area | Gate |
|---|---|
| B1-FINAL-v1 contract | FROZEN |
| Reference engine | MUST PASS |
| Unit tests | MUST PASS |
| Signal parity | MUST PASS |
| Trade parity | MUST PASS |
| Restart/idempotency | MUST PASS |
| Broker symbol handling | MUST PASS |
| Error handling | MUST PASS |

## Broker validation

| Area | Gate |
|---|---|
| Exness real ticks | MUST PASS |
| Actual spread | INCLUDED |
| Commission | INCLUDED |
| Swap | INCLUDED where applicable |
| Slippage | MEASURED |
| Volume constraints | VALIDATED |
| Margin rules | VALIDATED |

## Robustness

| Area | Gate |
|---|---|
| OOS expectancy | > 0 |
| Max Equity DD | < 12% |
| Monte Carlo tail DD | MUST BE ACCEPTABLE |
| Long-history failure | MUST BE ADDRESSED |
| Regime concentration | MUST BE REPORTED |

## Forward

| Area | Gate |
|---|---|
| Demo >= 8 weeks | REQUIRED |
| Demo >= 50 trades | REQUIRED |
| Logic mismatch | 0 |
| Duplicate trades | 0 |
| Critical incidents | 0 unresolved |

## Real money

```text
Small real:  NO-GO until all above pass
Production:  separate GO / NO-GO decision
```

---

# 39. Immediate Work Queue

## P0 — Reference and code

- [ ] Create `B1-FINAL-v1.yaml`.
- [ ] Commit/freeze strategy specification.
- [ ] Freeze indicator formulas.
- [ ] Build deterministic reference engine.
- [ ] Export known reference ledger.
- [ ] Implement MQL5 indicator/signal module.
- [ ] Implement risk module.
- [ ] Implement order adapter.
- [ ] Implement persistent state.
- [ ] Implement idempotency.
- [ ] Implement structured logging.

## P1 — Reconciliation

- [ ] Run reference vs EA on identical history.
- [ ] Diff indicators.
- [ ] Diff signals.
- [ ] Diff trades.
- [ ] Diff risk tiers.
- [ ] Resolve every mismatch.
- [ ] Store regression artifact.

## P2 — Exness

- [ ] Export actual symbol specification.
- [ ] Save broker/server metadata.
- [ ] Download/synchronize real ticks.
- [ ] Run `Every tick based on real ticks`.
- [ ] Export tester report.
- [ ] Export deals/orders/trades.
- [ ] Recompute metrics independently.
- [ ] Verify costs.
- [ ] Verify DD tiers.

## P3 — Robustness

- [ ] Multi-period OOS.
- [ ] Year/regime decomposition.
- [ ] Long/short decomposition.
- [ ] Cost sensitivity.
- [ ] Monte Carlo reshuffle.
- [ ] Monte Carlo bootstrap.
- [ ] Recalibrate risk downward if tail DD fails.

## P4 — Demo

- [ ] Deploy exact validated build.
- [ ] Run >=8 weeks and >=50 trades.
- [ ] Daily automated ledger export.
- [ ] Reconcile every signal/trade.
- [ ] Review execution variance.
- [ ] No mid-test tuning.

## P5 — Small live

- [ ] Separate formal GO decision.
- [ ] Start at 0.25%–0.50% risk.
- [ ] Confirm live execution parity.
- [ ] Scale only after evidence.

---

# 40. Definition of Done

Implementation validation is complete only when:

```text
[PASS] Exact frozen strategy contract exists
[PASS] Reference engine is reproducible
[PASS] MQL5 matches reference signals
[PASS] Position sizing matches reference
[PASS] Restart/idempotency tests pass
[PASS] Exness real-tick tester completed
[PASS] Actual broker costs included
[PASS] OOS/Walk-forward completed
[PASS] Long-history/regime issue explicitly evaluated
[PASS] Monte Carlo completed on final ledger
[PASS] Demo forward completed
[PASS] Every demo trade reconciled
[PASS] No unresolved critical execution defects
```

Only then:

```text
evaluate SMALL-REAL GO / NO-GO
```

Production approval is a separate decision.

---

# 41. Current Decision

```text
STRATEGY DISCOVERY       CLOSED
SMC TUNING               CLOSED
EXIT-MANAGEMENT TUNING   CLOSED
RR TUNING                CLOSED
POSITION-SIZING DESIGN   CLOSED

B1-FINAL-v1              FROZEN

IMPLEMENTATION VALIDATION ACTIVE
REAL MONEY               NO-GO
```

The engineering principle from this point onward:

> If B1 fails a validation gate, first determine whether the cause is implementation, execution, cost, regime dependence, or lack of edge. Do not immediately modify the strategy to force a pass.

---

# 42. External Technical References

Official MetaTrader / MQL5 documentation:

- Strategy testing and real ticks:  
  https://www.mql5.com/en/docs/runtime/testing
- `OrderSend()`:  
  https://www.mql5.com/en/docs/trading/ordersend
- Trade server return codes:  
  https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes
- `OnTradeTransaction()`:  
  https://www.mql5.com/en/docs/event_handlers/ontradetransaction
- Symbol properties (`SYMBOL_VOLUME_MIN`, tick value, contract size, etc.):  
  https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants
- `OrderCalcProfit()`:  
  https://www.mql5.com/en/docs/trading/ordercalcprofit
- `OrderCalcMargin()`:  
  https://www.mql5.com/en/docs/trading/ordercalcmargin

Exness public XAU/USD specification reference:

- Commodities / XAUUSD help article:  
  https://get.exness.help/hc/en-us/articles/17854173039388-Commodities

Important:

Broker-specific values must be read from the actual MT5 account/server during validation. Public web documentation is a reference, not the runtime source of truth.

---

# 43. Handoff Prompt for the Next Agent

```text
Use this Markdown document as the implementation-validation source of truth for BotTradeGold B1-FINAL-v1.

Do not retune the alpha logic.

Implement and validate:
- XAUUSD M15
- Donchian30 using previous 30 completed bars
- RSI14 guard: long <=75, short >=25
- ATR14
- entry on first executable tick of next M15 bar
- SL = 2.5 ATR
- TP = 3.5R
- max one B1 position
- no partial TP
- no BE
- no trailing
- no Martingale/grid
- fixed-fractional risk with equity-HWM DD tiers:
  <3% = 1%
  3–6% = 0.75%
  6–9% = 0.5%
  9–12% = 0.25%
  >=12% = stop new entries
- no daily hard stop
- no growth ladder

Prioritize deterministic parity and error handling before performance.

Build:
1. reference regression tests;
2. MQL5 EA;
3. trade-level structured ledger;
4. restart/idempotency safeguards;
5. Exness symbol-property adapter;
6. Exness Every-tick-based-on-real-ticks validation;
7. OOS/walk-forward;
8. Monte Carlo on final broker-realistic trade ledger;
9. Demo forward validation;
10. formal GO/NO-GO report.

Do not fabricate broker values.
Read them from MT5 at runtime.
Do not call a recent profitable result production-ready.
Keep the known 2012–2022 long-history failure visible.
If Monte Carlo tail risk is too high, reduce position-risk percentage rather than changing the signal logic or raising the DD limit.
```

---

**End of handoff**
