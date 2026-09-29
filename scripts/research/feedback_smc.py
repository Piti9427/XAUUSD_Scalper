"""Offline SMC diagnostics with equivalence-checked structure-state lookup."""

import argparse
import hashlib
import inspect
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from scripts.smc import detection
from scripts.smc.backtester import SMCBacktester
from scripts.smc.gold_v2_demo import GOLD_V2_DEMO
from scripts.smc.structure import find_fractals_5bar, StructureState, apply_close_break
from .feedback_round import WINDOWS


def structure_states(highs, lows, closes, sh, sl):
    """Same transition function; pivots become available only when index+2<i."""
    state = StructureState.initial()
    states = [state]
    ah, al = [], []
    for i, close in enumerate(closes):
        k = i - 3
        if k >= 0:
            if sh[k]:
                ah.append((k, float(highs[k])))
            if sl[k]:
                al.append((k, float(lows[k])))
        above = next(((k, p) for k, p in reversed(ah) if close > p), None)
        below = next(((k, p) for k, p in reversed(al) if close < p), None)
        prefer_above = close >= (closes[i - 1] if i else close)
        chosen = above if above is not None and (below is None or prefer_above) else below
        if chosen is not None:
            is_above = chosen is above
            opposite = al if is_above else ah
            latest = opposite[-1:] if opposite and opposite[-1][0] > chosen[0] else []
            state, _ = apply_close_break(
                state,
                break_side="above" if is_above else "below",
                broken_swing_price=chosen[1],
                break_index=i,
                opposite_pivots_between=latest,
            )
        states.append(state)
    return states


def run(baseline, output, capital=200.0):
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be finite and positive")
    output.mkdir(exist_ok=False, parents=True)
    times, bid = [
        np.load(baseline / "tape" / f"{key}.npy", mmap_mode="r") for key in ("time", "bid")
    ]
    chunks = []
    for left in range(0, len(times), 1000000):
        chunks.append(
            pd.DataFrame(
                {
                    "bucket": times[left : left + 1000000] // 300000,
                    "price": bid[left : left + 1000000],
                }
            )
            .groupby("bucket")
            .price.agg(["first", "max", "min", "last"])
        )
    m5 = (
        pd.concat(chunks)
        .groupby(level=0)
        .agg({"first": "first", "max": "max", "min": "min", "last": "last"})
    )
    m5.columns = ["open", "high", "low", "close"]
    m5.index = pd.to_datetime(m5.index * 300000, unit="ms", utc=True)
    h1 = (
        m5.resample("1h")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
        .reset_index(names="time")
    )
    m5 = m5.reset_index(names="time")
    m5.to_csv(output / "input_m5.csv", index=False)
    h1.to_csv(output / "input_h1.csv", index=False)
    allowed = inspect.signature(SMCBacktester).parameters
    gold = {k: v for k, v in GOLD_V2_DEMO.items() if k in allowed}
    profiles = {"SMC_NATIVE": {}, "GOLD_V2": gold, "GOLD_V2_TP2": {**gold, "tp_r": 2.0}}
    original = detection.replay_structure_until
    rows = []
    checks = []
    for window, dates in WINDOWS.items():
        start, end = [pd.Timestamp(x, tz="UTC") for x in dates]
        bars = m5.loc[(m5.time >= start) & (m5.time < end)].reset_index(drop=True)
        hi, lo, cl = [bars[k].tolist() for k in ("high", "low", "close")]
        sh, sl = find_fractals_5bar(bars)
        began = perf_counter()
        states = structure_states(hi, lo, cl, sh, sl)
        elapsed = perf_counter() - began
        # Compare actual candle prefixes, including pivot confirmation boundaries.
        for n in (0, 1, 3, 5, 20, 100, 300, 1000):
            n = min(n, len(bars))
            began = perf_counter()
            expected = original(
                hi[:n],
                lo[:n],
                cl[:n],
                sh[: max(0, n - 2)] + [False] * min(n, 2),
                sl[: max(0, n - 2)] + [False] * min(n, 2),
                n,
            )
            assert states[n] == expected, (window, n, states[n], expected)
            checks.append(
                {
                    "window": window,
                    "prefix": n,
                    "equal": True,
                    "reference_seconds": perf_counter() - began,
                }
            )

        def lookup(highs, lows, closes, swing_highs, swing_lows, end_index_exclusive):
            n = min(end_index_exclusive, len(highs), len(lows), len(closes))
            assert len(closes) <= len(cl) and closes[-1] == cl[len(closes) - 1]
            assert highs[0] == hi[0] and lows[0] == lo[0]
            return states[n]

        detection.replay_structure_until = lookup
        try:
            for name, profile in profiles.items():
                for capital in (capital,):
                    result = SMCBacktester(
                        **{**profile, "initial_balance": capital, "source_label": "exness_xauusdm"}
                    ).run(bars, h1)
                    stem = f"{window}_{name}_{capital}"
                    result.trades_df.to_csv(output / f"{stem}.csv", index=False)
                    (output / f"{stem}_funnel.json").write_text(json.dumps(result.funnel, indent=2))
                    rows.append(
                        {
                            "window": window,
                            "strategy": name,
                            "capital": capital,
                            "trades": result.total_trades,
                            "return_pct": result.net_profit / capital * 100,
                            "pf": result.profit_factor,
                            "dd_pct": result.max_drawdown_pct,
                            "sample_verdict": result.sample_verdict,
                            "ambiguous": int(
                                (
                                    result.trades_df.get("exit_reason", pd.Series(dtype=str))
                                    == "AMBIGUOUS"
                                ).sum()
                            ),
                        }
                    )
                    pd.DataFrame(rows).to_csv(output / "metrics.csv", index=False)
                    print(window, name, capital, "complete", flush=True)
        finally:
            detection.replay_structure_until = original
        print(window, "state precompute seconds", elapsed, flush=True)
        (output / "equivalence_checks.json").write_text(json.dumps(checks, indent=2))
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "research_only": True,
                "unseen_data": False,
                "capital": capital,
                "execution": "native SMC OHLC diagnostic; not tick parity",
                "acceleration": "Research process-local structure lookup; original transition function, prefix-checked",
                "limits": [
                    "Native SMC risk is 0.5%, distinct from B1 tiers",
                    "CHOCH mode targets liquidity pools; tp_r ablation may be inert",
                    "September is outside SMC foundation qualification window",
                    "No live order or notifier used",
                ],
                "sha256": {
                    str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [
                        Path(__file__),
                        Path("scripts/smc/structure.py"),
                        Path("scripts/smc/backtester.py"),
                        Path("scripts/smc/detection.py"),
                    ]
                },
            },
            indent=2,
        )
    )
    (output / "COMPLETE").write_text("Research diagnostic complete.\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--capital",
        type=float,
        default=200.0,
        help="Simulated Demo starting equity in USD (default: 200)",
    )
    a = p.parse_args()
    if not np.isfinite(a.capital) or a.capital <= 0:
        p.error("--capital must be finite and positive")
    run(a.baseline, a.output, capital=a.capital)
