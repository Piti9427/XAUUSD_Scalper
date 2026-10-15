"""Frozen m5 challenger catalogs; preserve enumeration order."""

from dataclasses import asdict
from itertools import product
from typing import Any

from .breakout_models import Rules


def build(catalog, contracts):
    if catalog == "annual_m5_atr_reward":
        reward_profiles: list[dict[str, Any]] = [
            dict(signal_spec=dict(buy_lookback=h, sell_lookback=h, trend_span=t))
            for h, t in product((24, 48, 96), (50, 200))
        ]
        reward_profiles += [
            dict(
                oscillator_spec=dict(
                    period=14,
                    threshold=25,
                    trend_span=50,
                    side="buy",
                    parent_lookback=96,
                    parent_trend_span=t,
                )
            )
            for t in (50, 200)
        ]
        return [
            dict(
                profile,
                hypothesis="M5_trigger_risk_with_parent_SELL_ATR_reward",
                buy_filter="off",
                depth=0.0,
                m5_ttl=ttl,
                rules=asdict(
                    Rules(
                        buy_stop_mode="trigger",
                        sell_stop_mode="trigger",
                        buy_target_rr=reward,
                        protect_mode="break_even",
                        protect_after_r=1,
                        buy_protect_mode=protect,
                        daily_loss_limit=0.1,
                        max_daily_losses=1,
                        holding_mode="bounded24",
                    )
                ),
            )
            for profile, ttl, reward, protect in product(
                reward_profiles, (2, 4), (1.5, 2.0), ("off", "break_even")
            )
        ]
    if catalog == "annual_m5_directional_sizing":
        seeds = contracts("annual_m5_hybrid")
        return [
            dict(
                seeds[n - 1],
                hypothesis="lower_BUY_equity_risk_keeps_SELL_fixed_admission",
                seed=f"annual_m5_hybrid:{n}",
                rules=dict(
                    seeds[n - 1]["rules"],
                    buy_risk_cap=cap,
                    buy_sizing_mode=sizing,
                    buy_target_rr=reward,
                    stop_atr=stop,
                ),
            )
            for n, cap, sizing, reward, stop in product(
                (14, 15), (0.02, 0.025, 0.05), ("fixed", "risk"), (2.0, 3.0), (2.0, 2.5)
            )
        ]
    if catalog == "annual_m5_hybrid_quality":
        seeds = contracts("annual_m5_hybrid")
        return [
            dict(
                seeds[n - 1],
                hypothesis="hybrid_sell_quality_stop_and_admission_profit_dd_v2",
                seed=f"annual_m5_hybrid:{n}",
                sell_filter=guard,
                rules=dict(
                    seeds[n - 1]["rules"], risk_cap=cap, stop_atr=stop, buy_target_rr=reward
                ),
            )
            for n, cap, stop, guard, reward in product(
                (14, 15), (0.05, 0.075, 0.10), (2.0, 2.5), ("off", "body_dominant"), (2.0, 3.0)
            )
        ]
    if catalog == "annual_m5_hybrid":
        return [
            dict(
                hypothesis="M5_buy_participation_preserves_M15_sell_ATR_edge",
                buy_filter="off",
                depth=0.0,
                hybrid_buy_horizon=buy,
                hybrid_sell_horizon=sell,
                m5_ttl=ttl,
                m5_buy_only=True,
                rules=asdict(
                    Rules(
                        buy_stop_mode="trigger",
                        buy_target_rr=reward,
                        buy_protect_mode=protect,
                        protect_mode="break_even",
                        protect_after_r=1,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                        holding_mode=holding,
                    )
                ),
            )
            for buy, sell, ttl, reward, protect, holding in product(
                (24, 48),
                (48, 96),
                (2, 4),
                (1.5, 2.0),
                ("off", "break_even"),
                ("intraday", "bounded24"),
            )
        ]
    if catalog in ("annual_m5_intraday", "annual_m5_bounded24"):
        profiles: list[dict[str, Any]] = [
            dict(signal_spec=dict(buy_lookback=h, sell_lookback=h, trend_span=t))
            for h, t in product((24, 48, 96), (50, 200))
        ]
        profiles += [
            dict(
                oscillator_spec=dict(
                    period=14,
                    threshold=25,
                    trend_span=50,
                    side="buy",
                    parent_lookback=96,
                    parent_trend_span=t,
                )
            )
            for t in (50, 200)
        ]
        return [
            dict(
                profile,
                hypothesis="M15_setup_M5_retest_trigger_stop_cost_admission",
                buy_filter="off",
                depth=0.0,
                m5_ttl=ttl,
                rules=asdict(
                    Rules(
                        stop_mode="trigger",
                        target_rr=reward,
                        protect_mode=protect,
                        protect_after_r=1.0,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                        holding_mode=catalog.removeprefix("annual_m5_"),
                    )
                ),
            )
            for profile, ttl, reward, protect in product(
                profiles, (2, 4), (1.5, 2.0), ("off", "break_even")
            )
        ]
