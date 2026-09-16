"""Fail-closed admission when market/account/news evidence is unknown or stale (story 32)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple


# Default: one M5 bar + small slack. Stale bars must not authorize new risk.
DEFAULT_MAX_BAR_AGE_SECONDS = 5 * 60 + 30


@dataclass(frozen=True)
class AdmissionGateReport:
    allowed: bool
    reason: str


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def market_data_allows_new_risk(
    *,
    last_bar_time: Optional[datetime],
    now: datetime,
    max_age_seconds: int = DEFAULT_MAX_BAR_AGE_SECONDS,
) -> Tuple[bool, str]:
    """Unknown or stale closed-bar feed blocks new risk."""
    if last_bar_time is None:
        return False, "missing_market_bar"
    if max_age_seconds <= 0:
        return False, "invalid_max_bar_age"
    age = (_as_utc(now) - _as_utc(last_bar_time)).total_seconds()
    if age < 0:
        return False, "market_bar_in_future"
    if age > max_age_seconds:
        return False, f"stale_market_bar_age_s:{int(age)}"
    return True, "ok"


def account_data_allows_new_risk(
    *,
    history_ready: bool,
    equity_known: bool,
) -> Tuple[bool, str]:
    """Incomplete account history/equity must not invent permission to trade."""
    if not history_ready:
        return False, "account_history_not_ready"
    if not equity_known:
        return False, "account_equity_unknown"
    return True, "ok"


def evaluate_new_risk_admission(
    *,
    last_bar_time: Optional[datetime],
    now: datetime,
    history_ready: bool,
    equity_known: bool,
    news_allowed: bool,
    news_reason: str = "ok",
    max_bar_age_seconds: int = DEFAULT_MAX_BAR_AGE_SECONDS,
) -> AdmissionGateReport:
    """
    Combine market + account + news gates. First failure wins (fail closed).
    """
    ok_mkt, reason_mkt = market_data_allows_new_risk(
        last_bar_time=last_bar_time,
        now=now,
        max_age_seconds=max_bar_age_seconds,
    )
    if not ok_mkt:
        return AdmissionGateReport(False, reason_mkt)

    ok_acct, reason_acct = account_data_allows_new_risk(
        history_ready=history_ready,
        equity_known=equity_known,
    )
    if not ok_acct:
        return AdmissionGateReport(False, reason_acct)

    if not news_allowed:
        return AdmissionGateReport(False, news_reason or "news_gate_blocked")

    return AdmissionGateReport(True, "ok")
