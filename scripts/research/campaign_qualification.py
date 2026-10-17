"""Frozen scenario qualification and executed-ledger metrics."""

import math


def qualifies_trial30(pair, baseline, min_trades, *, policy="strict_v1"):
    """Require both executed sides, fixed-lot risk and improvement in each scenario."""
    if len(pair) != 2 or len(baseline) != 2:
        return False
    if policy not in ("strict_v1", "profit_dd_v2"):
        raise ValueError("unsupported qualification policy")
    if policy == "profit_dd_v2":
        for candidate, parent in zip(pair, baseline):
            required = (
                "net_usd",
                "max_dd_pct",
                "max_admitted_risk_pct",
                "trades",
                "buy_trades",
                "sell_trades",
            )
            if any(candidate.get(k) is None or not math.isfinite(candidate[k]) for k in required):
                return False
            if any(
                parent.get(k) is None or not math.isfinite(parent[k])
                for k in ("net_usd", "max_dd_pct")
            ):
                return False
            if (
                candidate["net_usd"] <= max(0, parent["net_usd"])
                or not 0 <= candidate["max_dd_pct"] <= min(30, parent["max_dd_pct"])
                or not 0 <= candidate["max_admitted_risk_pct"] <= 20 + 1e-9
                or candidate["trades"] < min_trades
                or candidate["buy_trades"] < 1
                or candidate["sell_trades"] < 1
            ):
                return False
        return True
    keys = (
        "net_usd",
        "win_rate",
        "realized_rr",
        "max_dd_pct",
        "max_admitted_risk_pct",
        "trades",
        "buy_trades",
        "sell_trades",
    )
    for candidate, parent in zip(pair, baseline):
        if any(candidate.get(k) is None or not math.isfinite(candidate[k]) for k in keys):
            return False
        if any(
            parent.get(k) is None or not math.isfinite(parent[k])
            for k in (keys[0], keys[1], keys[3])
        ):
            return False
        parent_rr = parent.get("realized_rr")
        if parent_rr is None:
            if not (
                type(parent.get("trades")) is int
                and parent["trades"] > 0
                and parent.get("loss_trades") == parent["trades"]
                and parent["win_rate"] == 0
                and parent["net_usd"] < 0
            ):
                return False
            # Owner-approved all-loss reference floor, not a measured ratio.
            parent_rr = 0.0
        if not math.isfinite(parent_rr):
            return False
        if (
            candidate["trades"] < min_trades
            or candidate["buy_trades"] < 1
            or candidate["sell_trades"] < 1
            or not 0 <= candidate["max_admitted_risk_pct"] <= 10
            or not 0 <= candidate["max_dd_pct"] <= min(30, parent["max_dd_pct"])
            or not 0 <= candidate["win_rate"] <= 1
            or candidate["net_usd"] <= max(0, parent["net_usd"])
            or candidate["win_rate"] <= parent["win_rate"]
            or candidate["realized_rr"] <= max(1, parent_rr)
        ):
            return False
    return True


def metrics(result):
    summary = {k: v for k, v in result.items() if k not in ("ledger", "equity", "rejection_events")}
    summary["buy_trades"] = sum(p["direction"] == 1 for p in result["ledger"])
    summary["sell_trades"] = sum(p["direction"] == -1 for p in result["ledger"])
    summary["loss_trades"] = sum(p["net"] < 0 for p in result["ledger"])
    if summary["buy_trades"] + summary["sell_trades"] != summary["trades"]:
        raise ValueError("ledger direction/count mismatch")
    return summary
