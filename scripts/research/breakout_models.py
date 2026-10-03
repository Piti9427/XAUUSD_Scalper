"""Frozen offline replay rules and cost contracts."""

from dataclasses import dataclass, asdict
import math


RESEARCH_RISK_CAPS = (0.005, 0.01, 0.02, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20)


@dataclass(frozen=True)
class Rules:
    failed_closes: int = 0
    reset_after_exit: bool = False
    stagnant_bars: int = 0
    entry_mode: str = "immediate"
    stop_mode: str = "atr"
    protect_mode: str = "off"
    entry_guard: str = "off"
    buy_pause_drawdown: float = 0.0

    risk_mode: str = "static"
    risk_cap: float = 0.10
    daily_loss_limit: float = 0.40
    target_atr: float = 3.0
    min_depth_atr: float = 0.0
    target_rr: float = 0.0
    cooldown_bars: int = 0
    session_mode: str = "all"
    max_daily_losses: int = 0
    protect_after_r: float = 0.5
    stop_atr: float = 2.5
    buy_stop_atr: float | None = None
    buy_target_rr: float | None = None
    buy_protect_mode: str | None = None
    sizing_mode: str = "fixed"
    holding_mode: str = "legacy"
    buy_stop_mode: str | None = None
    buy_risk_cap: float | None = None
    buy_sizing_mode: str | None = None
    sell_stop_mode: str | None = None

    def __post_init__(self):
        if self.sell_stop_mode not in (None, "atr", "trigger"):
            raise ValueError("unsupported SELL stop mode")
        if self.buy_sizing_mode not in (None, "fixed", "risk"):
            raise ValueError("unsupported BUY sizing mode")
        if self.buy_risk_cap is not None and self.buy_risk_cap not in RESEARCH_RISK_CAPS:
            raise ValueError("unsupported BUY risk cap")
        if self.buy_stop_mode not in (None, "atr", "trigger"):
            raise ValueError("unsupported BUY stop mode")
        if self.holding_mode not in ("legacy", "intraday", "bounded24"):
            raise ValueError("unsupported holding mode")
        if self.buy_protect_mode not in (None, "off", "break_even"):
            raise ValueError("unsupported BUY protection")
        if self.buy_stop_atr is not None and self.buy_stop_atr not in (
            0.5,
            0.75,
            1.0,
            1.5,
            2.0,
            2.5,
        ):
            raise ValueError("unsupported BUY ATR stop multiplier")
        if self.buy_target_rr is not None and self.buy_target_rr not in (1.25, 1.35, 1.5, 2.0, 3.0):
            raise ValueError("unsupported BUY risk distance target")
        if (
            self.buy_stop_atr is not None or self.buy_target_rr is not None
        ) and self.stop_mode != "atr":
            raise ValueError("BUY exit profile requires ATR stop mode")
        if self.stop_atr not in (1.5, 2.0, 2.5):
            raise ValueError("unsupported ATR stop multiplier")
        if self.protect_after_r not in (0.5, 1.0, 1.5, 2.0):
            raise ValueError("unsupported protection activation")
        if self.cooldown_bars not in (0, 1, 4) or self.max_daily_losses not in (0, 1, 2):
            raise ValueError("unsupported loss circuit")
        if self.session_mode not in ("all", "london_ny"):
            raise ValueError("unsupported UTC session")
        if self.risk_mode not in ("static", "drawdown_steps"):
            raise ValueError("unsupported risk mode")
        if self.sizing_mode not in ("fixed", "risk"):
            raise ValueError("unsupported sizing mode")
        if self.risk_cap not in RESEARCH_RISK_CAPS:
            raise ValueError("unsupported risk cap")
        if self.daily_loss_limit not in (0.05, 0.10, 0.20, 0.40):
            raise ValueError("unsupported daily limit")
        if self.target_rr not in (0.0, 1.25, 1.35, 1.4, 1.45, 1.5, 2.0, 3.0):
            raise ValueError("unsupported risk distance target")
        if self.target_atr not in (3.0, 6.25):
            raise ValueError("unsupported parent target")
        if self.min_depth_atr not in (0.0, 0.15, 0.20, 0.25):
            raise ValueError("unsupported breakout depth")
        if self.failed_closes not in (0, 1, 2) or self.stagnant_bars not in (0, 4, 8, 16):
            raise ValueError("unsupported research rule")
        if self.entry_mode not in ("immediate", "confirm", "retest", "failed_reverse"):
            raise ValueError("unsupported entry mode")
        if self.stop_mode not in ("atr", "structure", "trigger", "boundary"):
            raise ValueError("unsupported stop mode")
        if self.protect_mode not in ("off", "break_even", "candle_trail", "runner"):
            raise ValueError("unsupported profit protection")
        if self.entry_guard not in (
            "off",
            "buy_only",
            "sell_only",
            "body_dominant",
            "close_extreme",
            "prior_day",
        ):
            raise ValueError("unsupported entry guard")
        if (
            not math.isfinite(self.buy_pause_drawdown)
            or self.buy_pause_drawdown < 0
            or self.buy_pause_drawdown >= 1
        ):
            raise ValueError("unsupported buy pause")


@dataclass(frozen=True)
class Costs:
    extra_spread: float = 0.0  # USD per ounce, divided across both sides
    slippage: float = 0.0  # USD per ounce, each adverse market fill
    commission_per_lot: float = 0.0  # USD round trip, reserved/charged on entry

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in asdict(self).values()):
            raise ValueError("costs must be finite and nonnegative")
