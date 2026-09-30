"""New predeclared research contracts; historical discovery only."""

from scripts.research.breakout_logic import Rules


def structure_candidates():
    """384 structural invalidation experiments, not adopted ATR-parent changes.

    Stop beyond setup/trigger extremes by one tick; fixed parent ATR target.
    Order sells first because previous reused-tape direction research motivates
    this hypothesis, not because that history is independent validation.
    """
    return [
        (
            parent,
            "structural_invalidation_and_protection",
            Rules(
                stop_mode="structure",
                target_atr=target,
                entry_mode=entry,
                entry_guard=guard,
                risk_cap=risk,
                daily_loss_limit=0.05,
                protect_mode=protect,
            ),
        )
        for parent, target in (("donchian48", 3.0), ("core", 6.25))
        for guard in ("sell_only", "off", "buy_only", "prior_day")
        for entry in ("immediate", "confirm", "retest", "failed_reverse")
        for risk in (0.025, 0.05, 0.10)
        for protect in ("off", "break_even", "candle_trail", "runner")
    ]


def risk_target_candidates():
    """384 pullback/invalidation experiments; target follows initial stop risk."""
    return [
        (
            parent,
            "retest_trigger_stop_and_risk_target",
            Rules(
                stop_mode=stop,
                target_atr=target,
                target_rr=rr,
                entry_mode=entry,
                entry_guard=guard,
                risk_cap=risk,
                daily_loss_limit=0.05,
                protect_mode=protect,
            ),
        )
        for parent, target in (("donchian48", 3.0), ("core", 6.25))
        for guard in ("off", "sell_only")
        for entry in ("retest", "confirm")
        for stop in ("trigger", "structure")
        for risk in (0.025, 0.05)
        for rr in (1.5, 2.0, 3.0)
        for protect in ("off", "break_even", "candle_trail", "runner")
    ]


def boundary_candidates():
    """384 level-invalidation/session/loss-circuit experiments."""
    circuits = ((0, 0, "off"), (4, 0, "off"), (4, 2, "candle_trail"), (4, 2, "break_even"))
    return [
        (
            parent,
            "buffered_boundary_and_loss_circuit",
            Rules(
                stop_mode="boundary",
                target_atr=target,
                target_rr=rr,
                entry_mode=entry,
                entry_guard=guard,
                risk_cap=risk,
                daily_loss_limit=0.05,
                cooldown_bars=cooldown,
                max_daily_losses=losses,
                session_mode=session,
                protect_mode=protect,
            ),
        )
        for parent, target in (("donchian48", 3.0), ("core", 6.25))
        for guard in ("off", "sell_only")
        for entry in ("immediate", "retest")
        for session in ("london_ny", "all")
        for risk in (0.05, 0.10)
        for rr in (1.5, 2.0, 3.0)
        for cooldown, losses, protect in circuits
    ]


def wick_sweep_features(bars):
    """Current completed candle rejects one prior48-bar edge; two-edge sweeps skip."""
    import numpy as np
    from scripts.research.breakout_logic import features

    frame = features(bars)
    upper = (frame.high > frame.hh) & (frame.close < frame.hh) & (frame.low >= frame.ll)
    lower = (frame.low < frame.ll) & (frame.close > frame.ll) & (frame.high <= frame.hh)
    frame["direction"] = np.select([lower, upper], [1, -1], 0)
    return frame


def sweep_candidates():
    """384 new failed-auction strategies; no indicator tuning or parent replacement."""
    return [
        (
            "sweep",
            "wick_rejection_at_prior_range",
            Rules(
                stop_mode="structure",
                target_rr=rr,
                entry_guard=guard,
                session_mode=session,
                risk_cap=risk,
                daily_loss_limit=0.05,
                protect_mode=protect,
            ),
        )
        for guard in ("off", "buy_only", "sell_only", "body_dominant")
        for session in ("london_ny", "all")
        for risk in (0.025, 0.05, 0.10)
        for rr in (1.5, 2.0, 3.0, 0.0)
        for protect in ("off", "break_even", "candle_trail", "runner")
    ]


def trend_pullback_features(bars):
    """Completed two-candle reversal of pullback, aligned with fixed EMA50 slope."""
    import numpy as np
    from scripts.research.breakout_logic import features

    frame = features(bars)
    trend = frame.close.ewm(span=50, adjust=False).mean()
    previous = frame.shift(1)
    buy = (
        (previous.close < previous.open)
        & (frame.close > previous.high)
        & (frame.close > trend)
        & (trend > trend.shift(4))
    )
    sell = (
        (previous.close > previous.open)
        & (frame.close < previous.low)
        & (frame.close < trend)
        & (trend < trend.shift(4))
    )
    frame["direction"] = np.select([buy, sell], [1, -1], 0)
    frame.loc[frame.index[:50], "direction"] = 0
    return frame


def pullback_candidates():
    """384 trend-continuation contracts; fixed detection, only execution/risk variants."""
    return [
        (
            "pullback",
            "trend_aligned_pullback_reclaim",
            Rules(
                stop_mode="trigger",
                target_rr=rr,
                entry_guard=guard,
                session_mode=session,
                risk_cap=risk,
                daily_loss_limit=0.05,
                protect_mode=protect,
            ),
        )
        for guard in ("off", "buy_only", "sell_only", "body_dominant")
        for session in ("london_ny", "all")
        for risk in (0.025, 0.05, 0.10)
        for rr in (1.5, 2.0, 3.0, 0.0)
        for protect in ("off", "break_even", "candle_trail", "runner")
    ]


def activation_candidates():
    """288 new profit-state transitions after1R/1.5R/2R; default halfR excluded."""
    return [
        (
            parent,
            "delay_profit_protection_until_full_r",
            Rules(
                stop_mode=stop,
                target_atr=target,
                entry_guard=guard,
                risk_cap=risk,
                daily_loss_limit=daily,
                protect_mode=protect,
                protect_after_r=activation,
            ),
        )
        for parent, target in (("donchian48", 3.0), ("core", 6.25))
        for guard in ("sell_only", "off")
        for stop in ("atr", "boundary")
        for risk in (0.05, 0.10)
        for daily in (0.05, 0.20)
        for activation in (1.0, 1.5, 2.0)
        for protect in ("runner", "candle_trail", "break_even")
    ]


def drawdown_candidates():
    """336 contracts with reversible drawdown-based admission, never lot changes."""
    protection_states = [("off", 0.5)] + [
        (mode, activation)
        for mode in ("break_even", "candle_trail", "runner")
        for activation in (0.5, 1.0)
    ]
    return [
        (
            parent,
            "reduce_admission_budget_during_drawdown",
            Rules(
                risk_mode="drawdown_steps",
                risk_cap=0.10,
                daily_loss_limit=daily,
                target_atr=target,
                entry_guard=guard,
                stop_mode=stop,
                protect_mode=protect,
                protect_after_r=activation,
                reset_after_exit=reset,
            ),
        )
        for parent, target in (("donchian48", 3.0), ("core", 6.25))
        for guard in ("off", "sell_only", "buy_only")
        for stop in ("atr", "boundary")
        for daily in (0.05, 0.20)
        for protect, activation in protection_states
        for reset in (False, True)
    ]
