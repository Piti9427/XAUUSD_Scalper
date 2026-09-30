"""Owner-approved research gates. Selection consumes discovery metrics only."""

from __future__ import annotations

import math


def qualifies(base, stress, baselines, *, min_trades, require_rr_improvement=False):
    """Beat both parents under each cost scenario, with absolute safety floors."""
    for result, column in ((base, 0), (stress, 1)):
        required = (
            "net_usd",
            "max_dd_pct",
            "realized_rr",
            "win_rate",
            "max_admitted_risk_pct",
            "trades",
        )
        if any(result.get(k) is None or not math.isfinite(result[k]) for k in required):
            return False
        if (
            result["trades"] < min_trades
            or result["net_usd"] <= 0
            or not 0 <= result["max_dd_pct"] <= 20
            or result["realized_rr"] < 1
            or not 0 <= result["max_admitted_risk_pct"] <= 10
        ):
            return False
        for pair in baselines:
            parent = pair[column]
            parent_rr = parent.get("realized_rr")
            if require_rr_improvement and parent_rr is not None:
                if not math.isfinite(parent_rr) or result["realized_rr"] <= parent_rr:
                    return False
            if (
                parent["win_rate"] is None
                or not all(math.isfinite(parent[k]) for k in ("net_usd", "max_dd_pct", "win_rate"))
                or result["net_usd"] <= parent["net_usd"]
                or result["max_dd_pct"] >= parent["max_dd_pct"]
                or result["win_rate"] <= parent["win_rate"]
            ):
                return False
    return len(baselines) == 2


def validation_readiness(
    *,
    first_tick,
    last_tick,
    nonempty_months,
    unseen_start,
    unseen_end,
    discovery_end,
    unseen_trades,
):
    """Necessary date/trade screen only; not a broker/data provenance verdict.

    Caller must derive coverage from verified actual ticks, never manifest dates.
    Date sufficiency alone cannot authorize Demo or mark historical qualification.
    """
    import pandas as pd

    stamps = [
        pd.Timestamp(v) for v in (first_tick, last_tick, unseen_start, unseen_end, discovery_end)
    ]
    if any(t.tzinfo is None or t.utcoffset() != pd.Timedelta(0) for t in stamps):
        return False
    first, last, start, end, consumed = stamps
    return bool(
        last >= first + pd.DateOffset(months=12)
        and nonempty_months >= 12
        and start >= consumed
        and end >= start + pd.DateOffset(months=3)
        and first <= start < end <= last
        and unseen_trades >= 30
    )
