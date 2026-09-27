"""Seeded robustness diagnostics and strictly prior-month retrospective selection."""

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def robustness(log, seed=260926, draws=100000):
    if log.empty:
        return {"trades": 0, "verdict": "INSUFFICIENT"}
    closed = log[log.reason != "END_OF_SAMPLE"].copy()
    if closed.empty:
        return {"trades": len(log), "verdict": "INSUFFICIENT_CLOSED"}
    times = pd.to_datetime(closed.exit_time, utc=True, format="mixed")
    monday = times.dt.normalize() - pd.to_timedelta(times.dt.dayofweek, unit="D")
    data = pd.DataFrame({"r": closed.r.to_numpy(), "week": monday})
    weekly = data.groupby("week").r.agg(["sum", "count"])
    # Include zero-trade weeks; no selectively dropping quiet calendar periods.
    all_weeks = pd.date_range(
        pd.Timestamp("2026-05-11T00:00Z"), pd.Timestamp("2026-09-21T00:00Z"), freq="7D"
    )
    weekly = weekly.reindex(all_weeks, fill_value=0)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(weekly), size=(draws, len(weekly)))
    sums = weekly["sum"].to_numpy()[indices].sum(axis=1)
    counts = weekly["count"].to_numpy()[indices].sum(axis=1)
    estimates = np.divide(sums, counts, out=np.full(draws, np.nan), where=counts > 0)
    valid = estimates[np.isfinite(estimates)]
    # Conditional order-resampling: frozen observed return fractions, no claim of fresh lot-admission replay.
    previous = closed.balance.to_numpy() - closed.net.to_numpy()
    fractions = closed.net.to_numpy() / previous
    dd = []
    for _ in range(10000):
        perm = rng.permutation(fractions)
        equity = np.r_[1.0, np.cumprod(1 + perm)]
        peak = np.maximum.accumulate(equity)
        dd.append(float(np.max((peak - equity) / peak) * 100))
    return {
        "trades": len(log),
        "closed_trades": len(closed),
        "weeks": len(weekly),
        "seed": seed,
        "bootstrap_draws": draws,
        "mean_r": float(closed.r.mean()),
        "weekly_block_lower_2p5pct_r": float(np.quantile(valid, 0.025)),
        "bonferroni_320_policy_lower_r": float(np.quantile(valid, 0.025 / 320)),
        "tail_expected_draws": draws * 0.025 / 320,
        "bootstrap_empty_replicates": int((counts == 0).sum()),
        "permutation_draws": 10000,
        "permutation_closed_dd_median_pct": float(np.median(dd)),
        "permutation_closed_dd_p95_pct": float(np.quantile(dd, 0.95)),
        "permutation_fraction_dd_over_5pct": float((np.array(dd) > 5).mean()),
        "limitations": [
            "conditional on observed returns; not future probability",
            "closed-equity permutations omit intratrade ticks and new broker sizing",
            "same-period tuning; bootstrap does not create untouched OOS",
            "corrected tail based on approximately 8 extreme draws, imprecise",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not (a.matrix / "COMPLETE").exists():
        raise ValueError("matrix incomplete")
    if a.output.exists():
        raise FileExistsError(a.output)
    temp = a.output.with_name(a.output.name + ".partial")
    temp.mkdir(parents=True, exist_ok=False)
    selection = json.loads((a.matrix / "locked_selection.json").read_text())
    policies = [r["policy_id"] for r in selection["ranking"]]
    logs = {
        ident: pd.read_csv(a.matrix / "trades" / f"{ident}__continuous__0.2.csv")
        for ident in policies
    }
    diagnostics = []
    for ident in selection["research_shortlist"]:
        diagnostics.append({"policy_id": ident, **robustness(logs[ident])})
    folds = []
    for month in ("2026-07", "2026-08", "2026-09"):
        start = pd.Timestamp(month + "-01T00:00Z")
        end = start + pd.offsets.MonthBegin(1)
        ranked = []
        for ident, log in logs.items():
            if log.empty:
                continue
            exit_time = pd.to_datetime(log.exit_time, utc=True, format="mixed")
            entry_time = pd.to_datetime(log.entry_time, utc=True, format="mixed")
            past = log[(entry_time < start) & (exit_time < start) & (log.reason != "END_OF_SAMPLE")]
            if len(past) < 30:
                continue
            net = float(past.net.sum())
            dd = float(past.cumulative_max_dd_pct.max())
            loss = -past.loc[past.net < 0, "net"].sum()
            pf = float(past.loc[past.net > 0, "net"].sum() / loss) if loss else None
            passed = net > 0 and dd <= 5 and pf is not None and pf >= 1.1
            ranked.append((passed, net / max(dd, 0.1), len(past), ident))
        if not ranked:
            folds.append(
                {"month": month, "selected": None, "reason": "no prior closed-ledger sample >=30"}
            )
            continue
        passed, score, n, ident = max(ranked)
        log = logs[ident]
        entry_time = pd.to_datetime(log.entry_time, utc=True, format="mixed")
        exit_time = pd.to_datetime(log.exit_time, utc=True, format="mixed")
        future = log[
            (entry_time >= start)
            & (entry_time < end)
            & (exit_time < end)
            & (log.reason != "END_OF_SAMPLE")
        ]
        folds.append(
            {
                "month": month,
                "research_selected": ident,
                "prior_screen_pass": passed,
                "training_closed_trades": n,
                "test_closed_trades_same_month": len(future),
                "test_net": float(future.net.sum()),
                "boundary": "diagnostic of each independent continuous ledger; cross-month open trades excluded; not newly stitched executable portfolio",
            }
        )
    (temp / "robustness.json").write_text(json.dumps(diagnostics, indent=2))
    (temp / "monthly_selection.json").write_text(json.dumps(folds, indent=2))
    manifest = {
        "matrix_manifest_sha256": hashlib.sha256(
            (a.matrix / "manifest.json").read_bytes()
        ).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "created_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "production_ready": False,
    }
    (temp / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (temp / "COMPLETE").write_text(
        "Seeded conditional robustness and retrospective monthly selection diagnostics complete.\n"
    )
    temp.rename(a.output)
    print(json.dumps({"diagnostics": diagnostics, "monthly_selection": folds}, indent=2))


if __name__ == "__main__":
    main()
