# Specification: Live Execution Bridge & Real-Money Risk Shield (Phase 2 & Phase 3)

> **Triage Label:** `ready-for-agent`  
> **Target Asset:** XAUUSD (Gold)  
> **Execution Seam:** Single-Point HTTP Webhook Ingestion API (`POST /webhook/tradingview`)  
> **Governing Standards:** [ADR-007], [ADR-011], [ADR-013], [ADR-018], [ADR-019], [ADR-020], [ADR-021], [ADR-022], [ADR-024]

---

## Problem Statement

Traders using the XAUUSD Master Pro indicator currently receive high-quality signals and JSON alert payloads on TradingView, but order execution in MetaTrader 5 remains manual or disconnected. 

In gold scalping (M15), manual execution introduces human error, delayed entries, emotional deviation, slippage during fast-moving market spikes, and missed scale-out opportunities (such as closing 50% volume at 1.0R and moving Stop Loss to Breakeven). Furthermore, running an automated bridge without institutional risk controls risks catastrophic account drawdown due to large lot sizing, news spikes, weekend rollover spread widening, and revenge trading after consecutive losses.

The user requires a fully automated, rock-solid execution bridge that translates TradingView alerts into broker-executed MT5 trades with strict real-money capital preservation safeguards.

---

## Solution

A robust, asynchronous Webhook Bridge service that listens for authenticated TradingView alerts, translates deterministic `order_id` lifecycle events into broker operations via MetaTrader 5, and enforces a multi-layered Risk Shield (dynamic lot sizing, strict small-account risk gates, daily circuit breakers, and rollover flats).

The system breaks down into three distinct operational phases:
- **Phase 1: Signal Engine & Strategy Hardening (COMPLETED)**: Hardened indicator and twin backtester on TradingView M15 with conservative Stop Loss precedence, `tp1Bar` runner protection, Ask-spread calibration ($0.30), killzone guard, and deterministic order ID generation.
- **Phase 2: Live Execution Bridge (Current Focus)**: Lightweight, authenticated FastAPI bridge receiving JSON webhooks, validating cryptographic tokens, mapping deterministic order IDs, sizing lots via dynamic risk formula, and executing pending limits, partial closes, and breakeven adjustments via the MT5 adapter.
- **Phase 3: Demo Staging & Real-Money Risk Shield**: Deployment verification pipeline starting with dry-run tests, 2-week live demo forward-testing, automated daily circuit breaker enforcement (max 2 daily losses), news blackout guards, and final production rollout with 1.0% account risk.

---

## User Stories

1. As a live gold scalper, I want TradingView `SETUP_PENDING` alerts to automatically place Limit Orders in MT5, so that I never miss an institutional FVG pullback entry.
2. As a risk-conscious trader, I want the bridge to dynamically calculate lot size based on 1.0% account risk and actual SL dollar distance, so that my risk per trade remains constant regardless of volatility.
3. As a small-account owner, I want the bridge to reject any order where a 0.01 lot size would exceed 1.5% account risk, so that my account never violates the Strict Small-Account Risk Gate ([ADR-020]).
4. As an automated trader, I want every webhook to carry a deterministic `order_id` based on symbol and bar index, so that duplicate or retried webhooks are 100% idempotent and never place duplicate trades.
5. As a live gold scalper, I want TradingView `ORDER_FILLED` alerts to update the active trade state and log MT5 ticket IDs, so that the lifecycle state machine remains synchronized with the broker.
6. As a profit-taking trader, I want TradingView `TP1_HIT_MOVE_BE` alerts to automatically close 50% of the active MT5 position, so that cash profits are locked at +1.0R ([ADR-018]).
7. As a capital-preserving trader, I want the bridge to move the remaining 50% runner's Stop Loss to Breakeven (+0.10 buffer) upon TP1 hit, so that the trade becomes completely risk-free.
8. As a disciplined trader, I want TradingView `ORDER_CANCELED` alerts to immediately delete pending Limit orders in MT5 when TTL expires or killzones close, so that orphan orders do not trigger unexpectedly during off-hours.
9. As an automated trader, I want TradingView `TRADE_CLOSED` alerts to cleanly finalize the trade lifecycle in the local SQLite audit log, so that I have a persistent record of all realized trades.
10. As a security-conscious operator, I want incoming webhooks to require a secure Bearer token or secret passphrase, so that unauthorized internet requests cannot trigger orders on my broker account.
11. As a gold scalper, I want all orders to automatically close before 20:55 UTC, so that I avoid triple-swap charges and extreme rollover spread widening ([ADR-007]).
12. As an investor protecting capital, I want a Daily Circuit Breaker that halts all new trade entries for the rest of the UTC day after 2 consecutive realized losses, so that emotional revenge trading is mechanically impossible ([ADR-011]).
13. As an automated trader, I want a 30-minute cooldown period after any Stop Loss hit, so that the system does not re-enter choppy or adverse market conditions.
14. As an institutional trader, I want trade entries blocked during high-impact USD news blackout windows (30 minutes before and after CPI/NFP), so that slippage does not destroy expectancy ([ADR-010]).
15. As a mobile operator, I want real-time Telegram notification cards sent immediately upon each execution event, so that I can monitor system behavior from anywhere ([ADR-013]).
16. As a macOS developer, I want the bridge to gracefully fall back to dry-run simulation mode when MT5 is unavailable, so that the entire execution stack can be verified on Mac without Windows virtualization.
17. As an auditor, I want all lifecycle events and execution results logged to SQLite with UTC timestamps, so that trade history can be synced with Google Sheets or post-trade analytics.
18. As a production operator, I want a health-check endpoint (`GET /health`) reporting MT5 connection status, account equity, and circuit breaker state, so that monitoring systems can verify uptime.

---

## Implementation Decisions

### Architectural Topology
The execution architecture is organized as a unidirectional, event-driven pipeline:
```
TradingView Alert (M15) 
  --> HTTPS POST /webhook/tradingview 
  --> Authentication & Invariant Gate 
  --> Risk Shield (Lot Sizing & Small-Account Gate) 
  --> MT5 Execution Adapter 
  --> SQLite Audit Log & Telegram Notification
```

### Module Boundaries & Interfaces

1. **Webhook Ingestion Engine (`scripts/webhook_bridge.py`)**:
   - Exposes asynchronous FastAPI endpoint `POST /webhook/tradingview`.
   - Parses incoming payload against strongly typed Event Schemas.
   - Enforces secret token header verification.
   - Idempotency guard: Tracks processed `order_id` + `event` pairs in an in-memory cache and SQLite to reject duplicate deliveries.

2. **Domain Event Payload Contract**:
   ```
   {
     "event": "SETUP_PENDING" | "ORDER_FILLED" | "TP1_HIT_MOVE_BE" | "ORDER_CANCELED" | "TRADE_CLOSED",
     "order_id": string (e.g. "XAUUSD_12345"),
     "symbol": string,
     "dir": "BUY" | "SELL",
     "type": "SMC_PRIME" | "TSS" | "GSS_OTE",
     "limit": float (optional),
     "entry": float (optional),
     "sl": float (optional),
     "new_sl": float (optional),
     "tp1": float (optional),
     "tp2": float (optional),
     "action": string (optional, e.g. "PARTIAL_CLOSE"),
     "close_percent": int (optional, e.g. 50),
     "reason": string (optional),
     "ttl": int (optional),
     "time": string (UTC format: "YYYY-MM-DD HH:MM:SS")
   }
   ```

3. **Risk Shield & Sizing Interface**:
   - Integrates existing `scripts/smc/risk.py` and `scripts/smc/orchestrator.py`.
   - Dynamic lot sizing formula:
     $$\text{Lot} = \frac{\text{Equity} \times \text{RiskPct}}{\text{SL Distance} \times 100}$$
   - **Zero-Double-Buffer Invariant:** When invoking `calculate_lot_size()` using alert payload prices, pass `spread_buffer=0.0`. The incoming `sl` from TradingView is already spread-buffered (`rawSl = extremum - slBuffer`). Re-adding spread buffer would artificially inflate distance and under-allocate position size by ~15%.
   - Clamped to broker minimum (0.01) and maximum lot steps.
   - Invariant rejection: If `Lot < 0.01` and forcing 0.01 produces `RiskPct > 1.5%`, reject order immediately ([ADR-020]).
   - Circuit breaker check: Query daily realized loss count. If $\ge 2$, reject entry ([ADR-011]).
   - Rollover flat check: Check UTC time $\ge 20:55$. Reject new setups and close open positions ([ADR-007]).

4. **Execution Adapter & Order-Scoping Interface (`scripts/smc/mt5_adapter.py`)**:
   - `OrderIntent` carries `order_id: Optional[str] = None` and `ticket: Optional[int] = None`.
   - Idempotency is persistently recorded in SQLite `processed_webhooks (order_id, event, processed_at)` table to prevent duplicate execution across process restarts.
   - Translates domain `OrderIntent` to `MetaTrader5` platform calls:
     - `PLACE_LIMIT` $\rightarrow$ `ORDER_TYPE_BUY_LIMIT` / `ORDER_TYPE_SELL_LIMIT` with SL and TP. Stores `comment=f"SMC_{order_id}"` for persistent ticket correlation.
     - `PARTIAL_CLOSE` $\rightarrow$ `TRADE_ACTION_DEAL` with volume = 50% of open volume, targeted strictly to the matching ticket.
     - `MOVE_SL_TO_BE` $\rightarrow$ `TRADE_ACTION_SLTP` updating SL to entry $\pm$ spread buffer, targeted strictly to the matching ticket.
     - `CANCEL_LIMIT` $\rightarrow$ `TRADE_ACTION_REMOVE` targeted strictly to the pending order matching `ticket` or `order_id` comment. Never cancels unrelated orders on the symbol.
   - Cross-platform parity: If `MetaTrader5` package is missing or running on macOS, automatically activate dry-run mode with simulated execution and persistent SQLite audit logs.

---

## Testing Decisions

### The Single Testing Seam
The entire execution bridge will be tested at the highest possible seam:
**`TestClient(app).post("/webhook/tradingview", json=payload, headers=auth_headers)`**

A good test verifies external behavior and real business invariants, not internal function calls:
- Verifies that sending `SETUP_PENDING` with valid risk produces a pending limit order, logs a SQLite lifecycle record, and returns HTTP 200.
- Verifies that sending `SETUP_PENDING` when daily losses = 2 returns HTTP 200 with `REJECTED_CIRCUIT_BREAKER`.
- Verifies that sending `SETUP_PENDING` with excess risk on a small account returns HTTP 200 with `REJECTED_RISK_GATE`.
- Verifies that repeating the exact same `order_id` payload returns HTTP 200 with `IGNORED_DUPLICATE`.
- Verifies that `TP1_HIT_MOVE_BE` triggers a 50% volume close and shifts Stop Loss to entry + buffer.
- Verifies that `ORDER_CANCELED` deletes the active pending order ticket.
- Verifies that invalid tokens return HTTP 401 Unauthorized.

### Prior Art
- Unit test harness in `tests/test_smc_mt5_adapter.py` (verifies SQLite logging and dry-run execution).
- Test harness in `tests/test_smc_live_execution.py` (verifies orchestrator state machine and circuit breakers).

---

## Out of Scope

- Multi-pair trading (this system is strictly optimized and calibrated for XAUUSD).
- High-frequency tick scalping (M1/M5 tick arbitrage); the system operates on M15 bars with institutional limit entries.
- Automated web scraping of Forex Factory (news blackout schedules are fed via YAML configuration or structured API).
- Custom mobile app development (Telegram bot cards serve as the mobile copilot interface).

---

## Further Notes

- **Phase Breakdown & Milestones:**
  - **Phase 1 (Complete):** TradingView Pine Script v6 Indicator & Strategy with ADR-024 hardened execution and 67/67 passing tests.
  - **Phase 2 (Next Immediate Work):** Build `scripts/webhook_bridge.py`, configuration schema, and test suite `tests/test_webhook_bridge.py`.
  - **Phase 3 (Staging & Live Run):** Forward demo validation (Exness / IC Markets Demo MT5 account), Telegram live feed validation, and real-capital activation.
