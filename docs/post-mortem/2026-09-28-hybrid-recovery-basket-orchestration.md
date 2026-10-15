# Post-Mortem: Hybrid Sniper-Recovery & Basket Orchestration Flaws

- **Date:** 2026-09-28 13:09 UTC+7
- **Commit:** [`24049af049faf765ac19a3a4e1dcbbf8366f93a3`](https://github.com/Piti9427/XAUUSD_Scalper/commit/24049af049faf765ac19a3a4e1dcbbf8366f93a3)
- **Target Modules:**
  - `scripts/smc/basket_manager.py`
  - `scripts/smc/orchestrator.py`
  - `scripts/strategy.py`
- **Author/Owner:** Piti9427
- **Status:** Resolved & Validated

---

### 1. Summary
Initial implementation of Hybrid Sniper-Recovery overlay (EMA trend filter + multi-leg `BasketManager`) introduced 5 structural seam flaws. The most critical caused newly opened baskets to immediately self-close on the subsequent bar at break-even ($0.00), desynchronized `account.pending_order` state in `StrategyOrchestrator`, caused EMA filter to fail-open on missing data, permanently locked baskets in `CLOSE_PENDING`, and rendered basket stop-loss inert when callers omitted `floating_pnl`. Fixed by enforcing strictly positive TP (`> 0.0`), synchronizing pending order intent, making EMA checks fail-closed, adding optimistic leg-close transitions, and implementing MTM bar-level floating PnL estimation in `orchestrator.py`. Validated via automated repro suite and 33 new/updated unit tests.

---

### 2. Symptom
1. **Premature Basket TP:** Basket opened via `on_new_signal()` immediately emitted `CLOSE_MARKET` on the very next bar with reason `BASKET_TP_NET_POSITIVE leg-0` without price moving in profit.
2. **Orchestrator State Loss:** `account.pending_order` remained `None` after basket creation. Step-2b in `orchestrator.py` ran on every subsequent bar thinking the position was flat.
3. **EMA Filter Fail-Open:** When `calculate_indicators()` was skipped or `ema_long` column was missing, counter-trend setup signals were silently emitted as `BUY`/`SELL`.
4. **Permanent Stall in `CLOSE_PENDING`:** After a basket SL breach emitted `CLOSE_MARKET`, `mgr.state` remained stuck in `BasketState.CLOSE_PENDING`. All future `on_new_signal()` calls returned `[]`.
5. **Inert Basket SL:** When `floating_pnl` defaulted to `0.0`, a 300-point gold market crash failed to trigger the $30 basket stop-loss.

---

### 3. Root Cause

1. **`basket_manager.py::basket_tp_reached`:**  
   Condition was `net_pnl_with_floating(floating_pnl) >= 0.0`. On fresh baskets, `net_realized_pnl == 0.0` and default `floating_pnl == 0.0`. Condition evaluated `0.0 >= 0.0` as `True` immediately.
2. **`orchestrator.py::on_bar` (Step 5a):**  
   Basket branch returned `intents` directly (`return intents`) without assigning `account.pending_order = basket_intents[0]`. Orchestrator lifecycle lost track of pending limit orders.
3. **`strategy.py::check_signals` (Step 6):**  
   Used `if ema_long_val is not None and not pd.isna(ema_long_val): ...` to wrap filter comparisons. Missing/NaN data bypassed the block and fell through directly to `return "BUY" / "SELL"`.
4. **`basket_manager.py::_close_all_legs`:**  
   Emitted `CLOSE_MARKET` intents and set `self.state = BasketState.CLOSE_PENDING` but did not modify `leg.is_open`. `on_bar()` had no transition from `CLOSE_PENDING` back to `FLAT`, and `on_leg_closed()` was never called by the non-broker harness.
5. **`orchestrator.py::on_bar` Signature Default:**  
   Parameter `floating_pnl: float = 0.0` defaulted to zero with no fallback MTM calculation from `bar["close"]` vs `leg.entry_price`.

---

### 4. Why It Produced the Symptom
- **Seam gap between State Machine and Detection:** When `orchestrator.py` exited early without updating `account.pending_order`, it decoupled `AccountState` from `BasketManager`.
- **Default zero treated as profit:** Financial break-even ($0.00) was mathematically grouped with profit targets (`>= 0.0`), confusing zero-delta initialization with a profitable target.
- **Fail-open fallback:** Missing data was treated as "filter not applicable" instead of "data corrupted/unavailable".

---

### 5. Fix

- **`scripts/smc/basket_manager.py`:**
  - In `basket_tp_reached()`, changed condition to strictly positive: `> 0.0`.
  - In `_close_all_legs()`, added optimistic close: `leg.is_open = False`.
  - In `on_bar()`, added auto-transition: if `self.state == BasketState.CLOSE_PENDING` and not `open_legs`, reset `self.basket = None` and `self.state = BasketState.FLAT`.
- **`scripts/smc/orchestrator.py`:**
  - In Step 5a, added `account.pending_order = basket_intents[0]` and `account.pending_bars_held = 0`.
  - In Step 2b, added fallback MTM floating PnL estimation when `floating_pnl == 0.0`:
    $$\text{price\_diff} \times \text{lot\_size} \times 100.0$$
- **`scripts/strategy.py`:**
  - In Step 6, made missing data fail-closed:
    ```python
    if ema_long_val is None or pd.isna(ema_long_val):
        return "EMA_DATA_MISSING"
    ```

---

### 6. How It Was Found
- **Trigger:** Code review via `/scrutinize` traced end-to-end seam calls between `main.py`, `strategy.py`, `orchestrator.py`, and `basket_manager.py`.
- **Repro:** Script `.gemini/antigravity-cli/brain/1730c142-c74c-49ae-b1bc-af441f236211/scratch/repro_verdict.py` reproduced 5/5 deterministic failures prior to code changes:
  ```
  FAIL B2: basket_tp NOT triggered at floating_pnl=0.0 immediately after open
  FAIL B1: account.pending_order set after basket opens
  FAIL B3: EMA filter returns EMA_DATA_MISSING when ema_long column absent
  FAIL M4/6: BasketManager auto-resets to FLAT after CLOSE_PENDING
  FAIL M5: orchestrator estimates floating PnL from bar price when caller omits it
  ```

---

### 7. Why It Slipped Through
- **Unit test isolation bias:** Initial 12 tests in `tests/test_basket_manager.py` called `mgr.on_bar(floating_pnl=1.0)` directly and manually invoked `mgr.on_leg_closed(0, 1.0)`. They tested internal math without exercising integration seams against `StrategyOrchestrator` or testing default edge cases (`floating_pnl=0.0`).
- **Missing seam harness:** Orchestrator tests had not yet been updated with a `BasketManager` fixture.

---

### 8. Validation
- **Deterministic Repro:** `repro_verdict.py` flipped from 0/5 to 5/5 PASS:
  ```
  PASS B2: basket_tp NOT triggered at floating_pnl=0.0 immediately after open
  PASS B1: account.pending_order set after basket opens
  PASS B3: EMA filter returns EMA_DATA_MISSING when ema_long column absent
  PASS M4/6: BasketManager auto-resets to FLAT after CLOSE_PENDING
  PASS M5: orchestrator estimates floating PnL from bar price when caller omits it
  ```
- **Module Unit Tests:**
  - `tests/test_basket_manager.py`: 14/14 passed (added tests 13 & 14).
  - `tests/test_strategy.py`: 7/7 passed (added 3 EMA filter tests).
  - `tests/test_smc_orchestrator.py`: 22/22 passed (added orchestrator basket integration test).
- **Regression Suite:** Full discovery ran 486 tests; 0 new regressions introduced.

---

### 9. Action Items / Follow-ups
1. **Wire Broker Trade-Closed Event:** Ensure live adapter (`scripts/smc/mt5_adapter/`) invokes `basket_manager.on_leg_closed()` upon official ticket fill/close confirmations rather than relying solely on optimistic bar transitions.
2. **Configurable Basket Profit Target:** Add `basket_target_usd` or `basket_target_r` to `settings.yaml` under `money_management:` so minimum take-profit buffer is explicitly configurable instead of hardcoded `> 0.0`.
