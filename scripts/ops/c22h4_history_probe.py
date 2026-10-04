"""Read-only candidate history/parity probe. No journal or order APIs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def compare(bars, archived, *, spec):
    """Full causal prefixes; shared hypothetical quotes/costs isolate feed drift."""
    import pandas as pd
    from scripts.c22h4.strategy import CONTRACT
    from scripts.research.reward156_search import prepare_candidate
    from scripts.research.reward156_tuning import closed_h4_ema
    from scripts.research.breakout_entry import prepare_entry
    from scripts.research.breakout_models import Costs

    live, live_rules = prepare_candidate(bars, CONTRACT)
    reference, ref_rules = prepare_candidate(archived, CONTRACT)
    live["macro_ema"] = closed_h4_ema(bars, 200)
    reference["macro_ema"] = closed_h4_ema(archived, 200)
    start = max(bars.index[0], archived.index[0])
    end = min(bars.index[-1], archived.index[-1], pd.Timestamp("2026-10-02T23:59:59Z"))
    complete = bars.close.resample("4h").count()
    warm = complete[complete == 16].index
    # Runtime requires 201 completed H4 before any decision can be admitted.
    if len(warm) >= 201:
        start = max(start, warm[200] + pd.Timedelta(hours=4, minutes=-15))
    else:
        start = end + pd.Timedelta(minutes=15)
    joined = (
        live.add_suffix("_broker")
        .join(reference.add_suffix("_archive"), how="outer")
        .loc[start:end]
    )
    signals = joined[
        (joined.raw_direction_broker.fillna(0) != 0) | (joined.raw_direction_archive.fillna(0) != 0)
    ].copy()
    records = []
    for stamp, pair in signals.iterrows():
        bid = pair.get("close_archive")
        if pd.isna(bid):
            bid = pair.get("close_broker")
        record = dict(time_utc=stamp.isoformat())
        for name, frame, rules in (("broker", live, live_rules), ("archive", reference, ref_rules)):
            if stamp not in frame.index:
                record["admission_" + name] = "missing_complete_bar"
                continue
            row = frame.loc[stamp]
            if int(row.direction) == 0:
                record["admission_" + name] = "no_signal"
                continue
            plan = prepare_entry(
                row, float(bid), float(bid) + 0.2, spec, rules, Costs(slippage=0.1), 200.0, 200.0
            )
            record["admission_" + name] = (
                plan if isinstance(plan, str) else "ADMIT_" + str(int(row.direction))
            )
            if not isinstance(plan, str):
                record.update(
                    {
                        key + "_" + name: getattr(plan, key)
                        for key in ("entry", "stop", "target", "risk")
                    }
                )
        missing = stamp not in live.index or stamp not in reference.index
        geometry_keys = ("entry", "stop", "target", "risk")
        record["geometry_diverges"] = any(
            record.get(k + "_broker") != record.get(k + "_archive") for k in geometry_keys
        )
        indicator_diff = False
        if not missing:
            for key in ("macro_ema", "atr"):
                left, right = live.loc[stamp, key], reference.loc[stamp, key]
                if not (pd.isna(left) and pd.isna(right)) and left != right:
                    indicator_diff = True
        record["indicator_diverges"] = missing or indicator_diff
        if missing:
            record["evidence"] = "missing_complete_bar"
        elif any(
            live.loc[stamp, k] != reference.loc[stamp, k] for k in ("open", "high", "low", "close")
        ):
            record["evidence"] = "OHLC_difference"
        elif indicator_diff or any(
            live.loc[stamp, k] != reference.loc[stamp, k] for k in ("direction", "raw_direction")
        ):
            record["evidence"] = "causal_prefix_or_prior_bar_difference"
        elif record["geometry_diverges"]:
            record["evidence"] = "geometry_difference"
        else:
            record["evidence"] = "match"
        record["admission_diverges"] = record["admission_broker"] != record["admission_archive"]
        records.append(record)
    admissions = pd.DataFrame(records)
    direction_diff = signals.loc[signals.direction_broker != signals.direction_archive]
    return joined, direction_diff, admissions


def probe(mt5, *, now, archive, output):
    import hashlib
    import pandas as pd
    from scripts.pure_b1.broker_data import completed_m15_from_m1
    from scripts.c22h4.strategy import CONTRACT_ID, verify_sources

    config = json.loads((ROOT / "config/c22h4-demo.json").read_text())
    verify_sources(config)
    started = time.monotonic()
    rates = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M1, 0, 100000)
    bars = completed_m15_from_m1(rates, now=now)
    elapsed = time.monotonic() - started
    # Probe terminal maximum separately; parity uses exact runtime bootstrap.
    deepest = rates
    depth = len(rates)
    queries = [{"requested": 100000, "returned": depth, "seconds": elapsed}]
    if depth == 100000:
        for request in (200000, 400000, 800000):
            if time.monotonic() - started >= 60:
                break
            query_start = time.monotonic()
            extra = mt5.copy_rates_from_pos("XAUUSDm", mt5.TIMEFRAME_M1, 0, request)
            returned = len(extra) if extra is not None else 0
            queries.append(
                dict(requested=request, returned=returned, seconds=time.monotonic() - query_start)
            )
            if returned > depth:
                deepest = extra
                depth = returned
            if returned < request:
                break
    minute_stamps = pd.DataFrame(deepest).time
    groups = (minute_stamps.diff() != 60).cumsum()
    contiguous = int(groups.value_counts().max())
    deepest_bars = completed_m15_from_m1(deepest, now=now)
    output.mkdir(parents=True, exist_ok=True)
    bars.to_csv(output / "broker-bars.csv")
    archived = pd.read_csv(archive, index_col=0, parse_dates=True, float_precision="round_trip")
    archived.index = pd.to_datetime(archived.index, utc=True)
    info, account = mt5.symbol_info("XAUUSDm"), mt5.account_info()
    spec = dict(
        trade_tick_size=float(info.trade_tick_size),
        trade_contract_size=float(info.trade_contract_size),
        leverage=float(account.leverage),
    )
    joined, differences, admissions = compare(bars, archived, spec=spec)
    differences.to_csv(output / "decision-divergences.csv")
    admissions.to_csv(output / "admissions.csv", index=False)
    joined[
        [
            k + suffix
            for k in ("direction", "macro_ema", "atr")
            for suffix in ("_broker", "_archive")
        ]
    ].to_csv(output / "parity.csv")
    h4 = int((bars.close.resample("4h").count() == 16).sum())
    admission_diff = int(admissions.admission_diverges.sum()) if len(admissions) else 0
    artifacts = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.glob("*.csv")
    }
    result = dict(
        captured_utc=now.isoformat(),
        contract_id=CONTRACT_ID,
        order_api_called=False,
        fetch_seconds=elapsed,
        requested_m1_count=100000,
        m1_count=len(rates),
        m15_count=len(bars),
        complete_h4=h4,
        first_utc=bars.index[0].isoformat(),
        last_utc=bars.index[-1].isoformat(),
        signal_bars=len(admissions),
        decision_divergences=len(differences),
        admission_divergences=admission_diff,
        geometry_divergences=int(admissions.geometry_diverges.sum()) if len(admissions) else 0,
        indicator_divergences=int(admissions.indicator_diverges.sum()) if len(admissions) else 0,
        history_gate=h4 >= 201 and elapsed < 60,
        parity_gate=len(admissions) > 0 and len(differences) == 0 and admission_diff == 0,
        geometry_assumptions=dict(
            equity=200,
            commission_per_lot=0,
            slippage=0.1,
            spread=0.2,
            quote_basis="shared_archive_close",
        ),
        source_hashes=config["source_hashes"],
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        artifacts=artifacts,
        depth_scope="bounded terminal-depth exploration; parity uses runtime 100000-M1 bootstrap",
        depth_queries=queries,
        maximum_returned_m1=depth,
        longest_contiguous_deepest_m1=contiguous,
        deepest_complete_m15=len(deepest_bars),
        deepest_complete_h4=int((deepest_bars.close.resample("4h").count() == 16).sum()),
    )
    (output / "probe.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv=None):
    from scripts.smc.mt5_init import resolve_mt5_account_kwargs

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT
        / "data/research_output_four_strategy_full_history_2026_10_04/input/continuous-bars.csv",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "data/c22h4-history-probe")
    args = parser.parse_args(argv)
    import MetaTrader5 as mt5

    credentials = resolve_mt5_account_kwargs()
    if not credentials:
        raise ValueError("target_credentials_missing")
    if not mt5.initialize(
        path=r"C:\Program Files\MetaTrader 5\terminal64.exe", timeout=10000, **credentials
    ):
        print(
            json.dumps(dict(status="BLOCKED", reason="initialize_failed", order_api_called=False))
        )
        return 1
    try:
        account = mt5.account_info()
        if (
            not account
            or account.login != credentials["login"]
            or account.server != credentials["server"]
            or account.trade_mode != 0
        ):
            raise ValueError("demo_identity_required")
        result = probe(
            mt5, now=datetime.now(timezone.utc), archive=args.archive, output=args.output
        )
        print(json.dumps(result))
        return 0 if result["history_gate"] and result["parity_gate"] else 1
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
