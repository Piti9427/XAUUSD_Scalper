"""Closed, local maintenance contract. No executable commands or callbacks."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
import math
import re


class NotificationMode(str, Enum):
    STRICT_ZERO = "STRICT_ZERO"
    OFF_NOTIFICATION_HANDOFF = "OFF_NOTIFICATION_HANDOFF"


@dataclass(frozen=True)
class Cohort:
    account: str
    source: str
    config: str
    unit: str
    policy: str
    review: str
    snapshot: str


@dataclass(frozen=True)
class APMeasurement:
    probe_sha256: str


@dataclass(frozen=True)
class Reboot:
    """Exactly one dispatch attempt; changed boot is independent evidence."""


@dataclass(frozen=True)
class CostInstallation:
    generation: str
    policy: str
    review: str


@dataclass(frozen=True)
class Plan:
    operation: str
    cohort: Cohort
    backup_sha256: str
    action: APMeasurement | Reboot | CostInstallation
    mode: NotificationMode = NotificationMode.STRICT_ZERO
    pause_seconds: int = 900
    action_seconds: int = 180
    recovery_seconds: int = 60
    freshness_seconds: int = 20
    # Exact row id, original payload SHA256 and private owner review reference.
    reviewed_critical: tuple[tuple[int, str, str], ...] = ()


@dataclass(frozen=True)
class Handle:
    operation: str
    digest: str


@dataclass(frozen=True)
class Approval:
    plan_digest: str
    owner_ref: str
    approved_utc: datetime
    allow_manager_recovery: bool = False
    allow_probe_cleanup: bool = False
    valid_until: datetime | None = None


@dataclass(frozen=True)
class OwnedProbe:
    operation: str
    boot: str
    pid: int
    started: str
    source: str


@dataclass(frozen=True)
class Observation:
    captured_utc: datetime
    monotonic: float
    boot: str
    cohort: Cohort
    backup_sha256: str
    backup_restore_verified: bool
    sender_running: bool = True
    sender_count: int = 1
    review_held: bool = False
    review_restore_safe: bool = True
    post_hold_cycle: bool = False
    readers: tuple[str, ...] = ()
    # Identity must be operation/boot/pid/start, proven by the host adapter.
    owned_probe: OwnedProbe | None = None
    delivery_off: bool = True
    delivery_inflight: bool = False
    unresolved_critical: tuple[int, ...] = ()
    cost_marker: str | None = "original"
    startup_verified: bool = False
    recovered_cycle: bool = False
    outside_pause_seconds: float | None = None


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("aware_utc_required")
    return value.isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate(plan):
    if type(plan) is not Plan or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", plan.operation):
        raise ValueError("invalid_plan_identity")
    if type(plan.action) not in (APMeasurement, Reboot, CostInstallation):
        raise ValueError("unsupported_action")
    if type(plan.cohort) is not Cohort or type(plan.mode) is not NotificationMode:
        raise ValueError("invalid_plan_contract")
    # DemoRunner/BrokerView persist the established 16-character fingerprint.
    # It is an identity token, not a full source/artifact SHA256.
    if not isinstance(plan.cohort.account, str) or not re.fullmatch(
        r"[a-f0-9]{16}", plan.cohort.account
    ):
        raise ValueError("invalid_account_fingerprint")
    hashes = [v for k, v in asdict(plan.cohort).items() if k not in ("snapshot", "account")] + [
        plan.backup_sha256
    ]
    if not isinstance(plan.cohort.snapshot, str) or not plan.cohort.snapshot:
        raise ValueError("invalid_strategy_snapshot")
    if type(plan.action) is APMeasurement:
        hashes.append(plan.action.probe_sha256)
    if type(plan.action) is CostInstallation:
        hashes.extend((plan.action.policy, plan.action.review))
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", plan.action.generation)
            or plan.action.generation == "original"
        ):
            raise ValueError("invalid_generation")
    if any(not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h) for h in hashes):
        raise ValueError("invalid_source_binding")
    times = (plan.pause_seconds, plan.action_seconds, plan.recovery_seconds, plan.freshness_seconds)
    if any(type(t) is not int or t <= 0 for t in times) or plan.pause_seconds > 900:
        raise ValueError("invalid_budget")
    if plan.action_seconds + plan.recovery_seconds > plan.pause_seconds:
        raise ValueError("insufficient_recovery_reserve")
    for ident, payload_hash, reference in plan.reviewed_critical:
        if (
            type(ident) is not int
            or ident <= 0
            or not re.fullmatch(r"[a-f0-9]{64}", payload_hash)
            or not reference
        ):
            raise ValueError("invalid_critical_review")


def plan_document(plan):
    validate(plan)
    result = asdict(plan)
    result["family"] = type(plan.action).__name__
    return result


def read_plan(document):
    value = dict(document)
    family = value.pop("family")
    types = {t.__name__: t for t in (APMeasurement, Reboot, CostInstallation)}
    value["action"] = types[family](**value["action"])
    value["cohort"] = Cohort(**value["cohort"])
    value["mode"] = NotificationMode(value["mode"])
    value["reviewed_critical"] = tuple(tuple(row) for row in value["reviewed_critical"])
    result = Plan(**value)
    validate(result)
    return result


def validate_observation(value):
    if type(value) is not Observation:
        raise ValueError("invalid_host_observation")
    flags = (
        "backup_restore_verified",
        "sender_running",
        "review_held",
        "review_restore_safe",
        "post_hold_cycle",
        "delivery_off",
        "delivery_inflight",
        "startup_verified",
        "recovered_cycle",
    )
    if any(type(getattr(value, key)) is not bool for key in flags):
        raise ValueError("invalid_host_observation")
    if (
        type(value.cohort) is not Cohort
        or type(value.readers) is not tuple
        or any(not isinstance(reader, str) or not reader for reader in value.readers)
    ):
        raise ValueError("invalid_host_observation")
    if value.owned_probe is not None and type(value.owned_probe) is not OwnedProbe:
        raise ValueError("invalid_host_observation")
    if type(value.unresolved_critical) is not tuple or any(
        type(ident) is not int or ident <= 0 for ident in value.unresolved_critical
    ):
        raise ValueError("invalid_host_observation")
    utc(value.captured_utc)
    if (
        not isinstance(value.boot, str)
        or not value.boot
        or type(value.monotonic) not in (int, float)
        or not math.isfinite(value.monotonic)
        or value.monotonic < 0
    ):
        raise ValueError("invalid_clock_observation")
    if value.outside_pause_seconds is not None and (
        type(value.outside_pause_seconds) not in (int, float)
        or not math.isfinite(value.outside_pause_seconds)
        or value.outside_pause_seconds < 0
    ):
        raise ValueError("invalid_outside_clock")
