"""Bounded offline comparison. Never promotes research results to live config."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .b1_final import RiskState, normalize_price, reference_bars
from .b1_d_ticks import replay
from .b1_d_comprehensive import summarize
from .strategies import Spec
from scripts.strategy import XAUUSDSniperStrategy

WINDOWS = {
    "development": ("2026-05-14", "2026-06-01"),
    "validation": ("2026-06-01", "2026-09-01"),
    "confirmation": ("2026-09-01", "2026-09-26"),
}
COSTS = (0.0, 0.1, 0.2)


def directions(frame, config):
    out = {"B1": frame.direction.copy()}
    fast = frame.close.ewm(span=20, adjust=False, min_periods=20).mean()
    slow = frame.close.ewm(span=50, adjust=False, min_periods=50).mean()
    cross = pd.Series(
        np.select(
            [
                (fast > slow) & (fast.shift() <= slow.shift()),
                (fast < slow) & (fast.shift() >= slow.shift()),
            ],
            [1, -1],
            0,
        ),
        index=frame.index,
    )
    # Explicit reconstruction of README: crossover with exhaustion thresholds.
    out["EMA_RSI_RECONSTRUCTED"] = cross.where(
        ((cross == 1) & (frame.rsi <= 35)) | ((cross == -1) & (frame.rsi >= 70)), 0
    )
    out["EMA_CROSS"] = cross
    # Call production detector, supply completed bar at -2 as its contract requires.
    # EMA/ATR here use reference research smoothing; no pandas_ta parity claim.
    strategy = XAUUSDSniperStrategy(config)
    d = frame.copy().reset_index(names="time")
    d["ema_long"] = slow.to_numpy()
    values = []
    for i in range(len(d)):
        if i < 4:
            values.append(0)
            continue
        context = pd.concat([d.iloc[i - 4 : i + 1], d.iloc[[i]]], ignore_index=True)
        result = strategy.check_signals(context, pd.DataFrame(), pd.DataFrame(), 0)
        values.append({"BUY": 1, "SELL": -1}.get(result, 0))
    out["LEGACY_MSS"] = pd.Series(values, index=frame.index)
    for key in out:
        out[key] = out[key].where(frame.ready, 0)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--capital",
        type=float,
        default=200.0,
        help="Simulated Demo starting equity in USD (default: 200)",
    )
    args = p.parse_args()
    if not np.isfinite(args.capital) or args.capital <= 0:
        p.error("--capital must be finite and positive")
    args.output.mkdir(exist_ok=False, parents=True)
    out = args.output
    meta = json.loads((args.baseline / "manifest.json").read_text())
    if not (args.baseline / "COMPLETE").exists():
        raise ValueError("incomplete baseline")
    for name, expected in meta["artifacts_sha256"].items():
        assert hashlib.sha256((args.baseline / name).read_bytes()).hexdigest() == expected
    raw = pd.read_csv(args.baseline / "reference_bars.csv")
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop("bar_open_utc"), utc=True))
    frame = reference_bars(raw)
    config = yaml.safe_load(Path("config/settings.yaml").read_text())
    sigs = directions(frame, config)
    for n in (150, 1000, len(frame) // 2):
        prefix = directions(reference_bars(raw.iloc[:n]), config)
        for key in sigs:
            pd.testing.assert_series_equal(sigs[key].iloc[:n], prefix[key])
    candidates = {
        "B1": ("B1", 2.5, 3.5),
        "B1_SL2": ("B1", 2.0, 3.5),
        "B1_TP25": ("B1", 2.5, 2.5),
        "EMA_RSI_RECONSTRUCTED": ("EMA_RSI_RECONSTRUCTED", 1.5, 2 / 1.5),
        "EMA_CROSS": ("EMA_CROSS", 1.5, 2 / 1.5),
        "EMA_CROSS_TP2": ("EMA_CROSS", 1.5, 2.0),
        "LEGACY_MSS": (
            "LEGACY_MSS",
            config["strategy"]["atr_multiplier_sl"],
            config["strategy"]["atr_multiplier_tp"] / config["strategy"]["atr_multiplier_sl"],
        ),
        "LEGACY_MSS_TP2": ("LEGACY_MSS", 1.5, 2.0),
    }
    contract = {
        "windows": WINDOWS,
        "candidates": candidates,
        "costs_r": COSTS,
        "capital": [args.capital],
        "research_only": True,
        "unseen_data": False,
        "selection": "Development only: >=20 trades, PF>1 at every cost, positive net, DD<12%, no stop. Rank minimum net across costs; otherwise no candidate.",
        "smc": "Separate native OHLC diagnostics; not eligible for tick ranking.",
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baseline_manifest_sha256": hashlib.sha256(
            (args.baseline / "manifest.json").read_bytes()
        ).hexdigest(),
        "limitations": [
            "Historical periods already exposed",
            "Legacy indicator smoothing is research reference, not pandas_ta parity",
            "Historical margin, commission, slippage unknown; costs are scenarios",
            "SMC uses native risk and OHLC fills, cannot rank against tick cohort",
        ],
    }
    (out / "contract.json").write_text(json.dumps(contract, indent=2))
    times, bid, ask = [
        np.load(args.baseline / "tape" / f"{key}.npy", mmap_mode="r")
        for key in ("time", "bid", "ask")
    ]
    rows = []
    for window, dates in WINDOWS.items():
        start, end = [pd.Timestamp(x, tz="UTC") for x in dates]
        a, b = np.searchsorted(times, [start.value // 10**6, end.value // 10**6])
        mask = (frame.index + pd.Timedelta(minutes=15) >= start) & (
            frame.index + pd.Timedelta(minutes=15) < end
        )
        for name, (key, sl, tp) in candidates.items():
            sig = sigs[key].where(mask, 0).to_frame("direction")
            for capital in (args.capital,):
                for cost in COSTS:
                    state = RiskState(capital)
                    log, stats = replay(
                        times[a:b],
                        bid[a:b],
                        ask[a:b],
                        frame,
                        sig,
                        Spec(name, "research", sl=sl, tp=tp),
                        meta["broker_snapshot"],
                        capital,
                        extra_cost_r=cost,
                        risk_state=state,
                        price_normalizer=normalize_price,
                        entry_window_ms=900000,
                        _validated_tape=True,
                    )
                    if not log.empty:
                        assert (
                            log.risk_money + log.extra_cost_scenario <= log.risk_budget + 1e-8
                        ).all()
                        np.testing.assert_allclose(
                            capital + log.net.cumsum(), log.balance, atol=1e-7
                        )
                    log.to_csv(out / f"{window}_{name}_{capital}_{cost}.csv", index=False)
                    rows.append(
                        {
                            "window": window,
                            "strategy": name,
                            "capital": capital,
                            "cost_r": cost,
                            "return_pct": (stats["final_balance"] / capital - 1) * 100,
                            **summarize(log, stats),
                        }
                    )
            print(window, name, "complete", flush=True)
        if window == "development":
            eligible = []
            for name in candidates:
                selected = [
                    r for r in rows if r["strategy"] == name and r["capital"] == args.capital
                ]
                if all(
                    r["trades"] >= 20
                    and (r["pf"] or 0) > 1
                    and r["net"] > 0
                    and r["max_tick_equity_dd_pct"] < 12
                    and not r["hard_dd_stop"]
                    for r in selected
                ):
                    eligible.append((min(r["net"] for r in selected), name))
            (out / "selection_locked.json").write_text(
                json.dumps(
                    {
                        "selected": max(eligible)[1] if eligible else None,
                        "eligible": eligible,
                        "locked_before_later_windows": True,
                    },
                    indent=2,
                )
            )
        pd.DataFrame(rows).to_csv(out / "tick_metrics.csv", index=False)
    from .feedback_smc import run as run_smc

    run_smc(args.baseline, out / "smc", capital=args.capital)
    (out / "COMPLETE").write_text("Offline retrospective research only; no live promotion.\n")


if __name__ == "__main__":
    main()
