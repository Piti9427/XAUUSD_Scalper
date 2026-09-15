"""Persistent account risk halt state for foundation BaselinePlay."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class RiskHaltState:
    high_water_equity: float
    day_start_equity: float
    day_utc: str
    drawdown_halt: bool = False
    daily_equity_halt: bool = False
    net_losing_trades_today: int = 0

    @property
    def halted(self) -> bool:
        return self.drawdown_halt or self.daily_equity_halt or self.net_losing_trades_today >= 2


def _utc_today(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    return now.date().isoformat()


def new_risk_halt_state(equity: float, now: Optional[datetime] = None) -> RiskHaltState:
    day = _utc_today(now)
    return RiskHaltState(
        high_water_equity=float(equity),
        day_start_equity=float(equity),
        day_utc=day,
    )


def observe_equity(
    state: RiskHaltState,
    equity: float,
    *,
    now: Optional[datetime] = None,
    drawdown_pct: float = 0.05,
    daily_decline_pct: float = 0.01,
) -> RiskHaltState:
    """
    Update high-water / daily equity gates.

    Drawdown halt persists across days/restarts once tripped.
    Daily equity halt resets only on a new UTC day together with losing-trade count.
    """
    day = _utc_today(now)
    equity = float(equity)
    if day != state.day_utc:
        state.day_utc = day
        state.day_start_equity = equity
        state.daily_equity_halt = False
        state.net_losing_trades_today = 0
        # high_water and drawdown_halt intentionally survive day rollover

    if equity > state.high_water_equity:
        state.high_water_equity = equity

    if state.high_water_equity > 0:
        dd = (state.high_water_equity - equity) / state.high_water_equity
        if dd >= drawdown_pct:
            state.drawdown_halt = True

    if state.day_start_equity > 0:
        decline = (state.day_start_equity - equity) / state.day_start_equity
        if decline >= daily_decline_pct:
            state.daily_equity_halt = True

    return state


def record_net_losing_trade(state: RiskHaltState) -> RiskHaltState:
    state.net_losing_trades_today += 1
    return state


def save_risk_halt_state(path: Path, state: RiskHaltState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n")


def load_risk_halt_state(path: Path) -> Optional[RiskHaltState]:
    if not path.is_file():
        return None
    raw = json.loads(path.read_text())
    return RiskHaltState(**raw)
