"""Original trial30 hooks; defaults preserve its frozen SELL contract."""

from scripts.strategy import trial30_bars
from scripts.pure_b1.decision import round_level


class Trial30Strategy:
    snapshot = "RESEARCH-D48-SELL-BE1R-20261001-T030"
    magic = 30261001
    prefix = "T30_"
    allowed_sides = (-1,)
    daily_loss_limit = 0.20
    risk_cap = 0.10
    max_daily_losses = 0
    no_signal_reason = "no_sell_signal"

    def frame(self, bars, mt5, symbol, now):
        frame = trial30_bars(bars)
        if len(frame) < 49:
            raise ValueError("warmup_insufficient")
        return frame

    def levels(self, row, tick, info, costs, account):
        entry = float(tick.bid)
        return (
            entry - float(costs["slippage_allowance_price"]),
            round_level(entry + float(row.atr) * 2.5, float(info.trade_tick_size), -1),
            round_level(entry - float(row.atr) * 3, float(info.trade_tick_size), -1),
        )

    def protects(self, direction):
        return direction == -1

    def diagnostics(self):
        return {}
