"""Read-only, consistent financial snapshot and independent row continuity.

The existing financial journal schema is consumed, never migrated. Protected
value transitions not independently attributable remain unverified (#23).
"""

from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from .model import NotificationMode, canonical, utc


PROTECTED = (
    "identity",
    "strategy_snapshot",
    "day",
    "utc_boundary_mark",
    "selected_last_loss_ms",
    "safety_halt",
)
KINDS = {"FILLED", "BE_MOVED", "CLOSED", "SAFETY_CLOSED", "CRITICAL"}
EVENT_SCHEMA = [
    (0, "id", "INTEGER", 0, None, 1),
    (1, "payload", "TEXT", 1, None, 0),
    (2, "sent", "INTEGER", 1, "0", 0),
]


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("invalid_journal_json")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("invalid_journal_json")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def read_journal(path, *, original_highwater=None):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        schema = db.execute("PRAGMA table_info(events)").fetchall()
        if schema != EVENT_SCHEMA:
            raise ValueError("unknown_outbox_schema")
        kv = dict(db.execute("SELECT key,value FROM kv"))
        values = {k: parse(v) for k, v in kv.items()}
        canonical(values)
        rows = db.execute("SELECT id,payload,sent FROM events ORDER BY id").fetchall()
        lineage = {}
        prefix = hashlib.sha256(b"C22_MAINTENANCE_AUDIT_V1\0")
        saved_prefix = prefix.hexdigest() if original_highwater == 0 else None
        highwater = 0
        for ident, raw in db.execute("SELECT id,payload FROM audit_events ORDER BY id"):
            if ident != highwater + 1 or not isinstance(raw, str):
                raise ValueError("audit_prefix_gap")
            data = raw.encode("utf-8")
            prefix.update(ident.to_bytes(8, "big") + len(data).to_bytes(8, "big") + data)
            highwater = ident
            if ident == original_highwater:
                saved_prefix = prefix.hexdigest()
            item = parse(raw)
            if item.get("kind") in ("LIFECYCLE", "ALERT") and isinstance(item.get("event"), dict):
                event = item["event"]
                event_id = event.get("event_id")
                if event_id in lineage:
                    raise ValueError("duplicate_event_lineage")
                lineage[event_id] = event
        return {
            "schema": schema,
            "rows": rows,
            "protected": {k: (k in kv, kv.get(k)) for k in PROTECTED},
            "values": values,
            "highwater": highwater,
            "audit_sha256": prefix.hexdigest(),
            "original_prefix": saved_prefix,
            "lineage": lineage,
        }


def classify(snapshot, plan, observation):
    if (
        snapshot["values"].get("identity") != plan.cohort.account
        or snapshot["values"].get("strategy_snapshot") != plan.cohort.snapshot
    ):
        raise ValueError("journal_account_or_strategy_drift")
    if plan.mode is NotificationMode.OFF_NOTIFICATION_HANDOFF and (
        not observation.delivery_off or observation.delivery_inflight
    ):
        raise ValueError("notification_delivery_uncertain")
    reviewed = {(i, h) for i, h, _ in plan.reviewed_critical}
    seen = set()
    for ident, raw, sent in snapshot["rows"]:
        if (
            type(ident) is not int
            or ident <= 0
            or type(sent) is not int
            or sent not in (0, 1)
            or not isinstance(raw, str)
        ):
            raise ValueError("invalid_outbox_row")
        event = parse(raw)
        if (
            not isinstance(event, dict)
            or event.get("kind") not in KINDS
            or type(event.get("schema_version", 1)) is not int
            or event.get("schema_version", 1) != 1
        ):
            raise ValueError("unknown_notification_kind_or_schema")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in seen:
            raise ValueError("notification_identity_invalid")
        seen.add(event_id)
        expected = {
            "account_fingerprint": plan.cohort.account,
            "release_hash": plan.cohort.source,
            "config_hash": plan.cohort.config,
        }
        if any(event.get(k) != v for k, v in expected.items()):
            raise ValueError("notification_cohort_drift")
        if snapshot["lineage"].get(event_id) != event:
            raise ValueError("notification_lineage_unverified")
        if sent == 0:
            if plan.mode is NotificationMode.STRICT_ZERO:
                raise ValueError("sender_outbox_defer")
            if event["kind"] == "CRITICAL" and (
                (ident, hashlib.sha256(raw.encode()).hexdigest()) not in reviewed
                or ident in observation.unresolved_critical
            ):
                raise ValueError("critical_review_required")


def require_flat(snapshot, now, freshness, *, after=None):
    values = snapshot["values"]
    if values.get("active") is not None or values.get("safety_halt"):
        raise ValueError("owned_unknown_halt_defer")
    last = values.get("last_result") or {}
    if (
        last.get("execute") is not True
        or type(last.get("observed_positions")) is not int
        or last["observed_positions"] != 0
        or last.get("position_protection") != "flat"
    ):
        raise ValueError("flat_cycle_missing")
    stamp = datetime.fromisoformat(last["captured_utc"])
    utc(stamp)
    age = (now - stamp).total_seconds()
    if not 0 <= age < freshness:
        raise ValueError("cycle_not_fresh")
    if after is not None and stamp <= datetime.fromisoformat(after):
        raise ValueError("post_hold_cycle_required")


def continuity(original, current, *, allow_append=False):
    if canonical(original["schema"]) != canonical(current["schema"]):
        raise ValueError("outbox_schema_changed")
    if current["original_prefix"] != original["audit_sha256"]:
        raise ValueError("audit_prefix_changed")
    if canonical(current["protected"]) != canonical(original["protected"]):
        raise ValueError("protected_values_continuity_unverified")
    before = {row[0]: canonical(row) for row in original["rows"]}
    after = {row[0]: canonical(row) for row in current["rows"]}
    if any(after.get(key) != raw for key, raw in before.items()):
        raise ValueError("outbox_row_changed")
    if not allow_append and after != before:
        raise ValueError("approved_outbox_set_changed")
    if allow_append and any(k <= max(before, default=0) for k in after.keys() - before.keys()):
        raise ValueError("outbox_identity_reused")
