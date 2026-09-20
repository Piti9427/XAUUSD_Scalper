"""Actions taken when foundation risk halt trips (story 10)."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from scripts.smc.types import OrderIntent, OrderIntentType


def plan_halt_flatten_intents(
    *,
    pending_order_ids: Iterable[str] = (),
    open_position_ids: Iterable[str] = (),
    reason: str = "foundation_risk_halt",
) -> List[OrderIntent]:
    """
    Request cancel of bot pending orders and close of bot positions.

    Does not invent foreign tickets — caller supplies bot-owned IDs only.
    """
    intents: List[OrderIntent] = []
    for order_id in pending_order_ids:
        if not order_id:
            continue
        intents.append(
            OrderIntent(
                intent_type=OrderIntentType.CANCEL_LIMIT,
                order_id=str(order_id),
                reason=f"{reason}: cancel bot pending",
            )
        )
    for order_id in open_position_ids:
        if not order_id:
            continue
        intents.append(
            OrderIntent(
                intent_type=OrderIntentType.CLOSE_MARKET,
                order_id=str(order_id),
                reason=f"{reason}: close bot position",
            )
        )
    return intents


def bot_owned_order_ids(
    exposure: Optional[Iterable[Any]], *, comment_prefix: str = "SMC_"
) -> List[str]:
    """Extract bot-owned order/position comment suffixes as order_ids."""
    if not exposure:
        return []
    out: List[str] = []
    for item in exposure:
        comment = str(getattr(item, "comment", "") or "")
        if not comment.startswith(comment_prefix):
            continue
        out.append(comment[len(comment_prefix) :])
    return out
