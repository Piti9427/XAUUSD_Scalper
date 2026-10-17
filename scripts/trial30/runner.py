"""Rollback strategy adapter; legacy constructor and cycle interface retained."""

from __future__ import annotations

from pathlib import Path
import time as time  # Legacy patch target shares the runtime's time module.
from typing import Any, Callable

from scripts.demo_runtime.runner import DemoRunner
from scripts.trial30.strategy import Trial30Strategy

SNAPSHOT = "RESEARCH-D48-SELL-BE1R-20261001-T030"
MAGIC = 30261001


class Trial30DemoRunner(DemoRunner):
    def __init__(
        self,
        *,
        mt5: Any,
        expected_login: int,
        expected_server: str,
        journal_path: Path,
        cost_policy: dict,
        execute: bool = False,
        notify: Callable[[dict], None] | None = None,
        symbol: str = "XAUUSDm",
        strategy=None,
        account_guard_dir: Path | None = None,
    ):
        super().__init__(
            mt5=mt5,
            expected_login=expected_login,
            expected_server=expected_server,
            journal_path=journal_path,
            cost_policy=cost_policy,
            execute=execute,
            notify=notify,
            symbol=symbol,
            strategy=strategy or Trial30Strategy(),
            account_guard_dir=account_guard_dir,
        )
