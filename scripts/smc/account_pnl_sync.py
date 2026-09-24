"""Classify broker deals into bot / manual / cash_flow (foundation stories 5–7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from scripts.smc.types import AccountState, apply_account_pnl_event


BOT_COMMENT_PREFIX = "SMC_"

# MetaTrader5 DEAL_TYPE_* common values (avoid importing MetaTrader5 on Mac).
DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1
DEAL_TYPE_BALANCE = 2
DEAL_TYPE_CREDIT = 3
DEAL_TYPE_CHARGE = 4
DEAL_TYPE_CORRECTION = 5
DEAL_TYPE_BONUS = 6
DEAL_TYPE_COMMISSION = 7

CASH_FLOW_TYPES = frozenset(
    {
        DEAL_TYPE_BALANCE,
        DEAL_TYPE_CREDIT,
        DEAL_TYPE_CHARGE,
        DEAL_TYPE_CORRECTION,
        DEAL_TYPE_BONUS,
        DEAL_TYPE_COMMISSION,
        "balance",
        "credit",
        "charge",
        "correction",
        "bonus",
        "commission",
    }
)


@dataclass(frozen=True)
class ClassifiedDeal:
    ticket: Optional[int]
    source: str  # bot | manual | cash_flow
    amount: float
    comment: str


def deal_cashflow_amount(deal: Any) -> float:
    """Net cash from one deal row (profit + commission + swap + fee)."""
    profit = float(getattr(deal, "profit", 0.0) or 0.0)
    commission = float(getattr(deal, "commission", 0.0) or 0.0)
    swap = float(getattr(deal, "swap", 0.0) or 0.0)
    fee = float(getattr(deal, "fee", 0.0) or 0.0)
    return round(profit + commission + swap + fee, 2)


def classify_deal_source(deal: Any) -> str:
    """
    Map a broker deal to expectancy buckets.

    - cash_flow: balance/credit/bonus-style deals
    - bot: comment owned by SMC_ strategy
    - manual: everything else (human/other EAs)
    """
    dtype = getattr(deal, "type", None)
    if dtype in CASH_FLOW_TYPES:
        return "cash_flow"
    comment = str(getattr(deal, "comment", "") or "")
    if comment.startswith(BOT_COMMENT_PREFIX):
        return "bot"
    return "manual"


def classify_deals(deals: Iterable[Any]) -> List[ClassifiedDeal]:
    out: List[ClassifiedDeal] = []
    for deal in deals:
        amount = deal_cashflow_amount(deal)
        if amount == 0.0:
            continue
        out.append(
            ClassifiedDeal(
                ticket=getattr(deal, "ticket", None),
                source=classify_deal_source(deal),
                amount=amount,
                comment=str(getattr(deal, "comment", "") or ""),
            )
        )
    return out


def apply_classified_deals(
    account: AccountState,
    classified: Iterable[ClassifiedDeal],
) -> int:
    """Apply classified deals to AccountState. Returns number applied."""
    n = 0
    for row in classified:
        apply_account_pnl_event(account, amount=row.amount, source=row.source)
        n += 1
    return n
