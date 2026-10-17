"""Frozen parent challenger catalogs; preserve enumeration order."""

from dataclasses import asdict
from itertools import product

from .breakout_models import Rules


def build(catalog, contracts):
    if catalog == "hybrid_parent_invalidation":
        # Freeze the measured parent-trend178 contract as the control origin.
        base = next(
            candidate
            for candidate in contracts("hybrid_parent_trend")
            if candidate["oscillator_spec"]
            == dict(
                period=7,
                threshold=35,
                trend_span=50,
                side="buy",
                parent_lookback=48,
                parent_trend_span=50,
            )
            and all(
                candidate["rules"][key] == value
                for key, value in dict(
                    buy_pause_drawdown=0.05,
                    target_rr=1.35,
                    daily_loss_limit=0.10,
                    max_daily_losses=1,
                ).items()
            )
        )
        return [
            dict(
                base,
                hypothesis="bearish_d48_parent_reward_and_setup_invalidation",
                rules=asdict(
                    Rules(
                        **dict(
                            base["rules"],
                            target_rr=reward,
                            cooldown_bars=cooldown,
                            failed_closes=failed,
                            stagnant_bars=stagnant,
                        )
                    )
                ),
            )
            for reward, cooldown, failed, stagnant in product(
                (1.35, 1.4, 1.45), (0, 1, 4), (0, 1), (0, 4)
            )
        ]
    if catalog == "hybrid_parent_protection":
        return [
            dict(
                hypothesis="d24_parent_rounded_reward_with_earlier_protection",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=24,
                    parent_trend_span=parent_trend,
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        target_rr=reward,
                        daily_loss_limit=0.10,
                        max_daily_losses=losses,
                        protect_mode=protection,
                        protect_after_r=activation,
                    )
                ),
            )
            for threshold, pause, parent_trend, reward, (protection, activation), losses in product(
                (30, 35),
                (0.05, 0.10),
                (0, 50),
                (1.35, 1.4, 1.45),
                (("break_even", 0.5), ("candle_trail", 0.5), ("candle_trail", 1.0)),
                (0, 1),
            )
        ]
    if catalog == "hybrid_parent_atr":
        return [
            dict(
                hypothesis="bearish_d96_parent_with_intermediate_atr_stop",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=96,
                    parent_trend_span=200,
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        stop_atr=stop,
                        target_rr=reward,
                        daily_loss_limit=0.10,
                        max_daily_losses=losses,
                        protect_mode="off",
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, stop, reward, losses in product(
                (30, 35),
                (0.05, 0.10),
                (1.5, 2.0),
                (1.35, 1.45, 1.5),
                (0, 1, 2),
            )
        ]
    if catalog == "hybrid_parent_risk":
        return [
            dict(
                hypothesis="partially_passing_parent_with_stricter_risk_admission",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=35,
                    trend_span=50,
                    side="buy",
                    parent_lookback=lookback,
                    parent_trend_span=parent_trend,
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=0.05,
                        target_rr=reward,
                        risk_mode=risk_mode,
                        risk_cap=cap,
                        cooldown_bars=cooldown,
                        daily_loss_limit=0.10,
                        max_daily_losses=losses,
                        protect_mode="off",
                        protect_after_r=1.0,
                    )
                ),
            )
            for (lookback, parent_trend, reward), (risk_mode, cap), cooldown, losses in product(
                ((24, 0, 1.35), (96, 200, 1.45)),
                (("static", 0.05), ("drawdown_steps", 0.10)),
                (0, 1, 4),
                (0, 1, 2),
            )
        ]
    if catalog in ("hybrid_parent_reward_fine", "hybrid_parent_reward_pause"):
        pause_followup = catalog == "hybrid_parent_reward_pause"
        return [
            dict(
                hypothesis=(
                    "bearish_d96_parent_intermediate_reward_tighter_buy_pause"
                    if pause_followup
                    else "bearish_d96_parent_intermediate_rounded_reward"
                ),
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=96,
                    parent_trend_span=200,
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        target_rr=reward,
                        daily_loss_limit=daily,
                        max_daily_losses=losses,
                        protect_mode="off",
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, reward, daily, losses in product(
                (30, 35),
                (0.025,) if pause_followup else (0.05, 0.10),
                (1.4, 1.45),
                (0.10,) if pause_followup else (0.10, 0.20),
                (0, 1, 2),
            )
        ]
    if catalog == "hybrid_parent_quality":
        return [
            dict(
                hypothesis="bearish_d24_parent_with_symmetric_candle_guard",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=24,
                    parent_trend_span=50,
                ),
                rules=asdict(
                    Rules(
                        entry_guard=guard,
                        buy_pause_drawdown=pause,
                        target_rr=reward,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                        protect_mode="off",
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, reward, guard in product(
                (30, 35),
                (0.05, 0.10),
                (1.35, 1.5),
                ("body_dominant", "close_extreme", "prior_day"),
            )
        ]
    if catalog == "hybrid_parent_trend":
        return [
            dict(
                hypothesis="rsi_buy_with_bearish_sell_parent_filter",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=lookback,
                    parent_trend_span=parent_trend,
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        target_rr=reward,
                        daily_loss_limit=daily,
                        max_daily_losses=losses,
                        protect_mode="off",
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, lookback, parent_trend, reward, daily, losses in product(
                (30, 35),
                (0.05, 0.10),
                (24, 48, 96),
                (0, 50, 200),
                (1.35, 1.5),
                (0.10, 0.20),
                (0, 1),
            )
        ]
    if catalog == "hybrid_parent_horizon":
        return [
            dict(
                hypothesis="rsi_buy_with_directional_sell_horizon",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=lookback,
                ),
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        stop_atr=stop,
                        target_rr=reward,
                        daily_loss_limit=daily,
                        max_daily_losses=losses,
                        protect_mode="off",
                        protect_after_r=1.0,
                    )
                ),
            )
            for threshold, pause, lookback, stop, reward, daily, losses in product(
                (30, 35),
                (0.05, 0.10),
                (24, 48, 96),
                (2.0, 2.5),
                (1.35, 1.5),
                (0.10, 0.20),
                (0, 1),
            )
        ]
