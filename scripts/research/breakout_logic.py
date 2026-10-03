"""Compatible public API for offline single-position breakout research."""

from .breakout_models import (
    Rules as Rules,
    Costs as Costs,
    RESEARCH_RISK_CAPS as RESEARCH_RISK_CAPS,
)
from .breakout_signals import features as features, _entry_signals as _entry_signals
from .breakout_entry import _level as _level
from .breakout_replay import replay as replay


def dominates(candidate, baseline, stressed, stressed_baseline, *, min_trades):
    """Fail closed; no weighted score can hide deterioration in a required metric."""
    return bool(
        candidate["trades"] >= min_trades
        and stressed["trades"] >= min_trades
        and candidate["realized_rr"] is not None
        and baseline["realized_rr"] is not None
        and candidate["net_usd"] > max(0, baseline["net_usd"])
        and candidate["max_dd_pct"] < baseline["max_dd_pct"]
        and candidate["realized_rr"] > baseline["realized_rr"]
        and stressed["net_usd"] > max(0, stressed_baseline["net_usd"])
        and stressed["max_dd_pct"] <= stressed_baseline["max_dd_pct"]
        and candidate["max_admitted_risk_pct"] <= 10
        and stressed["max_admitted_risk_pct"] <= 10
    )
