"""Frozen basic challenger catalogs; preserve enumeration order."""

from dataclasses import asdict
from itertools import product

from .breakout_models import Rules
from .catalog_common import rules


def build(catalog, contracts):
    if catalog == "oscillator":
        return [
            dict(
                hypothesis="rolling_rsi_price_reversal",
                buy_filter="off",
                depth=0.0,
                oscillator_spec=dict(period=period, threshold=threshold, trend_span=trend),
                rules=rules(guard, 3.0, protection, 1.0),
            )
            for period, threshold, trend, guard, protection in product(
                (7, 14, 21),
                (25, 30, 35),
                (0, 50),
                ("off", "body_dominant"),
                ("break_even", "candle_trail"),
            )
        ]
    if catalog == "compression":
        return [
            dict(
                hypothesis="prior_range_compression",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(
                    buy_lookback=buy, sell_lookback=sell, trend_span=trend, max_range_atr=maximum
                ),
                rules=rules(guard, 3.0, protection, 1.0),
            )
            for buy, sell, maximum, trend, guard, protection in product(
                (24, 48, 96),
                (24, 48, 96),
                (6.0, 9.0, 12.0),
                (0, 50),
                ("off", "body_dominant"),
                ("break_even", "candle_trail"),
            )
        ]
    if catalog == "horizon_quality":
        return [
            dict(
                hypothesis="horizon_candle_quality",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=buy, sell_lookback=sell, trend_span=0),
                rules=rules(guard, 3.0, protection, activation),
            )
            for buy, sell, guard, protection, activation in product(
                (12, 24, 48, 96),
                (12, 24, 48, 96),
                ("body_dominant", "close_extreme"),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
    if catalog == "horizons":
        return [
            dict(
                hypothesis="direction_horizons_and_trend",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=buy, sell_lookback=sell, trend_span=trend),
                rules=rules("off", target, protection, activation),
            )
            for buy, sell, trend, target, protection, activation in product(
                (12, 24, 48, 96),
                (12, 24, 48, 96),
                (0, 50, 200),
                (3.0, 6.25),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
    if catalog == "admission":
        return [
            dict(
                hypothesis="selective_buy_admission",
                buy_signal="breakout",
                buy_filter=buy_filter,
                depth=0.0,
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        risk_mode=risk_mode,
                        entry_guard=guard,
                        protect_mode=protection,
                        protect_after_r=1.0,
                        target_atr=target,
                        daily_loss_limit=0.2,
                    )
                ),
            )
            for pause, risk_mode, guard, protection, target, buy_filter in product(
                (0.025, 0.05, 0.10),
                ("static", "drawdown_steps"),
                ("off", "body_dominant"),
                ("break_even", "candle_trail"),
                (3.0, 6.25),
                ("off", "prior_day"),
            )
        ]
    if catalog == "tuning":
        result = []
        for signal, guard, stop, rr, protection, activation in product(
            ("breakout", "lower_wick"),
            ("off", "body_dominant"),
            ("atr", "trigger", "boundary"),
            (1.5, 2.0),
            ("break_even", "candle_trail"),
            (0.5, 1.0),
        ):
            result.append(
                dict(
                    hypothesis="stop_geometry",
                    buy_signal=signal,
                    buy_filter="prior_day",
                    depth=0.0,
                    rules=asdict(
                        Rules(
                            entry_guard=guard,
                            stop_mode=stop,
                            target_rr=rr,
                            daily_loss_limit=0.2,
                            protect_mode=protection,
                            protect_after_r=activation,
                        )
                    ),
                )
            )
        for entry, stop, guard, rr, protection, buy_filter in product(
            ("confirm", "retest"),
            ("atr", "trigger", "boundary"),
            ("off", "body_dominant"),
            (1.5, 2.0),
            ("break_even", "candle_trail"),
            ("off", "prior_day"),
        ):
            result.append(
                dict(
                    hypothesis="entry_timing",
                    buy_signal="breakout",
                    buy_filter=buy_filter,
                    depth=0.0,
                    rules=asdict(
                        Rules(
                            entry_mode=entry,
                            entry_guard=guard,
                            stop_mode=stop,
                            target_rr=rr,
                            daily_loss_limit=0.2,
                            protect_mode=protection,
                            protect_after_r=1.0,
                        )
                    ),
                )
            )
        for entry, failed, stagnant, target, protection, buy_filter in product(
            ("immediate", "confirm"),
            (0, 1, 2),
            (0, 4),
            (3.0, 6.25),
            ("break_even", "candle_trail"),
            ("off", "prior_day"),
        ):
            result.append(
                dict(
                    hypothesis="false_breakout_exit",
                    buy_signal="breakout",
                    buy_filter=buy_filter,
                    depth=0.0,
                    rules=asdict(
                        Rules(
                            entry_mode=entry,
                            failed_closes=failed,
                            stagnant_bars=stagnant,
                            target_atr=target,
                            daily_loss_limit=0.2,
                            protect_mode=protection,
                            protect_after_r=1.0,
                        )
                    ),
                )
            )
        return result
    if catalog == "symmetric":
        return [
            dict(
                buy_signal=signal,
                buy_filter=buy_filter,
                depth=0.0,
                rules=rules(guard, target, protection, activation),
            )
            for guard, signal, buy_filter, target, protection, activation in product(
                ("body_dominant", "close_extreme", "prior_day"),
                ("breakout", "lower_wick"),
                ("off", "prior_day"),
                (3.0, 6.25),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
    if catalog == "buy_setups":
        return [
            dict(
                buy_signal=signal,
                buy_filter=guard,
                depth=depth,
                rules=rules("off", target, protection, activation),
            )
            for signal, guard, depth, target, protection, activation in product(
                ("lower_wick", "trend_pullback"),
                ("off", "prior_day", "body"),
                (0.0, 0.15),
                (3.0, 6.25),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
    if catalog != "quality":
        raise ValueError("unknown catalog")
    return [
        dict(
            buy_filter=guard,
            depth=depth,
            rules=rules("off", target, protection, activation),
        )
        for guard, depth, target, protection, activation in product(
            ("off", "ema50", "prior_day", "body", "extreme", "ema_prior"),
            (0.0, 0.15),
            (3.0, 6.25),
            ("break_even", "candle_trail"),
            (1.0, 1.5),
        )
    ]
