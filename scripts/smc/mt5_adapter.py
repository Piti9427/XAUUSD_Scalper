from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import sqlite3
import logging
import hashlib
import json
import threading
from uuid import uuid4
from scripts.smc.types import Direction, OrderIntentType, OrderIntent
from scripts.smc.mt5_filling import resolve_type_filling
from scripts.smc.mt5_init import initialize_mt5

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    order_id: Optional[int]
    message: str
    status: str = "OK"  # OK | REJECTED | UNKNOWN


BOT_COMMENT_PREFIX = "SMC_"


def is_bot_owned_comment(comment: Optional[str], order_id: Optional[str] = None) -> bool:
    """True only for comments owned by this strategy — never symbol-only matches."""
    if not comment or not comment.startswith(BOT_COMMENT_PREFIX):
        return False
    if order_id is None:
        return True
    return comment in {f"SMC_{order_id}", f"SMC_Partial_{order_id}"}


class SMCExecutionAdapter:
    """
    Execution Adapter for MetaTrader 5.
    Safely degrades to dry-run/mock mode when running on non-Windows platforms.
    Maintains a local SQLite lifecycle audit trail.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        dry_run: bool = False,
        db_path: str = "data/smc_trades.db",
        terminal_path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
    ):
        self.symbol = symbol
        self.dry_run = dry_run
        self.terminal_path = terminal_path
        self.login = login
        self.server = server
        if not dry_run and db_path == ":memory:":
            raise OSError("Live execution requires persistent SQLite journal")
        if not dry_run:
            if mt5 is None:
                raise RuntimeError("MT5 live mode requested but MetaTrader5 package missing")
            init = initialize_mt5(
                mt5,
                path=terminal_path,
                login=login,
                password=password,
                server=server,
            )
            if not init.ok:
                raise RuntimeError(
                    f"MT5 live mode unavailable ({init.detail}): {init.last_error}"
                )
        self.connected = not dry_run
        self.db_path = db_path
        self._claim_lock = threading.Lock()
        self._init_sqlite()

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
        if mt5 is not None and (self.connected or self.dry_run):
            orders = mt5.orders_get(symbol=self.symbol)
            if orders:
                for o in orders:
                    if getattr(o, "comment", "") == target_comment:
                        ticket = getattr(o, "ticket", None)
                        self.update_setup_status(order_id, "accepted", ticket=ticket)
                        return "accepted"
            positions = mt5.positions_get(symbol=self.symbol)
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

            hist_orders = mt5.history_orders_get(from_date, now)
            if hist_orders is not None:
                for ho in hist_orders:
                    if getattr(ho, "comment", "") == target_comment:
                        order_state = getattr(ho, "state", None)
                        filled_state = getattr(mt5, "ORDER_STATE_FILLED", 1)
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
                parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00").replace(" ", "T"))
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
        if self.dry_run or mt5 is None or not self.connected:
            return []
        now = datetime.now(timezone.utc)
        from_date = now - timedelta(hours=max(1, int(lookback_hours)))
        deals = mt5.history_deals_get(from_date, now)
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

    def get_account_equity(self) -> Optional[float]:
        """Fetches real-time equity from MT5 terminal or None if offline/dry-run."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
        info = mt5.account_info()
        return float(info.equity) if info else None

    def _type_filling_for_symbol(self, *, for_pending: bool) -> Optional[int]:
        if mt5 is None or not self.connected:
            return None
        sym = mt5.symbol_info(self.symbol)
        if sym is None:
            return None
        raw_mode = getattr(sym, "filling_mode", 0)
        if isinstance(raw_mode, (int, float)):
            filling_mode = int(raw_mode)
        else:
            filling_mode = 0
        return resolve_type_filling(
            filling_mode,
            for_pending=for_pending,
            mt5_mod=mt5,
        )

    def get_risk_snapshot(self) -> Optional[Dict[str, float]]:
        """Return current broker account and XAUUSD sizing rules, or None."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
        account = mt5.account_info()
        symbol = mt5.symbol_info(self.symbol)
        if account is None or symbol is None:
            return None
        margin_free = getattr(account, "margin_free", None)
        if margin_free is None:
            return None
        trade_allowed = getattr(account, "trade_allowed", None)
        point = getattr(symbol, "point", None)
        stops_level = getattr(symbol, "trade_stops_level", None)
        freeze_level = getattr(symbol, "trade_freeze_level", None)
        if point is None or stops_level is None or freeze_level is None:
            return None
        try:
            snapshot = {
                "balance": float(account.balance),
                "equity": float(account.equity),
                "min_lot": float(symbol.volume_min),
                "max_lot": float(symbol.volume_max),
                "lot_step": float(symbol.volume_step),
                "contract_size": float(symbol.trade_contract_size),
                "margin_free": float(margin_free),
                "point": float(point),
                "stops_level": float(stops_level),
                "freeze_level": float(freeze_level),
            }
        except (TypeError, ValueError):
            return None
        if trade_allowed is not None:
            snapshot["trade_allowed"] = 1.0 if bool(trade_allowed) else 0.0
        return snapshot

    def get_market_quotes(self) -> Optional[Dict[str, float]]:
        """Return current bid/ask for freeze-level SL checks, or None if unknown."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return None
        bid = getattr(tick, "bid", None)
        ask = getattr(tick, "ask", None)
        try:
            if bid is None or ask is None:
                return None
            return {"bid": float(bid), "ask": float(ask)}
        except (TypeError, ValueError):
            return None

    def get_open_exposure(self) -> Optional[List[Any]]:
        """Return all XAUUSD pending orders and positions; None means broker unknown."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
        orders = mt5.orders_get(symbol=self.symbol)
        positions = mt5.positions_get(symbol=self.symbol)
        if orders is None or positions is None:
            return None
        return list(orders) + list(positions)

    def get_matching_position(self, order_id: str) -> Optional[Any]:
        """Find open position matching SMC_{order_id} comment on broker."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return None
        for pos in positions:
            if getattr(pos, "comment", "") == f"SMC_{order_id}":
                return pos
        return None

    def get_matching_pending_order(self, order_id: str) -> Optional[Any]:
        """Find open pending order matching SMC_{order_id} comment on broker."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
        orders = mt5.orders_get(symbol=self.symbol)
        if not orders:
            return None
        for order in orders:
            if getattr(order, "comment", "") == f"SMC_{order_id}":
                return order
        return None

    def get_realized_pnl_for_order(self, order_id: str) -> Optional[float]:
        """Calculate net realized PnL (profit + swap + commission + fee) from broker deal history."""
        if self.dry_run or mt5 is None or not self.connected:
            return None
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

        deals = mt5.history_deals_get(from_date, now)
        if deals is None:
            return None
        from scripts.smc.cost_accounting import aggregate_deal_cashflows

        target_comment = f"SMC_{order_id}"
        partial_comment = f"SMC_Partial_{order_id}"
        matching = [
            d
            for d in deals
            if getattr(d, "comment", "") in {target_comment, partial_comment}
        ]
        return aggregate_deal_cashflows(matching)

    def execute_intent(self, intent: OrderIntent) -> ExecutionResult:
        """Translates domain OrderIntent into MT5 broker calls or dry-run simulation."""
        # Enforce target scoping (ADR-024) on live broker execution
        is_rollover_all = "ROLLOVER" in intent.reason.upper() and (intent.ticket is None and not intent.order_id)
        if not self.dry_run:
            if intent.intent_type in (OrderIntentType.CANCEL_LIMIT, OrderIntentType.MOVE_SL_TO_BE, OrderIntentType.PARTIAL_CLOSE):
                if intent.ticket is None and not intent.order_id:
                    return ExecutionResult(
                        success=False,
                        order_id=None,
                        message=f"{intent.intent_type.value} rejected: Both ticket and order_id are missing. Targeted execution required.",
                    )
            elif intent.intent_type == OrderIntentType.CLOSE_MARKET:
                if intent.ticket is None and not intent.order_id and not is_rollover_all:
                    return ExecutionResult(
                        success=False,
                        order_id=None,
                        message="CLOSE_MARKET rejected: Both ticket and order_id are missing. Targeted execution required.",
                    )

        if self.dry_run:
            msg = f"DRY_RUN: Successfully simulated {intent.intent_type.value} for {self.symbol} - {intent.reason}"
            logger.info(msg)
            self.log_lifecycle_event(
                event_type=intent.intent_type.value,
                direction=intent.direction.value if intent.direction else None,
                entry_price=intent.limit_price,
                sl_price=intent.sl_price,
                tp_price=intent.tp_price,
                lot_size=intent.lot_size,
                reason=intent.reason,
                order_id=intent.order_id,
                ticket=intent.ticket,
            )
            return ExecutionResult(success=True, order_id=intent.ticket or 123456, message=msg)

        if intent.intent_type == OrderIntentType.PLACE_LIMIT:
            order_type = (
                mt5.ORDER_TYPE_BUY_LIMIT
                if intent.direction == Direction.BUY
                else mt5.ORDER_TYPE_SELL_LIMIT
            )
            comment_str = (
                f"SMC_{intent.order_id}"
                if intent.order_id
                else f"SMC_v1_{intent.reason[:20]}"
            )
            # Defense in depth: stops_level geometry even if caller skipped webhook gate.
            from scripts.smc.stops_geometry import pending_stops_geometry_allows

            snap = self.get_risk_snapshot()
            if snap is None:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message="PLACE_LIMIT rejected: broker risk snapshot unavailable",
                    status="REJECTED",
                )
            geom_ok, geom_reason = pending_stops_geometry_allows(
                entry_price=float(intent.limit_price),
                sl_price=float(intent.sl_price),
                tp_price=float(intent.tp_price) if intent.tp_price else None,
                point=float(snap["point"]),
                stops_level=float(snap["stops_level"]),
            )
            if not geom_ok:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message=f"PLACE_LIMIT rejected: {geom_reason}",
                    status="REJECTED",
                )
            self.log_lifecycle_event(
                event_type="INTENT_SUBMITTED",
                direction=intent.direction.value if intent.direction else None,
                entry_price=intent.limit_price,
                sl_price=intent.sl_price,
                tp_price=intent.tp_price,
                lot_size=intent.lot_size,
                reason=intent.reason,
                order_id=intent.order_id,
                ticket=intent.ticket,
            )
            type_filling = self._type_filling_for_symbol(for_pending=True)
            if type_filling is None:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message="Cannot resolve type_filling for symbol — broker symbol_info unavailable",
                    status="REJECTED",
                )
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": self.symbol,
                "volume": intent.lot_size,
                "type": order_type,
                "price": intent.limit_price,
                "sl": intent.sl_price,
                "tp": intent.tp_price,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
                "comment": comment_str,
            }
            result = mt5.order_send(request)
            if result is None:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message="Order submit returned None — status UNKNOWN; reconcile before retry",
                    status="UNKNOWN",
                )
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = f"retcode {result.retcode}: {result.comment}"
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message=f"Order failed with {err_msg}",
                    status="REJECTED",
                )
            self.log_lifecycle_event(
                event_type="PLACE_LIMIT",
                direction=intent.direction.value if intent.direction else None,
                entry_price=intent.limit_price,
                sl_price=intent.sl_price,
                tp_price=intent.tp_price,
                lot_size=intent.lot_size,
                reason=intent.reason,
                order_id=intent.order_id,
                ticket=result.order,
            )
            return ExecutionResult(
                success=True,
                order_id=result.order,
                message=f"Limit order #{result.order} placed successfully",
            )

        elif intent.intent_type == OrderIntentType.CANCEL_LIMIT:
            orders = mt5.orders_get(symbol=self.symbol)
            canceled_count = 0
            if orders:
                for o in orders:
                    owned = is_bot_owned_comment(getattr(o, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and o.ticket == intent.ticket
                        and is_bot_owned_comment(getattr(o, "comment", ""))
                    )
                    match_order_id = intent.order_id is not None and owned
                    if match_ticket or match_order_id:
                        req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                        result = mt5.order_send(req)
                        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(False, o.ticket, "Broker rejected limit cancellation")
                        canceled_count += 1
            if canceled_count == 0:
                return ExecutionResult(False, intent.ticket, "Target limit order not found")
            self.log_lifecycle_event(
                event_type="CANCEL_LIMIT",
                order_id=intent.order_id,
                ticket=intent.ticket,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Cancelled {canceled_count} limit order(s) for {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.MOVE_SL_TO_BE:
            # Defense in depth: reject SL mods inside broker freeze distance.
            from scripts.smc.stops_geometry import sl_modify_freeze_allows

            snap = self.get_risk_snapshot()
            if snap is None:
                return ExecutionResult(
                    False,
                    intent.ticket,
                    "MOVE_SL_TO_BE rejected: broker risk snapshot unavailable",
                )
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return ExecutionResult(
                    False,
                    intent.ticket,
                    "MOVE_SL_TO_BE rejected: broker symbol tick unavailable",
                )
            freeze_ok, freeze_reason = sl_modify_freeze_allows(
                new_sl=float(intent.sl_price),
                market_bid=float(getattr(tick, "bid", float("nan"))),
                market_ask=float(getattr(tick, "ask", float("nan"))),
                point=float(snap["point"]),
                freeze_level=float(snap["freeze_level"]),
            )
            if not freeze_ok:
                return ExecutionResult(
                    False,
                    intent.ticket,
                    f"MOVE_SL_TO_BE rejected: {freeze_reason}",
                )
            positions = mt5.positions_get(symbol=self.symbol)
            moved_count = 0
            if positions:
                for pos in positions:
                    owned = is_bot_owned_comment(getattr(pos, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and pos.ticket == intent.ticket
                        and is_bot_owned_comment(getattr(pos, "comment", ""))
                    )
                    match_order_id = intent.order_id is not None and owned
                    if match_ticket or match_order_id:
                        req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": intent.sl_price,
                            "tp": pos.tp,
                        }
                        result = mt5.order_send(req)
                        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(False, pos.ticket, "Broker rejected SL modification")
                        moved_count += 1
            if moved_count == 0:
                return ExecutionResult(False, intent.ticket, "Target position not found")
            self.log_lifecycle_event(
                event_type="MOVE_SL_TO_BE",
                order_id=intent.order_id,
                ticket=intent.ticket,
                sl_price=intent.sl_price,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Moved SL to BE for {moved_count} position(s) on {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.PARTIAL_CLOSE:
            positions = mt5.positions_get(symbol=self.symbol)
            closed_count = 0
            if positions:
                for pos in positions:
                    owned = is_bot_owned_comment(getattr(pos, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and pos.ticket == intent.ticket
                        and is_bot_owned_comment(getattr(pos, "comment", ""))
                    )
                    match_order_id = intent.order_id is not None and owned
                    if match_ticket or match_order_id:
                        close_type = (
                            mt5.ORDER_TYPE_SELL
                            if pos.type == mt5.ORDER_TYPE_BUY
                            else mt5.ORDER_TYPE_BUY
                        )
                        tick = mt5.symbol_info_tick(self.symbol)
                        if tick is None:
                            return ExecutionResult(False, intent.ticket, "Broker symbol tick unavailable")
                        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                        vol = min(pos.volume, intent.lot_size or (pos.volume * 0.5))
                        deal_filling = self._type_filling_for_symbol(for_pending=False)
                        if deal_filling is None:
                            return ExecutionResult(
                                False,
                                intent.ticket,
                                "Cannot resolve type_filling for market deal",
                            )
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": self.symbol,
                            "volume": vol,
                            "type": close_type,
                            "price": price,
                            "deviation": 20,
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": deal_filling,
                            "comment": f"SMC_Partial_{intent.order_id or ''}",
                        }
                        result = mt5.order_send(req)
                        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(False, pos.ticket, "Broker rejected partial close")
                        closed_count += 1
            if closed_count == 0:
                return ExecutionResult(False, intent.ticket, "Target position not found")
            self.log_lifecycle_event(
                event_type="PARTIAL_CLOSE",
                order_id=intent.order_id,
                ticket=intent.ticket,
                lot_size=intent.lot_size,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Partially closed {closed_count} position(s) on {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.CLOSE_MARKET:
            positions = mt5.positions_get(symbol=self.symbol)
            closed_count = 0
            if positions:
                for pos in positions:
                    owned_any = is_bot_owned_comment(getattr(pos, "comment", ""))
                    owned = is_bot_owned_comment(getattr(pos, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and pos.ticket == intent.ticket
                        and owned_any
                    )
                    match_order_id = intent.order_id is not None and owned
                    # Rollover closes only bot-owned exposure — never foreign manual trades.
                    if match_ticket or match_order_id or (is_rollover_all and owned_any):
                        close_type = (
                            mt5.ORDER_TYPE_SELL
                            if pos.type == mt5.ORDER_TYPE_BUY
                            else mt5.ORDER_TYPE_BUY
                        )
                        tick = mt5.symbol_info_tick(self.symbol)
                        if tick is None:
                            return ExecutionResult(False, intent.ticket, "Broker symbol tick unavailable")
                        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                        deal_filling = self._type_filling_for_symbol(for_pending=False)
                        if deal_filling is None:
                            return ExecutionResult(
                                False,
                                intent.ticket,
                                "Cannot resolve type_filling for market close",
                            )
                        close_comment = (
                            f"SMC_{intent.order_id}"
                            if intent.order_id
                            else (getattr(pos, "comment", "") or BOT_COMMENT_PREFIX)
                        )
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": self.symbol,
                            "volume": pos.volume,
                            "type": close_type,
                            "price": price,
                            "deviation": 20,
                            "type_filling": deal_filling,
                            "comment": close_comment[:31],
                        }
                        result = mt5.order_send(req)
                        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(False, pos.ticket, "Broker rejected market close")
                        closed_count += 1
            if closed_count == 0:
                return ExecutionResult(False, intent.ticket, "Target position not found")
            self.log_lifecycle_event(
                event_type="CLOSE_MARKET",
                order_id=intent.order_id,
                ticket=intent.ticket,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Closed {closed_count} market position(s) for {self.symbol}",
            )

        return ExecutionResult(success=True, order_id=None, message="No action needed")

    def close(self):
        """Cleanly close SQLite connection and release file locks."""
        if hasattr(self, "conn") and self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
