"""SQLite schema, setup inbox, and webhook idempotency."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import sqlite3
import hashlib
import json
from uuid import uuid4

from . import runtime


class JournalInboxMixin:
    def _init_sqlite(self):
        import os
        try:
            dir_name = os.path.dirname(self.db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute("PRAGMA busy_timeout=5000")
            cursor = self.conn.cursor()
            # Test actual write permissions (important in sandboxed or read-only mounted filesystems)
            cursor.execute("CREATE TABLE IF NOT EXISTS _write_test (id INT)")
            cursor.execute("INSERT INTO _write_test (id) VALUES (1)")
            cursor.execute("DROP TABLE _write_test")
            self.conn.commit()
        except (sqlite3.OperationalError, OSError) as exc:
            if hasattr(self, "conn"):
                self.conn.close()
            if not self.dry_run:
                raise OSError("Live execution requires writable persistent SQLite journal") from exc
            self.db_path = ":memory:"
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                direction TEXT,
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                lot_size REAL,
                pnl_r REAL,
                pnl_dollar REAL,
                reason TEXT,
                order_id TEXT,
                ticket INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(order_id, event_type)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS setup_inbox (
                receipt_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS setup_inbox_one_active
            ON setup_inbox ((1))
            WHERE status IN ('claimed', 'submitted', 'accepted', 'uncertain')
            """
        )
        # Ensure new columns exist for pre-existing databases
        cursor.execute("PRAGMA table_info(trade_lifecycle)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "order_id" not in existing_cols:
            cursor.execute("ALTER TABLE trade_lifecycle ADD COLUMN order_id TEXT")
        if "ticket" not in existing_cols:
            cursor.execute("ALTER TABLE trade_lifecycle ADD COLUMN ticket INTEGER")
        cursor.execute("PRAGMA table_info(setup_inbox)")
        inbox_cols = {row[1] for row in cursor.fetchall()}
        if "ticket" not in inbox_cols:
            cursor.execute("ALTER TABLE setup_inbox ADD COLUMN ticket INTEGER")
        if "reconciled_at" not in inbox_cols:
            cursor.execute("ALTER TABLE setup_inbox ADD COLUMN reconciled_at TEXT")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_deals (
                deal_ticket INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                processed_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def claim_setup(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Atomically claim one setup; uncertain claims remain active after restart."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        order_id = str(payload["order_id"])
        with self._claim_lock:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "SELECT receipt_id, payload_hash FROM setup_inbox WHERE order_id = ?",
                    (order_id,),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    status = "duplicate" if existing[1] == payload_hash else "conflict"
                    return {"status": status, "receipt_id": existing[0]}
                cursor.execute(
                    "SELECT receipt_id FROM setup_inbox WHERE status IN "
                    "('claimed', 'submitted', 'accepted', 'uncertain') LIMIT 1"
                )
                if cursor.fetchone() is not None:
                    return {"status": "busy", "receipt_id": ""}
                receipt_id = uuid4().hex
                cursor.execute(
                    "INSERT INTO setup_inbox "
                    "(receipt_id, order_id, payload_json, payload_hash, status, created_at) "
                    "VALUES (?, ?, ?, ?, 'claimed', ?)",
                    (receipt_id, order_id, canonical, payload_hash,
                     datetime.now(timezone.utc).isoformat()),
                )
                return {"status": "claimed", "receipt_id": receipt_id}

    def update_setup_status(
        self, order_id: str, status: str, ticket: Optional[int] = None
    ) -> None:
        """Update setup status and optional ticket; releases claim lock on 'rejected'/'closed'."""
        with self._claim_lock:
            with self.conn:
                now_iso = datetime.now(timezone.utc).isoformat()
                self.conn.execute(
                    """
                    UPDATE setup_inbox
                    SET status = ?, ticket = COALESCE(?, ticket), reconciled_at = ?
                    WHERE order_id = ?
                    """,
                    (status, ticket, now_iso, order_id),
                )

    def get_setup_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Return setup details from inbox."""
        cursor = self.conn.execute(
            "SELECT status, ticket, created_at, receipt_id, reconciled_at FROM setup_inbox WHERE order_id = ?",
            (order_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "status": row[0],
            "ticket": row[1],
            "created_at": row[2],
            "receipt_id": row[3],
            "reconciled_at": row[4],
        }

    def reconcile_uncertain(self, order_id: str) -> str:
        """Reconciles uncertain setup against MT5 pending orders, positions, and deal history."""
        target_comment = f"SMC_{order_id}"
        if runtime.mt5 is not None and (self.connected or self.dry_run):
            orders = runtime.mt5.orders_get(symbol=self.symbol)
            if orders:
                for o in orders:
                    if getattr(o, "comment", "") == target_comment:
                        ticket = getattr(o, "ticket", None)
                        self.update_setup_status(order_id, "accepted", ticket=ticket)
                        return "accepted"
            positions = runtime.mt5.positions_get(symbol=self.symbol)
            if positions:
                for pos in positions:
                    if getattr(pos, "comment", "") == target_comment:
                        ticket = getattr(pos, "ticket", None)
                        self.update_setup_status(order_id, "accepted", ticket=ticket)
                        return "accepted"
            # Check history orders if available with created_at lookback
            now = datetime.now(timezone.utc)
            from_date = None
            cursor = self.conn.execute("SELECT created_at FROM setup_inbox WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    from_date = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                    if from_date.tzinfo is None:
                        from_date = from_date.replace(tzinfo=timezone.utc)
                    from_date = from_date - timedelta(hours=1)
                except Exception:
                    from_date = None
            if from_date is None:
                from_date = now - timedelta(days=7)

            hist_orders = runtime.mt5.history_orders_get(from_date, now)
            if hist_orders is not None:
                for ho in hist_orders:
                    if getattr(ho, "comment", "") == target_comment:
                        order_state = getattr(ho, "state", None)
                        filled_state = getattr(runtime.mt5, "ORDER_STATE_FILLED", 1)
                        if order_state == filled_state:
                            ticket = getattr(ho, "ticket", None)
                            self.update_setup_status(order_id, "accepted", ticket=ticket)
                            return "accepted"
                        self.update_setup_status(order_id, "rejected")
                        return "rejected"
            # If not in orders, positions, or history, and open exposure is flat
            if orders == [] and positions == []:
                self.update_setup_status(order_id, "rejected")
                return "rejected"
        return "uncertain"

    def finish_setup(self, order_id: str) -> None:
        """Release one claim after caller confirms broker is flat."""
        with self._claim_lock:
            with self.conn:
                self.conn.execute(
                    "UPDATE setup_inbox SET status = 'closed', reconciled_at = ? "
                    "WHERE order_id = ? AND status IN "
                    "('claimed', 'submitted', 'accepted', 'uncertain')",
                    (datetime.now(timezone.utc).isoformat(), order_id),
                )

    def get_setup_receipt(self, order_id: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT receipt_id FROM setup_inbox WHERE order_id = ?", (order_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def inspect_setup(self, payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Read an existing claim before setup guards; claim_setup resolves races."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        cursor = self.conn.execute(
            "SELECT receipt_id, payload_json FROM setup_inbox WHERE order_id = ?",
            (str(payload["order_id"]),),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "status": "duplicate" if row[1] == canonical else "conflict",
            "receipt_id": row[0],
        }

    def is_webhook_processed(self, order_id: str, event_type: str) -> bool:
        """Checks if a given webhook event has already been executed for idempotency."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM processed_webhooks WHERE order_id = ? AND event_type = ?",
            (order_id, event_type),
        )
        return cursor.fetchone() is not None

    def mark_webhook_processed(
        self, order_id: str, event_type: str, status: str = "success"
    ):
        """Records a processed webhook event to guarantee idempotency."""
        cursor = self.conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT OR REPLACE INTO processed_webhooks (order_id, event_type, processed_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, event_type, now_utc, status),
        )
        self.conn.commit()
