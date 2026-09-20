"""Lifecycle event log, open-fill queries, and classified deal sync."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import sqlite3
import json

from . import runtime


class JournalLifecycleMixin:
    def log_lifecycle_event(
        self,
        event_type: str,
        direction: Optional[str] = None,
        entry_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
        lot_size: Optional[float] = None,
        pnl_r: Optional[float] = None,
        pnl_dollar: Optional[float] = None,
        reason: str = "",
        order_id: Optional[str] = None,
        ticket: Optional[int] = None,
        timestamp: Optional[str] = None,
    ):
        cursor = self.conn.cursor()
        if timestamp:
            ts = timestamp
            # Normalize payload clock times into ISO so daily LIKE filters stay stable.
            try:
                parsed = datetime.fromisoformat(
                    str(timestamp).replace("Z", "+00:00").replace(" ", "T")
                )
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                else:
                    parsed = parsed.astimezone(timezone.utc)
                ts = parsed.isoformat()
            except ValueError:
                ts = datetime.now(timezone.utc).isoformat()
        else:
            ts = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO trade_lifecycle (
                timestamp, event_type, direction, entry_price, sl_price, tp_price,
                lot_size, pnl_r, pnl_dollar, reason, order_id, ticket
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                event_type,
                direction,
                entry_price,
                sl_price,
                tp_price,
                lot_size,
                pnl_r,
                pnl_dollar,
                reason,
                order_id,
                ticket,
            ),
        )
        self.conn.commit()

    def get_lifecycle_logs(self) -> List[Dict[str, Any]]:
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trade_lifecycle ORDER BY id ASC")
        rows = [dict(row) for row in cursor.fetchall()]
        return rows

    def list_open_fills(self) -> List[Dict[str, Any]]:
        """
        Fills still open locally: ORDER_FILLED with no later TRADE_CLOSED.

        Used by wall-clock TIME_EXIT when the M5/TV feed stalls.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT order_id, MIN(timestamp) AS open_ts, MAX(direction) AS direction
            FROM trade_lifecycle
            WHERE event_type = 'ORDER_FILLED'
              AND order_id IS NOT NULL
              AND order_id NOT IN (
                  SELECT order_id FROM trade_lifecycle
                  WHERE event_type = 'TRADE_CLOSED' AND order_id IS NOT NULL
              )
            GROUP BY order_id
            ORDER BY open_ts ASC
            """
        )
        rows = []
        for order_id, open_ts, direction in cursor.fetchall():
            if not open_ts:
                continue
            try:
                open_time = datetime.fromisoformat(
                    str(open_ts).replace("Z", "+00:00").replace(" ", "T")
                )
            except ValueError:
                continue
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=timezone.utc)
            else:
                open_time = open_time.astimezone(timezone.utc)
            rows.append(
                {
                    "order_id": order_id,
                    "open_time": open_time,
                    "direction": direction,
                }
            )
        return rows

    def list_unfilled_pendings(self) -> List[str]:
        """
        Accepted/submitted setups with no ORDER_FILLED yet.

        Used to cancel unfilled pendings on news blackout without touching fills.
        """
        return [row["order_id"] for row in self.list_unfilled_pending_setups()]

    def get_pending_direction(self, order_id: str) -> Optional[str]:
        """Direction for an unfilled pending from inbox payload or PLACE_LIMIT log."""
        geom = self.get_pending_geometry(order_id)
        if geom and geom.get("direction"):
            return str(geom["direction"]).strip().upper()
        return None

    def get_pending_geometry(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Limit/SL/direction for an unfilled pending (inbox payload or PLACE_LIMIT log)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT payload_json FROM setup_inbox WHERE order_id = ?",
            (str(order_id),),
        )
        row = cursor.fetchone()
        if row and row[0]:
            try:
                payload = json.loads(row[0])
            except (TypeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                direction = payload.get("dir") or payload.get("direction")
                limit_raw = (
                    payload.get("entry") or payload.get("limit") or payload.get("limit_price")
                )
                sl_raw = payload.get("sl") or payload.get("sl_price")
                try:
                    limit_price = float(limit_raw) if limit_raw is not None else None
                    sl_price = float(sl_raw) if sl_raw is not None else None
                except (TypeError, ValueError):
                    limit_price = None
                    sl_price = None
                if direction or limit_price is not None or sl_price is not None:
                    return {
                        "direction": str(direction).strip().upper() if direction else None,
                        "limit_price": limit_price,
                        "sl_price": sl_price,
                    }
        cursor.execute(
            """
            SELECT direction, entry_price, sl_price FROM trade_lifecycle
            WHERE order_id = ? AND event_type = 'PLACE_LIMIT'
            ORDER BY id DESC LIMIT 1
            """,
            (str(order_id),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        direction, entry_price, sl_price = row
        return {
            "direction": str(direction).strip().upper() if direction else None,
            "limit_price": float(entry_price) if entry_price is not None else None,
            "sl_price": float(sl_price) if sl_price is not None else None,
        }

    def list_uncertain_order_ids(self) -> List[str]:
        """Active uncertain claims awaiting broker reconciliation (story 35)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT order_id FROM setup_inbox
            WHERE status = 'uncertain'
            ORDER BY created_at ASC
            """
        )
        return [str(row[0]) for row in cursor.fetchall() if row and row[0]]

    def is_deal_processed(self, deal_ticket: int) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM processed_deals WHERE deal_ticket = ?",
            (int(deal_ticket),),
        )
        return cursor.fetchone() is not None

    def mark_deal_processed(self, deal_ticket: int, *, source: str, amount: float) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO processed_deals "
                "(deal_ticket, source, amount, processed_at) VALUES (?, ?, ?, ?)",
                (
                    int(deal_ticket),
                    str(source),
                    float(amount),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def fetch_recent_broker_deals(self, *, lookback_hours: int = 48) -> List[Any]:
        """
        Read broker deal history for shared-account PnL classification.

        Dry-run / missing MT5 → empty list (no invented deals).
        """
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return []
        now = datetime.now(timezone.utc)
        from_date = now - timedelta(hours=max(1, int(lookback_hours)))
        deals = runtime.mt5.history_deals_get(from_date, now)
        if not deals:
            return []
        return list(deals)

    def sync_classified_account_pnl(self, *, lookback_hours: int = 48) -> List[Dict[str, Any]]:
        """
        Classify new broker deals as bot/manual/cash_flow and persist lifecycle rows.

        Idempotent via processed_deals tickets. Does not mutate equity inventively —
        broker equity snapshot remains the risk gate input.
        """
        from scripts.smc.account_pnl_sync import classify_deals

        recorded: List[Dict[str, Any]] = []
        for row in classify_deals(self.fetch_recent_broker_deals(lookback_hours=lookback_hours)):
            if row.ticket is None:
                continue
            if self.is_deal_processed(int(row.ticket)):
                continue
            self.log_lifecycle_event(
                event_type="ACCOUNT_PNL",
                ticket=int(row.ticket),
                pnl_dollar=float(row.amount),
                reason=f"{row.source}:{row.comment[:40]}",
            )
            self.mark_deal_processed(int(row.ticket), source=row.source, amount=row.amount)
            recorded.append(
                {
                    "ticket": int(row.ticket),
                    "source": row.source,
                    "amount": float(row.amount),
                }
            )
        return recorded

    def list_unfilled_pending_setups(self) -> List[Dict[str, Any]]:
        """Pending setups with parsed UTC created_at for TTL reconciliation."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT order_id, created_at FROM setup_inbox
            WHERE status IN ('claimed', 'submitted', 'accepted', 'uncertain')
              AND order_id NOT IN (
                  SELECT order_id FROM trade_lifecycle
                  WHERE event_type = 'ORDER_FILLED' AND order_id IS NOT NULL
              )
            ORDER BY created_at ASC
            """
        )
        rows: List[Dict[str, Any]] = []
        for order_id, created_raw in cursor.fetchall():
            if not order_id or not created_raw:
                continue
            try:
                created_at = datetime.fromisoformat(
                    str(created_raw).replace("Z", "+00:00").replace(" ", "T")
                )
            except ValueError:
                continue
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)
            rows.append({"order_id": str(order_id), "created_at": created_at})
        return rows

    def has_lifecycle_event(self, order_id: str, event_type: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM trade_lifecycle
            WHERE order_id = ? AND event_type = ?
            LIMIT 1
            """,
            (order_id, event_type),
        )
        return cursor.fetchone() is not None

    def get_daily_realized_losses(self, date_utc_str: Optional[str] = None) -> int:
        """Queries SQLite for number of realized loss trades today (ADR-011)."""
        if date_utc_str is None:
            date_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = self.conn.cursor()
        # Only count explicit negative PnL — never invent losses from reason text.
        cursor.execute(
            """
            SELECT COUNT(*) FROM trade_lifecycle
            WHERE event_type = 'TRADE_CLOSED'
              AND (pnl_dollar < 0 OR pnl_r < 0)
              AND timestamp LIKE ?
            """,
            (f"{date_utc_str}%",),
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_last_loss_timestamp(self) -> Optional[datetime]:
        """Queries SQLite for the UTC timestamp of the most recent loss trade (ADR-011)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT timestamp FROM trade_lifecycle
            WHERE event_type = 'TRADE_CLOSED'
              AND (pnl_dollar < 0 OR pnl_r < 0)
            ORDER BY id DESC LIMIT 1
            """
        )
        row = cursor.fetchone()
        if row and row[0]:
            ts_str = row[0]
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00").replace(" ", "T"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return None

    def get_fill_geometry(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Latest ORDER_FILLED entry/sl/lot for frozen-R recovery."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT entry_price, sl_price, lot_size, direction
            FROM trade_lifecycle
            WHERE event_type = 'ORDER_FILLED' AND order_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (order_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "entry_price": row[0],
            "sl_price": row[1],
            "lot_size": row[2],
            "direction": row[3],
        }
