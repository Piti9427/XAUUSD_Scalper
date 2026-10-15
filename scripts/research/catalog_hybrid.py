"""Frozen hybrid challenger catalogs; preserve enumeration order."""

from dataclasses import asdict
from itertools import product

from .breakout_models import Rules
from .catalog_common import rules


def build(catalog, contracts):
    if catalog == "hybrid_atr_stop":
        return [
            dict(
                hypothesis="intermediate_atr_stop_with_loss_admission",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(period=7, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        stop_atr=stop,
                        target_rr=reward,
                        daily_loss_limit=daily,
                        max_daily_losses=losses,
                        protect_mode=protection,
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, stop, reward, daily, losses, protection in product(
                (25, 30, 35),
                (0.025, 0.05, 0.10),
                (1.5, 2.0),
                (1.35, 1.5, 2.0),
                (0.10, 0.20),
                (0, 1),
                ("off", "candle_trail"),
            )
        ]
    if catalog == "hybrid_reward_geometry":
        return [
            dict(
                hypothesis="rsi_buy_rounded_reward_trigger_boundary_stop",
                buy_filter="off",
                depth=0.0,
                entry_session=session,
                oscillator_spec=dict(period=7, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        daily_loss_limit=0.2,
                        stop_mode=stop,
                        target_rr=reward,
                        protect_mode=protection,
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, reward, stop, protection, session in product(
                (25, 30, 35),
                (0.025, 0.05, 0.10),
                (1.35, 1.5, 2.0),
                ("trigger", "boundary"),
                ("off", "candle_trail"),
                ("all", "avoid_rollover"),
            )
        ]
    if catalog == "hybrid_reward_quality":
        return [
            dict(
                hypothesis="rounded_reward_symmetric_candle_quality",
                buy_filter="off",
                depth=0.0,
                entry_session=session,
                oscillator_spec=dict(period=7, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        daily_loss_limit=0.2,
                        target_rr=reward,
                        protect_mode="off",
                        protect_after_r=1.0,
                        entry_guard=guard,
                    )
                ),
            )
            for threshold, pause, reward, guard, session in product(
                (25, 30, 35),
                (0.025, 0.05, 0.10),
                (1.35, 1.5),
                ("body_dominant", "close_extreme", "prior_day"),
                ("all", "avoid_rollover"),
            )
        ]
    if catalog == "hybrid_reward_admission":
        return [
            dict(
                hypothesis="rounded_reward_loss_cluster_admission",
                buy_filter="off",
                depth=0.0,
                entry_session=session,
                oscillator_spec=dict(period=7, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=0.05,
                        risk_cap=cap,
                        risk_mode=mode,
                        daily_loss_limit=daily,
                        target_rr=1.35,
                        protect_mode="off",
                        cooldown_bars=cooldown,
                        max_daily_losses=losses,
                    )
                ),
            )
            for threshold, (cap, mode), daily, cooldown, losses, session in product(
                (25, 30, 35),
                ((0.10, "static"), (0.05, "static"), (0.10, "drawdown_steps")),
                (0.10, 0.20),
                (0, 1, 4),
                (0, 1, 2),
                ("all", "avoid_rollover"),
            )
        ]
    if catalog == "hybrid_reward_session":
        return [
            dict(
                hypothesis="rounded_reward_avoid_utc_rollover",
                buy_filter="off",
                depth=0.0,
                entry_session="avoid_rollover",
                oscillator_spec=dict(period=period, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        daily_loss_limit=0.2,
                        target_rr=reward,
                        protect_mode=protection,
                        protect_after_r=1.0,
                    )
                ),
            )
            for period, threshold, pause, reward, protection in product(
                (7, 14, 21),
                (25, 30, 35),
                (0.05, 0.10),
                (1.35, 1.5),
                ("off", "break_even", "candle_trail"),
            )
        ]
    if catalog == "hybrid_reward":
        protection_states = [(reward, "off", 1.0) for reward in (1.25, 1.35, 1.5, 2.0)]
        protection_states += [
            (reward, protection, activation)
            for reward, protection, activation in product(
                (1.25, 1.35, 1.5, 2.0), ("break_even", "candle_trail"), (0.5, 1.0, 1.5)
            )
            if activation < reward
        ]
        return [
            dict(
                hypothesis="rsi_buy_rounded_stop_reward",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(period=period, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        daily_loss_limit=0.2,
                        target_rr=reward,
                        protect_mode=protection,
                        protect_after_r=activation,
                    )
                ),
            )
            for period, threshold, pause, (reward, protection, activation) in product(
                (7, 14, 21),
                (25, 30, 35),
                (0.025, 0.05, 0.10),
                protection_states,
            )
        ]
    if catalog == "hybrid_invalidation":
        return [
            dict(
                hypothesis="rsi_buy_setup_invalidation",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(period=period, threshold=threshold, trend_span=50, side="buy"),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        daily_loss_limit=0.2,
                        target_atr=3.0,
                        protect_mode=protection,
                        protect_after_r=1.0,
                        failed_closes=failed,
                        stagnant_bars=stagnant,
                    )
                ),
            )
            for period, threshold, pause, protection, (failed, stagnant) in product(
                (7, 14, 21),
                (25, 30, 35),
                (0.05, 0.10),
                ("break_even", "candle_trail"),
                ((1, 0), (0, 4), (1, 4)),
            )
        ]
    if catalog == "hybrid_admission":
        return [
            dict(
                hypothesis="rsi_buy_drawdown_admission",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=period, threshold=threshold, trend_span=trend, side="buy"
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        daily_loss_limit=0.2,
                        target_atr=3.0,
                        protect_mode=protection,
                        protect_after_r=1.0,
                    )
                ),
            )
            for period, threshold, trend, pause, protection in product(
                (7, 14, 21),
                (25, 30, 35),
                (0, 50),
                (0.025, 0.05, 0.10),
                ("break_even", "candle_trail"),
            )
        ]
    if catalog == "hybrid_oscillator":
        return [
            dict(
                hypothesis="direction_specific_rsi_and_d48",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=period, threshold=threshold, trend_span=trend, side=side
                ),
                rules=rules("off", 3.0, protection, activation),
            )
            for period, threshold, trend, side, protection, activation in product(
                (7, 14, 21),
                (25, 30, 35),
                (0, 50),
                ("buy", "sell"),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
