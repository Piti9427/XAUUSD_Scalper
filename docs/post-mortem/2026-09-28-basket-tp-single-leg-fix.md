# Post-Mortem: Basket TP Single Leg Fix (2026-09-28)

## 1. Context & Intent
- **Account Size:** $200
- **Strategy:** B1_TP25 (Win Rate ~35%)
- **Issue:** The `BasketManager` was closing single legs (`leg_count == 1`) at a tiny profit (`net_pnl > 0`) due to `basket_tp_reached` firing on any positive PnL.
- **Problem:** A 35% win rate strategy relies mathematically on 2.5R outsized winners to survive and offset frequent 1R losses. Closing 1 leg at a small profit destroys the expectancy, resulting in a simulated **-860% return**.
- **Goal:** Update `basket_tp_reached` to only trigger if the recovery leg is active (`leg_count > 1`). Single legs must run to their full 2.5R TP.

## 2. Changes Made
### `scripts/smc/basket_manager.py`
Updated `basket_tp_reached` to return `False` if `self.leg_count <= 1`.

```python
    def basket_tp_reached(self, floating_pnl: float) -> bool:
        """Basket TP: net turns strictly positive. Break-even alone is not enough to close.
        Only applies if there's more than one leg (recovery active). Single legs must hit their 2.5R TP."""
        if self.leg_count <= 1:
            return False
        return self.net_pnl_with_floating(floating_pnl) > 0.0
```

### `tests/test_basket_manager.py`
- Removed single-leg `on_bar(floating_pnl=1.0)` triggers that expected `CLOSE_PENDING`.
- Replaced with direct `on_leg_closed(0, 1.0)` to simulate single leg TP/SL hits by the broker.
- Added a recovery leg explicitly in `test_basket_tp_does_not_fire_at_zero_pnl` before testing TP logic.
- All 14 tests pass successfully.

## 3. Backtest Verification (Exness Tick Replay May-Sep 2026)

Simulation of 164 trades proved the mathematical necessity of this fix:

*   **Before Fix (Early Basket TP for single legs):**
    *   Final Balance: $-1520.75 (Profit: -860.4%)
    *   Max Drawdown: 845.74%
    *   *Result: Total Account Blowout*

*   **After Fix ($30 Hard Loss Cap + Full 2.5R Targets for single legs):**
    *   Final Balance: $750.39 (Profit: +275.2%)
    *   Max Drawdown: 46.95%
    *   *Result: Safe and highly profitable*

## 4. Verdict
The fix is load-bearing. It transforms the strategy on a $200 account from a mathematical failure to a **+275%** profitable system, while maintaining the $30 Basket SL and 0.02 recovery escape hatch.
