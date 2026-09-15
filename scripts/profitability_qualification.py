"""Deterministic, normalized-R profitability and capital qualification gates."""

from dataclasses import dataclass
from datetime import datetime
import math
import random
from typing import Iterable, Mapping


@dataclass(frozen=True)
class QualificationPolicy:
    min_trades: int = 100
    min_profit_factor: float = 1.5
    max_drawdown_pct: float = 5.0
    risk_pct: float = 0.005
    bootstrap_samples: int = 10_000
    seed: int = 20260915


@dataclass(frozen=True)
class Metrics:
    trade_count: int
    expectancy_r: float
    profit_factor: float
    max_drawdown_pct: float


@dataclass(frozen=True)
class QualificationResult:
    status: str
    base: Metrics
    stress: Metrics
    bootstrap_lower_95_expectancy_r: float
    failures: tuple[str, ...]


@dataclass(frozen=True)
class CapitalViability:
    viable: bool
    allowed_lot: float
    required_split_lot: float
    risk_budget: float
    minimum_capital: float


def _metrics(rows: list[Mapping], risk_pct: float) -> Metrics:
    pnl = [float(row["pnl_r"]) for row in rows]
    gross_win = sum(value for value in pnl if value > 0)
    gross_loss = -sum(value for value in pnl if value < 0)
    pf = gross_win / gross_loss if gross_loss else (math.inf if gross_win else 0.0)
    equity = peak = 1.0
    max_dd = 0.0
    for value in pnl:
        equity *= max(0.0, 1.0 + value * risk_pct)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100)
    return Metrics(len(pnl), sum(pnl) / len(pnl) if pnl else 0.0, pf, max_dd)


def _bootstrap_lower(rows: list[Mapping], samples: int, seed: int) -> float:
    if not rows:
        return 0.0
    weeks: dict[tuple[int, int], list[float]] = {}
    for row in rows:
        closed = row["closed_at"]
        if not isinstance(closed, datetime) or closed.tzinfo is None:
            raise ValueError("closed_at must be timezone-aware")
        iso = closed.isocalendar()
        weeks.setdefault((iso.year, iso.week), []).append(float(row["pnl_r"]))
    blocks = list(weeks.values())
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        sample = [value for _ in blocks for value in rng.choice(blocks)]
        estimates.append(sum(sample) / len(sample))
    estimates.sort()
    return estimates[max(0, int(samples * 0.025) - 1)]


def qualify_candidate(
    trades: Iterable[Mapping], stress_trades: Iterable[Mapping], policy: QualificationPolicy = QualificationPolicy()
) -> QualificationResult:
    if policy.bootstrap_samples <= 0 or not 0 < policy.risk_pct <= 1 or policy.min_trades <= 0:
        raise ValueError("qualification policy values must be positive")
    base_rows, stress_rows = list(trades), list(stress_trades)
    base, stress = _metrics(base_rows, policy.risk_pct), _metrics(stress_rows, policy.risk_pct)
    lower = _bootstrap_lower(base_rows, policy.bootstrap_samples, policy.seed)
    failures: list[str] = []
    if base.trade_count < policy.min_trades:
        failures.append(f"trade_count<{policy.min_trades}")
    for dimension, values in (("direction", ("long", "short")), ("session", ("london", "new_york"))):
        for value in values:
            subset = [row for row in base_rows if row.get(dimension) == value]
            if not subset:
                failures.append(f"missing_{dimension}:{value}")
            elif _metrics(subset, policy.risk_pct).expectancy_r < 0:
                failures.append(f"negative_{dimension}:{value}")
    if base.profit_factor < policy.min_profit_factor:
        failures.append("base_profit_factor")
    if base.expectancy_r <= 0:
        failures.append("base_expectancy")
    if base.max_drawdown_pct > policy.max_drawdown_pct:
        failures.append("max_drawdown")
    if stress.profit_factor <= 1.0 or stress.expectancy_r <= 0:
        failures.append("cost_stress")
    if lower <= 0:
        failures.append("bootstrap_lower_95")
    incomplete = base.trade_count < policy.min_trades or any(item.startswith("missing_") for item in failures)
    status = "INCONCLUSIVE" if incomplete else ("REWORK" if failures else "HISTORICAL_QUALIFIED")
    return QualificationResult(status, base, stress, lower, tuple(failures))


def assess_capital_viability(*, balance: float, equity: float, risk_pct: float, entry: float, stop: float,
                             contract_size: float, min_lot: float, lot_step: float) -> CapitalViability:
    risk_budget = min(balance, equity) * risk_pct
    risk_per_lot = abs(entry - stop) * contract_size
    if risk_per_lot <= 0 or risk_pct <= 0:
        raise ValueError("risk inputs must be positive")
    required = max(2 * min_lot, 2 * lot_step)
    raw = risk_budget / risk_per_lot
    split_units = math.floor((raw + 1e-12) / required)
    allowed = round(split_units * required, 8)
    minimum_capital = required * risk_per_lot / risk_pct
    return CapitalViability(allowed >= required, allowed, required, risk_budget, minimum_capital)
