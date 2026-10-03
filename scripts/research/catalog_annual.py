"""Frozen annual challenger catalogs; preserve enumeration order."""

from dataclasses import asdict
from itertools import product
from typing import Any

from .breakout_models import Rules


def build(catalog, contracts):
    if catalog == "annual_short_buy":
        seed = contracts("annual_directional_fine")[6]
        return [
            dict(
                seed,
                hypothesis="more_causal_buy_setups_with_shorter_cost_admissible_stops",
                oscillator_spec=dict(seed["oscillator_spec"], period=period, threshold=threshold),
                rules=dict(
                    seed["rules"], buy_stop_atr=stop, buy_target_rr=reward, buy_protect_mode=protect
                ),
            )
            for period, threshold, stop, reward, protect in product(
                (7, 14), (25, 35), (0.5, 0.75), (2.0, 3.0), ("off", "break_even")
            )
        ]
    if catalog == "annual_sizing":
        seeds = (
            ("annual_directional_fine", 7),
            ("annual_directional_circuit", 22),
            ("annual_hybrid_unpaused", 28),
        )
        candidates = []
        for family, trial in seeds:
            seed = contracts(family)[trial - 1]
            for cap, sizing in product(
                (0.005, 0.01, 0.02, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20), ("fixed", "risk")
            ):
                candidates.append(
                    dict(
                        seed,
                        hypothesis="current_equity_sizing_admission_under_profit_dd_v2",
                        seed=f"{family}:{trial}",
                        rules=dict(
                            seed["rules"], risk_mode="static", risk_cap=cap, sizing_mode=sizing
                        ),
                    )
                )
        return candidates
    if catalog == "annual_fast_quality":
        return [
            dict(
                hypothesis="shorter_trend_breakout_with_causal_candle_quality",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=lookback, sell_lookback=lookback, trend_span=trend),
                rules=asdict(
                    Rules(
                        stop_atr=1.5,
                        target_rr=reward,
                        entry_mode=entry,
                        entry_guard=guard,
                        protect_mode="off",
                        protect_after_r=1.0,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                    )
                ),
            )
            for lookback, trend, guard, reward, entry in product(
                (12, 24, 48),
                (50, 200),
                ("off", "body_dominant", "close_extreme"),
                (1.35, 1.5),
                ("immediate", "confirm"),
            )
        ]
    if catalog == "annual_short_sell":
        return [
            dict(
                hypothesis="short_sell_stop_retains_three_atr_reward_with_directional_buy_exits",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=period,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=lookback,
                    parent_trend_span=200,
                ),
                rules=asdict(
                    Rules(
                        stop_atr=1.5,
                        target_atr=3.0,
                        protect_mode=protection,
                        protect_after_r=activation,
                        buy_stop_atr=1.5,
                        buy_target_rr=reward,
                        buy_protect_mode="off",
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                    )
                ),
            )
            for (period, threshold), lookback, reward, (protection, activation) in product(
                ((7, 35), (14, 25)),
                (48, 96),
                (1.35, 2.0),
                (("off", 1.0), ("break_even", 0.5), ("break_even", 1.0)),
            )
        ]
    if catalog in (
        "annual_directional",
        "annual_directional_trend",
        "annual_directional_circuit",
        "annual_directional_fine",
    ):
        if catalog == "annual_directional":
            choices: Any = product(
                (7, 14), (25, 35), (48,), (0,), (1.5, 2.0, 2.5), (1.25, 1.35, 1.5, 2.0), ("static",)
            )
        elif catalog == "annual_directional_trend":
            choices = product(
                (7,),
                (35,),
                (24, 48, 96),
                (50, 200),
                (1.5, 2.0),
                (1.25, 1.35),
                ("static", "drawdown_steps"),
            )
        elif catalog == "annual_directional_circuit":
            choices = (
                (period, threshold, lookback, trend, 1.5, reward, "static")
                for (period, threshold), lookback, trend, reward in product(
                    ((7, 35), (14, 25)), (24, 48, 96), (50, 200), (1.35, 2.0)
                )
            )
        else:
            choices = product(
                (14,), (25, 30, 35), (96,), (50, 200), (1.0, 1.5), (1.5, 2.0), ("static",)
            )
        circuit = catalog in ("annual_directional_circuit", "annual_directional_fine")
        hypotheses = {
            "annual_directional": "buy_specific_exits_preserve_trial30_sell_contract",
            "annual_directional_trend": "directional_exits_with_causal_sell_trend_and_admission",
            "annual_directional_circuit": "directional_profiles_with_daily_loss_circuit",
            "annual_directional_fine": "directional_full_pass_with_more_cost_admissible_buy_signals",
        }
        return [
            dict(
                hypothesis=hypotheses[catalog],
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=period,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=lookback,
                    parent_trend_span=trend,
                ),
                rules=asdict(
                    Rules(
                        stop_atr=2.5,
                        target_atr=3.0,
                        target_rr=0.0,
                        protect_mode="break_even",
                        protect_after_r=1.0,
                        daily_loss_limit=0.10 if circuit else 0.20,
                        max_daily_losses=1 if circuit else 0,
                        risk_cap=0.10,
                        risk_mode=risk,
                        buy_stop_atr=stop,
                        buy_target_rr=reward,
                        buy_protect_mode="off",
                    )
                ),
            )
            for period, threshold, lookback, trend, stop, reward, risk in choices
        ]
    if catalog == "annual_sessions":
        return [
            dict(
                hypothesis="annual_immediate_signals_by_fixed_utc_session",
                buy_filter="off",
                depth=0.0,
                entry_session=session,
                **(
                    dict(signal_spec=dict(buy_lookback=48, sell_lookback=48, trend_span=50))
                    if signal == "symmetric"
                    else dict(
                        oscillator_spec=dict(
                            period=7,
                            threshold=35,
                            trend_span=50,
                            side="buy",
                            parent_lookback=48,
                            parent_trend_span=50,
                        )
                    )
                ),
                rules=asdict(
                    Rules(
                        stop_atr=stop,
                        target_rr=reward,
                        protect_mode="off",
                        protect_after_r=1.0,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                        buy_pause_drawdown=0.0,
                    )
                ),
            )
            for signal, session, stop, reward in product(
                ("symmetric", "hybrid"),
                ("utc_00_07", "utc_07_13", "utc_13_20"),
                (1.5, 2.5),
                (1.25, 1.35, 2.0),
            )
        ]
    if catalog == "annual_hybrid_unpaused":
        return [
            dict(
                hypothesis="annual_shorter_stop_without_rsi_buy_drawdown_pause",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(
                    period=7,
                    threshold=threshold,
                    trend_span=50,
                    side="buy",
                    parent_lookback=lookback,
                    parent_trend_span=trend,
                ),
                rules=asdict(
                    Rules(
                        stop_atr=stop,
                        target_rr=reward,
                        risk_mode=risk,
                        buy_pause_drawdown=0.0,
                        protect_mode="off",
                        protect_after_r=1.0,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                    )
                ),
            )
            for lookback, trend, threshold, stop, reward, risk in product(
                (24, 48, 96),
                (50, 200),
                (25, 35),
                (1.5, 2.0),
                (1.25, 1.35),
                ("static", "drawdown_steps"),
            )
        ]
    if catalog in ("annual_risk", "annual_confirmation"):
        choices = (
            [
                (reward, 2.5, "immediate", risk, cap)
                for reward, (risk, cap) in product(
                    (1.35, 1.5, 2.0), (("static", 0.05), ("drawdown_steps", 0.10))
                )
            ]
            if catalog == "annual_risk"
            else [
                (reward, stop, entry, "static", 0.10)
                for reward, stop, entry in product((1.25, 1.35), (1.5, 2.5), ("confirm", "retest"))
            ]
        )
        return [
            dict(
                hypothesis=(
                    "annual_symmetric_tighter_risk"
                    if catalog == "annual_risk"
                    else "annual_symmetric_causal_confirmation_smaller_reward"
                ),
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=lookback, sell_lookback=lookback, trend_span=trend),
                rules=asdict(
                    Rules(
                        target_rr=reward,
                        stop_atr=stop,
                        entry_mode=entry,
                        risk_mode=risk,
                        risk_cap=cap,
                        protect_mode="off",
                        protect_after_r=1.0,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                    )
                ),
            )
            for lookback, trend, (reward, stop, entry, risk, cap) in product(
                (24, 48, 96), (50, 200), choices
            )
        ]
    if catalog == "annual_bidirectional":
        return [
            dict(
                hypothesis="symmetric_trend_breakout_without_buy_pause_on_annual_archive",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=lookback, sell_lookback=lookback, trend_span=trend),
                rules=asdict(
                    Rules(
                        target_rr=reward,
                        protect_mode=protection,
                        protect_after_r=1.0,
                        daily_loss_limit=0.10,
                        max_daily_losses=1,
                    )
                ),
            )
            for lookback, trend, reward, protection in product(
                (24, 48, 96), (50, 200), (1.35, 1.5, 2.0), ("off", "break_even")
            )
        ]
