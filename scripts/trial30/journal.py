"""Durable claims/outbox and single local writer for trial30 Demo."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3


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
        self.conn = sqlite3.connect(path)
        self.conn.executescript("""
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0);
        """)
        self.conn.commit()

    def get(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value):
        raw = json.dumps(value, sort_keys=True, allow_nan=False)
        with self.conn:
            self.conn.execute(
                "INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, raw),
            )

    def transition(self, key: str, value, event: dict):
        """Commit reconciled state and notification atomically."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, sort_keys=True, allow_nan=False)),
            )
            self.conn.execute(
                "INSERT INTO events(payload) VALUES (?)", (json.dumps(event, allow_nan=False),)
            )

    def event(self, payload: dict):
        with self.conn:
            self.conn.execute(
                "INSERT INTO events(payload) VALUES (?)", (json.dumps(payload, allow_nan=False),)
            )

    def flush(self, notify):
        if notify is None:
            return
        for ident, raw in self.conn.execute(
            "SELECT id,payload FROM events WHERE sent=0 ORDER BY id"
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
