"""Bounded CSV checks; never mutate input or certify historical completeness."""

import csv
import math
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from .artifacts import make_report, parse_utc, read_json, source_ref


def _read_rows(path: Path, max_rows: int) -> tuple[list[dict], bool]:
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV requires a header")
        headers = [header.strip().lower() for header in reader.fieldnames]
        if len(headers) != len(set(headers)):
            raise ValueError("Duplicate CSV column after normalization")
        rows = []
        for index, row in enumerate(reader):
            if index == max_rows:
                return rows, True
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row{index + 2}")
            rows.append({str(key).strip().lower(): value for key, value in row.items()})
        return rows, False


def audit_data(
    manifest_path: Path,
    bars_path: Path | None = None,
    ticks_path: Path | None = None,
    max_rows: int = 10000,
) -> dict:
    """Report observed defects and exact scan coverage without repairing data."""
    if (
        isinstance(max_rows, bool)
        or not isinstance(max_rows, int)
        or not 1 <= max_rows <= 1_000_000
    ):
        raise ValueError("max_rows must be an integer from1 through1000000")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("Data manifest must be an object")
    timeframe = manifest.get("bar_timeframe_minutes", 15)
    if isinstance(timeframe, bool) or not isinstance(timeframe, int) or timeframe not in (1, 15):
        raise ValueError("bar_timeframe_minutes must be1 or15")
    sources = [source_ref(manifest_path)]
    checks = {}
    issues = []
    counts = Counter()

    def issue(code, source, row, **detail):
        counts[code] += 1
        if len(issues) < 50:
            issues.append({"code": code, "source": source, "row": row, **detail})

    manifest_times = {}
    for field in ("first_quote_utc", "last_quote_utc"):
        if field in manifest:
            try:
                manifest_times[field] = parse_utc(manifest[field])
            except (ValueError, TypeError):
                issue("INVALID_MANIFEST_TIMESTAMP", "manifest", None, field=field)
    if (
        len(manifest_times) == 2
        and manifest_times["first_quote_utc"] > manifest_times["last_quote_utc"]
    ):
        issue("INVALID_MANIFEST_INTERVAL", "manifest", None)
    for field in ("ticks", "bars"):
        value = manifest.get(field)
        if field in manifest and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            issue("INVALID_MANIFEST_COUNT", "manifest", None, field=field)

    for name, path in (("bars", bars_path), ("ticks", ticks_path)):
        if path is not None:
            rows, truncated = _read_rows(path, max_rows)
            times = []
            seen_times = set()
            seen_quotes = set()
            previous = None
            buckets = defaultdict(set)
            for number, row in enumerate(rows, 2):
                time_value = next(
                    (
                        row[key]
                        for key in (
                            "bar_open_utc",
                            "time_utc",
                            "timestamp_utc",
                            "quote_utc",
                            "timestamp",
                            "time",
                        )
                        if key in row
                    ),
                    None,
                )
                try:
                    if not isinstance(time_value, str):
                        raise ValueError("Missing timestamp column or string value")
                    timestamp = parse_utc(time_value)
                except (ValueError, TypeError):
                    issue("INVALID_TIMESTAMP", name, number)
                    timestamp = None
                if timestamp is not None:
                    times.append(timestamp)
                    if name == "bars" and timestamp in seen_times:
                        issue(
                            "DUPLICATE_TIMESTAMP", name, number, timestamp_utc=timestamp.isoformat()
                        )
                    if previous is not None and timestamp < previous:
                        issue("OUT_OF_ORDER", name, number, timestamp_utc=timestamp.isoformat())
                    if name == "bars" and (
                        timestamp.second != 0
                        or timestamp.microsecond != 0
                        or timestamp.minute % timeframe
                    ):
                        issue("BAR_ALIGNMENT", name, number, timestamp_utc=timestamp.isoformat())
                    elif name == "bars" and timeframe == 1:
                        bucket = timestamp.replace(minute=timestamp.minute // 15 * 15)
                        buckets[bucket].add(timestamp.minute % 15)
                    if (
                        name == "bars"
                        and previous is not None
                        and timestamp - previous > timedelta(minutes=timeframe)
                    ):
                        span = timestamp - previous
                        days = min(span.days + 1, 7)
                        weekend = any(
                            (previous + timedelta(days=day)).weekday() >= 5 for day in range(days)
                        )
                        issue(
                            "MISSING_INTERVAL",
                            name,
                            number,
                            previous_utc=previous.isoformat(),
                            next_utc=timestamp.isoformat(),
                            missing_intervals=int(span.total_seconds() // (timeframe * 60)) - 1,
                            classification="WEEKEND_OVERLAP_UNVERIFIED"
                            if weekend
                            else "UNEXPLAINED_GAP",
                        )
                    seen_times.add(timestamp)
                    previous = timestamp
                fields = ("open", "high", "low", "close") if name == "bars" else ("bid", "ask")
                try:
                    values = {field: float(row[field]) for field in fields}
                except (ValueError, TypeError, KeyError):
                    issue("INVALID_PRICE", name, number)
                    continue
                if not all(math.isfinite(value) for value in values.values()):
                    issue("NONFINITE_PRICE", name, number)
                    continue
                if min(values.values()) <= 0:
                    issue("NONPOSITIVE_PRICE", name, number)
                if name == "ticks":
                    if values["ask"] < values["bid"]:
                        issue("NEGATIVE_SPREAD", name, number)
                    quote = (timestamp, values["bid"], values["ask"])
                    if timestamp is not None and quote in seen_quotes:
                        issue("DUPLICATE_QUOTE", name, number, timestamp_utc=timestamp.isoformat())
                    seen_quotes.add(quote)
                if name == "bars" and not (
                    values["low"]
                    <= min(values["open"], values["close"])
                    <= max(values["open"], values["close"])
                    <= values["high"]
                ):
                    issue("INVALID_OHLC", name, number)
            checks[name] = {
                "rows_examined": len(rows),
                "truncated": truncated,
                "first_observed_utc": min(times).isoformat() if times else None,
                "last_observed_utc": max(times).isoformat() if times else None,
            }
            if not rows:
                issue("EMPTY_INPUT", name, None)
            if name == "bars":
                checks[name]["timeframe_minutes"] = timeframe
                checks[name]["timeframe_basis"] = (
                    "manifest.bar_timeframe_minutes"
                    if "bar_timeframe_minutes" in manifest
                    else "ASSUMED_M15_CANONICAL_BARS"
                )
            if name == "bars" and timeframe == 1:
                assembly = {
                    "complete_buckets": 0,
                    "incomplete_buckets": 0,
                    "sample_boundary_partial_buckets": 0,
                    "incomplete_examples": [],
                }
                last_bucket = max(buckets, default=None)
                for bucket, minutes in sorted(buckets.items()):
                    if len(minutes) == 15:
                        assembly["complete_buckets"] += 1
                    elif truncated and bucket == last_bucket:
                        assembly["sample_boundary_partial_buckets"] += 1
                    else:
                        assembly["incomplete_buckets"] += 1
                        example = {
                            "bucket_open_utc": bucket.isoformat(),
                            "observed_minutes": len(minutes),
                            "missing_minutes": sorted(set(range(15)) - minutes),
                        }
                        if len(assembly["incomplete_examples"]) < 20:
                            assembly["incomplete_examples"].append(example)
                        issue("INCOMPLETE_M15_FROM_M1", name, None, **example)
                checks[name]["m15_from_m1"] = assembly
            reference = source_ref(path, max_bytes=0)
            reference["scan_scope"] = "BOUNDED_CSV_ROWS"
            artifacts = manifest.get("artifacts", {})
            try:
                relative = (
                    Path(path)
                    .resolve()
                    .relative_to(Path(manifest_path).resolve().parent)
                    .as_posix()
                )
            except ValueError:
                relative = None
            reference["declared_sha256"] = (
                artifacts.get(relative) if isinstance(artifacts, dict) else None
            )
            reference["declared_hash_verified"] = False
            sources.append(reference)
    return make_report(
        "data_quality",
        "DATA_QUALITY_ISSUES" if counts else "INCONCLUSIVE",
        sources=sources,
        coverage={
            "manifest_ticks": manifest.get("ticks"),
            "manifest_bars": manifest.get("bars"),
            "max_rows_per_csv": max_rows,
            "scans": {
                name: {
                    key: scan[key]
                    for key in (
                        "rows_examined",
                        "truncated",
                        "first_observed_utc",
                        "last_observed_utc",
                    )
                }
                for name, scan in checks.items()
            },
        },
        reasons=[
            "Manifest counts do not certify provider-history completeness.",
            "CSV checks cover only the declared bounded prefix; input hashes are not recomputed.",
            "No broker/session calendar or comparison feed was supplied; gaps remain unqualified.",
        ],
        source_completeness="NOT_CERTIFIED",
        feed_parity="NOT_TESTED",
        signal_or_level_impact="NOT_EVALUATED_WITHOUT_FROZEN_CANDIDATE_AND_COMPARISON_FEED",
        bounded_checks_status="ISSUES_FOUND" if counts else "PASS" if checks else "NOT_RUN",
        checks=checks,
        issue_counts=dict(counts),
        issues=issues,
    )
