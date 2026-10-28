"""Explicit, research-only C22 risk overlays; no broker or execution interface."""

from dataclasses import asdict, dataclass
from decimal import Decimal
import math

from .breakout_entry import _level


@dataclass(frozen=True)
class RiskOverlay:
    daily_budget: bool = False
    drawdown_budget: bool = False
    net_be_first: bool = False
    dd_pause_hours: int = 0

    def __post_init__(self):
        if any(type(value) is not bool for value in
               (self.daily_budget, self.drawdown_budget, self.net_be_first)):
            raise ValueError("risk overlay flags must be bool")
        if type(self.dd_pause_hours) is not int or self.dd_pause_hours not in (0, 24):
            raise ValueError("DD pause must be zero or24 hours")
        if self.dd_pause_hours and not self.drawdown_budget:
            raise ValueError("DD pause requires drawdown budget")

    @property
    def enabled(self):
        return self.daily_budget or self.drawdown_budget or self.net_be_first


@dataclass
class BudgetPauseState:
    pause_started_ms: int | None = None
    resume_not_before_ms: int | None = None
    last_signal_ms: int | None = None
    last_stamp_ms: int | None = None
    episodes: int = 0
    resumes: int = 0

    def snapshot(self):
        return asdict(self)

    @classmethod
    def restore(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("incomplete risk pause state")
        result = cls(**value)
        for name in ("pause_started_ms", "resume_not_before_ms", "last_signal_ms", "last_stamp_ms"):
            stamp = getattr(result, name)
            if stamp is not None and (type(stamp) is not int or stamp < 0):
                raise ValueError("invalid risk pause timestamp")
        for name in ("episodes", "resumes"):
            if type(getattr(result, name)) is not int or getattr(result, name) < 0:
                raise ValueError("invalid risk pause counter")
        if result.resumes > result.episodes:
            raise ValueError("invalid risk resume count")
        if (result.last_signal_ms is None) != (result.last_stamp_ms is None):
            raise ValueError("incomplete risk signal clock")
        if result.last_signal_ms is not None and result.last_signal_ms > result.last_stamp_ms:
            raise ValueError("invalid risk signal clock")
        if (result.pause_started_ms is None) != (result.resume_not_before_ms is None):
            raise ValueError("incomplete risk pause interval")
        if result.pause_started_ms is not None and (
            result.resume_not_before_ms - result.pause_started_ms != 24 * 3600000
            or result.episodes != result.resumes + 1
            or result.last_stamp_ms is None or result.pause_started_ms > result.last_stamp_ms
        ):
            raise ValueError("invalid risk pause interval")
        if result.pause_started_ms is None and result.episodes != result.resumes:
            raise ValueError("missing active risk pause interval")
        return result


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reasons: tuple[str, ...]
    started_pause: bool = False
    resumed: bool = False


def _positive(value, name):
    if isinstance(value, bool):
        raise ValueError("invalid " + name)
    try:
        valid = math.isfinite(value) and value > 0
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError("invalid " + name)
    return Decimal(str(value))


def evaluate_budget(overlay, state, *, equity, day_start, peak, risk, stamp_ms, signal_ms=None):
    """Check both prospective floors, then the optional persistent pause.

    The caller supplies a fresh native signal after native geometry/admission.
    E is flat-account equity and R already includes the declared round-trip fee
    and slippage; do not subtract posted costs or floating loss a second time.
    High-water/day proof are supplied separately and are never reset here.
    """
    if not isinstance(overlay, RiskOverlay) or not isinstance(state, BudgetPauseState):
        raise ValueError("explicit risk overlay/state required")
    BudgetPauseState.restore(state.snapshot())
    if state.pause_started_ms is not None and not overlay.dd_pause_hours:
        raise ValueError("pause state does not match overlay")
    current = _positive(equity, "equity")
    liability = _positive(risk, "risk")
    day = _positive(day_start, "day baseline") if overlay.daily_budget else None
    high = _positive(peak, "equity peak") if overlay.drawdown_budget else None
    if high is not None and high < current:
        raise ValueError("equity peak below current equity")
    signal_ms = stamp_ms if signal_ms is None else signal_ms
    if any(type(value) is not int or value < 0 for value in (stamp_ms, signal_ms)):
        raise ValueError("risk timestamps must be integer UTC milliseconds")
    if signal_ms > stamp_ms:
        raise ValueError("risk signal is in the future")
    if state.last_stamp_ms is not None and stamp_ms < state.last_stamp_ms:
        raise ValueError("risk observation moved backwards")
    if state.last_signal_ms is not None and signal_ms <= state.last_signal_ms:
        return BudgetDecision(False, ("stale_signal",))

    state.last_signal_ms = signal_ms
    state.last_stamp_ms = stamp_ms
    projected = current - liability
    daily_failed = day is not None and projected <= Decimal("0.90") * day
    dd_failed = high is not None and projected <= Decimal("0.60") * high
    reasons = []
    if daily_failed:
        reasons.append("daily_budget")
    if dd_failed:
        reasons.append("drawdown_budget")
    started = False
    if dd_failed and overlay.dd_pause_hours and state.pause_started_ms is None:
        state.pause_started_ms = stamp_ms
        state.resume_not_before_ms = stamp_ms + overlay.dd_pause_hours * 3600000
        state.episodes += 1
        started = True
    if state.resume_not_before_ms is not None and stamp_ms < state.resume_not_before_ms:
        reasons.append("dd_pause")
    if (state.resume_not_before_ms is not None and stamp_ms >= state.resume_not_before_ms
            and signal_ms < state.resume_not_before_ms):
        reasons.append("stale_signal")
    resumed = not reasons and state.pause_started_ms is not None
    if resumed:
        state.pause_started_ms = None
        state.resume_not_before_ms = None
        state.resumes += 1
    return BudgetDecision(not reasons, tuple(reasons), started, resumed)


def net_break_even(*, entry, direction, fee, factor, slippage, accrued_swap, grid):
    """Price net of costs accrued now, not a guarantee against future swap/gaps."""
    _positive(entry, "entry")
    _positive(factor, "contract factor")
    _positive(grid, "tick grid")
    if type(direction) is not int or direction not in (-1, 1):
        raise ValueError("direction must be BUY1 or SELL-1")
    try:
        valid_costs = all(not isinstance(value, bool) and math.isfinite(value)
                          for value in (fee, slippage, accrued_swap))
    except (TypeError, ValueError, OverflowError):
        valid_costs = False
    if not valid_costs:
        raise ValueError("nonfinite net BE costs")
    if fee < 0 or slippage < 0:
        raise ValueError("negative declared fee or slippage")
    candidate = entry + direction * ((fee - accrued_swap) / factor + slippage)
    _positive(candidate, "net BE price")
    return _level(candidate, grid, -direction)
