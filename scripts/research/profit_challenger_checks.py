"""Post-selection diagnostics; never change the locked challenger."""

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .profit_challengers import load_engine, candidate_features, simulate_candidate, parameters, sha
from .b1_d_comprehensive import load_capture, summarize
from .b1_d_ticks import replay
from .b1_final import RiskState, normalize_price
from .strategies import Spec


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--research", type=Path, required=True)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    out = args.output
    if out.exists():
        raise FileExistsError(out)
    out.mkdir()
    research = args.research
    locked = json.loads((research / "selection_locked.json").read_text())
    selected = locked["selected"]
    engine = load_engine(research / "inputs")
    raw = pd.read_csv(research / "inputs/data/verified.csv", parse_dates=["datetime"]).set_index(
        "datetime"
    )
    frame = candidate_features(engine, raw)
    periods = [
        ("2026-06-26T00:00:00Z", "2026-07-26T00:00:00Z"),
        ("2026-07-26T00:00:00Z", "2026-08-26T00:00:00Z"),
        ("2026-08-26T00:00:00Z", "2026-09-26T00:00:00Z"),
    ]
    rolling = []
    for start, end in periods:
        for name in dict.fromkeys(["B1", selected]):
            tr, _, _ = simulate_candidate(engine, frame, name, start, end, 0.15, False)
            sized, curve, m = simulate_candidate(engine, frame, name, start, end, 0.15, True)
            rolling.append({"start": start, "end": end, "strategy": name, **engine.stats(tr), **m})
    # Paired weekly block bootstrap of realized fixed-R differences, not an equity MC.
    daily = []
    index = pd.date_range("2026-06-26", "2026-09-25", freq="D", tz="UTC")
    for name in ["B1", selected]:
        tr = pd.read_csv(research / f"ledgers/primary_{name}_0.15_trades.csv")
        tr["exit_time"] = pd.to_datetime(tr.exit_time, utc=True)
        daily.append(
            tr.set_index("exit_time").net_r.resample("D").sum().reindex(index, fill_value=0.0)
        )
    difference = daily[1] - daily[0]
    # All seven-day blocks including quiet days; last partial block retained.
    blocks = difference.groupby(np.arange(len(difference)) // 7).sum().to_numpy()
    rng = np.random.default_rng(260926)
    draws = blocks[rng.integers(0, len(blocks), size=(20000, len(blocks)))].sum(axis=1)
    bootstrap = {
        "comparison": selected + " minus B1",
        "observed_delta_total_r": float(difference.sum()),
        "paths": 20000,
        "weekly_blocks": len(blocks),
        "ci95_r": [float(x) for x in np.quantile(draws, [0.025, 0.975])],
        "lower_bonferroni_8_challengers_r": float(np.quantile(draws, 0.025 / 8)),
        "fraction_positive_resampled_delta": float((draws > 0).mean()),
        "limitations": "Conditional retrospective realized-R block bootstrap, not future profitability probability, not broker-cost equity Monte Carlo",
    }
    # Carry equity/HWM and any existing position from February; no risk reset.
    carry = []
    for name in dict.fromkeys(["B1", selected]):
        cv = pd.read_csv(research / f"ledgers/robustness_{name}_0.15_equity.csv")
        cv["time"] = pd.to_datetime(cv.time, utc=True)
        cut = pd.Timestamp("2026-06-26T00:00:00Z")
        prior = cv.loc[cv.time <= cut].iloc[-1]
        final = cv.iloc[-1]
        carry.append(
            {
                "strategy": name,
                "equity_at_primary_start": float(prior.equity),
                "ending_equity": float(final.equity),
                "primary_carry_return_pct": float((final.equity / prior.equity - 1) * 100),
            }
        )
    # Exact captured broker minimum lot on simulated $100. Never invent symbol specs.
    (out / "tape").mkdir()
    meta, t, b, a, ohlc = load_capture(args.capture, out / "tape")
    broker_raw = ohlc[["open", "high", "low", "close"]].copy()
    broker_raw["volume"] = 0.0
    broker_frame = candidate_features(engine, broker_raw)
    start = pd.Timestamp("2026-06-26T00:00:00Z")
    end = pd.Timestamp("2026-09-26T00:00:00Z")
    left, right = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
    broker = []
    for name in dict.fromkeys(["B1", selected]):
        sig = broker_frame[[name]].rename(columns={name: "direction"}).copy()
        available = broker_frame.index + pd.Timedelta(minutes=15)
        sig.loc[(available < start) | (available >= end), "direction"] = 0
        sl, tp = parameters(name)
        state = RiskState(100.0)
        decisions = []
        log, stats = replay(
            t[left:right],
            b[left:right],
            a[left:right],
            broker_frame,
            sig,
            Spec(name, "donchian", sl=sl, tp=tp),
            meta["symbol_spec"],
            100.0,
            risk_state=state,
            price_normalizer=normalize_price,
            entry_window_ms=900000,
            _validated_tape=True,
            decision_log=decisions,
        )
        pd.DataFrame(decisions).to_csv(out / f"{name}_broker_decisions.csv", index=False)
        if log.empty:
            log = pd.DataFrame(columns=["entry_time", "exit_time", "net", "r", "risk_money"])
        log.to_csv(out / f"{name}_broker_trades.csv", index=False)
        broker.append({"strategy": name, "simulated_equity": 100.0, **summarize(log, stats)})
    result = {
        "selected_unchanged": selected,
        "rolling_fresh_windows": rolling,
        "carry_state": carry,
        "paired_weekly_bootstrap": bootstrap,
        "broker_primary_replay": broker,
        "broker_symbol_spec": meta["symbol_spec"],
        "checks_code_sha256": sha(__file__),
        "selection_sha256": sha(research / "selection_locked.json"),
        "capture_manifest_sha256": sha(args.capture / "manifest.json"),
        "limitations": [
            "Broker and public OHLC sources differ",
            "Broker replay uses quote/tick normalization and next-interval entry, public model next-observed M15 open",
            "Broker swap current-spec scenario; historical execution costs/margin unknown",
            "No order API called",
        ],
        "production_ready": False,
    }
    (out / "diagnostics.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    (out / "COMPLETE").write_text("Post-selection diagnostics; no promotion or live trading.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
