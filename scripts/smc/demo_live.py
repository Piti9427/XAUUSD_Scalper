"""Demo live helpers: PLACE_LIMIT-only admission and quote-driven two-tier."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from scripts.smc.types import Direction, OrderIntent, OrderIntentType


def admit_place_intents(intents: Sequence[OrderIntent]) -> Tuple[str, List[OrderIntent]]:
    """Keep PLACE_LIMIT only. Any other intent is a live fill-path leak."""
    if not intents:
        return "no_intent", []
    bad = [i.intent_type.value for i in intents if i.intent_type != OrderIntentType.PLACE_LIMIT]
    if bad:
        return "blocked_non_place:" + ",".join(bad), []
    return "ok", list(intents)


def two_tier_intents(
    *,
    order_id: str,
    lot_size: float,
    direction: str,
    entry: float,
    sl: float,
    bid: float,
    ask: float,
    already_scaled: bool,
    min_split_lot: float = 0.02,
    partial_ratio: float = 0.5,
    be_buffer: float = 0.10,
    min_lot: float = 0.01,
) -> List[OrderIntent]:
    """PARTIAL_CLOSE + MOVE_SL_TO_BE after broker fill, only at +1.0R and splitable lot."""
    if already_scaled or order_id is None:
        return []
    if float(lot_size) + 1e-9 < float(min_split_lot):
        return []
    sl_dist = abs(float(entry) - float(sl))
    if sl_dist <= 0:
        return []
    side = str(direction or "").upper()
    hit = (
        float(bid) >= float(entry) + sl_dist
        if side == "BUY"
        else float(ask) <= float(entry) - sl_dist
    )
    if not hit:
        return []
    partial_lot = round(float(lot_size) * float(partial_ratio), 2)
    remaining = round(float(lot_size) - partial_lot, 2)
    if partial_lot < min_lot or remaining < min_lot:
        return []
    be_price = round(
        float(entry) + (float(be_buffer) if side == "BUY" else -float(be_buffer)),
        2,
    )
    dir_enum = Direction.BUY if side == "BUY" else Direction.SELL
    return [
        OrderIntent(
            intent_type=OrderIntentType.PARTIAL_CLOSE,
            direction=dir_enum,
            lot_size=partial_lot,
            order_id=order_id,
            reason="TP1_50_PCT_SCALE_OUT",
        ),
        OrderIntent(
            intent_type=OrderIntentType.MOVE_SL_TO_BE,
            direction=dir_enum,
            sl_price=be_price,
            order_id=order_id,
            reason="TP1_RELOCATE_SL_TO_BE",
        ),
    ]
