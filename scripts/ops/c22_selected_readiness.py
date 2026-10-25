"""Read-only selected26b8 readiness; measured results never activate a sender."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import math

from scripts.c22_selected.strategy import CANDIDATE_ID, MAGIC, ROOT, SNAPSHOT
from scripts.ops.c22h4_readiness import build_report, utc

DURATION_GATES = (
    "shadow_48h_continuous_observation_missing",
    "shadow_96_new_complete_m15_missing",
)
WAIVER_DECISION = "เริ่ม Demo trial เมื่อหลักฐานพร้อม โดยยกเว้นเวลา shadow 48 ชั่วโมง/96 แท่งสำหรับ 26b8"


def canonical_json_sha256(value):
    """Match existing evidence bindings: sorted keys, finite JSON, UTF-8 bytes."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def build_selected_report(conn, *, now, since, broker, parity, policy, feed_review=None, shadow_waiver=None):
    """Measure selected identity and exact inputs without inheriting old waivers."""
    now, since = utc(now), utc(since)
    values = {key: json.loads(value) for key, value in conn.execute("SELECT key,value FROM kv")}
    fingerprint = values.get("identity")
    cohorts = set()
    wrong_snapshot = False
    latest_cycle = {}
    fresh_prospective_bar = False
    for (raw,) in conn.execute("SELECT payload FROM audit_events ORDER BY id"):
        try:
            event = json.loads(raw)
            if event.get("kind") not in ("CYCLE", "SIGNAL") or not since <= utc(event["utc"]) <= now:
                continue
            cohorts.add(tuple(event.get(key) for key in
                              ("account_fingerprint", "release_hash", "config_hash")))
            if event["kind"] == "CYCLE":
                latest_cycle = event.get("result") or {}
                if latest_cycle.get("snapshot") != SNAPSHOT:
                    wrong_snapshot = True
            else:
                bar = utc(event["bar"])
                if bar >= since and 0 <= (now - bar).total_seconds() <= 900:
                    fresh_prospective_bar = True
        except (KeyError, TypeError, ValueError):
            continue  # Shared measurement below records invalid evidence as a blocker.
    cohort = None
    if len(cohorts) == 1:
        account, release, config = next(iter(cohorts))
        hashes = (release, config)
        if account == fingerprint and all(
            isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value) for value in hashes
        ):
            cohort = dict(release_hash=release, config_hash=config)
    review_ok = bool(
        feed_review and isinstance(feed_review, dict)
        and feed_review.get("snapshot") == SNAPSHOT
        and feed_review.get("contract_id") == CANDIDATE_ID
        and feed_review.get("account_fingerprint") == fingerprint
        and cohort is not None
        and all(feed_review.get(key) == value for key, value in cohort.items())
    )
    accepted_review = None
    if isinstance(feed_review, dict) and review_ok and "shadow_time_waiver" not in feed_review:
        accepted_review = feed_review
    result = build_report(
        conn, now=now, since=since, broker=broker, parity=parity, policy=policy,
        feed_review=accepted_review,
        expected_snapshot=SNAPSHOT, contract_id=CANDIDATE_ID, magic=MAGIC,
    )
    blockers = result["blockers"]
    if cohort is None:
        blockers.append("selected_single_cohort_missing_or_invalid")
    if wrong_snapshot or (values.get("last_result") or {}).get("snapshot") != SNAPSHOT:
        blockers.append("selected_cycle_snapshot_mismatch")
    if not latest_cycle or latest_cycle.get("captured_utc") != (
        values.get("last_result") or {}
    ).get("captured_utc"):
        blockers.append("selected_latest_cycle_not_bound_to_heartbeat")
    if not (
        parity.get("snapshot") == SNAPSHOT
        and parity.get("contract_id") == CANDIDATE_ID
        and parity.get("account_fingerprint") == fingerprint
        and cohort is not None
        and all(parity.get(key) == value for key, value in cohort.items())
    ):
        blockers.append("selected_parity_identity_or_cohort_mismatch")
    if feed_review is not None and not review_ok:
        blockers.append("selected_feed_review_identity_or_cohort_mismatch")
    if isinstance(feed_review, dict) and "shadow_time_waiver" in feed_review:
        blockers.append("selected_shadow_time_waiver_not_authorized")
    waiver_ok = False
    if shadow_waiver is not None:
        try:
            gates = shadow_waiver["waived_gates"]
            waiver_ok = bool(
                type(shadow_waiver["version"]) is int and shadow_waiver["version"] == 1
                and shadow_waiver["scope"] == "SELECTED_DEMO_TRIAL_DURATION_ONLY"
                and shadow_waiver["owner_decision"] == WAIVER_DECISION
                and shadow_waiver["snapshot"] == SNAPSHOT and shadow_waiver["contract_id"] == CANDIDATE_ID
                and shadow_waiver["magic"] == MAGIC and shadow_waiver["account_fingerprint"] == fingerprint
                and cohort is not None and all(shadow_waiver[key] == value for key, value in cohort.items())
                and utc(shadow_waiver["accepted_utc"]) <= now
                and isinstance(gates, list) and len(gates) == 2 and set(gates) == set(DURATION_GATES)
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            waiver_ok = False
        if waiver_ok:
            blockers[:] = [reason for reason in blockers if reason not in DURATION_GATES]
            shadow = result["shadow"]
            if not shadow["cycles"] or shadow["max_cycle_gap_seconds"] > 120:
                blockers.append("selected_recent_observation_missing_or_interrupted")
            if not shadow["new_complete_m15_bars"] or not fresh_prospective_bar:
                blockers.append("selected_fresh_prospective_m15_missing")
            try:
                macro = (values.get("last_result") or {}).get("macro_ema")
                macro_ok = macro is not None and not isinstance(macro, bool) and math.isfinite(float(macro))
            except (ValueError, TypeError, OverflowError):
                macro_ok = False
            if not macro_ok:
                blockers.append("selected_current_macro_warmup_not_verified")
        else:
            blockers.append("selected_duration_waiver_invalid")
    result["shadow"].update(selected_duration_waiver_applied=waiver_ok,
                            waived_gates=list(DURATION_GATES) if waiver_ok else [])
    result.update(
        snapshot=SNAPSHOT, contract_id=CANDIDATE_ID, magic=MAGIC,
        account_fingerprint=fingerprint, cohort=cohort,
        input_sha256={name: canonical_json_sha256(value) for name, value in {
            "broker": broker, "parity": parity, "policy": policy, "feed_review": feed_review,
        }.items()},
        input_representation="json.dumps(sort_keys=True, allow_nan=False).encode('utf-8')",
        status="BLOCKED" if blockers else "AWAITING_OPERATOR_REVIEW",
        execution_authorized=False,
    )
    if shadow_waiver is not None:
        result["input_sha256"]["shadow_waiver"] = canonical_json_sha256(shadow_waiver)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ("journal", "broker", "parity", "cost-policy", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--feed-review", type=Path)
    parser.add_argument("--shadow-waiver", type=Path)
    parser.add_argument("--since", type=utc, required=True)
    args = parser.parse_args(argv)
    output = args.out.resolve()
    if not output.is_relative_to((ROOT / "runs").resolve()) or output.exists():
        parser.error("output must be a new report under ignored runs/; never overwrite evidence")
    paths = {"broker": args.broker, "parity": args.parity, "policy": args.cost_policy}
    if args.feed_review:
        paths["feed_review"] = args.feed_review
    if args.shadow_waiver:
        paths["shadow_waiver"] = args.shadow_waiver
    try:
        raw_inputs = {name: path.read_bytes() for name, path in paths.items()}
        documents = {name: json.loads(raw) for name, raw in raw_inputs.items()}
        if any(not isinstance(value, dict) for value in documents.values()):
            raise ValueError("evidence must be JSON objects")
        conn = sqlite3.connect(args.journal.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            result = build_selected_report(
                conn, now=datetime.now(timezone.utc), since=args.since,
                broker=documents["broker"], parity=documents["parity"],
                policy=documents["policy"], feed_review=documents.get("feed_review"),
                shadow_waiver=documents.get("shadow_waiver"),
            )
        finally:
            conn.close()
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        parser.error("read-only readiness input rejected: " + str(exc))
    result["raw_input_sha256"] = {
        name: hashlib.sha256(raw).hexdigest() for name, raw in raw_inputs.items()
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        output.chmod(0o600)
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "execution_authorized": False,
                      "blockers": result["blockers"]}))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
