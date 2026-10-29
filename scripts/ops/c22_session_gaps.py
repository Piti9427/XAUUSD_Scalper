"""Offline account-bound session-gap classification; no SDK or runtime writes.

Missing schedule provenance remains UNKNOWN. This report never authorizes an
entry, fills a candle, changes quote freshness or changes native H4 mapping.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("aware_utc_timestamp_required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("aware_utc_timestamp_required")
    return stamp


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _schedule(packet, raw, *, account, symbol, now):
    if packet is None:
        return None, "dated_account_schedule_missing"
    if isinstance(packet, dict) and packet.get("load_error") in {
        "schedule_packet_unreadable",
        "schedule_packet_invalid_json",
    }:
        return None, packet["load_error"]
    if not isinstance(packet, dict) or packet.get("source_kind") != "BROKER_ACCOUNT_SYMBOL_DATED":
        return None, "schedule_source_scope_unverified"
    if not isinstance(raw, bytes):
        return None, "schedule_source_bytes_missing"
    if hashlib.sha256(raw).hexdigest() != packet.get("source_sha256"):
        return None, "schedule_source_hash_mismatch"
    try:
        document = json.loads(raw, object_pairs_hook=_unique_object)
        if document != packet.get("document") or not isinstance(document, dict):
            return None, "schedule_source_document_mismatch"
        if document.get("account_fingerprint") != account or document.get("symbol") != symbol:
            return None, "schedule_account_symbol_mismatch"
        if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
            return None, "schedule_schema_invalid"
        if document.get("timezone") != "UTC":
            return None, "schedule_timezone_unverified"
        if _utc(packet["captured_utc"]) > now:
            return None, "schedule_capture_in_future"
        coverage = document["coverage"]
        lower, upper = _utc(coverage["from_utc"]), _utc(coverage["until_utc"])
        if not lower < upper:
            return None, "schedule_coverage_invalid"
        if not isinstance(document["intervals"], list) or not document["intervals"]:
            return None, "schedule_intervals_missing"
        rows = []
        for item in document["intervals"]:
            start, end = _utc(item["from_utc"]), _utc(item["until_utc"])
            if (
                not lower <= start < end <= upper
                or item["state"] not in {"OPEN", "CLOSED"}
                or not isinstance(item.get("reason"), str)
                or not item["reason"].strip()
            ):
                return None, "schedule_interval_invalid"
            rows.append((start, end, item["state"], item["reason"]))
        rows.sort()
        if any(left[1] > right[0] for left, right in zip(rows, rows[1:])):
            return None, "schedule_intervals_overlap"
        return rows, None
    except (KeyError, TypeError, ValueError, UnicodeError):
        return None, "schedule_document_invalid"


def _classify(start, end, rows):
    cursor, states, reasons = start, set(), set()
    for lower, upper, state, reason in rows:
        if upper <= cursor:
            continue
        if lower > cursor:
            break
        cursor = min(end, upper)
        states.add(state)
        reasons.add(reason)
        if cursor == end:
            break
    if cursor != end:
        return "UNKNOWN", "schedule_dated_coverage_missing", sorted(reasons)
    if len(states) != 1:
        return "UNKNOWN", "partial_open_closed_interval", sorted(reasons)
    if states == {"CLOSED"}:
        return "EXPECTED_SESSION_CLOSURE", "source_declares_closed", sorted(reasons)
    return "UNEXPECTED_GAP_DURING_DECLARED_OPEN", "source_declares_open", sorted(reasons)


def classify_gaps(gaps, *, schedule=None, source_bytes=None, account_fingerprint, symbol, now):
    """Classify explicit missing intervals without inferring a broker schedule."""
    if (
        not isinstance(account_fingerprint, str)
        or not re.fullmatch(r"[0-9a-f]{16}", account_fingerprint)
        or symbol != "XAUUSDm"
        or not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() != timedelta(0)
    ):
        raise ValueError("account_symbol_aware_utc_context_required")
    if not isinstance(gaps, list):
        raise ValueError("gap_list_required")
    rows, schedule_reason = _schedule(
        schedule, source_bytes, account=account_fingerprint, symbol=symbol, now=now
    )
    results, identities = [], set()
    for gap in gaps:
        if not isinstance(gap, dict) or gap.get("kind") not in {"M1", "M15"}:
            raise ValueError("gap_kind_invalid")
        start, end = _utc(gap.get("from_utc")), _utc(gap.get("until_utc"))
        grid = timedelta(minutes=1 if gap["kind"] == "M1" else 15)
        if (
            not start < end <= now
            or end - start != grid
            or start.second
            or start.microsecond
            or (gap["kind"] == "M15" and start.minute % 15)
        ):
            raise ValueError("gap_interval_invalid")
        identity = (gap["kind"], start, end)
        if identity in identities:
            raise ValueError("duplicate_gap_observation")
        identities.add(identity)
        classification, reason, reasons = (
            ("UNKNOWN", schedule_reason, []) if rows is None else _classify(start, end, rows)
        )
        results.append(
            dict(
                kind=gap["kind"],
                from_utc=start.isoformat(),
                until_utc=end.isoformat(),
                classification=classification,
                reason=reason,
                schedule_reasons=reasons,
            )
        )
    return dict(
        schema_version=1,
        account_fingerprint=account_fingerprint,
        symbol=symbol,
        captured_utc=now.isoformat(),
        gaps=results,
        schedule_evidence=dict(
            status="UNKNOWN" if rows is None else "SOURCE_BYTES_BOUND",
            reason=schedule_reason,
            source_sha256=(
                hashlib.sha256(source_bytes).hexdigest()
                if isinstance(source_bytes, bytes)
                else None
            ),
            authenticity="NOT_INDEPENDENTLY_ATTESTED_BY_CLASSIFIER",
        ),
        native_rules_changed=False,
        candles_created=0,
        execution_authorized=False,
    )


def capture_report(
    capture_dir, *, account_fingerprint, symbol, now, schedule=None, source_bytes=None
):
    """Recheck declared missing M15 bars against a preserved source-bound cache.

    This is a historical capture report, not proof of current VM/feed state or
    the precise missing M1 members inside an incomplete M15 bucket.
    """
    root = Path(capture_dir)
    names = ("vm-snapshot.json", "vm-bars.csv", "additional-evidence.json")
    raw = {name: (root / name).read_bytes() for name in names}
    snapshot = json.loads(raw["vm-snapshot.json"], object_pairs_hook=_unique_object)
    evidence = json.loads(raw["additional-evidence.json"], object_pairs_hook=_unique_object)
    if (
        snapshot["journal"]["identity"] != account_fingerprint
        or snapshot["config"]["symbol"] != symbol
    ):
        raise ValueError("capture_account_symbol_mismatch")
    if hashlib.sha256(raw["vm-bars.csv"]).hexdigest() != snapshot["cache_sha256"]:
        raise ValueError("capture_cache_hash_mismatch")
    captured = _utc(snapshot["captured_utc"])
    if captured > now:
        raise ValueError("capture_observation_in_future")
    rows = csv.DictReader(io.StringIO(raw["vm-bars.csv"].decode()))
    if rows.fieldnames != ["bar_open_utc", "open", "high", "low", "close"]:
        raise ValueError("capture_cache_schema_invalid")
    stamps = [_utc(row["bar_open_utc"]) for row in rows]
    if (
        not stamps
        or stamps != sorted(set(stamps))
        or any(stamp.minute % 15 or stamp.second or stamp.microsecond for stamp in stamps)
        or stamps[-1] + timedelta(minutes=15) > captured
    ):
        raise ValueError("capture_cache_chronology_invalid")
    declarations = evidence.get("missing_bar_open_utc")
    if not isinstance(declarations, list) or not declarations:
        raise ValueError("capture_missing_bar_declarations_required")
    missing = [_utc(stamp) for stamp in declarations]
    if len(set(missing)) != len(missing):
        raise ValueError("capture_duplicate_gap_declaration")
    lower, upper = min(missing), max(missing) + timedelta(minutes=15)
    if not stamps[0] < lower < upper <= stamps[-1]:
        raise ValueError("capture_gap_outside_observed_bounds")
    expected, cursor = set(), lower
    while cursor < upper:
        expected.add(cursor)
        cursor += timedelta(minutes=15)
    if expected.difference(stamps) != set(missing):
        raise ValueError("capture_missing_bar_proof_mismatch")
    gaps = [
        dict(
            kind="M15",
            from_utc=stamp.isoformat(),
            until_utc=(stamp + timedelta(minutes=15)).isoformat(),
        )
        for stamp in sorted(missing)
    ]
    result = classify_gaps(
        gaps,
        schedule=schedule,
        source_bytes=source_bytes,
        account_fingerprint=account_fingerprint,
        symbol=symbol,
        now=now,
    )
    result.update(
        status="BOUNDED_CAPTURE_REPORTED",
        capture_observed_utc=captured.isoformat(),
        capture_age_seconds=(now - captured).total_seconds(),
        observation_scope=dict(
            from_utc=lower.isoformat(),
            until_utc=upper.isoformat(),
            gap_evidence="DECLARED_M15_ABSENCE_RECHECKED_AGAINST_CAPTURED_CACHE",
            cache_bars=len(stamps),
            current_vm_or_feed_attestation=False,
        ),
        classification_counts=dict(Counter(row["classification"] for row in result["gaps"])),
        raw_m1_membership="NOT_CAPTURED",
        source_bindings=[
            dict(name=name, sha256=hashlib.sha256(raw[name]).hexdigest()) for name in names
        ],
        limitations=[
            "M15 absence does not prove every constituent M1 minute was missing",
            "Historical capture is not current VM/feed evidence",
            "A generic public-hours page is not account-specific dated session proof",
            "Source-byte binding does not independently authenticate a broker attestation",
            "UNKNOWN never creates candles or weakens native quote/H4/admission checks",
        ],
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--account-fingerprint", required=True)
    parser.add_argument("--symbol", default="XAUUSDm")
    parser.add_argument("--schedule", type=Path)
    parser.add_argument("--schedule-source", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if bool(args.schedule) != bool(args.schedule_source):
        parser.error("--schedule and --schedule-source are required together")
    output = args.out.resolve()
    runs = Path(__file__).resolve().parents[2] / "runs"
    if not output.is_relative_to(runs.resolve()) or output == runs.resolve():
        parser.error("--out must be a new directory under runs/")
    schedule, source = None, None
    if args.schedule:
        try:
            schedule = json.loads(args.schedule.read_bytes(), object_pairs_hook=_unique_object)
        except OSError:
            schedule = dict(load_error="schedule_packet_unreadable")
        except (ValueError, UnicodeError):
            schedule = dict(load_error="schedule_packet_invalid_json")
        try:
            source = args.schedule_source.read_bytes()
        except OSError:
            # A missing optional source is evidence unavailability, not a
            # classifier failure. Preserve the actual observation report.
            source = None
    report = capture_report(
        args.capture_dir,
        account_fingerprint=args.account_fingerprint,
        symbol=args.symbol,
        now=datetime.now(timezone.utc),
        schedule=schedule,
        source_bytes=source,
    )
    report["classifier_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=report["status"],
                gaps=len(report["gaps"]),
                counts=report["classification_counts"],
                report=str(output / "report.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
