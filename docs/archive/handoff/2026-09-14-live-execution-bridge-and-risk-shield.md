# Engineering Handoff: Live Webhook Bridge & Async Risk Shield (Phase 2 & Phase 3)

> **Date:** 2026-09-14  
> **Repository:** `/Users/nopparuj/my-agents/XAUUSD_Scalper`  
> **Current Branch:** `feature/smc-v2-hardening`  
> **Target Asset:** Spot Gold (XAUUSD) on Timeframe M15 / M5  
> **Specification:** [`docs/specs/2026-09-14-live-execution-bridge-and-risk-shield-spec.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/specs/2026-09-14-live-execution-bridge-and-risk-shield-spec.md)  
> **Governing Standards:** [ADR-007], [ADR-011], [ADR-012], [ADR-018], [ADR-019], [ADR-020], [ADR-022], [ADR-024]  

---

## 1. Executive Summary & Current Operational State

In this session, we built, hardened, verified, and launched the **Production-Grade XAUUSD Live Webhook Bridge & Risk Shield Engine** to translate TradingView alerts into broker-executed MT5 trades (or dry-run simulations) with strict real-money financial safety guards.

### Live Running Status
- **Service Status:** Active background task (`task-1170`, PID 62700)
- **Host & Port:** Bound to `http://0.0.0.0:8000`
- **Execution Mode:** `DRY-RUN` (Simulated execution with SQLite persistent audit trail)
- **Account Sizing:** Initial Equity `$10,000.00` | Risk per Trade `1.0%` ($100 max)
- **Circuit Breaker:** Max 2 daily losses before halt ([ADR-011])
- **Rollover Flat Cutoff:** 20:55 UTC ([ADR-007])
- **Logs:** `.system_generated/tasks/task-1170.log`
- **Database:** `data/smc_trades.db`

---

## 2. Hardened Architecture & Async Python Patterns

The bridge ([`scripts/webhook_bridge.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/webhook_bridge.py)) implements 3 foundational high-throughput patterns to maintain webhook responses under 20ms:

1. **Pattern A — Non-Blocking Broker & Disk Offloading (`asyncio.to_thread`)**
   - Offloads all synchronous MetaTrader 5 broker operations and SQLite transactions (`execute_intent`, `get_daily_realized_losses`, `get_account_equity`, `log_lifecycle_event`) to the worker thread pool.
   - Prevents GIL bottlenecks and never blocks the FastAPI async event loop.

2. **Pattern B — Fire-and-Forget Notification Side Effects (`BackgroundTasks`)**
   - Out-of-band delivery of Telegram cards via `background_tasks.add_task(_dispatch_tg_safe, card)`.
   - Webhook returns HTTP 200 to TradingView immediately without waiting on external Telegram API HTTP latency.

3. **Pattern C — Two-Tier In-Memory Idempotency Cache ([ADR-024])**
   - First checks an in-memory `Set[Tuple[str, str]]` (`(order_id, event)`), bypassing disk I/O entirely for repeated webhook retries with $O(1)$ lookup.
   - Backed by SQLite table `processed_webhooks` for persistence across service restarts.

---

## 3. Real-Money Risk Shields & Financial Invariants

All incoming webhooks pass through a multi-layered gate before any broker intent is generated:

| Seam / Safeguard | Mechanism & Standard | Behavior on Violation |
| :--- | :--- | :--- |
| **Authentication** | Bearer Token / `X-Webhook-Secret` | HTTP 401 Unauthorized |
| **Idempotency** | Memory Cache + SQLite Unique `(order_id, event)` | HTTP 200 `ignored_duplicate` (< 1ms) |
| **Daily Circuit Breaker** | [ADR-011] Realized Loss Count $\ge 2$ | Rejects order, halts trading until 00:00 UTC |
| **Post-SL Cooldown** | [ADR-011] 30-min window after Stop Loss | Rejects new setups during adverse market conditions |
| **Rollover Flat Guard** | [ADR-007] UTC Hour $\ge 20:55$ | Rejects order, flattens positions before swap/spread spike |
| **News Blackout Window** | [ADR-010] $\pm 30$ mins high-impact USD news | Rejects order during high slippage periods |
| **Small-Account Risk Gate** | [ADR-020] Min lot (0.01) risk > 1.5% balance | Rejects order to prevent small-account wipeout |
| **Target Scoping** | [ADR-024] `order_id` / `ticket` scoping | Rejects untargeted bulk order cancellations / modifications |

---

## 4. Verification Evidence & Test Coverage

1. **Unit Test Suite:**
   - Command: `.venv/bin/python -m unittest discover -s tests`
   - Result: **88/88 tests passed in 0.831s (100% Green)**.
   - Covers authentication, limit execution, order lifecycle, scale-outs, Breakeven moves, circuit breakers, and async patterns.

2. **End-to-End Dry-Run Verification:**
   - Script: [`scripts/verify_dry_run.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/verify_dry_run.py)
   - Result: **8/8 verification gates passed 100%**:
     - `[1/8]` Health Check (`/health` telemetry)
     - `[2/8]` `SETUP_PENDING` (BUY limit placement, dynamic lot sizing)
     - `[3/8]` Two-tier idempotency duplicate rejection
     - `[4/8]` `ORDER_FILLED` lifecycle logging
     - `[5/8]` `TP1_HIT_MOVE_BE` (50% scale-out + SL moved to BE +0.10)
     - `[6/8]` `TRADE_CLOSED` (Runner TP2 hit +2.5R PnL tracking)
     - `[7/8]` `ORDER_CANCELED` (Targeted TTL limit order cancellation)
     - `[8/8]` Daily Circuit Breaker (Blocked 3rd trade after 2 daily losses)

---

## 5. Key Repository Artifacts

- **Server Runner:** [`scripts/run_staging_bridge.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/run_staging_bridge.py)
- **Webhook Bridge Engine:** [`scripts/webhook_bridge.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/webhook_bridge.py)
- **MT5 Execution Adapter:** [`scripts/smc/mt5_adapter.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/mt5_adapter.py)
- **Risk Calculator:** [`scripts/smc/risk.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/risk.py)
- **TradingView Pine Script v6:** [`tradingview/xauusd_master_pro_v6.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine)
- **Runtime Configuration:** [`config/settings.yaml`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/config/settings.yaml)
- **Verification Harness:** [`scripts/verify_dry_run.py`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/verify_dry_run.py)

---

## 6. Immediate Next Steps for Next Session

1. **Expose Public Webhook URL**:
   - Run a tunnel (e.g. `cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`) or deploy to a VPS.
   - Point TradingView Alert Webhook URL to `https://<public-url>/webhook/tradingview`.
2. **Forward-Testing in Demo Mode**:
   - Run forward-testing against demo signals for 2 weeks in dry-run/demo to observe signal alignment.
   - Verify SQLite trade journal in `data/smc_trades.db`.
3. **Live MT5 Connector (Windows / Wine)**:
   - When deploying to a live MT5 terminal, set `dry_run: false` in `config/settings.yaml` and configure broker login credentials in `mt5` section.

---

## 7. Suggested Skills for Next Agent

1. `verification-before-completion`: Run regression tests and verify process logs before modifying any core execution modules.
2. `diagnosing-bugs`: If any webhook delivery failure, network timeout, or broker rejection occurs during live testing.
3. `async-python-patterns`: When adding new asynchronous consumers (e.g., websockets, streaming quotes, or real-time web UI).
4. `code-review`: For validating any future strategy parameter adjustments or risk policy changes.
