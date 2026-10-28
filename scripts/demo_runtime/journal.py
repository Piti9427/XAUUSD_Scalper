"""Durable claims/outbox and single local writer for trial30 Demo."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import uuid
import json
from pathlib import Path
import sqlite3


def audit_value(value):
    """Lossless labels for invalid broker numerics; strict JSON remains readable."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"invalid_number": repr(value)}
    if isinstance(value, dict):
        return {str(k): audit_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [audit_value(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_asdict"):
        return audit_value(value._asdict())
    if hasattr(value, "__dict__"):
        return audit_value(vars(value))
    return repr(value)


class Journal:
    def __init__(self, path: Path):
        if str(path) == ":memory:":
            raise ValueError("persistent journal required")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.guard = sqlite3.connect(str(path) + ".lock", timeout=0, isolation_level=None)
        self.guard.execute("CREATE TABLE IF NOT EXISTS writer (id INTEGER PRIMARY KEY)")
        try:
            self.guard.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            self.guard.close()
            raise ValueError("another trial30 writer owns journal") from None
        self.audit_context = {}
        self.conn = sqlite3.connect(path)
        self.conn.executescript("""
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries (consumer TEXT NOT NULL, event_id INTEGER NOT NULL, PRIMARY KEY(consumer,event_id));
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'append_only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'append_only'); END;
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
        """)
        self.conn.commit()

    def get(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value):
        raw = json.dumps(value, sort_keys=True, allow_nan=False)
        prior = self.get(key)
        if prior == value:
            return
        with self.conn:
            if key in ("active", "day", "utc_boundary_mark", "safety_halt", "last_bar", "identity", "strategy_snapshot"):
                self._audit("STATE", expected={key: prior}, observed={key: value})
            self.conn.execute(
                "INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, raw),
            )

    def transition(self, key: str, value, event: dict):
        """Commit reconciled state and notification atomically."""
        event = dict(self.audit_context, event_id=uuid.uuid4().hex, **event)
        with self.conn:
            self._audit(
                "LIFECYCLE",
                expected={key: self.get(key)},
                observed={key: value},
                event=event,
                active=value if value is not None else self.get(key),
            )
            self.conn.execute(
                "INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, sort_keys=True, allow_nan=False)),
            )
            self.conn.execute(
                "INSERT INTO events(payload) VALUES (?)", (json.dumps(event, allow_nan=False),)
            )

    def event(self, payload: dict):
        payload = dict(self.audit_context, event_id=uuid.uuid4().hex, **payload)
        with self.conn:
            self._audit("ALERT", event=payload)
            self.conn.execute(
                "INSERT INTO events(payload) VALUES (?)", (json.dumps(payload, allow_nan=False),)
            )

    def _audit(self, kind, **facts):
        payload = audit_value(
            dict(
                self.audit_context,
                kind=kind,
                event_id=uuid.uuid4().hex,
                utc=datetime.now(timezone.utc).isoformat(),
                **facts,
            )
        )
        raw = json.dumps(payload, sort_keys=True, allow_nan=False)
        self.conn.execute("INSERT INTO audit_events(payload) VALUES (?)", (raw,))
        return payload

    def audit(self, kind, **facts):
        with self.conn:
            return self._audit(kind, **facts)

    def consume(self, consumer, callback, *, kinds=None, limit=10, latest=False):
        """At-least-once delivery; consumers deduplicate using stable event_id."""
        condition = ""
        args = [consumer]
        if kinds:
            condition = (
                " AND json_extract(payload, '$.kind') IN (" + ",".join("?" for _ in kinds) + ")"
            )
            args.extend(kinds)
        rows = self.conn.execute(
            "SELECT id,payload FROM audit_events WHERE id NOT IN "
            "(SELECT event_id FROM deliveries WHERE consumer=?)"
            + condition
            + (" ORDER BY id DESC LIMIT 1" if latest else " ORDER BY id LIMIT ?"),
            args if latest else args + [limit],
        ).fetchall()
        for ident, raw in rows:
            callback(json.loads(raw))
            with self.conn:
                if latest:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO deliveries SELECT ?,id FROM audit_events WHERE id<=?"
                        + condition,
                        [consumer, ident] + (list(kinds) if kinds else []),
                    )
                else:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO deliveries VALUES (?,?)", (consumer, ident)
                    )

    def flush(self, notify):
        if notify is None:
            return
        for ident, raw in self.conn.execute(
            "SELECT id,payload FROM events WHERE sent=0 "
            "ORDER BY CASE json_extract(payload, '$.kind') WHEN 'CRITICAL' THEN 0 ELSE 1 END, id LIMIT 1"
        ).fetchall():
            notify(json.loads(raw))
            with self.conn:
                self.conn.execute("UPDATE events SET sent=1 WHERE id=?", (ident,))

    def close(self):
        for name in ("conn", "guard"):
            obj = getattr(self, name, None)
            if obj is not None:
                obj.close()
                setattr(self, name, None)
