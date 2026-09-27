"""Frozen 320-policy B1/D matrix with real-tick account sizing and chronology."""

from dataclasses import replace, asdict
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from .strategies import registry, features, signals
from .b1_d_ticks import replay

RISK = (0.005, 0.01, 0.015, 0.02)
SL = (1.0, 1.5, 2.0, 2.5, 3.0)
RR = (1.5, 2.0, 2.5, 3.0)
COST = (0.0, 0.1, 0.2)
START = pd.Timestamp("2026-05-14T00:00:00Z")
STAGES = {
    "development": (START, pd.Timestamp("2026-07-01T00:00:00Z")),
    "validation": (pd.Timestamp("2026-07-01T00:00:00Z"), pd.Timestamp("2026-09-01T00:00:00Z")),
    "confirmation": (pd.Timestamp("2026-09-01T00:00:00Z"), pd.Timestamp("2026-09-26T00:00:00Z")),
    "continuous": (START, pd.Timestamp("2026-09-26T00:00:00Z")),
}


def summarize(log, stats):
    if log.empty:
        return {
            **stats,
            "trades": 0,
            "net": 0.0,
            "pf": None,
            "expectancy_r": None,
            "win_rate": None,
            "max_loss_streak": 0,
            "long_net": 0.0,
            "short_net": 0.0,
        }
    loss = -log.loc[log.net < 0, "net"].sum()
    streak = longest = 0
    for value in log.net:
        streak = streak + 1 if value < 0 else 0
        longest = max(longest, streak)
    return {
        **stats,
        "trades": len(log),
        "net": float(log.net.sum()),
        "pf": float(log.loc[log.net > 0, "net"].sum() / loss) if loss else None,
        "expectancy_r": float(log.r.mean()),
        "win_rate": float((log.net > 0).mean()),
        "max_loss_streak": longest,
        "long_net": float(log.loc[log.direction == 1, "net"].sum()),
        "short_net": float(log.loc[log.direction == -1, "net"].sum()),
    }


def eligible(row):
    return (
        row["trades"] >= 30
        and row["net"] > 0
        and row["pf"] is not None
        and row["pf"] >= 1.1
        and row["max_tick_equity_dd_pct"] <= 5
    )


def rank_development(rows):
    """Only declared development rows participate. Missing costs never pass."""
    groups = {}
    for row in rows:
        if row["stage"] == "development":
            groups.setdefault(row["policy_id"], {})[row["cost_r"]] = row
    ranking = []
    for ident, costs in groups.items():
        if set(costs) != set(COST):
            continue
        stressed = costs[0.2]
        passed = all(eligible(costs[c]) for c in COST)
        score = stressed["net"] / max(stressed["max_tick_equity_dd_pct"], 0.1)
        ranking.append(
            {
                "policy_id": ident,
                "research_screen_pass": passed,
                "score": score,
                "stress_trades": stressed["trades"],
                "stress_net": stressed["net"],
                "stress_dd": stressed["max_tick_equity_dd_pct"],
                "risk_pct": stressed["risk_pct"],
            }
        )
    return sorted(
        ranking,
        key=lambda r: (r["research_screen_pass"], r["score"], r["stress_trades"], -r["risk_pct"]),
        reverse=True,
    )


def filtered_signal(frame, raw, start, end, session):
    signal = raw.copy()
    available = frame.index + pd.Timedelta(minutes=15)
    keep = (available >= start) & (available < end)
    if session == "london_ny":
        minute = available.hour * 60 + available.minute
        keep &= ((minute >= 420) & (minute < 630)) | ((minute >= 750) & (minute < 990))
    signal.loc[~keep, "direction"] = 0
    return signal


def load_capture(root, working):
    if not (root / "COMPLETE").exists():
        raise ValueError("capture incomplete")
    meta = json.loads((root / "manifest.json").read_text())
    if not meta["target_demo_verified"] or meta["symbol"] != "XAUUSDm":
        raise ValueError("Demo identity mismatch")
    total = sum(d["ticks"] for d in meta["days"])
    times = np.lib.format.open_memmap(
        working / "time.npy", mode="w+", dtype=np.int64, shape=(total,)
    )
    bid = np.lib.format.open_memmap(working / "bid.npy", mode="w+", dtype=float, shape=(total,))
    ask = np.lib.format.open_memmap(working / "ask.npy", mode="w+", dtype=float, shape=(total,))
    offset = 0
    minutes = []
    audit = []
    for day in meta["days"]:
        path = root / (day["day"] + ".npz")
        if hashlib.sha256(path.read_bytes()).hexdigest() != day["sha256"]:
            raise ValueError("capture hash mismatch")
        with np.load(path) as z:
            t, b, a = z["time_msc"], z["bid"], z["ask"]
        if (
            len(t) != day["ticks"]
            or (np.diff(t) < 0).any()
            or not np.isfinite(b).all()
            or not np.isfinite(a).all()
            or (b <= 0).any()
            or (a < b).any()
        ):
            raise ValueError("invalid daily ticks")
        lo = pd.Timestamp(day["day"], tz="UTC").value // 1_000_000
        if len(t) and (t[0] < lo or t[-1] >= lo + 86400000):
            raise ValueError("out-of-day tick")
        if len(t) and offset and t[0] < times[offset - 1]:
            raise ValueError("daily ordering")
        n = len(t)
        times[offset : offset + n] = t
        bid[offset : offset + n] = b
        ask[offset : offset + n] = a
        offset += n
        if n:
            minute = t // 60000
            starts = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
            ends = np.r_[starts[1:] - 1, n - 1]
            df = pd.DataFrame(
                {
                    "open": b[starts],
                    "high": np.maximum.reduceat(b, starts),
                    "low": np.minimum.reduceat(b, starts),
                    "close": b[ends],
                },
                index=pd.to_datetime(minute[starts] * 60000, unit="ms", utc=True),
            )
            minutes.append(df)
        audit.append(
            {"day": day["day"], "ticks": n, "missing_history_before_first_tick": offset == 0}
        )
    m1 = pd.concat(minutes)
    if m1.index.duplicated().any() or not m1.index.is_monotonic_increasing:
        raise ValueError("invalid M1 aggregation")
    f = features(m1.add_prefix("bid_").join(m1.add_prefix("ask_")), 15)
    times.flush()
    bid.flush()
    ask.flush()
    audit_meta = {
        "requested_start": meta["start"],
        "actual_first_tick": str(pd.Timestamp(int(times[0]), unit="ms", tz="UTC")),
        "actual_last_tick": str(pd.Timestamp(int(times[-1]), unit="ms", tz="UTC")),
        "ticks": total,
        "m1_minutes": len(m1),
        "m15_complete_bars": len(f),
        "days": audit,
    }
    (working / "coverage.json").write_text(json.dumps(audit_meta, indent=2))
    return meta, times, bid, ask, f


def write_log(path, log):
    if log.empty:
        log = pd.DataFrame(
            columns=[
                "entry_time",
                "exit_time",
                "net",
                "risk_money",
                "risk_budget",
                "volume",
                "extra_cost_scenario",
            ]
        )
    if not log.empty:
        if not (log.risk_money + log.extra_cost_scenario <= log.risk_budget + 1e-8).all():
            raise RuntimeError("risk invariant")
        if not np.isclose(log.volume / 0.01, np.round(log.volume / 0.01)).all():
            raise RuntimeError("lot step invariant")
    log.to_csv(path, index=False)
    reread = pd.read_csv(path)
    if len(reread) != len(log) or not np.isclose(reread.net.sum(), log.net.sum()):
        raise RuntimeError("FAILED_REPORT ledger reconciliation")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    out = args.output.with_name(args.output.name + ".partial")
    out.mkdir(parents=True, exist_ok=False)
    (out / "trades").mkdir()
    (out / "tape").mkdir()
    meta, times, bid, ask, frame = load_capture(args.capture, out / "tape")
    base = [s for s in registry() if s.name in ("B_Donchian30_RSI", "D_ATR1.5_RSI_FVG")]
    raw = {s.name: signals(frame, s) for s in base}
    policies = []
    for s, sl, rr, risk, session in itertools.product(base, SL, RR, RISK, ("all", "london_ny")):
        ident = (
            f"{'B1' if s.family == 'donchian' else 'D'}_sl{sl:g}_rr{rr:g}_risk{risk:g}_{session}"
        )
        policies.append((ident, replace(s, sl=sl, tp=rr, reconstruction=True), risk, session))
    manifest = {
        "version": "b1-d-comprehensive-v2.0.0",
        "policy_count": len(policies),
        "cost_reserves": COST,
        "policies": [
            {"policy_id": i, "spec": asdict(s), "risk_pct": r, "session": t}
            for i, s, r, t in policies
        ],
        "stages": {k: [str(a), str(b)] for k, (a, b) in STAGES.items()},
        "selection": "development only; positive each cost/PF>=1.1/trades>=30/DD<=5; rank 0.20R net/DD; else research-only least-bad",
        "initial_balance": meta["account"]["balance"],
        "account_snapshot": meta["account"],
        "symbol_spec": meta["symbol_spec"],
        "capture_manifest_sha256": hashlib.sha256(
            (args.capture / "manifest.json").read_bytes()
        ).hexdigest(),
        "code_sha256": {
            n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
            for n in ("b1_d_comprehensive.py", "b1_d_ticks.py", "strategies.py", "data.py")
        },
        "limitations": [
            "Jan-May6 ticks unavailable",
            "historical swap uses current specs/UTC-midnight assumption",
            "commission/slippage/margin histories unknown",
            "retrospective exposed data, not prospective OOS",
            "news calendar and broker execution/restarts not established by price replay",
        ],
        "production_ready": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rows = []
    breakdowns = []
    for stage, (start, end) in STAGES.items():
        a = int(np.searchsorted(times, start.value // 1_000_000))
        b = int(np.searchsorted(times, end.value // 1_000_000))
        tt, bb, aa = times[a:b], bid[a:b], ask[a:b]
        cache = {}
        for index, (ident, spec, risk, session) in enumerate(policies):
            sig = filtered_signal(frame, raw[spec.name], start, end, session)
            for cost in COST:
                log, stats = replay(
                    tt,
                    bb,
                    aa,
                    frame,
                    sig,
                    spec,
                    meta["symbol_spec"],
                    meta["account"]["balance"],
                    cost,
                    risk_pct=risk,
                    _validated_tape=True,
                    _exit_cache=cache,
                )
                row = {
                    "policy_id": ident,
                    "strategy": "B1" if spec.family == "donchian" else "D",
                    "sl_atr": spec.sl,
                    "rr": spec.tp,
                    "risk_pct": risk,
                    "session_filter": session,
                    "stage": stage,
                    "cost_r": cost,
                    **summarize(log, stats),
                }
                rows.append(row)
                write_log(out / "trades" / f"{ident}__{stage}__{cost:g}.csv", log)
                if stage == "continuous" and not log.empty:
                    entry = pd.to_datetime(log.entry_time, utc=True)
                    mins = entry.dt.hour * 60 + entry.dt.minute
                    cats = {
                        "month": entry.dt.strftime("%Y-%m"),
                        "direction": log.direction,
                        "regime": log.entry_regime,
                        "session": np.where(
                            (mins >= 420) & (mins < 630),
                            "London",
                            np.where((mins >= 750) & (mins < 990), "NewYork", "Other"),
                        ),
                    }
                    for dimension, values in cats.items():
                        for value, part in log.groupby(values):
                            loss = -part.loc[part.net < 0, "net"].sum()
                            breakdowns.append(
                                {
                                    "policy_id": ident,
                                    "cost_r": cost,
                                    "dimension": dimension,
                                    "value": str(value),
                                    "trades": len(part),
                                    "net": float(part.net.sum()),
                                    "expectancy_r": float(part.r.mean()),
                                    "pf": float(part.loc[part.net > 0, "net"].sum() / loss)
                                    if loss
                                    else None,
                                }
                            )
            if (index + 1) % 20 == 0:
                print(f"{stage}: {index + 1}/{len(policies)} policies complete", flush=True)
        pd.DataFrame(rows).to_csv(out / "matrix.csv", index=False)
        if stage == "development":
            ranking = rank_development(rows)
            # Lock before later periods scored; retain short samples as rejected rows.
            finalists = [r["policy_id"] for r in ranking if r["stress_trades"] >= 30][:3]
            if not finalists:
                finalists = [r["policy_id"] for r in ranking][:3]
            locked = {
                "created_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                "research_shortlist": finalists,
                "development_screen_pass_count": sum(r["research_screen_pass"] for r in ranking),
                "ranking": ranking,
            }
            (out / "locked_selection.json").write_text(json.dumps(locked, indent=2))
    pd.DataFrame(breakdowns).to_csv(out / "breakdowns.csv", index=False)
    # Extra quote/latency/fill stresses only for locked candidates, preserving independent accounts.
    stress = []
    a = int(np.searchsorted(times, START.value // 1_000_000))
    tt = times[a:]
    bb = bid[a:]
    aa = ask[a:]
    for ident in locked["research_shortlist"]:
        _, spec, risk, session = next(x for x in policies if x[0] == ident)
        sig = filtered_signal(frame, raw[spec.name], START, STAGES["continuous"][1], session)
        for label, spread_mult, delay, slip, cost in [
            ("twice_spread", 2, 0, 0, 0.2),
            ("latency_2s", 1, 2000, 0, 0.2),
            ("slippage_0p10", 1, 0, 0.1, 0.2),
            ("combined", 2, 2000, 0.1, 0.2),
        ]:
            sb, sa = bb, aa
            if spread_mult == 2:
                midpoint = (bb + aa) / 2
                spread = aa - bb
                sb = midpoint - spread
                sa = midpoint + spread
            log, stats = replay(
                tt,
                sb,
                sa,
                frame,
                sig,
                spec,
                meta["symbol_spec"],
                meta["account"]["balance"],
                cost,
                risk_pct=risk,
                delay_ms=delay,
                slippage=slip,
                _validated_tape=True,
            )
            stress.append({"policy_id": ident, "scenario": label, **summarize(log, stats)})
            write_log(out / "trades" / f"{ident}__stress__{label}.csv", log)
    (out / "stress.json").write_text(json.dumps(stress, indent=2))
    result = []
    for ident in locked["research_shortlist"]:
        subset = [r for r in rows if r["policy_id"] == ident]
        confirmations = [
            r
            for r in subset
            if r["stage"] in ("validation", "confirmation", "continuous") and r["cost_r"] == 0.2
        ]
        passed = all(eligible(r) for r in confirmations)
        result.append(
            {
                "policy_id": ident,
                "confirmation_screen_pass": passed,
                "metrics": subset,
                "stress": [r for r in stress if r["policy_id"] == ident],
            }
        )
    # Preserve development ordering; do not pick a later winner by changing selector.
    selected = locked["research_shortlist"][0] if locked["research_shortlist"] else None
    (out / "selection.json").write_text(
        json.dumps(
            {
                "research_selected": selected,
                "deployment_selected": None,
                "verdict": "RESEARCH_ONLY_PENDING_PROSPECTIVE_AND_COST_VALIDATION",
                "finalists": result,
            },
            indent=2,
        )
    )
    expected = len(policies) * len(COST) * len(STAGES)
    if len(rows) != expected:
        raise RuntimeError("FAILED_REPORT matrix coverage")
    (out / "COMPLETE").write_text(
        f"{expected} staged account replays plus {len(stress)} execution stresses complete; research only.\n"
    )
    out.rename(args.output)
    print(
        json.dumps(
            {"matrix_rows": len(rows), "selected_research": selected, "deployment_selected": None}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
