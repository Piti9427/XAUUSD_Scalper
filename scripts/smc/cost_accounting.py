"""Separate trading expectancy from operating costs (foundation scenario 21)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CostAccountingReport:
    bot_realized_pnl: float
    fees_and_swap: float
    operating_costs: float
    net_trading_profit: float
    net_operating_profit: float
    note: str


def summarize_profit_layers(
    *,
    bot_realized_pnl: float,
    fees_and_swap: float = 0.0,
    operating_costs: float = 0.0,
    spread_already_in_bid_ask: bool = True,
) -> CostAccountingReport:
    """
    Keep strategy expectancy distinct from runtime burn.

    - bot_realized_pnl: closed bot trades using bid/ask fills (spread already in prices)
    - fees_and_swap: explicit commission/swap not already in bid/ask
    - operating_costs: VPS/data/API burn — never mixed into per-trade expectancy
    """
    fees = float(fees_and_swap)
    ops = float(operating_costs)
    bot = float(bot_realized_pnl)
    if spread_already_in_bid_ask:
        note = "spread embedded in bid/ask; do not subtract again"
    else:
        note = "caller must disclose any extra spread model not in fills"
    net_trading = bot - fees
    net_operating = net_trading - ops
    return CostAccountingReport(
        bot_realized_pnl=round(bot, 4),
        fees_and_swap=round(fees, 4),
        operating_costs=round(ops, 4),
        net_trading_profit=round(net_trading, 4),
        net_operating_profit=round(net_operating, 4),
        note=note,
    )


def expectancy_hides_operating_loss(
    *,
    positive_trade_expectancy: bool,
    net_operating_profit: float,
) -> bool:
    """True when positive trade expectancy would mask ops burn — reporting hazard."""
    return bool(positive_trade_expectancy) and float(net_operating_profit) < 0.0
