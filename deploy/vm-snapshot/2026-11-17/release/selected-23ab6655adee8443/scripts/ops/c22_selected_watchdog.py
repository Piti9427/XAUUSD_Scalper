"""Independent Selected26b8 health observer; never imports or mutates MT5.

Run from a separate systemd timer so a dead sender cannot silence its monitor.
The financial SQLite journal is opened read-only; incident state and a separate
delivery outbox belong to a distinct watchdog SQLite file. Remote delivery is
explicitly opt-in and reuses the existing bounded Telegram client.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from scripts.demo_runtime.delivery import HealthDelivery, TelegramDelivery

SNAPSHOT = "RESEARCH-C22-SELECTED-20261025-26B8"
SERVICE = "c22-selected-execution.service"
SERVICE_STATES = {"active", "activating", "inactive", "failed", "deactivating", "unknown"}
VALID_STATUSES = {
    "BLOCKED", "UNKNOWN", "REJECTED", "WAIT", "SHADOW_ADMIT", "SHADOW_BE",
    "FILLED", "MANAGING", "BE_MOVED", "CLOSED", "SAFETY_CLOSED",
}
ISSUE_CODES = {"service_" + state for state in SERVICE_STATES} | {
    "journal_unavailable", "snapshot_mismatch", "identity_unverified", "heartbeat_missing",
    "heartbeat_snapshot_mismatch", "execution_not_armed", "heartbeat_future_clock",
    "heartbeat_stale", "heartbeat_invalid", "heartbeat_status_invalid", "position_protection_critical",
    "safety_halt", "position_unreconciled", "entry_blocked", "active_manager_blocked",
    "exposure_unknown", "market_data_wait_session_unverified", "entry_review_blocked",
    "watchdog_state_invalid",
}


def utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("watchdog_clock_must_be_aware_utc")
    return stamp


def read_journal(path):
    """A read transaction binds heartbeat, exposure intent and halt together."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        values = dict(conn.execute(
            "SELECT key,value FROM kv WHERE key IN "
            "('last_result','active','safety_halt','identity','strategy_snapshot')"
        ))
        return {key: json.loads(value) for key, value in values.items()}


def service_state(service=SERVICE):
    if service != SERVICE:
        raise ValueError("watchdog_selected_service_required")
    try:
        result = subprocess.run(
            ["systemctl", "show", service, "--property=ActiveState", "--value"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    state = result.stdout.strip()
    return state if result.returncode == 0 and state in SERVICE_STATES else "unknown"


def evaluate(values, *, now, unit_state, expected_fingerprint, stale_seconds=180):
    """Return finite operational codes only, never financial or broker payloads."""
    now = utc(now)
    issues, urgent = [], False
    unit_state = unit_state if isinstance(unit_state, str) and unit_state in SERVICE_STATES else "unknown"
    if unit_state != "active":
        issues.append("service_" + unit_state)
        urgent = unit_state == "failed"
    if values is None:
        issues.append("journal_unavailable")
        return dict(issues=sorted(issues), urgent=urgent, service=unit_state)
    if values.get("strategy_snapshot") != SNAPSHOT:
        issues.append("snapshot_mismatch")
        urgent = True
    if values.get("identity") != expected_fingerprint:
        issues.append("identity_unverified")
    result = values.get("last_result")
    if not isinstance(result, dict):
        issues.append("heartbeat_missing")
        return dict(issues=sorted(issues), urgent=urgent, service=unit_state)
    if result.get("snapshot") != SNAPSHOT:
        issues.append("heartbeat_snapshot_mismatch")
        urgent = True
    if result.get("execute") is not True:
        issues.append("execution_not_armed")
        urgent = True
    try:
        age = (now - utc(result.get("captured_utc"))).total_seconds()
        if age < -5:
            issues.append("heartbeat_future_clock")
            urgent = True
        elif age > stale_seconds:
            issues.append("heartbeat_stale")
            urgent = True
    except (TypeError, ValueError):
        issues.append("heartbeat_invalid")
        urgent = True
    status = result.get("status")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        issues.append("heartbeat_status_invalid")
    if result.get("critical") is True:
        issues.append("position_protection_critical")
        urgent = True
    if values.get("safety_halt"):
        issues.append("safety_halt")
        urgent = True
    active = values.get("active") is not None
    if active and result.get("position_protection") != "confirmed":
        issues.append("position_unreconciled")
    expected_market_wait = (
        result.get("reason") == "quote_stale"
        and not active and result.get("observed_positions") == 0
        and not values.get("safety_halt") and result.get("critical") is False
    )
    # An old quote cannot attest a broker session closure. Keep that uncertainty
    # explicit, without weakening the sender's independent <=60s quote check.
    quote_age = result.get("quote_age_seconds")
    valid_age = (type(quote_age) in (int, float) and math.isfinite(quote_age)
                 and quote_age >= 0)
    if expected_market_wait and valid_age and quote_age > stale_seconds:
        issues.append("market_data_wait_session_unverified")
    if status in ("BLOCKED", "REJECTED") and not expected_market_wait:
        issues.append("entry_blocked" if not active else "active_manager_blocked")
    if status == "UNKNOWN" and not active:
        issues.append("exposure_unknown")
    review = result.get("execution_review")
    review = review if isinstance(review, dict) else {}
    if review.get("status") == "BLOCKED":
        issues.append("entry_review_blocked")
    advisories = []
    due = review.get("policy_due")
    if isinstance(due, str) and due in {"DUE_72H", "DUE_24H", "DUE_6H"}:
        advisories.append("cost_review_" + due.lower())
    try:
        expires = utc(review.get("policy_expires_utc")).isoformat()
    except (TypeError, ValueError):
        expires = None
    return dict(issues=sorted(set(issues)), urgent=urgent, service=unit_state,
                market_data_wait=expected_market_wait, advisories=advisories,
                policy_expires_utc=expires)


def _get(conn, key, default=None):
    row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def _put(conn, key, value):
    conn.execute(
        "INSERT INTO state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, sort_keys=True, allow_nan=False)),
    )


def _event(conn, kind, findings, now, unit_state):
    payload = dict(kind=kind, snapshot=SNAPSHOT, captured_utc=now.isoformat(),
                   findings=findings, service_state=unit_state)
    ident = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
    payload["event_id"] = ident
    conn.execute("INSERT OR IGNORE INTO outbox(id,payload) VALUES (?,?)",
                 (ident, json.dumps(payload, sort_keys=True)))


def _deliver(conn, notify, now):
    """At-least-once messages; stable event_id survives a lost acknowledgement."""
    if notify is None:
        return "disabled"
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT id,payload,attempts,retry_after FROM outbox WHERE delivered=0 ORDER BY rowid LIMIT 1"
    ).fetchone()
    if row is None:
        conn.commit()
        return "idle"
    ident, raw, attempts, retry_after = row
    if retry_after is not None and now < utc(retry_after):
        conn.commit()
        return "retry_deferred"
    try:
        notify(json.loads(raw))
    except Exception:
        delay = min(900, 30 * 2 ** min(attempts, 5))
        conn.execute("UPDATE outbox SET attempts=attempts+1,retry_after=? WHERE id=?",
                     ((now + timedelta(seconds=delay)).isoformat(), ident))
        conn.commit()
        return "pending_retry"
    conn.execute("UPDATE outbox SET delivered=1,attempts=attempts+1 WHERE id=?", (ident,))
    conn.commit()
    return "delivered"


def check_once(*, journal, state, now, expected_fingerprint, notify=None,
               health_notify=None, unit_reader=service_state, stale_seconds=180,
               problem_grace_seconds=180):
    now = utc(now)
    if not 60 <= stale_seconds <= 3600 or not 0 <= problem_grace_seconds <= 3600:
        raise ValueError("watchdog_bounded_stale_grace_required")
    journal, state = Path(journal), Path(state)
    if journal.resolve() == state.resolve() or (
        journal.exists() and state.exists() and journal.samefile(state)
    ):
        raise ValueError("watchdog_state_must_not_be_financial_journal")
    if not re.fullmatch(r"[0-9a-f]{16}", expected_fingerprint):
        raise ValueError("watchdog_account_fingerprint_required")
    try:
        values = read_journal(journal)
    except (OSError, sqlite3.Error, json.JSONDecodeError, TypeError):
        values = None
    observed = evaluate(values, now=now, unit_state=unit_reader(),
                        expected_fingerprint=expected_fingerprint, stale_seconds=stale_seconds)
    state.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(state, timeout=2, isolation_level=None)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and tables != {"state", "outbox"}:
            raise ValueError("watchdog_state_database_required")
        conn.executescript("""
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(
                id TEXT PRIMARY KEY,payload TEXT NOT NULL,delivered INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,retry_after TEXT
            );
        """)
        conn.execute("BEGIN IMMEDIATE")
        binding = dict(snapshot=SNAPSHOT, fingerprint=expected_fingerprint,
                       journal=str(journal.resolve()))
        prior_binding = _get(conn, "binding")
        if prior_binding not in (None, binding):
            raise ValueError("watchdog_state_binding_mismatch")
        _put(conn, "binding", binding)
        prior = _get(conn, "incident", {})
        issues = list(observed["issues"])
        state_invalid = False

        def observed_time(value):
            nonlocal state_invalid
            try:
                stamp = utc(value)
                if stamp <= now:
                    return stamp.isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
            state_invalid = True
            return now.isoformat()

        if not isinstance(prior, dict):
            prior = {}
            state_invalid = True
        if prior:
            prior["first_seen_utc"] = observed_time(prior.get("first_seen_utc"))
            prior_issues = prior.get("issues")
            if (not isinstance(prior_issues, list) or not prior_issues
                    or any(not isinstance(x, str) or x not in ISSUE_CODES for x in prior_issues)):
                state_invalid = True
            prior["issues"] = [x for x in prior_issues if isinstance(x, str) and x in ISSUE_CODES
                               ] if isinstance(prior_issues, list) else []
            if type(prior.get("announced")) is not bool:
                state_invalid = True
                prior["announced"] = False
            if prior.get("healthy_since_utc") is not None:
                prior["healthy_since_utc"] = observed_time(prior["healthy_since_utc"])
                if utc(prior["healthy_since_utc"]) < utc(prior["first_seen_utc"]):
                    state_invalid = True
                    prior["healthy_since_utc"] = now.isoformat()
        wait_since = _get(conn, "market_wait_since_utc")
        if wait_since is not None:
            wait_since = observed_time(wait_since)
        if observed.get("market_data_wait"):
            wait_since = wait_since or now.isoformat()
            wait_elapsed = (now - utc(wait_since)).total_seconds()
            if wait_elapsed >= problem_grace_seconds:
                issues = sorted(set(issues + ["market_data_wait_session_unverified"]))
        else:
            wait_since = None
        _put(conn, "market_wait_since_utc", wait_since)
        if state_invalid:
            issues = sorted(set(issues + ["watchdog_state_invalid"]))
            observed["urgent"] = True
        recovering = False
        if not issues:
            incident = prior
            if prior:
                healthy_since = prior.get("healthy_since_utc") or now.isoformat()
                incident["healthy_since_utc"] = healthy_since
                stable_for = (now - utc(healthy_since)).total_seconds()
                if stable_for >= problem_grace_seconds:
                    if prior.get("announced"):
                        _event(conn, "C22_WATCHDOG_RECOVERED", [], now, observed["service"])
                    incident = {}
                else:
                    recovering = True
        else:
            # A brief good sample or rotating blockers do not erase an incident.
            incident = prior or dict(issues=[], first_seen_utc=(wait_since or now.isoformat()),
                                     announced=False)
            incident["issues"] = sorted(set(incident["issues"] + issues))
            incident.pop("healthy_since_utc", None)
            elapsed = (now - utc(incident["first_seen_utc"])).total_seconds()
            if not incident["announced"] and (observed["urgent"] or elapsed >= problem_grace_seconds):
                _event(conn, "C22_WATCHDOG_ALERT", issues, now, observed["service"])
                incident["announced"] = True
        _put(conn, "incident", incident)
        conn.commit()
        delivery = _deliver(conn, notify, now)
        pending = conn.execute("SELECT count(*) FROM outbox WHERE delivered=0").fetchone()[0]
    status = ("DEGRADED" if issues else "RECOVERING" if recovering
              else "WAITING_MARKET_DATA" if observed.get("market_data_wait") else "HEALTHY")
    result = dict(status=status, captured_utc=now.isoformat(),
                  critical=bool(incident.get("announced")),
                  findings=issues, delivery=delivery, pending_notifications=pending,
                  incident_findings=incident.get("issues", []),
                  incident_since_utc=incident.get("first_seen_utc"),
                  recovery_since_utc=incident.get("healthy_since_utc"),
                  stable_recovery_seconds=problem_grace_seconds,
                  market_session="UNVERIFIED" if observed.get("market_data_wait") else "NOT_EVALUATED",
                  delivery_status="DELIVERY_DISABLED" if notify is None else "CONFIGURED",
                  advisories=observed.get("advisories", []),
                  policy_expires_utc=observed.get("policy_expires_utc"))
    protection = (values or {}).get("last_result", {})
    protection = protection.get("position_protection") if isinstance(protection, dict) else None
    result["position_protection"] = (protection if isinstance(protection, str)
        and protection in {"flat", "confirmed", "unknown"} else "unknown")
    result["health_delivery"] = "disabled"
    if health_notify is not None:
        try:
            health_notify(dict(result=result))
            result["health_delivery"] = "delivered"
        except Exception:
            # Health endpoint consumes current state next timer, never stale backlog.
            result["health_delivery"] = "pending_retry"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--service", choices=(SERVICE,), default=SERVICE)
    parser.add_argument("--stale-seconds", type=int, default=180)
    parser.add_argument("--problem-grace-seconds", type=int, default=180)
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args(argv)
    if not 60 <= args.stale_seconds <= 3600 or not 0 <= args.problem_grace_seconds <= 3600:
        parser.error("bounded stale/grace seconds required")
    notify = health_notify = None
    if args.notify:
        token, chat = os.environ.get("DEMO_TELEGRAM_TOKEN"), os.environ.get("DEMO_TELEGRAM_CHAT_ID")
        health_url = os.environ.get("DEMO_HEALTHCHECK_URL")
        if bool(token) != bool(chat) or not ((token and chat) or health_url):
            print(json.dumps(dict(status="BLOCKED", reason="watchdog_notification_config_required")))
            return 2
        if token and chat:
            notify = TelegramDelivery(token, chat)
        if health_url:
            health_notify = HealthDelivery(health_url)
    try:
        result = check_once(journal=args.journal, state=args.state,
                            now=datetime.now(timezone.utc), expected_fingerprint=args.expected_fingerprint,
                            unit_reader=lambda: service_state(args.service), notify=notify,
                            health_notify=health_notify,
                            stale_seconds=args.stale_seconds, problem_grace_seconds=args.problem_grace_seconds)
    except (OSError, ValueError, sqlite3.Error):
        print(json.dumps(dict(status="BLOCKED", reason="watchdog_observation_failed")))
        return 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
