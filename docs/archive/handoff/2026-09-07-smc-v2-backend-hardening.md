# Engineering Handoff: XAUUSD SMC v2 Hardening & Production Seams

> **Date:** 2026-09-07  
> **Current Branch:** `feature/smc-v2-hardening`  
> **Base Branch:** `develop` (clean at `6db6a51`)  
> **Last Commit:** `3f6655c` (`feat(smc): harden SMC v2 strategy logic and execution seams for real-money trading`)  
> **Test Status:** 53/53 Unit Tests Passing (`python3 -m unittest discover -s tests`)  
> **Canonical Documents:** [AGENTS.md](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/AGENTS.md) (Real-Money Safety Rules), [CONTEXT.md](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md) (ADR-001 through ADR-022)

---

## 1. Executive Summary & Current State

This project is a high-precision, production-grade algorithmic trading and Telegram copilot engine for **XAUUSD (Gold)** built on Smart Money Concepts (SMC: Liquidity Sweeps, Market Structure Shifts, Displacement, and Fair Value Gaps).

### What Has Been Implemented & Verified on `feature/smc-v2-hardening`:
1. **Dynamic SL Cap & True Swing Extremum (ADR-019)**:
   - Expanded SL cap from narrow $6.00 to realistic **$25.00** in [scripts/smc/detection.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py) to accommodate Gold's high price ($4,500–$5,200).
   - Invalidation SL anchored to True Swing Extremum (absolute lowest/highest wick between sweep and MSS) preventing double-wick stop-outs.
2. **Two-Tier Scale-Out Profit Architecture (ADR-018)**:
   - Implemented in [scripts/smc/orchestrator.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py) and [scripts/smc/backtester.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py): Closes 50% volume at **+1.0R**, moves SL to Breakeven (+ spread buffer), and allows 50% runner to target **+2.5R**.
3. **Strict Small-Account Risk Gate (ADR-020)**:
   - Implemented in [scripts/smc/risk.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/risk.py): Strictly rejects (`is_valid=False`) setups if the minimum broker lot size (0.01 lot) risks more than 1.5% of account balance.
4. **Immediate Fill-Bar SL/TP Evaluation**:
   - Unified position lifecycle via `_evaluate_open_position()` in [scripts/smc/orchestrator.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py). Immediately handles same-bar stop-outs on limit fills.
5. **Execution-Coupled Notifications (ADR-021)**:
   - In [smc_main.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py), moved Telegram trade setup card dispatching inside the intent loop to trigger strictly after Orchestrator approves `OrderIntentType.PLACE_LIMIT`. Added trade closed notification card dispatching upon position closure.
6. **Timezone Uniformity (ADR-022)**:
   - Normalized all timestamps across MT5, candles, news, and detection to timezone-aware UTC.

### Backtest Validation Evidence ([scripts/run_backtest.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/run_backtest.py)):
- **Dataset**: 69 trading days of historical Gold data (2026-03-10 to 2026-05-18).
- **Baseline SMC v1 ($6 Cap, Flat BE)**: 0 trades, $0.00 profit (100% of setups filtered by narrow SL).
- **Optimized SMC v2**: 4 trades, 75.00% win rate (3 wins, 1 loss), **Profit Factor 1.49**, Max Drawdown 0.50%, Net Profit +$24.81 (positive mathematical expectancy).

---

## 2. Priority Fix Queue (Audited via `/scrutinize`)

Before deploying to the Oracle Cloud VM (Ampere A1 aarch64) or merging to `develop`, the following 6 findings must be resolved on `feature/smc-v2-hardening`:

### 🔴 Blocker 1: Hardcoded $10,000 Balance in `smc_main.py`
- **Location:** [smc_main.py:64](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py#L64), [scripts/mt5_connector.py](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/mt5_connector.py)
- **Problem:** `account = AccountState(balance=10000.0, equity=10000.0)` is hardcoded. `MT5Connector` has no method to query `mt5.account_info()`. If connected to a real $500 or $1,000 account, position sizing risks $50 per trade (10% risk!), bypassing the Strict Small-Account Risk Gate.
- **Action Required:**
  1. Add `get_account_info()` to `MT5Connector` (`info = mt5.account_info()`, return `{"balance": info.balance, "equity": info.equity, "margin_free": info.margin_free}`).
  2. In `smc_main.py`, dynamically sync `account.balance` and `account.equity` on startup and on every bar evaluation. In dry-run mode, update `account.balance += pnl_dollars` when trades close.

### 🔴 Blocker 2: Broker Order Rejection Leaves Phantom Position & Sends Telegram Alert
- **Location:** [smc_main.py:204-220](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py#L204-L220), [scripts/smc/orchestrator.py:257-268](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py#L257-L268)
- **Problem:** `orchestrator.on_bar()` sets `account.pending_order = new_order` in memory *before* broker execution. If `adapter.execute_intent(PLACE_LIMIT)` fails at the broker (`res.success == False` due to margin, volume, or closed market), `account.pending_order` is not rolled back, and the Telegram alert is still dispatched.
- **Action Required:**
  In `smc_main.py`:
  ```python
  if intent.intent_type == OrderIntentType.PLACE_LIMIT:
      if not res.success:
          logger.error("Broker rejected order: %s. Rolling back pending order.", res.message)
          account.pending_order = None
          continue
      # Only send alert if broker placement succeeded
      ...
  ```

### 🟡 Major 3: Missing `type_filling` in MT5 Order Requests
- **Location:** [scripts/smc/mt5_adapter.py:137-147, 203-214, 232-241](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/mt5_adapter.py#L137-L147)
- **Problem:** MT5 broker requests (`TRADE_ACTION_PENDING` and `TRADE_ACTION_DEAL`) omit `type_filling`. Brokers like Exness, IC Markets, and Pepperstone reject these requests with error 10030 (`TRADE_RETCODE_UNSUPPORTED_FILLING_MODE`).
- **Action Required:**
  Query `mt5.symbol_info(self.symbol).filling_mode` to select `mt5.ORDER_FILLING_IOC`, `mt5.ORDER_FILLING_FOK`, or `mt5.ORDER_FILLING_RETURN`, and pass `type_filling` in all `order_send` request dictionaries.

### 🟡 Major 4: Spread Heuristic Breaks on 3-Digit Gold Quotes
- **Location:** [scripts/mt5_connector.py:67-75](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/mt5_connector.py#L67-L75), [smc_main.py:92-96](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py#L92-L96)
- **Problem:** `MT5Connector.get_spread()` returns raw integer points from `symbol_info.spread`. `smc_main.py` multiplies points by 0.01 if > 1.0. On brokers where Gold has 3 decimals (point = 0.001, spread = 250 points = $0.25), it calculates `250 * 0.01 = $2.50`, triggering the `$0.35` spread circuit breaker and blocking 100% of trades.
- **Action Required:**
  Update `MT5Connector.get_spread()` to compute `round(symbol_info.ask - symbol_info.bid, 4)` directly from price quotes.

### 🟡 Major 5: SQLite Lifecycle Audit Logging Silent During Live Trading
- **Location:** [scripts/smc/mt5_adapter.py:117-129, 148-246](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/mt5_adapter.py#L117-L129)
- **Problem:** `self.log_lifecycle_event(...)` is only invoked inside `if self.dry_run:`. Real MT5 executions (`PLACE_LIMIT`, `PARTIAL_CLOSE`, `CANCEL_LIMIT`, `MOVE_SL_TO_BE`, `CLOSE_MARKET`) do not write to SQLite `data/smc_trades.db`, violating ADR-013.
- **Action Required:**
  Call `self.log_lifecycle_event(...)` on successful execution across all live order branches.

### 🟢 Nit 6: `StrategyOrchestrator` Hardcodes 0.5% Risk Pct
- **Location:** [scripts/smc/orchestrator.py:20-43, 250](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py#L20-L43)
- **Problem:** `StrategyOrchestrator` does not accept `risk_pct` in `__init__` and calls `calculate_lot_size(..., max_sl_cap=self.max_sl_cap)` without passing `risk_pct`. Config changes in `settings.yaml` under `strategy.risk_pct` are ignored.
- **Action Required:**
  Add `risk_pct: float = 0.005` to `StrategyOrchestrator.__init__` and pass it through to `calculate_lot_size`.

---

## 3. Recommended Skills for Next Agent

- **`test-driven-development` / `tdd`**:
  Use to write reproduction tests in `tests/test_smc_mt5_adapter.py` and `tests/test_smc_orchestrator.py` for broker rejection rollback, account balance dynamic loading, and `type_filling` resolution before applying production changes.
- **`systematic-debugging` / `diagnosing-bugs`**:
  Use when validating broker reconciliation seams and MT5 tick data responses.
- **`verification-before-completion`**:
  Run full regression suite (`python3 -m unittest discover -s tests`) and `scripts/run_backtest.py` before proposing git commits or deployment cutovers.

---

## 4. Verification Checklist Before Deployment

1. [ ] Apply Fixes 1 through 6 on `feature/smc-v2-hardening`.
2. [ ] Run unit tests: `python3 -m unittest discover -s tests` (must pass 100%).
3. [ ] Run comparative backtest: `python3 scripts/run_backtest.py`.
4. [ ] Test MT5 connection with broker credentials: `python3 test_mt5.py`.
5. [ ] Verify `git diff` and commit with message `fix(smc): resolve broker execution seams and live account polling`.
6. [ ] Create PR to merge `feature/smc-v2-hardening` into `develop`.
