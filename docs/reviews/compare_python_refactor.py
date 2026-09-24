"""Compare a frozen pre-refactor detector against current code on local CSVs."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_backtest import load_csv
from scripts.smc import backtester, detection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    namespace = {}
    source = args.baseline.read_text()
    exec(compile(source, str(args.baseline), "exec"), namespace)
    m15_path, h1_path = ROOT / "data/XAUUSD_M15.csv", ROOT / "data/XAUUSD_H1.csv"
    m15, h1 = load_csv(m15_path), load_csv(h1_path)
    profiles = {
        "v1": dict(max_sl_cap=6.0, partial_tp_enabled=False, extended_killzones=False),
        "v2": dict(max_sl_cap=25.0, partial_tp_enabled=True, partial_tp_r=1.0,
                   partial_tp_ratio=0.5, be_trigger_r=1.0, extended_killzones=True,
                   tp_r=2.5, min_body_ratio=0.45, max_sweep_pierce=8.0,
                   sweep_lookback=25, max_sweep_to_mss_bars=8, max_mss_to_fvg_bars=4),
    }
    output = {
        "python": platform.python_version(), "platform": platform.platform(),
        "baseline_sha256": sha256(source.encode()).hexdigest(),
        "current_sha256": sha256((ROOT / "scripts/smc/detection.py").read_bytes()).hexdigest(),
        "data": {p.name: {"sha256": sha256(p.read_bytes()).hexdigest(),
                           "source_header": p.read_text().splitlines()[1]} for p in (m15_path, h1_path)},
        "coverage": {"bars": len(m15), "start": str(m15.time.min()), "end": str(m15.time.max())},
        "warning": "Legacy M15 GC=F proxy simulation; no broker M5, costs, or live-readiness certification.",
        "profiles": {},
    }
    for profile, params in profiles.items():
        results = {}
        for label, detect in (("before", namespace["detect_smc_setup"]),
                              ("after", detection.detect_smc_setup)):
            timings = []
            checks = []
            for _ in range(3):
                signals = sha256()
                count = 0

                def record(*a, **kw):
                    nonlocal count
                    signal = detect(*a, **kw)
                    signals.update((repr(signal) + "\n").encode())
                    count += 1
                    return signal

                with patch.object(backtester, "detect_smc_setup", record):
                    start = perf_counter()
                    summary = backtester.SMCBacktester(**params).run(m15, h1)
                    timings.append(perf_counter() - start)
                trades = summary.trades_df.to_json(orient="records", date_format="iso")
                checks.append((signals.hexdigest(), trades))
            assert len(set(checks)) == 1, f"Nondeterministic output: {profile}/{label}"
            metrics = asdict(summary)
            del metrics["trades_df"]
            results[label] = {"seconds": timings, "median_seconds": median(timings),
                              "detector_calls": count, "signals_sha256": signals.hexdigest(),
                              "metrics": metrics, "trades": json.loads(trades)}
            print(profile, label, f"median={median(timings):.3f}s", flush=True)
        assert results["before"]["signals_sha256"] == results["after"]["signals_sha256"]
        assert results["before"]["trades"] == results["after"]["trades"]
        assert results["before"]["metrics"] == results["after"]["metrics"]
        output["profiles"][profile] = {"parameters": params, **results,
            "speedup": results["before"]["median_seconds"] / results["after"]["median_seconds"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
