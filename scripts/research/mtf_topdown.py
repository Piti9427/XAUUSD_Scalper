"""One declared W1→M15 research contract; historical M1, never Demo qualification.

Uses existing EMA20x50 and Donchian20 primitives. Higher timeframes supply
last-closed directional states; M15 Donchian20 breakout supplies each entry.
No parameter search or broker orders.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .data import REVISION, acquire, bars, load_year
from .engine import Costs, metrics, simulate
from .matrix import check_trade_log, sha256
from .strategies import Spec, features, signals


NAME = "W1D1_EMA20x50_H4H1M30_Donchian20_M15Break"
ANY_NAME = "W1D1_AnyEMA20x50_H4H1M30_Donchian20_M15Break"
DUAL_NAME = "W1D1_EMA20x50_H4H1_Donchian20_M30orM15Break"
SPEC = Spec(
    NAME, "donchian", lookback=20, fast=20, slow=50, sl=2.0, tp=2.0, timeframe=15, entry="market"
)
ANY_SPEC = Spec(
    ANY_NAME,
    "donchian",
    lookback=20,
    fast=20,
    slow=50,
    sl=2.0,
    tp=2.0,
    timeframe=15,
    entry="market",
)
DUAL_SPEC = Spec(
    DUAL_NAME,
    "donchian",
    lookback=20,
    fast=20,
    slow=50,
    sl=2.0,
    tp=2.0,
    timeframe=15,
    entry="market",
)
BASE = Spec("Donchian20", "donchian", lookback=20, sl=2.0, tp=2.0, timeframe=15, entry="market")
M30_TRIGGER = Spec(
    "Donchian20_M30_Trigger", "donchian", lookback=20, sl=2.0, tp=2.0, timeframe=30, entry="market"
)
CONTEXT = (
    ("w1", pd.Timedelta(days=7)),
    ("d1", pd.Timedelta(days=1)),
    ("h4", pd.Timedelta(hours=4)),
    ("h1", pd.Timedelta(hours=1)),
    ("m30", pd.Timedelta(minutes=30)),
)


def weekly_bid_bars(m1: pd.DataFrame) -> pd.DataFrame:
    """UTC Monday-to-Monday calendar bars; source's flat weekends remain visible."""
    bid = m1[[f"bid_{field}" for field in ("open", "high", "low", "close")]].copy()
    bid.columns = ("open", "high", "low", "close")
    weekly = bid.resample("W-MON", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    count = bid.close.resample("W-MON", label="left", closed="left").count()
    return weekly.loc[count == 7 * 24 * 60].dropna()


def ema_direction(frame: pd.DataFrame) -> pd.Series:
    """Existing EMA20x50 pair used as a state, available only at bar close."""
    fast = frame.close.ewm(span=20, adjust=False, min_periods=20).mean()
    slow = frame.close.ewm(span=50, adjust=False, min_periods=50).mean()
    state = np.sign(fast - slow).fillna(0).astype(int)
    return pd.Series(state.to_numpy(), index=frame.index)


def donchian_direction(frame: pd.DataFrame) -> pd.Series:
    """Persist direction of last Donchian20 close breakout until opposite break."""
    upper = frame.high.shift().rolling(20).max()
    lower = frame.low.shift().rolling(20).min()
    event = np.where(frame.close > upper, 1, np.where(frame.close < lower, -1, 0))
    state = pd.Series(event, index=frame.index).replace(0, np.nan).ffill().fillna(0)
    return state.astype(int)


def last_closed_state(
    state: pd.Series, bar_length: pd.Timedelta, signal_close: pd.DatetimeIndex
) -> pd.Series:
    """Align only completed HTF bars, rejecting context older than one bar."""
    if state.index.tz is None or signal_close.tz is None:
        raise ValueError("context and signal times must be timezone-aware UTC")
    if any(
        index.utcoffset() != pd.Timedelta(0)
        for index in (state.index[:1].tolist() + signal_close[:1].tolist())
    ):
        raise ValueError("context and signal times must be UTC")
    if state.empty:
        return pd.Series(0, index=signal_close, dtype=int)
    available = state.copy()
    available.index = available.index + bar_length
    return (
        available.reindex(signal_close, method="ffill", tolerance=bar_length).fillna(0).astype(int)
    )


def context_any_mask(direction, w1, d1, h4, h1, m30):
    """Actual M15 breakout; both EMA states known, one aligned; setup states aligned."""
    direction = np.asarray(direction)
    w1, d1, h4, h1, m30 = (np.asarray(state) for state in (w1, d1, h4, h1, m30))
    return (
        (direction != 0)
        & (w1 != 0)
        & (d1 != 0)
        & ((direction == w1) | (direction == d1))
        & (direction == h4)
        & (direction == h1)
        & (direction == m30)
    )


def combine_entry_events(m15_direction, m30_direction):
    """One event per M15 close; conflicting simultaneous breakouts abstain."""
    m15_direction, m30_direction = np.asarray(m15_direction), np.asarray(m30_direction)
    conflict = (m15_direction != 0) & (m30_direction != 0) & (m15_direction != m30_direction)
    return np.where(conflict, 0, np.where(m15_direction != 0, m15_direction, m30_direction))


def m30_events_at_m15_close(m30_frame, m30_events, signal_close):
    """A completed M30 breakout can trigger only at its close, never at bar open."""
    m30_close = m30_frame.index + pd.Timedelta(minutes=30)
    return (
        pd.Series(m30_events.direction.to_numpy(), index=m30_close)
        .reindex(signal_close, fill_value=0)
        .to_numpy()
    )


def topdown_signals(m1: pd.DataFrame, year: int, policy: str = "strict"):
    """Return causal M15 entry events and stage counts for one scored year."""
    if policy not in ("strict", "context_any", "dual_entry"):
        raise ValueError(f"Unknown top-down policy: {policy}")
    frame = features(m1, 15)
    raw = signals(frame, BASE)
    scored = frame.index.year == year
    raw.loc[~scored, "direction"] = 0
    signal_close = frame.index + pd.Timedelta(minutes=15)
    filtered = raw.copy()
    stage_counts = {"m15_raw": int((raw.direction != 0).sum())}
    if policy == "dual_entry":
        m30_frame = features(m1, 30)
        m30_events = signals(m30_frame, M30_TRIGGER)
        m30_at_m15_close = m30_events_at_m15_close(m30_frame, m30_events, signal_close)
        filtered["direction"] = combine_entry_events(raw.direction.to_numpy(), m30_at_m15_close)
        filtered.loc[~scored, "direction"] = 0
        stage_counts["m30_raw"] = int(((m30_at_m15_close != 0) & scored).sum())
        stage_counts["combined_raw"] = int((filtered.direction != 0).sum())
    context_frames = {
        "w1": weekly_bid_bars(m1),
        "d1": bars(m1, 1440),
        "h4": bars(m1, 240),
        "h1": bars(m1, 60),
    }
    if policy != "dual_entry":
        context_frames["m30"] = bars(m1, 30)
    aligned_states = {}
    for name, length in CONTEXT[:4] if policy == "dual_entry" else CONTEXT:
        source = context_frames[name]
        state = ema_direction(source) if name in ("w1", "d1") else donchian_direction(source)
        aligned = last_closed_state(state, length, signal_close)
        aligned_states[name] = aligned.to_numpy()
        if policy in ("strict", "dual_entry"):
            valid = filtered.direction.to_numpy() == aligned_states[name]
            filtered.loc[~valid, "direction"] = 0
            stage_counts[f"after_{name}"] = int((filtered.direction != 0).sum())
    if policy == "context_any":
        valid = context_any_mask(
            raw.direction.to_numpy(), *(aligned_states[name] for name, _ in CONTEXT)
        )
        filtered.loc[~valid, "direction"] = 0
        stage_counts["after_context_any"] = int(valid.sum())
    return frame, raw, filtered, stage_counts


def run(cache: Path, output: Path, years: list[int], policy: str = "strict") -> dict:
    years = sorted(set(years))
    if policy not in ("strict", "context_any", "dual_entry"):
        raise ValueError(f"Unknown top-down policy: {policy}")
    if not years or any(year < 2011 or year > 2026 for year in years):
        raise ValueError("2010 is warmup; scored years must be 2011–2026 (2026 is partial)")
    if output.exists():
        raise FileExistsError(output)
    required_years = sorted(set(years) | {year - 1 for year in years})
    source = acquire(cache, required_years, download=False)
    output.mkdir(parents=True)
    (output / "trades").mkdir()
    active_spec = {"strict": SPEC, "context_any": ANY_SPEC, "dual_entry": DUAL_SPEC}[policy]
    manifest = {
        "schema": "btg-topdown-research-v1",
        "status": "research_only_no_broker_costs_or_untouched_oos",
        "policy": policy,
        "source_revision": REVISION,
        "source_inputs": source,
        "scored_years": years,
        "partial_years": [2026] if 2026 in years else [],
        "warmup_years": required_years,
        "contract": asdict(active_spec),
        "context": {
            "w1_d1": (
                "last closed EMA20 >/< EMA50; both must be known and at least one aligned"
                if policy == "context_any"
                else "last closed EMA20 >/< EMA50; both must align"
            ),
            "h4_h1_m30": (
                "H4/H1 last Donchian20 close breakout direction; M30 is an entry event"
                if policy == "dual_entry"
                else "last Donchian20 close breakout direction, persists until opposite breakout"
            ),
            "entry": (
                "M15 Donchian20 close breakout, H4/H1/M30 aligned and at least one of known W1/D1 aligned; exact next M1 open"
                if policy == "context_any"
                else "M30 or M15 Donchian20 close breakout aligned with W1/D1/H4/H1; simultaneous opposite events abstain; M15 ATR exit; exact next M1 open"
                if policy == "dual_entry"
                else "M15 Donchian20 close breakout aligned with all five states; exact next M1 open"
            ),
            "exit": "native Donchian20 regime and 2 ATR stop / 2R target",
            "week": "UTC Monday 00:00 to next Monday 00:00; only 10080-minute complete weeks",
            "year": "previous complete year for indicators; positions reset and liquidated at each scored sample end",
        },
        "costs": asdict(Costs()),
        "risk": "1 oz-equivalent research exposure; no Exness lot/capital sizing",
        "code_sha256": {
            name: sha256(Path(__file__).with_name(name))
            for name in ("mtf_topdown.py", "data.py", "strategies.py", "engine.py")
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    annual, funnels, audits = [], [], []
    previous_year = min(required_years)
    previous, audit = load_year(cache, previous_year)
    audits.append(audit)
    for year in years:
        if previous_year != year - 1:
            previous, audit = load_year(cache, year - 1)
            audits.append(audit)
        current, audit = load_year(cache, year)
        audits.append(audit)
        combined = pd.concat((previous, current))
        frame, raw, filtered, counts = topdown_signals(combined, year, policy)
        for name, signal, spec in (
            ("base_donchian20", raw, BASE),
            (active_spec.name, filtered, active_spec),
        ):
            log, dd = simulate(current, frame, signal, spec, Costs(), native=True)
            filename = f"{name}__native__{year}.csv"
            log.to_csv(output / "trades" / filename, index=False)
            row = {"strategy": name, "year": year, **metrics(log, dd)}
            annual.append(row)
            check_trade_log(output / "trades" / filename, row)
        funnels.append(
            {
                "year": year,
                **counts,
                "base_trades": annual[-2]["trades"],
                "topdown_trades": annual[-1]["trades"],
            }
        )
        previous, previous_year = current, year
        print(
            f"{year}: raw={counts['m15_raw']} aligned={int((filtered.direction != 0).sum())} "
            f"trades={annual[-1]['trades']}",
            flush=True,
        )
    pd.DataFrame(annual).to_csv(output / "annual.csv", index=False)
    pd.DataFrame(funnels).to_csv(output / "funnel.csv", index=False)
    (output / "data-audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    manifest["outputs_sha256"] = {
        str(path.relative_to(output)): sha256(path) for path in sorted(output.rglob("*.csv"))
    }
    manifest["outputs_sha256"]["data-audit.json"] = sha256(output / "data-audit.json")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "COMPLETE").write_text(
        "Top-down research backtest complete; no Demo qualification.\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2011, 2026)))
    parser.add_argument(
        "--policy", choices=("strict", "context_any", "dual_entry"), default="strict"
    )
    args = parser.parse_args()
    manifest = run(args.cache, args.output, args.years, args.policy)
    print(json.dumps({"status": manifest["status"], "years": manifest["scored_years"]}))


if __name__ == "__main__":
    main()
