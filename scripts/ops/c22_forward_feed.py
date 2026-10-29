"""Offline cache and daily coverage companion to immutable V2 audit batches.

No SDK, financial calculation, runtime mutation or new qualification authority.
Paired cache bytes establish provenance, not independent M1/tick verification.
"""

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path

from scripts.ops.c22_forward_seal import verify_batch, _new_output, _write

AGGREGATION = "UTC_BID_M15_FROM_15_COMPLETE_M1_V1"
KINDS = ("SIGNAL", "CYCLE", "REQUEST", "RESPONSE", "LIFECYCLE", "HEALTH", "BLOCKER", "STATE")


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("forward_feed_aware_utc_required")
    return stamp


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("forward_feed_duplicate_json_key")
            value[key] = item
        return value

    return json.loads(raw, object_pairs_hook=unique)


def _cache(csv_bytes, metadata_bytes, protocol, now):
    metadata = _json(metadata_bytes)
    if not isinstance(metadata, dict):
        raise ValueError("forward_feed_metadata_invalid")
    expected = dict(
        version=1,
        aggregation=AGGREGATION,
        account_fingerprint=protocol["account_fingerprint"],
        symbol="XAUUSDm",
        contract_id=protocol["candidate_id"],
        config_sha256=protocol["config_hash"],
    )
    if type(metadata.get("version")) is not int or any(
        metadata.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("forward_feed_metadata_binding_mismatch")
    if _hash(csv_bytes) != metadata.get("sha256"):
        raise ValueError("forward_feed_csv_hash_mismatch")
    created = _utc(metadata["created_utc"])
    if created > now:
        raise ValueError("forward_feed_future_metadata")
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    if reader.fieldnames != ["bar_open_utc", "open", "high", "low", "close"]:
        raise ValueError("forward_feed_csv_schema_invalid")
    stamps = []
    for row in reader:
        stamp = _utc(row["bar_open_utc"])
        if stamp.second or stamp.microsecond or stamp.minute % 15:
            raise ValueError("forward_feed_unaligned_bar")
        try:
            prices = [float(row[key]) for key in ("open", "high", "low", "close")]
        except (TypeError, ValueError) as exc:
            raise ValueError("forward_feed_invalid_ohlc") from exc
        op, high, low, close = prices
        if (
            not all(math.isfinite(x) and x > 0 for x in prices)
            or high < max(op, low, close)
            or low > min(op, high, close)
        ):
            raise ValueError("forward_feed_invalid_ohlc")
        stamps.append(stamp)
        if len(stamps) > 100000:
            raise ValueError("forward_feed_cache_limit_exceeded")
    if (
        not stamps
        or stamps != sorted(set(stamps))
        or stamps[-1] + timedelta(minutes=15) > created
        or type(metadata.get("rows")) is not int
        or metadata["rows"] != len(stamps)
        or _utc(metadata["first_bar_utc"]) != stamps[0]
        or _utc(metadata["last_bar_utc"]) != stamps[-1]
    ):
        raise ValueError("forward_feed_cache_chronology_or_range_invalid")
    gaps = [
        dict(
            from_utc=(left + timedelta(minutes=15)).isoformat(),
            until_utc=right.isoformat(),
            missing_m15_slots=int((right - left).total_seconds() / 900) - 1,
            reason="UNKNOWN_NO_DATED_SESSION_CLASSIFICATION",
        )
        for left, right in zip(stamps, stamps[1:])
        if right - left > timedelta(minutes=15)
    ]
    freeze = _utc(protocol["freeze_utc"])
    return dict(
        rows=len(stamps),
        csv_sha256=_hash(csv_bytes),
        metadata_sha256=_hash(metadata_bytes),
        original_created_utc=created.isoformat(),
        first_bar_utc=stamps[0].isoformat(),
        last_bar_utc=stamps[-1].isoformat(),
        last_close_age_seconds=(now - stamps[-1] - timedelta(minutes=15)).total_seconds(),
        aggregation_claim=AGGREGATION,
        independent_m1_membership="NOT_CAPTURED",
        provenance="SOURCE_BYTES_BOUND_NOT_INDEPENDENT_BROKER_ATTESTATION",
        data_classification="REUSED_CACHE_NOT_HOLDOUT",
        post_freeze_bar_closes=sum(x + timedelta(minutes=15) > freeze for x in stamps),
        post_freeze_count_is_qualification=False,
        internal_gaps=gaps,
    )


def _daily(manifest, records):
    since, until = _utc(manifest["since_utc"]), _utc(manifest["until_utc"])
    cursor, output = since, []
    while cursor < until:
        end = min(
            until, cursor.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        )
        rows = [x for x in records if cursor <= _utc(x["payload"]["utc"]) < end]
        matched = [x for x in rows if x["exclusion_reason"] is None]
        kinds = Counter(x["payload"].get("kind", "UNKNOWN_KIND") for x in matched)
        output.append(
            dict(
                start_utc=cursor.isoformat(),
                end_utc=end.isoformat(),
                partial_day=not (
                    cursor.hour == cursor.minute == cursor.second == cursor.microsecond == 0
                    and end - cursor == timedelta(days=1)
                ),
                source_window_records=len(rows),
                matched_records=len(matched),
                excluded_records=len(rows) - len(matched),
                audit_ids=[x["audit_id"] for x in rows],
                kind_counts=dict(kinds),
                missing_audit_kinds=[kind for kind in KINDS if not kinds[kind]],
                blocked_cycle_reasons=dict(
                    Counter(
                        (x["payload"].get("result") or {}).get("reason", "UNSPECIFIED")
                        for x in matched
                        if x["payload"].get("kind") == "CYCLE"
                        and (x["payload"].get("result") or {}).get("status") == "BLOCKED"
                    )
                ),
                unknown_cycles=sum(
                    x["payload"].get("kind") == "CYCLE"
                    and (
                        (x["payload"].get("result") or {}).get("status") == "UNKNOWN"
                        or (x["payload"].get("result") or {}).get("position_protection")
                        == "unknown"
                    )
                    for x in matched
                ),
                broker_fill_count=None,
                observed_closed_net_usd=None,
                cashflow_total_usd=None,
                money_evaluation="NOT_EVALUATED_BY_COVERAGE_COMPANION",
                profitability="INCONCLUSIVE",
            )
        )
        cursor = end
    if sum(x["source_window_records"] for x in output) != manifest["records"]:
        raise ValueError("forward_feed_daily_denominator_mismatch")
    return output


def _build(batch, journal, now, cache_bytes=None, metadata_bytes=None):
    snapshot = {
        name: (batch / name).read_bytes()
        for name in ("manifest.json", "protocol.json", "audit.jsonl")
    }
    manifest = verify_batch(batch, journal=journal)
    if (
        any((batch / name).read_bytes() != raw for name, raw in snapshot.items())
        or manifest != _json(snapshot["manifest.json"])
        or _hash(snapshot["audit.jsonl"]) != manifest["audit_sha256"]
    ):
        raise ValueError("forward_feed_batch_changed_during_verification")
    if (cache_bytes is None) != (metadata_bytes is None):
        raise ValueError("forward_feed_paired_cache_required")
    if _utc(manifest["sealed_utc"]) > now:
        raise ValueError("forward_feed_batch_in_future")
    protocol_raw = snapshot["protocol.json"]
    records = [_json(line) for line in snapshot["audit.jsonl"].splitlines()]
    feed = (
        _cache(cache_bytes, metadata_bytes, _json(protocol_raw), now)
        if cache_bytes is not None
        else None
    )
    return dict(
        schema_version=1,
        created_utc=now.isoformat(),
        batch_path=str(batch),
        batch_manifest_sha256=_hash(snapshot["manifest.json"]),
        protocol_sha256=_hash(protocol_raw),
        source_journal_sha256=manifest["source_journal_sha256"],
        account_fingerprint=manifest["account_fingerprint"],
        cohort_id=manifest["cohort_id"],
        data_classification=manifest["data_classification"],
        records=manifest["records"],
        daily=_daily(manifest, records),
        feed=feed,
        raw_m1="NOT_CAPTURED",
        raw_ticks="NOT_CAPTURED",
        broker_attachment=manifest["broker_attachment"],
        broker_ledger_coverage="NOT_CAPTURED"
        if manifest["broker_attachment"] is None
        else "SEALED_PARENT_LEDGER_ATTACHMENT",
        source_sha256=_hash(Path(__file__).read_bytes()),
        qualification="NOT_ESTABLISHED",
        execution_authorized=False,
    )


def create_coverage(batch, journal, output, *, now, cache=None, metadata=None):
    """Read a consistent local backup and optional stable cache pair only."""
    batch, journal = Path(batch).resolve(), Path(journal).resolve()
    now = _utc(now)
    if (cache is None) != (metadata is None):
        raise ValueError("forward_feed_paired_cache_required")
    csv_bytes = metadata_bytes = None
    if cache is not None:
        cache, metadata = Path(cache), Path(metadata)
        csv_bytes, metadata_bytes = cache.read_bytes(), metadata.read_bytes()
    result = _build(batch, journal, now, csv_bytes, metadata_bytes)
    if cache is not None and (
        cache.read_bytes() != csv_bytes or metadata.read_bytes() != metadata_bytes
    ):
        raise ValueError("forward_feed_pair_changed_during_read")
    target = _new_output(output, batch, journal, *([cache, metadata] if cache is not None else []))
    if csv_bytes is not None:
        _write(target / "cache.csv", csv_bytes)
        _write(target / "cache.meta.json", metadata_bytes)
    _write(
        target / "coverage.json",
        (json.dumps(result, sort_keys=True, allow_nan=False, indent=2) + "\n").encode(),
    )
    return result


def verify_coverage(path, *, journal):
    """Recompute source-backed counts/cache from unchanged original evidence."""
    path = Path(path).resolve()
    value = _json((path / "coverage.json").read_bytes())
    has_cache = value["feed"] is not None
    expected = _build(
        Path(value["batch_path"]),
        Path(journal),
        _utc(value["created_utc"]),
        (path / "cache.csv").read_bytes() if has_cache else None,
        (path / "cache.meta.json").read_bytes() if has_cache else None,
    )
    if expected != value:
        raise ValueError("forward_feed_coverage_mismatch")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    if args.verify:
        value = verify_coverage(args.verify, journal=args.journal)
    else:
        if not args.batch or not args.out:
            parser.error("create requires --batch and --out")
        value = create_coverage(
            args.batch,
            args.journal,
            args.out,
            now=datetime.now(timezone.utc),
            cache=args.cache,
            metadata=args.metadata,
        )
    print(
        json.dumps(
            dict(
                status="SOURCE_BOUND_COVERAGE_VERIFIED",
                records=value["records"],
                days=len(value["daily"]),
                raw_ticks=value["raw_ticks"],
                qualification=value["qualification"],
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
