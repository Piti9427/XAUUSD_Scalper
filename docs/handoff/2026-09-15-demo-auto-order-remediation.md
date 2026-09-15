# Handoff: Exness Demo Auto-Order Remediation & Scrutinize Review

**Date**: 2026-09-15
**Context**: Reviewing auto-order execution remediation plan ([`docs/plans/2026-09-15-demo-auto-order-remediation-plan.md`](../plans/2026-09-15-demo-auto-order-remediation-plan.md)) via `/scrutinize`.

---

## 1. Goal & Current Status

- **Goal**: Implement an automated order entry bot for Exness Demo MT5 driven by Pine Script (`tradingview/xauusd_master_pro_strategy.pine`) on M15, strictly enforcing 0.5% max risk per trade, broker-reconciled order lifecycles, and zero phantom Telegram alerts.
- **Current Status**: 
  - The remediation plan was scrutinized against codebase reality.
  - **Verdict**: `REWORK`. The plan has a fundamental architectural blocker (missing broker lifecycle reconciler daemon) and two major discrepancies (payload schema break and account capital sizing).
  - Baseline test suite has 1 pre-existing failing test in [`tests/test_verdict_repro.py`](../../tests/test_verdict_repro.py).

---

## 2. Key Scrutinize Findings & Critical Gaps

### [BLOCKER] Missing Broker Reconciliation Polling Worker
- **References**: [`scripts/webhook_bridge.py`](../../scripts/webhook_bridge.py), [`scripts/smc/mt5_adapter.py:119-161,257-266`](../../scripts/smc/mt5_adapter.py#L119-L161), [`docs/plans/2026-09-15-demo-auto-order-remediation-plan.md:15,74-82`](../plans/2026-09-15-demo-auto-order-remediation-plan.md#L15)
- **Problem**: The plan assumes the existing Webhook Bridge already owns reconciliation and that Pine only needs to emit `SETUP_PENDING`. In reality, `webhook_bridge.py` is a passive FastAPI server with NO background polling loop.
- **Deadlock Sequence**:
  1. MT5 Pending Limit Order only accepts a single TP (set to TP2). MT5 has no native partial close at TP1.
  2. If Pine only emits `SETUP_PENDING` and no background worker polls MT5, no process will trigger 50% partial close at TP1 or move SL to BE.
  3. No process cancels the pending order after TTL (4 bars = 60 mins) expires.
  4. When position closes on MT5 (SL or TP2 hit), no process detects it or calls `adapter.finish_setup()`.
  5. `setup_inbox` in SQLite remains locked at `status='accepted'`. Because of the `setup_inbox_one_active` UNIQUE INDEX, **all subsequent trades are permanently blocked with `busy`**.

### [MAJOR] Payload Schema Incompatibility
- **References**: [`scripts/webhook_bridge.py:118,262-268`](../../scripts/webhook_bridge.py#L118), [`docs/plans/2026-09-15-demo-auto-order-remediation-plan.md:30-32`](../plans/2026-09-15-demo-auto-order-remediation-plan.md#L30-L32)
- **Problem**: Plan defines Schema-v2 (`setup_id`, `entry`, `direction`, `symbol`, `engine`, etc.), while `webhook_bridge.py` and 1,000+ lines of existing tests expect `order_id`, `limit`, `dir`, `type`. Strict Pydantic enforcement without field aliases will break the existing test suite.

### [MAJOR] Demo Account Capital Sizing vs 0.5% Risk Rule
- **References**: [`tradingview/xauusd_master_pro_strategy.pine:2,231-233`](../../tradingview/xauusd_master_pro_strategy.pine#L2), [`scripts/profitability_qualification.py:113-124`](../../scripts/profitability_qualification.py#L113-L124)
- **Problem**: In XAUUSD (contract size 100 oz), 0.02 split lot with a typical $4.00 SL costs ~$8.90 risk. At 0.5% max risk, minimum account balance must be **>= $1,780 USD**. The plan mentions `$100 fixtures` and Pine has `initial_capital=100`. An Exness Demo account with < $1,800 will be permanently rejected as `NOT_VIABLE`. Exness Demo balance must be provisioned at >= $3,000.

### [MINOR / PREREQUISITE] Pre-existing Test Failure
- **References**: [`tests/test_verdict_repro.py:53-54`](../../tests/test_verdict_repro.py#L53-L54), [`scripts/smc/mt5_adapter.py:328`](../../scripts/smc/mt5_adapter.py#L328)
- **Problem**: `test_repro_trade_closed_webhook_does_not_trip_circuit_breaker` fails because `adapter.log_lifecycle_event` uses `datetime.now(timezone.utc)` instead of the event payload's timestamp. Needs to accept an optional `timestamp` argument to make the baseline test suite 100% green.

---

## 3. Work Sequence for Incoming Agent

1. **Step 0 (Pre-requisite)**: Fix `adapter.log_lifecycle_event` to accept an optional `timestamp` parameter and pass `event_dt` in `webhook_bridge.py:630`. Verify all 145 tests pass:
   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```
2. **Step 1**: Revise [`docs/plans/2026-09-15-demo-auto-order-remediation-plan.md`](../plans/2026-09-15-demo-auto-order-remediation-plan.md):
   - Add architecture specification for an active `BrokerLifecycleReconciler` background worker (runs in `asyncio` loop alongside FastAPI).
   - Define Reconciler responsibilities:
     - TTL check: cancel pending limit order if unfilled after `orderTtlBars` (60m).
     - Fill detection: detect pending -> open position transition, dispatch Telegram notification.
     - TP1 check: detect price reaching TP1, send partial close (50% vol), move SL to BE, notify Telegram.
     - Close detection: detect position closed, query `history_deals_get` for net PnL (profit + swap + commission), record `TRADE_CLOSED`, call `finish_setup()`.
   - Update Schema-v2 to support field aliases (`entry` / `limit`, `setup_id` / `order_id`, `direction` / `dir`).
   - Specify Exness Demo account balance requirement (>= $3,000).
3. **Step 2**: Implement Schema-v2 Pydantic model with aliases and test admissions.
4. **Step 3**: Implement `BrokerLifecycleReconciler` with comprehensive unit and fake-broker integration tests covering:
   `SETUP_PENDING` -> limit placed -> fill -> TP1 (50% close + BE move) -> TP2 close -> `setup_inbox` unlocked.
5. **Step 4**: Implement single canonical `alert()` in `tradingview/xauusd_master_pro_strategy.pine`.
6. **Step 5**: Dry-run verification and live Exness Demo canary validation.

---

## 4. Suggested Skills

- **`diagnosing-bugs` / `systematic-debugging`**: Use to resolve the pre-existing test failure in `test_verdict_repro.py`.
- **`codebase-design`**: Use to design a clean, modular `BrokerLifecycleReconciler` background task decoupled from FastAPI request handlers.
- **`test-driven-development`**: Build deterministic fake-broker lifecycle state machines before touching live MT5 execution.
- **`verification-before-completion`**: Mandate full test run (`.venv/bin/python -m unittest discover -s tests`) and RED loop checks before any commit.

---

## 5. Primary Code & Documentation Pointers

| Item | Path |
|---|---|
| Remediation Plan | [`docs/plans/2026-09-15-demo-auto-order-remediation-plan.md`](../plans/2026-09-15-demo-auto-order-remediation-plan.md) |
| Webhook Bridge | [`scripts/webhook_bridge.py`](../../scripts/webhook_bridge.py) |
| MT5 Adapter | [`scripts/smc/mt5_adapter.py`](../../scripts/smc/mt5_adapter.py) |
| Pine Strategy | [`tradingview/xauusd_master_pro_strategy.pine`](../../tradingview/xauusd_master_pro_strategy.pine) |
| Profitability ADR | [`docs/adr/0025-profitability-qualification.md`](../adr/0025-profitability-qualification.md) |
| Test Suite | [`tests/test_webhook_bridge.py`](../../tests/test_webhook_bridge.py), [`tests/test_verdict_repro.py`](../../tests/test_verdict_repro.py) |
