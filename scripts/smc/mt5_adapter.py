from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import sqlite3
import logging
from scripts.smc.types import Direction, OrderIntentType, OrderIntent

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
    ):
        self.symbol = symbol
        self.dry_run = dry_run or (mt5 is None)
        self.db_path = db_path
        self._init_sqlite()

    def _init_sqlite(self):
        import os
        try:
            dir_name = os.path.dirname(self.db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        except (sqlite3.OperationalError, OSError):
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
        # Ensure new columns exist for pre-existing databases
        cursor.execute("PRAGMA table_info(trade_lifecycle)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "order_id" not in existing_cols:
            cursor.execute("ALTER TABLE trade_lifecycle ADD COLUMN order_id TEXT")
        if "ticket" not in existing_cols:
            cursor.execute("ALTER TABLE trade_lifecycle ADD COLUMN ticket INTEGER")
        self.conn.commit()

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
    ):
        cursor = self.conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO trade_lifecycle (
                timestamp, event_type, direction, entry_price, sl_price, tp_price,
                lot_size, pnl_r, pnl_dollar, reason, order_id, ticket
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_utc,
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

    def get_daily_realized_losses(self, date_utc_str: Optional[str] = None) -> int:
        """Queries SQLite for number of realized loss trades today (ADR-011)."""
        if date_utc_str is None:
            date_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = self.conn.cursor()
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

    def execute_intent(self, intent: OrderIntent) -> ExecutionResult:
        """Translates domain OrderIntent into MT5 broker calls or dry-run simulation."""
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
                ticket=intent.ticket or 123456,
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
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": self.symbol,
                "volume": intent.lot_size,
                "type": order_type,
                "price": intent.limit_price,
                "sl": intent.sl_price,
                "tp": intent.tp_price,
                "type_time": mt5.ORDER_TIME_GTC,
                "comment": comment_str,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message=f"Order failed with retcode {result.retcode}: {result.comment}",
                )
            return ExecutionResult(
                success=True,
                order_id=result.order,
                message=f"Limit order #{result.order} placed successfully",
            )

        elif intent.intent_type == OrderIntentType.CANCEL_LIMIT:
            # Look up specific pending order and cancel
            orders = mt5.orders_get(symbol=self.symbol)
            canceled_count = 0
            if orders:
                for o in orders:
                    match_ticket = (intent.ticket is not None and o.ticket == intent.ticket)
                    match_order_id = (intent.order_id is not None and intent.order_id in getattr(o, "comment", ""))
                    if match_ticket or match_order_id or (intent.ticket is None and intent.order_id is None):
                        req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                        mt5.order_send(req)
                        canceled_count += 1
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Cancelled {canceled_count} limit order(s) for {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.MOVE_SL_TO_BE:
            positions = mt5.positions_get(symbol=self.symbol)
            moved_count = 0
            if positions:
                for pos in positions:
                    match_ticket = (intent.ticket is not None and pos.ticket == intent.ticket)
                    match_order_id = (intent.order_id is not None and intent.order_id in getattr(pos, "comment", ""))
                    if match_ticket or match_order_id or (intent.ticket is None and intent.order_id is None):
                        req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": intent.sl_price,
                            "tp": pos.tp,
                        }
                        mt5.order_send(req)
                        moved_count += 1
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
                    match_ticket = (intent.ticket is not None and pos.ticket == intent.ticket)
                    match_order_id = (intent.order_id is not None and intent.order_id in getattr(pos, "comment", ""))
                    if match_ticket or match_order_id or (intent.ticket is None and intent.order_id is None):
                        close_type = (
                            mt5.ORDER_TYPE_SELL
                            if pos.type == mt5.ORDER_TYPE_BUY
                            else mt5.ORDER_TYPE_BUY
                        )
                        tick = mt5.symbol_info_tick(self.symbol)
                        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                        vol = min(pos.volume, intent.lot_size or (pos.volume * 0.5))
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": self.symbol,
                            "volume": vol,
                            "type": close_type,
                            "price": price,
                            "deviation": 20,
                            "type_time": mt5.ORDER_TIME_GTC,
                            "comment": f"SMC_Partial_{intent.order_id or ''}",
                        }
                        mt5.order_send(req)
                        closed_count += 1
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Partially closed {closed_count} position(s) on {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.CLOSE_MARKET:
            positions = mt5.positions_get(symbol=self.symbol)
            if positions:
                for pos in positions:
                    close_type = (
                        mt5.ORDER_TYPE_SELL
                        if pos.type == mt5.ORDER_TYPE_BUY
                        else mt5.ORDER_TYPE_BUY
                    )
                    tick = mt5.symbol_info_tick(self.symbol)
                    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
                    req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": pos.ticket,
                        "symbol": self.symbol,
                        "volume": pos.volume,
                        "type": close_type,
                        "price": price,
                        "deviation": 20,
                    }
                    mt5.order_send(req)
            return ExecutionResult(
                success=True,
                order_id=None,
                message=f"Closed market position for {self.symbol}",
            )

        return ExecutionResult(success=True, order_id=None, message="No action needed")
