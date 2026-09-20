"""SMCExecutionAdapter composition root."""

from __future__ import annotations

from typing import Optional
import logging
import threading

from scripts.smc import mt5_init

from .broker import BrokerMixin
from .execution import ExecutionMixin
from .journal import JournalMixin
from . import runtime

logger = logging.getLogger(__name__)


class SMCExecutionAdapter(JournalMixin, BrokerMixin, ExecutionMixin):
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
            if runtime.mt5 is None:
                raise RuntimeError("MT5 live mode requested but MetaTrader5 package missing")
            init = mt5_init.initialize_mt5(
                runtime.mt5,
                path=terminal_path,
                login=login,
                password=password,
                server=server,
            )
            if not init.ok:
                raise RuntimeError(f"MT5 live mode unavailable ({init.detail}): {init.last_error}")
        self.connected = not dry_run
        self.db_path = db_path
        self._claim_lock = threading.Lock()
        self._init_sqlite()

    def close(self):
        """Cleanly close SQLite connection and release file locks."""
        if hasattr(self, "conn") and self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
