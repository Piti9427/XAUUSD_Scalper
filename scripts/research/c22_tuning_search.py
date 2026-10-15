"""Diversified research exploration; qualification and final winner rank stay frozen."""

from scripts.research.c22_frequency_policy import qualify, search_rank

LANES = ("frequency", "balanced", "quality")


def exploration_rank(identity, rows, controls, lane):
    verdict = qualify(rows, controls)
    gates = verdict["gates"]
    safe = all(g["survival"] and g["risk"] for g in gates.values())
    frequency = min(m["mean_entries"] for m in rows.values())
    dd = max(m["max_dd_pct"] for m in rows.values())
    net = min(m["net_usd"] for m in rows.values())
    if lane == "frequency":
        return (-int(safe), -frequency, dd, -net, identity)
    if lane == "balanced":
        # Continuous constraint distance prevents binary gate count from hiding
        # progress in frequency. This is exploration only, never qualification.
        gaps = []
        for view, metric in rows.items():
            floor = max(0.0, controls[view]["net_usd"])
            gaps.append(
                max(0.0, 15 - metric["mean_entries"]) / 15
                + max(0.0, metric["max_dd_pct"] - 40) / 40
                + max(0.0, floor - metric["net_usd"]) / max(1.0, abs(floor))
            )
        return (-int(safe), max(gaps), -frequency, dd, -net, identity)
    if lane == "quality":
        return (-int(safe), *search_rank(identity, rows, controls))
    raise ValueError("unknown exploration lane")


def select_parents(rows, expanded, controls):
    selected = []
    remaining = set(rows) - set(expanded)
    for lane in LANES:
        if not remaining:
            break
        identity = min(remaining, key=lambda i: exploration_rank(i, rows[i], controls, lane))
        selected.append(dict(id=identity, lane=lane))
        remaining.remove(identity)
    return selected
