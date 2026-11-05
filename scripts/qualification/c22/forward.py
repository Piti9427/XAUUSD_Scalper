"""Offline forward protocol; immutable versions, never runtime activation."""

from __future__ import annotations

import fcntl
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import (
    canonical_hash,
    make_report,
    parse_utc,
    read_json,
    sha256_file,
    source_ref,
    write_json,
)


def _validate_source_bindings(sources: Any) -> list[dict[str, Any]]:
    if not isinstance(sources, list) or not sources:
        raise ValueError("Report source bindings are required")
    checked: list[dict[str, Any]] = []
    for source in sources:
        if (
            not isinstance(source, dict)
            or source.get("hash_status") != "VERIFIED"
            or not source.get("sha256")
        ):
            raise ValueError("Report source binding is unverified")
        limit = source.get("hash_limit_bytes", 32 * 1024 * 1024)
        if type(limit) is not int or not 0 < limit <= 256 * 1024 * 1024:
            raise ValueError("Unbounded report dependency hash limit")
        current = source_ref(Path(source["path"]), max_bytes=limit)
        if current["hash_status"] != "VERIFIED" or current["sha256"] != source["sha256"]:
            raise ValueError("Report dependency source drift")
        checked.append(current)
    return checked


def _validate_report(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    if (
        document.get("schema_version") != 1
        or document.get("artifact_type") != kind
        or document.get("execution_authorized") is not False
        or not isinstance(document.get("data"), dict)
    ):
        raise ValueError("Invalid preparation report envelope")
    return _validate_source_bindings(document.get("sources"))


def draft_protocol(manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    return make_report(
        "forward_protocol",
        "DRAFT_NOT_FROZEN",
        candidate_id=manifest.get("candidate_id"),
        sources=[source_ref(manifest_path)],
        coverage={"prospective_observations": 0},
        reasons=["Review endpoints and operational stopping criteria require an explicit decision"],
        policy="FIXED_VERSION_NEW_COHORT_FOR_RETUNING",
        criteria={
            "schema_version": 1,
            "criteria_confirmed": False,
            "freeze_utc": None,
            "exposed_through_utc": None,
            "review_end_utc": None,
            "minimum_closed_positions": None,
            "operational_stop_reasons": [],
        },
        profitability="INCONCLUSIVE",
        shadow_is_fill=False,
    )


def freeze_cohort(
    manifest_path: Path,
    parity_path: Path,
    criteria_path: Path,
    cohort_dir: Path,
) -> dict[str, Any]:
    """Bind reviewed files; creating this definition authorizes no execution."""
    manifest = read_json(manifest_path)
    if manifest.get("status") != "RESEARCH_BOUND":
        raise ValueError("A RESEARCH_BOUND manifest is required before cohort freeze")
    bindings = _validate_report(manifest, "candidate_manifest")
    parity = read_json(parity_path)
    candidate = manifest.get("candidate_id")
    if (
        not candidate
        or parity.get("candidate_id") != candidate
        or parity.get("status") != "PARITY_PASS"
    ):
        raise ValueError("Candidate-bound PARITY_PASS is required")
    bindings += _validate_report(parity, "event_parity")
    criteria = read_json(criteria_path)
    if criteria.get("artifact_type") == "forward_protocol":
        if criteria.get("candidate_id") != candidate:
            raise ValueError("Forward protocol candidate mismatch")
        criteria = criteria["data"]["criteria"]
    required = {
        "schema_version",
        "criteria_confirmed",
        "freeze_utc",
        "exposed_through_utc",
        "review_end_utc",
        "minimum_closed_positions",
        "operational_stop_reasons",
    }
    if set(criteria) != required or criteria["schema_version"] != 1:
        raise ValueError("Unknown or missing forward criteria")
    if criteria["criteria_confirmed"] is not True:
        raise ValueError("Forward criteria are not confirmed")
    freeze = parse_utc(criteria["freeze_utc"])
    exposed = parse_utc(criteria["exposed_through_utc"])
    end = parse_utc(criteria["review_end_utc"])
    cutoff = parse_utc(manifest["data"]["manifest"]["data_cutoff_utc"])
    created = datetime.now(timezone.utc)
    if freeze < created:
        raise ValueError("freeze_utc cannot precede actual cohort creation")
    if not cutoff <= exposed <= freeze < end:
        raise ValueError("Forward freeze must follow all exposed data and precede review end")
    count = criteria["minimum_closed_positions"]
    stops = criteria["operational_stop_reasons"]
    if type(count) is not int or count <= 0:
        raise ValueError("minimum_closed_positions must be a positive integer")
    if (
        not isinstance(stops, list)
        or not stops
        or any(not isinstance(s, str) or not s.strip() for s in stops)
    ):
        raise ValueError("Explicit operational stopping reasons are required")
    definition = {
        "candidate_id": candidate,
        "criteria": criteria,
        "created_utc": created.isoformat(),
        "manifest": source_ref(manifest_path),
        "parity": source_ref(parity_path),
        "source_bindings": bindings,
        "policy": "FIXED_VERSION_NEW_COHORT_FOR_RETUNING",
    }
    digest = canonical_hash(definition)
    result = make_report(
        "forward_cohort",
        "FROZEN_DEFINITION_ONLY",
        candidate_id=candidate,
        cohort_id=digest[:24],
        sources=[source_ref(manifest_path), source_ref(parity_path), source_ref(criteria_path)],
        coverage={"prospective_observations": 0},
        reasons=["No forward observations, broker readiness or execution approval established"],
        definition=definition,
        definition_sha256=digest,
        profitability="INCONCLUSIVE",
    )
    result["created_utc"] = created.isoformat()
    write_json(Path(cohort_dir) / "cohort.json", result)
    return result


def _cohort_and_events(cohort_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cohort = read_json(cohort_dir / "cohort.json")
    if (
        cohort.get("schema_version") != 1
        or cohort.get("artifact_type") != "forward_cohort"
        or cohort.get("status") != "FROZEN_DEFINITION_ONLY"
        or cohort.get("execution_authorized") is not False
        or cohort.get("candidate_id") != cohort["data"]["definition"]["candidate_id"]
        or cohort.get("created_utc") != cohort["data"]["definition"]["created_utc"]
    ):
        raise ValueError("Frozen cohort envelope identity drift")
    digest = canonical_hash(cohort["data"]["definition"])
    if digest != cohort["data"]["definition_sha256"] or cohort["cohort_id"] != digest[:24]:
        raise ValueError("Frozen cohort definition drift")
    _validate_source_bindings(cohort["data"]["definition"]["source_bindings"])
    for name in ("manifest", "parity"):
        source = cohort["data"]["definition"][name]
        if sha256_file(Path(source["path"])) != source["sha256"]:
            raise ValueError(f"Frozen {name} source drift")
    log = cohort_dir / "observations.jsonl"
    raw = log.read_text() if log.exists() else ""
    if raw and not raw.endswith("\n"):
        raise ValueError("Incomplete observation tail; preserve evidence for investigation")
    events: list[dict[str, Any]] = []
    previous = digest
    for line in raw.splitlines():
        event = json.loads(line)
        if (
            event.get("candidate_id") != cohort["candidate_id"]
            or event.get("cohort_id") != cohort["cohort_id"]
            or event.get("evidence", {}).get("candidate_id") != cohort["candidate_id"]
            or event.get("evidence", {}).get("cohort_id") != cohort["cohort_id"]
        ):
            raise ValueError("Observation candidate/cohort identity drift")
        payload = {key: value for key, value in event.items() if key != "record_sha256"}
        if (
            event["previous_sha256"] != previous
            or event["sequence"] != len(events) + 1
            or canonical_hash(payload) != event["record_sha256"]
        ):
            raise ValueError("Observation chain drift")
        source = event["source"]
        if sha256_file(Path(source["path"])) != source["sha256"]:
            raise ValueError("Recorded evidence source drift")
        previous = event["record_sha256"]
        events.append(event)
    return cohort, events


def record_evidence(
    cohort_dir: Path,
    evidence_path: Path,
    *,
    kind: str,
    observed_utc: str,
) -> dict[str, Any]:
    """Append bound observations including losses; changing candidate is rejected."""
    if kind not in {"shadow", "broker_demo", "operational_stop", "review"}:
        raise ValueError("Unsupported observation kind")
    cohort_dir = Path(cohort_dir)
    # The lock serializes validation and append, including duplicate detection.
    with (cohort_dir / ".observations.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cohort, events = _cohort_and_events(cohort_dir)
        evidence = read_json(evidence_path)
        if (
            evidence.get("candidate_id") != cohort["candidate_id"]
            or evidence.get("cohort_id") != cohort["cohort_id"]
        ):
            raise ValueError("Evidence candidate/cohort mismatch; create a new cohort for retuning")
        if evidence.get("schema_version") != 1:
            raise ValueError("Unknown observation schema")
        if kind == "shadow" and any(
            key in evidence.get("data", {})
            for key in (
                "net_pnl",
                "net_profit",
                "trades",
                "fills",
                "fill_count",
                "closed_positions",
            )
        ):
            raise ValueError("Shadow decisions must not claim broker fills or PnL")
        criteria = cohort["data"]["definition"]["criteria"]
        if (
            kind == "operational_stop"
            and evidence.get("data", {}).get("reason") not in criteria["operational_stop_reasons"]
        ):
            raise ValueError("Operational stop reason was not declared before observation")
        start = parse_utc(evidence["coverage"]["from_utc"])
        end = parse_utc(evidence["coverage"]["until_utc"])
        observed = parse_utc(observed_utc)
        if observed > datetime.now(timezone.utc):
            raise ValueError("Future observations are not observed evidence")
        if not parse_utc(criteria["freeze_utc"]) <= start <= end <= observed:
            raise ValueError("Evidence is not prospective after cohort freeze")
        if end > parse_utc(criteria["review_end_utc"]):
            raise ValueError("Evidence extends beyond the agreed review window")
        if events and observed < parse_utc(events[-1]["observed_utc"]):
            raise ValueError("Observation timestamps must be chronological")
        source = source_ref(evidence_path)
        if source["hash_status"] != "VERIFIED":
            raise ValueError("Evidence snapshot too large for bounded provenance verification")
        if any(e["source"]["sha256"] == source["sha256"] for e in events):
            raise ValueError("Evidence already recorded")
        record = {
            "sequence": len(events) + 1,
            "previous_sha256": events[-1]["record_sha256"]
            if events
            else cohort["data"]["definition_sha256"],
            "candidate_id": cohort["candidate_id"],
            "cohort_id": cohort["cohort_id"],
            "kind": kind,
            "observed_utc": observed.isoformat(),
            "source": source,
            "evidence": evidence,
        }
        record["record_sha256"] = canonical_hash(record)
        with (cohort_dir / "observations.jsonl").open("a") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return record


def review_cohort(cohort_dir: Path) -> dict[str, Any]:
    """Read the versioned ledger; never convert observed snapshots to qualification."""
    cohort_dir = Path(cohort_dir)
    with (cohort_dir / ".observations.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        cohort, events = _cohort_and_events(cohort_dir)
    stopped = any(event["kind"] == "operational_stop" for event in events)
    return make_report(
        "forward_review",
        "OPERATIONALLY_STOPPED" if stopped else "OBSERVING",
        candidate_id=cohort["candidate_id"],
        cohort_id=cohort["cohort_id"],
        sources=[source_ref(cohort_dir / "cohort.json")],
        coverage={"observations": len(events), "by_kind": dict(Counter(e["kind"] for e in events))},
        reasons=[
            "Snapshots are evidence references, not independent trades or profitability qualification"
        ],
        observations=events,
        profitability="INCONCLUSIVE",
        sampled_equity_dd_is_tick_dd=False,
    )
