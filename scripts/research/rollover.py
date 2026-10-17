"""Current-spec swap sensitivity; explicit UTC-midnight research calendar."""

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SwapPolicy:
    """Debit at UTC midnight labelled by preceding business day.

    Wednesday business-day rollover posts Thursday 00:00 UTC. Saturday
    00:00 posts Friday's single debit; Sunday/Monday 00:00 post nothing.
    Not evidence of historical broker rollover time/rates or swap entitlement.
    """

    long_points: float
    short_points: float
    point: float
    triple_weekday: int = 2  # Monday=0

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.long_points, self.short_points, self.point)):
            raise ValueError("nonfinite swap policy")
        if self.point <= 0 or self.triple_weekday not in range(5):
            raise ValueError("invalid swap policy")

    @classmethod
    def from_broker(cls, broker):
        if broker["swap_mode"] != 1:
            raise ValueError("swap sensitivity requires points mode")
        # MT5 enum: Sunday=0, Wednesday=3.
        return cls(
            broker["swap_long"],
            broker["swap_short"],
            broker["point"],
            (int(broker["swap_rollover3days"]) - 1) % 7,
        )

    def schedule(self, start, end):
        days = pd.date_range(start.normalize(), end.normalize(), freq="D")
        weekdays = (days.dayofweek.to_numpy() - 1) % 7
        weights = np.where(weekdays >= 5, 0, np.where(weekdays == self.triple_weekday, 3, 1))
        return SwapSchedule(days.as_unit("ms").asi8, np.r_[0.0, np.cumsum(weights)], self)


@dataclass(frozen=True)
class SwapSchedule:
    times: np.ndarray
    accrued: np.ndarray
    policy: SwapPolicy

    def amount(self, entry_ms, stamps, direction, factor):
        # Entry exactly at rollover owes nothing for previous business day.
        counts = self.accrued[np.searchsorted(self.times, stamps, side="right")]
        born = self.accrued[np.searchsorted(self.times, entry_ms, side="right")]
        points = self.policy.long_points if direction == 1 else self.policy.short_points
        return (counts - born) * points * self.policy.point * factor
