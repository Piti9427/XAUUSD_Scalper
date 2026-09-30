# Product Requirements Document (PRD)
## BotTradeGold — Automated XAUUSD Trading System

**Document Version:** 1.1\
**Status:** Product-boundary document. Research target frozen. Live execution NO-GO.\
**Adopted:** 2026-09-29\
**Primary Environment:** macOS + Oracle Cloud Ubuntu ARM64 + MetaTrader 5 / Exness\
**Target Production Model:** MQL5 EA execution with external research/monitoring plane

This file is the product map: system boundaries, environment roles, and promotion gates. It does not replace the documents below.

| Role | Authority |
|---|---|
| Strategy rules, risk/fee math, live NO-GO | [`CORE_STRATEGY.md`](../CORE_STRATEGY.md) |
| Active research / Shadow plan | [`.cursor/plans/pure_b1_go-live_6dcb0773.plan.md`](../.cursor/plans/pure_b1_go-live_6dcb0773.plan.md) |
| Replay evidence | [`docs/reviews/2026-09-29-pure-b1-target-replay-verdict.md`](reviews/2026-09-29-pure-b1-target-replay-verdict.md) |
| SMC v2 glossary | [`CONTEXT.md`](../CONTEXT.md) |

Requirements in this file are product targets. They do not authorize `order_send`, Demo strategy automation, or real-money trading. Pure B1 in this repository is a research target with a read-only Shadow path. `main.py` runs the legacy wick strategy. `mql5/B1FinalEA.mq5` is a different contract.

---

## 1. Product Summary

BotTradeGold is an automated XAUUSD trading system designed to:

- ingest real market data;
- evaluate a deterministic trading strategy;
- apply strict risk controls;
- open, manage, and close trades automatically;
- preserve broker-side protection via SL/TP;
- run research/backtesting independently from live execution;
- provide monitoring, telemetry, alerting, and auditable trade history;
- support migration from Mac-based forward testing to a persistent production execution host without redesigning the core system.

The architecture separates **Research / Validation**, **Execution**, and **Monitoring / Control** so that failure of the research or monitoring server cannot directly stop or corrupt live order execution.

---

## 2. Problem Statement

The current project contains multiple architecture variants:

1. Python-centric strategy execution through MetaTrader5.
2. Oracle Ubuntu hosting Wine + headless MT5.
3. Native Windows VPS hosting MT5 + Python.
4. MQL5 EA as an alternative execution path.

These variants create ambiguity over:

- where strategy decisions run;
- which host is authoritative for live execution;
- whether Oracle ARM64 is part of the trading critical path;
- whether Python or MQL5 is the production execution engine;
- which strategy and risk configuration is the source of truth.

The product needs one production-oriented architecture that can be developed with existing hardware now and migrated later without major refactoring.

---

## 3. Product Goals

| Goal | Requirement |
|---|---|
| Automated trading | Detect signal, size position, open order, manage position, and exit without manual intervention |
| Deterministic behavior | Same strategy specification must produce equivalent signals in research and execution environments |
| Realistic validation | Backtest with real historical data and include spread, swap, slippage, and broker constraints |
| Safe execution | Every live position must use broker-side SL/TP and risk gates |
| Fault isolation | Oracle research/monitoring failure must not stop live execution |
| 24/5 readiness | Architecture must support migration to persistent MT5 hosting |
| Auditable operation | Every signal, order, rejection, error, and deployment version must be traceable |
| Controlled promotion | No direct research-code-to-live deployment without validation gates |

---

## 4. Non-Goals

This version does not require:

- AI/LLM inference in the live execution path;
- HFT or sub-millisecond execution;
- multi-broker routing;
- portfolio trading across multiple asset classes;
- martingale or unrestricted grid recovery;
- automatic strategy self-modification in production;
- forcing MT5 x86_64 to run on Oracle ARM64 through Wine/emulation as the primary production design.

---

## 5. Target Users

### Primary
**Trader / Owner**
- reviews strategy performance;
- supervises running bot;
- receives alerts;
- can halt trading;
- approves go-live releases.

### Secondary
**Developer / Operator**
- develops Python research code and MQL5 EA;
- runs tests and backtests;
- maintains infrastructure;
- deploys approved versions;
- investigates execution anomalies.

---

## 6. High-Level Architecture

```text
                         BOTTRADEGOLD
                              │
           ┌──────────────────┴──────────────────┐
           │                                     │
           ▼                                     ▼
┌─────────────────────┐              ┌────────────────────────┐
│ Mac                 │              │ Oracle Ubuntu ARM64    │
│                     │              │ 4 vCPU / ~24 GB RAM    │
│ DEVELOPMENT +       │              │                        │
│ FORWARD-TEST HOST   │              │ RESEARCH / OPS         │
│                     │              │                        │
│ Cursor / Codex      │◄────────────►│ Historical Data        │
│ Git                 │              │ Python Backtesting     │
│ MQL5                │              │ Optimization           │
│ MetaTrader 5        │              │ Walk-Forward / OOS     │
│ Strategy Tester     │              │ Analytics              │
│ BotTradeGold EA     │              │ Monitoring API         │
└──────────┬──────────┘              │ Trade Database         │
           │                         │ Alerts / Dashboard     │
           │                         └────────────────────────┘
           ▼
┌─────────────────────┐
│ Exness / MT5 Broker │
│                     │
│ Market Feed         │
│ Orders              │
│ Broker-side SL/TP   │
└─────────────────────┘
```

### Future Production Host

```text
Mac
Development only
     │
     ▼
Approved Release
     │
     ▼
MT5 VPS / Windows VPS
     │
     ├── MetaTrader 5
     └── BotTradeGold EA
              │
              ▼
            Exness
```

Oracle Ubuntu remains Research / Monitoring infrastructure after production migration.

The Mac box is the development and forward-test host. It is not an approved Pure B1 order path. Current Pure B1 work on that host is read-only Shadow: no `order_send` and no Telegram for that path.

---

## 7. Architecture Principles

1. **Execution must remain local to MT5.**\
   Strategy evaluation, risk checks, order dispatch, and position management must not depend on Oracle Ubuntu being reachable.

2. **Oracle Ubuntu is not in the hot path.**\
   It may receive telemetry and run analytics, but live orders must continue if the server is unavailable.

3. **Broker-side protection is mandatory.**\
   Every live order must submit valid SL/TP where supported. Local-only stop logic is not sufficient.

4. **MQL5 EA is the target production execution engine.**\
   Python remains the primary research/backtesting environment unless a future requirement explicitly changes this.

5. **One strategy specification must govern all implementations.**\
   Python and MQL5 implementations must derive from the same documented rules.

6. **Deployment is gated.**\
   Code must pass reproducible testing and forward validation before real-money release.

---

## 8. Core Trading Workflow

```text
Market Tick / New Bar
        │
        ▼
Market Guard
├── Market open?
├── Spread acceptable?
├── Session allowed?
├── News blackout?
└── Data valid?
        │
        ▼
Strategy Engine
        │
        ▼
Candidate Signal
        │
        ▼
Risk Manager
├── Position already open?
├── Risk budget available?
├── Daily / drawdown limits OK?
├── Lot within broker limits?
└── Margin sufficient?
        │
        ▼
Execution Engine
├── OrderCheck
├── Submit order
├── Confirm broker result
└── Persist execution state
        │
        ▼
Position Manager
├── SL / TP
├── Break-even
├── Partial close
├── Trailing
└── Exit
        │
        ▼
Telemetry / Audit
```

---

## 9. Functional Requirements

### FR-01 — Market Data

The system must:

- receive live bid/ask and bar data from MT5;
- support the strategy timeframe defined by `CORE_STRATEGY.md`;
- detect stale or missing data;
- record spread at signal and execution time.

### FR-02 — Strategy Engine

The strategy engine must:

- be deterministic;
- use only explicitly documented strategy rules;
- generate `BUY`, `SELL`, or `NO_TRADE`;
- record why a signal was accepted or rejected;
- be versioned independently from infrastructure code.

**Important:** Current project artifacts contain conflicting B1 definitions. The definitive Donchian period, RSI rules, EMA usage, ATR multipliers, and entry semantics must be frozen in `CORE_STRATEGY.md` before production.

### FR-03 — Market Guards

Before creating an entry, the EA must validate:

- market/trading session availability;
- maximum spread;
- broker symbol status;
- optional economic-news blackout;
- no duplicate signal/order on the same eligible event;
- valid quote/tick age.

### FR-04 — Risk Manager

The risk manager must enforce:

- maximum risk per trade;
- maximum lot;
- broker minimum lot and lot step;
- maximum concurrent positions;
- account drawdown stop;
- daily loss stop;
- minimum free margin;
- no order when calculated position size is below executable broker minimum unless the configured policy explicitly allows fixed minimum lot.

Risk parameters must be externalized and versioned.

### FR-05 — Order Execution

The execution layer must:

- run broker-side pre-checks before dispatch;
- set a unique Magic Number / strategy identifier;
- protect against duplicate submission;
- record broker order/deal IDs;
- reconcile requested vs executed volume and price;
- distinguish rejection, timeout, requote, partial fill, and successful execution;
- never send a success alert before broker confirmation.

### FR-06 — Position Management

The system must support configurable:

- hard Stop Loss;
- Take Profit;
- break-even trigger;
- partial close;
- trailing stop;
- time-based exit;
- emergency close behavior.

All management rules must be idempotent after restart.

### FR-07 — Restart Recovery

After EA/MT5 restart, the system must:

1. query broker positions/orders;
2. identify positions belonging to BotTradeGold;
3. rebuild internal state;
4. avoid reopening an already active signal;
5. resume position management safely.

### FR-08 — Telemetry

The EA should emit asynchronous telemetry containing at minimum:

- timestamp;
- environment;
- account type;
- symbol;
- strategy version;
- EA version;
- event type;
- signal side;
- entry / SL / TP;
- requested and executed lot;
- spread;
- broker order/deal ID;
- rejection/error reason;
- account equity;
- drawdown.

Failure to send telemetry must not block live trading.

### FR-09 — Monitoring

Oracle Ubuntu must support:

- heartbeat status;
- last received EA event;
- active position snapshot;
- daily realized P/L;
- current drawdown;
- execution/rejection/error counts;
- deployment version;
- alert when heartbeat becomes stale.

### FR-10 — Alerts

The system should alert on:

- confirmed trade open;
- confirmed trade close;
- stop-loss / take-profit;
- daily loss or drawdown guard activation;
- repeated order rejection;
- EA heartbeat missing;
- MT5/broker connectivity issue;
- strategy halted.

### FR-11 — Kill Switch

The operator must have a documented procedure to:

- disable new entries;
- preserve or close existing positions according to policy;
- manually close positions through broker/MT5;
- mark the system as halted;
- require explicit re-enable action.

Remote kill-switch implementation must use authenticated, auditable commands and must not expose public unauthenticated endpoints.

---

## 10. Research & Backtesting Requirements

Oracle Ubuntu is the primary research compute environment.

The backtesting pipeline must support:

```text
Historical Data
      ↓
Data Validation
      ↓
Strategy Replay
      ↓
Spread / Swap / Slippage Model
      ↓
Metrics
      ↓
Parameter Robustness
      ↓
Out-of-Sample
      ↓
Walk-Forward
      ↓
Monte Carlo
      ↓
Final Gate
```

Required metrics:

| Category | Metrics |
|---|---|
| Return | Net P/L, Total R, Expectancy |
| Quality | Profit Factor, Win Rate |
| Risk | Max Drawdown, Consecutive Losses |
| Execution | Spread cost, swap, slippage |
| Sample | Trade count, period coverage |
| Robustness | OOS result, walk-forward result, parameter sensitivity |

Backtests must use real historical market data. Synthetic data may be used only for unit/error-path tests and must never be presented as strategy-performance evidence.

---

## 11. Python ↔ MQL5 Parity Requirement

Before production, both implementations must be run over the same deterministic sample.

Minimum comparison:

| Field | Requirement |
|---|---|
| Signal timestamp | Must match according to defined bar/tick semantics |
| Direction | Must match |
| Entry condition | Must match |
| SL / TP calculation | Must match within symbol rounding rules |
| Signal count | Any divergence requires investigation |
| Position sizing | Must match the same risk policy |

A strategy cannot proceed to live deployment while unexplained parity differences remain.

---

## 12. Data & Storage

Recommended logical datasets:

```text
data/
├── raw/
├── processed/
├── broker_exports/
└── backtests/

Database
├── strategy_versions
├── backtest_runs
├── backtest_trades
├── deployments
├── ea_heartbeat
├── ea_events
├── live_trades
└── daily_metrics
```

Historical raw market data must be immutable after ingestion.

---

## 13. Repository Requirements

```text
BotTradeGold/
│
├── ea/
│   ├── BotTradeGold.mq5
│   ├── strategy/
│   ├── risk/
│   ├── execution/
│   ├── position/
│   └── monitoring/
│
├── research/
│   ├── strategies/
│   ├── backtest/
│   ├── optimization/
│   ├── walkforward/
│   └── montecarlo/
│
├── config/
│   ├── strategy/
│   ├── risk/
│   └── environments/
│
├── monitoring/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── parity/
│   └── failure/
│
└── docs/
    ├── PRD.md
    ├── ARCHITECTURE.md
    ├── CORE_STRATEGY.md
    ├── RISK_POLICY.md
    ├── BACKTEST_SPEC.md
    ├── GO_LIVE.md
    └── RUNBOOK.md
```

That tree is the target repository shape. The current repository keeps `CORE_STRATEGY.md` at the root, strategy code in `scripts/`, and this product map at `docs/PRD.md`.

---

## 14. Source-of-Truth Documents

| Document | Authority | Current file |
|---|---|---|
| `PRD.md` | Product requirements and system boundaries | this file |
| `CORE_STRATEGY.md` | Exact strategy rules, risk/fee math, and live NO-GO | [`CORE_STRATEGY.md`](../CORE_STRATEGY.md) |
| `ARCHITECTURE.md` | Runtime topology and component ownership | not created; section 6 is the product target |
| `RISK_POLICY.md` | Future split of capital/risk limits | not created; limits stay in `CORE_STRATEGY.md` |
| `BACKTEST_SPEC.md` | Validation methodology | not created; evidence stays in `docs/reviews/` |
| `GO_LIVE.md` | Promotion criteria | not created; section 17–18 state the target gates |
| `RUNBOOK.md` | Recovery, restart, incidents, kill switch | not created |

Create a planned document only when its content is known. Until then, the current file in this table keeps that authority. HTML diagrams under `docs/diagrams/` are presentation artifacts and do not override these documents.

---

## 15. Environment Model

### Development
**Host:** Mac

Purpose:

- coding;
- MT5 Strategy Tester;
- MQL5 compile/test;
- local Python development;
- controlled experiments.

### Research / Operations
**Host:** Oracle Ubuntu ARM64

Purpose:

- data ingestion/storage;
- Python backtesting;
- optimization;
- OOS/walk-forward;
- reporting;
- monitoring;
- telemetry;
- alerts.

### Forward-Test Execution
**Host:** Mac + MT5

Purpose:

- Exness demo forward testing after a separate approval;
- execution parity;
- live spread/slippage collection;
- restart/recovery testing.

Pure B1 on this host is read-only Shadow until that approval. `main.py` remains the legacy wick runtime.

Requirements:

- power connected;
- sleep disabled;
- stable network;
- AutoTrading enabled;
- monitoring active.

### Production
**Target Host:** MT5 VPS or native Windows VPS

Purpose:

- persistent MT5 runtime;
- BotTradeGold EA;
- 24/5 execution independent from local Mac.

---

## 16. Non-Functional Requirements

### Reliability

- Strategy execution must not depend on monitoring availability.
- Repeated evaluation must not generate duplicate orders.
- EA restart must recover broker state.
- Critical execution failures must fail closed for new entries.

### Security

- Broker credentials must not be committed to Git.
- API/Telegram secrets must use environment-specific secret storage.
- Oracle inbound ports must follow least privilege.
- Monitoring endpoints must require authentication.
- Kill-switch actions must be authenticated and logged.

### Observability

Every important decision must be explainable:

```text
NO_TRADE:
spread_too_high

REJECTED:
daily_loss_limit

ORDER_FAILED:
invalid_stops

TRADE_OPENED:
broker_deal_id=...
```

### Maintainability

- Strategy logic separated from execution logic.
- Risk policy separated from strategy.
- Environment-specific configuration not hard-coded.
- Production configuration versioned and reproducible.

### Portability

Migrating execution:

```text
Mac MT5
    ↓
MT5 VPS / Windows VPS
```

must not require redesign of the strategy or Oracle research services.

---

## 17. Go-Live Promotion Pipeline

```text
Strategy Idea
     ↓
CORE_STRATEGY.md
     ↓
Python Implementation
     ↓
Unit Tests
     ↓
Historical Backtest
     ↓
Realistic Costs
     ↓
Robustness Tests
     ↓
OOS
     ↓
Walk-Forward
     ↓
Final Gate
     ↓
MQL5 Implementation
     ↓
Python ↔ MQL5 Parity
     ↓
MT5 Strategy Tester
     ↓
Demo Forward Test
     ↓
Failure / Restart Test
     ↓
24/5 Stability Test
     ↓
Human Go-Live Approval
     ↓
Small Live Account
```

---

## 18. Go-Live Acceptance Criteria

A release is eligible for real-money review only if all of the following are satisfied:

### Strategy

- `CORE_STRATEGY.md` is frozen for the release.
- Backtest is reproducible.
- Realistic costs are included.
- OOS and walk-forward tests are complete.
- No unexplained Python/MQL5 signal divergence remains.

### Execution

- Duplicate-order protection verified.
- Broker-side SL/TP verified.
- Restart recovery verified.
- Broker rejection paths verified.
- Invalid lot / margin / stop-distance handling verified.

### Risk

- All configured risk caps are enforced by automated tests.
- Drawdown and daily-loss circuit breakers are tested.
- No code path bypasses Risk Manager for new entries.

### Operations

- Telemetry works.
- Heartbeat alerts work.
- Deployment version is visible in logs.
- Kill-switch runbook is tested.
- Operator can identify and manually close live positions independently from the bot.

### Forward Test

The demo forward test must run for the period defined in `GO_LIVE.md` and collect sufficient evidence for:

- real spread;
- slippage;
- order fill behavior;
- swap;
- reconnect/restart behavior;
- live-vs-backtest performance drift.

---

## 19. Decisions

Research-target parameters below are frozen in [`CORE_STRATEGY.md`](../CORE_STRATEGY.md) as of 2026-09-29. That freeze selects the contract for continued research. It does not approve Demo orders or real money.

| Decision | Research-target contract |
|---|---|
| Bar input | Completed UTC Bid M15 assembled from M1 bars with 15/15 minutes present |
| Donchian period | 30 prior bars, excluding the signal bar |
| EMA filter | EMA50. BUY only when close is above EMA50. SELL only when close is below EMA50 |
| RSI rules | RSI14, EWM span 14, `adjust=False`. Both sides require `30 < RSI < 70` |
| SL/TP model | SL 2.5 ATR, TP 6.25 ATR. ATR14 is the rolling mean of true range |
| Risk per trade | Fixed 0.01 lot. Reject the order when SL risk exceeds 10% of equity. Do not resize the lot |
| Daily loss limit | 40% of day-start equity, UTC day. Stop new entries until the next day |
| Position model | Single position. Recovery, martingale, and grid are disabled |
| Live promotion | NO-GO |

These items stay open until a later decision records them:

| Decision | Still open |
|---|---|
| News source | Provider and fallback are unset. News blackout stays optional |
| Production host | MT5 VPS or native Windows VPS |
| Telemetry storage | SQLite or PostgreSQL for the first production release |
| Alert channel | Telegram only, or an additional channel |
| Python ↔ MQL5 parity | Not demonstrated for this contract |
| Separate `RISK_POLICY.md` | Risk text remains in `CORE_STRATEGY.md` until an explicit split |

---

## 20. Milestones

### M1 — Specification Freeze
Deliver:

- PRD;
- architecture;
- core strategy specification;
- risk policy;
- backtest specification.

### M2 — Research Pipeline
Deliver:

- reproducible data loader;
- B1 backtester;
- realistic execution-cost model;
- standard metrics report;
- OOS / walk-forward support.

### M3 — MQL5 EA
Deliver:

- Strategy Engine;
- Risk Manager;
- Execution Engine;
- Position Manager;
- recovery;
- logging.

### M4 — Parity & Failure Testing
Deliver:

- Python ↔ MQL5 parity report;
- duplicate-order tests;
- restart tests;
- broker rejection simulations;
- SL/TP verification.

### M5 — Demo Forward Test
Deliver:

- continuous demo run;
- telemetry;
- execution-cost report;
- incident log;
- go-live evidence package.

### M6 — Persistent Hosting
Deliver:

- approved MT5 VPS / Windows VPS deployment;
- production runbook;
- monitoring;
- backup / recovery procedure.

### M7 — Small Live
Deliver:

- approved production configuration;
- restricted initial risk;
- active supervision;
- post-trade reconciliation.

---

## 21. Product Success Criteria

BotTradeGold v1 is successful when:

1. a validated strategy can be implemented once from a single authoritative specification;
2. Python and MQL5 produce explainably equivalent signals;
3. the EA can autonomously open, manage, and close XAUUSD trades;
4. risk limits cannot be bypassed by normal execution flow;
5. live execution survives monitoring-server failure;
6. open positions remain protected if the Mac/EA loses connectivity;
7. every live trade is attributable to an exact strategy, risk profile, and software version;
8. execution can be migrated from Mac to persistent MT5 hosting without redesigning the system.

---

## 22. Product Decision

For BotTradeGold v1:

> **Mac = Development + MT5 forward-test host. Pure B1 order path is not approved.**\
> **Oracle Ubuntu ARM64 = Research + Backtesting + Validation + Monitoring**\
> **MQL5 EA = Target production execution engine, not the current Pure B1 runtime**\
> **Exness/MT5 = Market and broker authority**\
> **MT5 VPS / Windows VPS = Future persistent production execution host**\
> **`CORE_STRATEGY.md` = Frozen research-target rules and live NO-GO**

Oracle Ubuntu must not be placed between the strategy EA and broker order execution.

---

## 23. Existing Artifact Reconciliation

The existing HTML artifacts should be treated as architecture/design references, not as the final source of truth.

Done in this adoption:

- exact strategy parameters and risk values for the research target live in `CORE_STRATEGY.md`;
- this PRD points at that file instead of leaving those parameters open.

Still required before any production claim:

- keep Oracle ARM64 + Wine/x86_64 MT5 off the primary production path;
- keep Python MT5 execution in research and Shadow tooling;
- treat the MQL5 EA as the target production runtime after parity, not as the current Pure B1 contract;
- regenerate architecture diagrams from `CORE_STRATEGY.md` and this PRD.
