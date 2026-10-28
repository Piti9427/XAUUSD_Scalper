"""Explicit incident-reviewed unhalt for a broker-proved CLOSED outcome.

No SDK, orders, service control, automatic halt clearing or baseline changes.
Planning is read-only. Applying acquires both existing local writer guards and
requires an independently pinned owner review plus a fresh unchanged proof.
"""

from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3

from scripts.demo_runtime.journal import Journal

SNAPSHOT = "RESEARCH-C22-SELECTED-20261025-26B8"
MAGIC = 22261025
UNKNOWN_HALTS = {
    "position_identity_unresolved",
    "ambiguous_position_identity",
    "position_ledger_unresolved",
}


def _raw(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("resolution_aware_utc_required")
    return value


def _fail(condition, code):
    if not condition:
        raise ValueError(code)


def _snapshot(connection):
    connection.execute("BEGIN")
    values = {key: json.loads(raw) for key, raw in connection.execute("select key,value from kv")}
    events = [
        (ident, raw, json.loads(raw))
        for ident, raw in connection.execute("select id,payload from audit_events order by id")
    ]
    pending = connection.execute("select count(*) from events where sent=0").fetchone()[0]
    connection.rollback()
    return values, events, pending


def _plan(snapshot, broker_bytes, now):
    now = _utc(now)
    values, events, pending = snapshot
    _fail(
        values.get("strategy_snapshot") == SNAPSHOT and values.get("identity"),
        "resolution_selected_identity_required",
    )
    _fail(values.get("active") is None, "resolution_reconciliation_pending")
    halt = values.get("safety_halt")
    _fail(isinstance(halt, str) and bool(halt), "resolution_no_latched_incident")
    _fail(halt in UNKNOWN_HALTS, "resolution_halt_outside_unknown_scope")
    incidents = [
        row
        for row in events
        if row[2].get("kind") == "STATE" and row[2].get("observed", {}).get("safety_halt") == halt
    ]
    _fail(bool(incidents), "resolution_incident_provenance_missing")
    incident = incidents[-1]
    closed = [
        row
        for row in events
        if row[0] > incident[0]
        and row[2].get("kind") == "LIFECYCLE"
        and row[2].get("event", {}).get("kind") in ("CLOSED", "SAFETY_CLOSED")
        and row[2].get("observed", {}) == {"active": None}
    ]
    _fail(bool(closed), "resolution_proved_close_missing")
    closure = closed[-1]
    event = closure[2]["event"]
    active = closure[2].get("active") or {}
    ident = event.get("position_id")
    _fail(
        type(ident) is int and ident > 0 and active.get("position_id") == ident,
        "resolution_position_binding_missing",
    )
    _fail(active.get("request", {}).get("magic") == MAGIC, "resolution_request_binding_invalid")
    contexts = [
        row[2]
        for row in events
        if row[2].get("account_fingerprint") == values["identity"]
        and row[2].get("release_hash")
        and row[2].get("config_hash")
    ]
    _fail(bool(contexts), "resolution_source_binding_missing")
    context = contexts[-1]
    packet = json.loads(broker_bytes)
    captured = _utc(packet["captured_utc"])
    observed = _utc(packet["read_observed_utc"])
    end = _utc(packet["history_end_utc"])
    _fail(
        timedelta(0) <= now - captured <= timedelta(minutes=5)
        and captured <= observed <= now
        and captured <= end <= observed,
        "resolution_broker_proof_stale",
    )
    _fail(
        packet.get("source") == "existing_sender_reads"
        and packet.get("execution_authorized") is False
        and packet.get("order_send_called") is False
        and packet.get("demo_verified") is True
        and packet.get("hedging_verified") is True
        and packet.get("symbol") == "XAUUSDm"
        and packet.get("terminal", {}).get("connected") is True
        and packet.get("account", {}).get("currency") == "USD"
        and packet.get("account_fingerprint") == values["identity"]
        and packet.get("release_hash") == context["release_hash"]
        and packet.get("config_hash") == context["config_hash"],
        "resolution_broker_identity_mismatch",
    )
    _fail(
        type(packet.get("positions")) is int
        and packet["positions"] == 0
        and type(packet.get("orders")) is int
        and packet["orders"] == 0,
        "resolution_foreign_or_unknown_exposure",
    )
    deals = packet.get("history_deals")
    _fail(
        packet.get("history_complete") is True
        and isinstance(deals, list)
        and type(packet.get("history_deals_total")) is int
        and len(deals) == packet["history_deals_total"]
        and _utc(packet["history_start_utc"]) == datetime(1970, 1, 1, tzinfo=timezone.utc),
        "resolution_complete_history_required",
    )
    tickets = set()
    amounts = []
    volume = {}
    for deal in deals:
        _fail(
            type(deal.get("ticket")) is int
            and deal["ticket"] > 0
            and deal["ticket"] not in tickets
            and type(deal.get("type")) is int
            and deal["type"] >= 0
            and type(deal.get("time_msc")) is int
            and 0 <= deal["time_msc"] <= end.timestamp() * 1000,
            "resolution_history_invalid",
        )
        tickets.add(deal["ticket"])
        cash = [deal.get(key) for key in ("profit", "commission", "swap", "fee")]
        _fail(
            all(type(x) in (int, float) and math.isfinite(x) for x in cash),
            "resolution_cash_unknown",
        )
        amounts.extend(cash)
        if deal["type"] in (0, 1):
            _fail(
                type(deal.get("volume")) in (int, float)
                and math.isfinite(deal["volume"])
                and deal["volume"] > 0
                and deal.get("entry") in (0, 1, 3),
                "resolution_volume_unknown",
            )
            position = deal.get("position_id")
            _fail(type(position) is int and position > 0, "resolution_position_unknown")
            volume[position] = volume.get(position, 0) + deal["volume"] * (
                1 if deal["type"] == 0 else -1
            )
    account = packet["account"]
    balance = account.get("balance")
    equity = account.get("equity")
    _fail(
        all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in (balance, equity))
        and abs(math.fsum(amounts) - balance) <= 0.02
        and abs(balance - equity) <= 0.02
        and all(abs(x) < 1e-8 for x in volume.values()),
        "resolution_cash_or_volume_unreconciled",
    )
    ledger = [d for d in deals if d["type"] in (0, 1) and d.get("position_id") == ident]
    openings = [
        d
        for d in ledger
        if d["entry"] == 0
        and d.get("magic") == MAGIC
        and d["time_msc"] >= active.get("entry_ms", float("inf"))
    ]
    exits = [d for d in ledger if d["entry"] in (1, 3)]
    _fail(
        bool(openings)
        and bool(exits)
        and len(openings) == sum(d["entry"] == 0 for d in ledger)
        and math.isclose(math.fsum(d["volume"] for d in openings), 0.01, abs_tol=1e-8, rel_tol=0),
        "resolution_owned_opening_or_exit_missing",
    )
    components = {
        key: math.fsum(d[key] for d in ledger) for key in ("profit", "commission", "swap", "fee")
    }
    _fail(
        all(
            type(event.get(key)) in (int, float)
            and math.isclose(event[key], value, abs_tol=1e-7, rel_tol=0)
            for key, value in components.items()
        )
        and math.isclose(
            event.get("net", float("inf")), math.fsum(components.values()), abs_tol=1e-7, rel_tol=0
        ),
        "resolution_closed_cash_mismatch",
    )
    financial = {
        key: value
        for key, value in values.items()
        if key not in ("last_result", "last_health_event", "last_alert_block")
    }
    scope = dict(
        schema=1,
        incident_id=f"{incident[0]}:{_sha(incident[1].encode())}",
        halt=halt,
        closure_audit_id=closure[0],
        closure_sha256=_sha(closure[1].encode()),
        position_id=ident,
        account_fingerprint=values["identity"],
        release_hash=context["release_hash"],
        config_hash=context["config_hash"],
        financial_sha256=_sha(_raw(financial)),
        history_sha256=_sha(_raw(deals)),
        balance=balance,
        resolver_sha256=_sha(Path(__file__).read_bytes()),
        outcome="PROVED_CLOSED",
    )
    return dict(
        schema=1,
        status="REVIEW_REQUIRED",
        scope=scope,
        scope_sha256=_sha(_raw(scope)),
        incident_id=scope["incident_id"],
        position_id=ident,
        broker_packet_sha256=_sha(broker_bytes),
        broker_captured_utc=captured.isoformat(),
        planned_utc=now.isoformat(),
        pending_notification_events=pending,
        execution_authorized=False,
    )


def plan_resolution(journal, broker_bytes, *, now):
    path = Path(journal).resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as connection:
        connection.execute("PRAGMA query_only=ON")
        return _plan(_snapshot(connection), broker_bytes, now)


def apply_resolution(journal, plan, broker_bytes, *, review_bytes, trusted_review_sha256, now):
    now = _utc(now)
    _fail(
        isinstance(review_bytes, bytes) and _sha(review_bytes) == trusted_review_sha256,
        "resolution_pinned_owner_review_required",
    )
    review = json.loads(review_bytes)
    _fail(
        plan.get("scope_sha256") == _sha(_raw(plan["scope"]))
        and plan.get("incident_id") == plan["scope"]["incident_id"]
        and plan.get("position_id") == plan["scope"]["position_id"]
        and plan.get("execution_authorized") is False,
        "resolution_plan_tampered",
    )
    approved = _utc(review["approved_utc"])
    expires = _utc(review["expires_utc"])
    _fail(
        review.get("schema") == 1
        and review.get("decision") == "RESOLVE_PROVED_CLOSED"
        and review.get("scope_sha256") == plan["scope_sha256"]
        and approved <= now <= expires
        and timedelta(0) < expires - approved <= timedelta(minutes=15)
        and isinstance(review.get("owner_decision_ref"), str)
        and bool(review["owner_decision_ref"]),
        "resolution_owner_review_invalid",
    )
    path = Path(journal).resolve()
    fingerprint = plan["scope"]["account_fingerprint"]
    guard_path = path.parent / f"demo-account-{fingerprint}.sqlite3"
    _fail(
        guard_path.is_file() and Path(str(guard_path) + ".lock").is_file(),
        "resolution_existing_account_guard_required",
    )
    account_guard = Journal(guard_path)
    try:
        store = Journal(path)
        try:
            fresh = _plan(_snapshot(store.conn), broker_bytes, now)
            _fail(
                fresh["scope_sha256"] == plan["scope_sha256"],
                "resolution_incident_or_financial_state_changed",
            )
            _fail(
                now - _utc(fresh["broker_captured_utc"]) <= timedelta(seconds=5),
                "resolution_final_flat_proof_stale",
            )
            store.audit_context = {
                key: plan["scope"][key]
                for key in ("account_fingerprint", "release_hash", "config_hash")
            }
            with store.conn:
                store._audit(
                    "OPERATOR_UNKNOWN_RESOLUTION",
                    incident_id=plan["incident_id"],
                    position_id=plan["position_id"],
                    scope_sha256=plan["scope_sha256"],
                    broker_packet_sha256=fresh["broker_packet_sha256"],
                    review_sha256=trusted_review_sha256,
                    approved_utc=review["approved_utc"],
                    owner_decision_ref=review["owner_decision_ref"],
                    expected={"safety_halt": plan["scope"]["halt"]},
                    observed={"safety_halt": None},
                    outcome="PROVED_CLOSED",
                    resolved_utc=now.isoformat(),
                )
                store.conn.execute("UPDATE kv SET value='null' WHERE key='safety_halt'")
            return dict(
                status="RESOLVED_PROVED_CLOSED",
                incident_id=plan["incident_id"],
                position_id=plan["position_id"],
                new_entry_authorized=False,
                next_step="fresh_runner_signal_and_all_original_admission_gates",
            )
        finally:
            store.close()
    finally:
        account_guard.close()


def main(argv=None, *, now=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--broker", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--review-sha256")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc) if now is None else _utc(now)
    _fail(not args.out.exists(), "resolution_output_must_be_new")
    # Reserve a new private receipt before any financial mutation. A final IO
    # failure cannot roll back an already committed journal; that append-only
    # resolution event remains authoritative across retries/restart.
    descriptor = os.open(args.out, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        try:
            if args.plan:
                _fail(
                    args.review is not None and args.review_sha256,
                    "resolution_owner_review_required",
                )
                result = apply_resolution(
                    args.journal,
                    json.loads(args.plan.read_bytes()),
                    args.broker.read_bytes(),
                    review_bytes=args.review.read_bytes(),
                    trusted_review_sha256=args.review_sha256,
                    now=now,
                )
            else:
                _fail(
                    args.review is None and args.review_sha256 is None,
                    "resolution_plan_has_no_approval",
                )
                result = plan_resolution(args.journal, args.broker.read_bytes(), now=now)
            handle.write(_raw(result) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        except Exception as error:
            handle.write(
                _raw(
                    dict(
                        status="FAILED_CHECK_JOURNAL_FOR_COMMITTED_RESOLUTION",
                        error_type=type(error).__name__,
                        execution_authorized=False,
                    )
                )
                + b"\n"
            )
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
