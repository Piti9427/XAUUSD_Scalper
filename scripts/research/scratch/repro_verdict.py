"""
repro_verdict.py — Reproduces all 5 verdict findings before any fixes are applied.
Each test is EXPECTED TO FAIL right now. Fixes will make them pass.

Run from project root:
  python3 .gemini/antigravity-cli/brain/1730c142-c74c-49ae-b1bc-af441f236211/scratch/repro_verdict.py
"""

import sys
from datetime import datetime, timezone

# ── helpers ──────────────────────────────────────────────────────────────────
OK = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
results = []


def check(label, condition, msg=""):
    mark = OK if condition else FAIL
    print(f"{mark}  {label}" + (f"  [{msg}]" if msg else ""))
    results.append((label, condition))


NOW = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)

# ─────────────────────────────────────────────────────────────────────────────
# Blocker 2: basket_tp_reached fires at 0.0 immediately after basket open
# ─────────────────────────────────────────────────────────────────────────────
from scripts.smc.basket_manager import BasketConfig, BasketManager, BasketState  # noqa: E402
from scripts.smc.types import Direction  # noqa: E402

cfg = BasketConfig(
    basket_fraction=0.15,
    basket_absolute_cap_usd=30.0,
    day_loss_fraction=0.15,
    max_new_baskets_per_utc_day=2,
    recovery_lots=[0.01, 0.02],
    max_recovery_legs=2,
    hwm_halt_fraction=0.20,
    reset_hwm_automatically=False,
)
mgr = BasketManager(config=cfg)
mgr.on_new_signal(Direction.BUY, 2600.0, 2595.0, 2620.0, equity=200.0, now=NOW)

# floating_pnl=0.0 (default) → net_pnl_with_floating = 0.0 >= 0.0 → TP fires immediately
intents = mgr.on_bar(floating_pnl=0.0, equity=200.0, now=NOW)
check(
    "B2: basket_tp NOT triggered at floating_pnl=0.0 immediately after open",
    len(intents) == 0,
    f"got {[i.reason for i in intents]}",
)

# ─────────────────────────────────────────────────────────────────────────────
# Blocker 1: account.pending_order not set when basket opens via orchestrator
# ─────────────────────────────────────────────────────────────────────────────
from scripts.smc.orchestrator import StrategyOrchestrator  # noqa: E402
from scripts.smc.types import AccountState, SetupSignal  # noqa: E402

import pandas as pd  # noqa: E402

mgr2 = BasketManager(config=cfg)
orch = StrategyOrchestrator(risk_pct=0.05, basket_manager=mgr2)
account = AccountState(balance=200.0, equity=200.0)

signal = SetupSignal(
    direction=Direction.BUY,
    sweep_price=2599.0,
    sweep_wick=2595.0,
    mss_price=2601.0,
    entry_price=2602.0,
    sl_price=2595.0,
    tp_price=2630.0,
    sl_distance=7.0,
    risk_r=2.0,
    fvg_high=2605.0,
    fvg_low=2601.0,
    reason="test signal",
    timestamp=NOW,
)
bar = {"time": NOW, "open": 2600.0, "high": 2605.0, "low": 2598.0, "close": 2603.0}
orch.on_bar(bar, account, setup_signal=signal, floating_pnl=0.0)
check(
    "B1: account.pending_order set after basket opens",
    account.pending_order is not None,
    f"pending_order={account.pending_order}",
)

# ─────────────────────────────────────────────────────────────────────────────
# Blocker 3: EMA filter fail-open when ema_long column is missing
# ─────────────────────────────────────────────────────────────────────────────
from scripts.strategy import XAUUSDSniperStrategy  # noqa: E402

config = {
    "strategy": {
        "ema_short": 20,
        "ema_long": 50,
        "rsi_period": 14,
        "rsi_oversold": 35,
        "rsi_overbought": 70,
        "tp_pips": 100,
        "sl_pips": 50,
        "max_spread": 30,
        "atr_multiplier_tp": 2.0,
        "atr_multiplier_sl": 1.5,
        "ema_trend_filter": True,  # enabled
    }
}
strat = XAUUSDSniperStrategy(config)

# Craft a bar that would trigger mss_long (bullish rejection, close > prev high)
# but has NO ema_long column → should block, not pass through
rows = []
for i in range(6):
    rows.append(
        {
            "time": datetime(2026, 9, 28, 11, i * 5, 0, tzinfo=timezone.utc),
            "open": 2600.0,
            "high": 2610.0,
            "low": 2590.0,
            "close": 2605.0,
            "tick_volume": 100,
        }
    )
# Force mss_long on iloc[-2]: wick-rejection + close > prev high
rows[-2] = {
    "time": datetime(2026, 9, 28, 11, 20, 0, tzinfo=timezone.utc),
    "open": 2600.0,
    "high": 2620.0,
    "low": 2598.0,
    "close": 2611.0,
    "tick_volume": 100,
}
rows[-3] = {
    "time": datetime(2026, 9, 28, 11, 15, 0, tzinfo=timezone.utc),
    "open": 2600.0,
    "high": 2608.0,
    "low": 2595.0,
    "close": 2607.0,
    "tick_volume": 100,
}

df = pd.DataFrame(rows)
# df has NO 'ema_long' column — simulating skipped calculate_indicators()
result = strat.check_signals(df, df, df, current_spread=5.0)
check(
    "B3: EMA filter returns EMA_DATA_MISSING when ema_long column absent",
    result == "EMA_DATA_MISSING",
    f"got '{result}' (expected EMA_DATA_MISSING, not BUY)",
)

# ─────────────────────────────────────────────────────────────────────────────
# Major 4&6: CLOSE_PENDING never clears — basket stuck after SL trigger
# ─────────────────────────────────────────────────────────────────────────────
mgr3 = BasketManager(config=cfg)
mgr3.on_new_signal(Direction.BUY, 2600.0, 2595.0, 2620.0, equity=200.0, now=NOW)
# Trigger basket SL
mgr3.on_bar(floating_pnl=-31.0, equity=169.0, now=NOW)
# State should be CLOSE_PENDING now; next bar should auto-recover to FLAT
# (requires optimistic close of legs in _close_all_legs)
next_bar = NOW.replace(minute=15)
mgr3.on_bar(floating_pnl=0.0, equity=169.0, now=next_bar)
check(
    "M4/6: BasketManager auto-resets to FLAT after CLOSE_PENDING",
    mgr3.state == BasketState.FLAT,
    f"got state={mgr3.state}",
)

# ─────────────────────────────────────────────────────────────────────────────
# Major 5: floating_pnl=0.0 default means basket SL never fires in practice
# Test: orchestrator estimates floating PnL from bar close when not provided
# ─────────────────────────────────────────────────────────────────────────────
mgr4 = BasketManager(config=cfg)
mgr4.on_new_signal(Direction.BUY, 2600.0, 2595.0, 2620.0, equity=200.0, now=NOW)
orch4 = StrategyOrchestrator(risk_pct=0.05, basket_manager=mgr4)
account4 = AccountState(balance=200.0, equity=200.0)

# Price crashes 300 points down — basket should sense loss via bar price
crash_bar = {"time": NOW, "open": 2600.0, "high": 2601.0, "low": 2298.0, "close": 2300.0}
intents4 = orch4.on_bar(crash_bar, account4, floating_pnl=0.0)  # no explicit floating_pnl
check(
    "M5: orchestrator estimates floating PnL from bar price when caller omits it",
    any(i.reason.startswith("BASKET_SL") for i in intents4),
    f"got {[i.reason for i in intents4]}",
)

# ─────────────────────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, v in results if v)
print(
    f"Results: {passed}/{len(results)} pass — {len(results) - passed} EXPECTED FAILURES (pre-fix)"
)
sys.exit(0 if passed == len(results) else 1)
