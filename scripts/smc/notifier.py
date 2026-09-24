from typing import Optional, Dict, Any
import logging
from scripts.smc.types import Direction, SetupSignal, Position

logger = logging.getLogger(__name__)

try:
    from telegram import Bot
except ImportError:
    Bot = None


def format_smc_trade_card(
    signal: SetupSignal, lot_size: float, risk_amount: float = 50.0, symbol: str = "XAUUSD"
) -> str:
    """Formats an institutional-grade Markdown alert card for Telegram."""
    direction_emoji = "🟢 BUY" if signal.direction == Direction.BUY else "🔴 SELL"
    pts_sl = signal.sl_distance
    pips_sl = pts_sl * 10.0
    pts_tp = abs(signal.tp_price - signal.entry_price)
    pips_tp = pts_tp * 10.0

    time_str = signal.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if signal.timestamp else "N/A"

    card = f"""🚨 *{symbol} SMC SIGNAL: {signal.direction.value}* {direction_emoji}
━━━━━━━━━━━━━━━━━━━━━
📍 *Entry (50% FVG):* `{signal.entry_price:.2f}`
🛑 *Stop Loss:* `{signal.sl_price:.2f}` (-{pts_sl:.2f} pts / -{pips_sl:.1f} pips)
🎯 *Take Profit:* `{signal.tp_price:.2f}` (+{pts_tp:.2f} pts / +{pips_tp:.1f} pips)
⚖️ *Risk/Reward:* `1:{signal.risk_r:.1f}` (Fixed)

💼 *Position Sizing:*
• Risk Amount: `0.5%` (${risk_amount:.2f})
• Recommended Lot: `{lot_size:.2f} Lot`
• Sweep Wick: `{signal.sweep_wick:.2f}` (Spread buffer: +$0.30)

🔍 *Rationale:*
{signal.reason}
⏰ *Time:* `{time_str}`
━━━━━━━━━━━━━━━━━━━━━"""
    return card


def format_order_filled_card(position: Position, symbol: str = "XAUUSD") -> str:
    """Formats a milestone card when a pending limit order is filled."""
    direction_emoji = "🟢 BUY" if position.direction == Direction.BUY else "🔴 SELL"
    time_str = position.open_time.strftime("%Y-%m-%d %H:%M:%S UTC") if position.open_time else "N/A"
    card = f"""⚡ *{symbol} ORDER FILLED: {position.direction.value}* {direction_emoji}
━━━━━━━━━━━━━━━━━━━━━
📍 *Fill Price:* `{position.entry_price:.2f}`
🛑 *Stop Loss:* `{position.sl_price:.2f}` (-{position.initial_sl_distance:.2f} pts)
🎯 *Take Profit:* `{position.tp_price:.2f}`
💼 *Volume:* `{position.lot_size:.2f} Lot`
⏰ *Fill Time:* `{time_str}`
━━━━━━━━━━━━━━━━━━━━━"""
    return card


def format_order_accepted_card(
    *,
    direction: Direction,
    limit_price: float,
    sl_price: float,
    tp_price: float,
    lot_size: float,
    order_id: Optional[str] = None,
    ticket: Optional[int] = None,
    symbol: str = "XAUUSD",
) -> str:
    """Broker-accepted pending only — must not be confused with a fill card."""
    direction_emoji = "🟢 BUY" if direction == Direction.BUY else "🔴 SELL"
    oid = order_id or "n/a"
    tix = ticket if ticket is not None else "n/a"
    card = f"""📥 *{symbol} ORDER ACCEPTED (PENDING): {direction.value}* {direction_emoji}
━━━━━━━━━━━━━━━━━━━━━
📍 *Limit:* `{limit_price:.2f}`
🛑 *Stop Loss:* `{sl_price:.2f}`
🎯 *Take Profit:* `{tp_price:.2f}`
💼 *Volume:* `{lot_size:.2f} Lot`
🆔 *Order ID:* `{oid}`
🎫 *Ticket:* `{tix}`
⚠️ *Not filled yet* — await ORDER_FILLED / broker fill evidence
━━━━━━━━━━━━━━━━━━━━━"""
    return card


def format_be_moved_card(position: Position, symbol: str = "XAUUSD") -> str:
    """Formats a milestone card when SL is moved to Breakeven (+1.0R)."""
    direction_emoji = "🟢 BUY" if position.direction == Direction.BUY else "🔴 SELL"
    card = f"""🛡️ *{symbol} BREAKEVEN SECURED: {position.direction.value}* {direction_emoji}
━━━━━━━━━━━━━━━━━━━━━
📍 *Entry Price:* `{position.entry_price:.2f}`
🛡️ *New SL (BE):* `{position.sl_price:.2f}` (Capital secured: +0.0R)
🎯 *Take Profit:* `{position.tp_price:.2f}`
📈 *Progress:* Price reached +1.0R. Free trade!
━━━━━━━━━━━━━━━━━━━━━"""
    return card


def format_partial_tp_card(
    direction: Direction,
    closed_lot: float,
    remaining_lot: float,
    r_multiple: float,
    entry_price: float,
    symbol: str = "XAUUSD",
) -> str:
    """Formats a milestone card when a partial take profit target is reached."""
    direction_emoji = "🟢 BUY" if direction == Direction.BUY else "🔴 SELL"
    card = f"""🎯 *{symbol} PARTIAL TAKE PROFIT HIT!* {direction_emoji}
━━━━━━━━━━━━━━━━━━━━━
💰 *Milestone:* `+{r_multiple:.1f}R Profit Locked In`
📦 *Closed Volume:* `{closed_lot:.2f} lots`
🛡️ *Remaining Volume:* `{remaining_lot:.2f} lots`
🔒 *Risk Management:* `SL Moved to Breakeven ({entry_price:.2f})`
🚀 *Target:* Final TP (Risk-Free Runner)
━━━━━━━━━━━━━━━━━━━━━"""
    return card


def format_trade_closed_card(
    direction: Direction,
    exit_price: float,
    pnl_dollars: float,
    pnl_r: float,
    reason: str,
    symbol: str = "XAUUSD",
) -> str:
    """Formats a milestone card when an open position is closed."""
    is_win = pnl_dollars >= 0
    res_emoji = "🏆 WIN" if is_win else "🛑 LOSS"
    direction_emoji = "🟢 BUY" if direction == Direction.BUY else "🔴 SELL"
    card = f"""🏁 *{symbol} TRADE CLOSED ({direction.value})* {direction_emoji}
━━━━━━━━━━━━━━━━━━━━━
📌 *Outcome:* *{res_emoji}*
💰 *Net P&L ($):* `${pnl_dollars:+.2f}`
📊 *P&L (R):* `{pnl_r:+.2f}R`
🏁 *Exit Price:* `{exit_price:.2f}`
🔍 *Reason:* {reason}
━━━━━━━━━━━━━━━━━━━━━"""
    return card


def format_circuit_breaker_card(
    losses_today: int,
    cooldown_mins: int = 30,
    symbol: str = "XAUUSD",
) -> str:
    """Formats an alert card when the daily circuit breaker triggers."""
    card = f"""🛑 *{symbol} CIRCUIT BREAKER ACTIVATED*
━━━━━━━━━━━━━━━━━━━━━
⚠️ *Daily Losses Reached:* `{losses_today}/2`
⏳ *Cooldown Period:* `{cooldown_mins} minutes`
🔒 *Status:* Trading halted to protect account equity.
━━━━━━━━━━━━━━━━━━━━━"""
    return card


class SMCTelegramNotifier:
    """Sends SMC trade alert cards and charts to Telegram."""

    def __init__(self, config: Dict[str, Any]):
        tg_conf = config.get("telegram", {})
        self.enabled = tg_conf.get("enabled", False)
        self.chat_id = tg_conf.get("chat_id")
        self.token = tg_conf.get("token")
        self.bot = Bot(token=self.token) if (self.enabled and Bot) else None

    async def send_message(self, text: str) -> bool:
        """Sends a plain or markdown text message to Telegram."""
        if not self.enabled or not self.bot:
            logger.info("Telegram notifier disabled or bot not available.")
            return False
        try:
            async with self.bot:
                await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="Markdown")
                return True
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False

    async def send_alert(
        self,
        signal: SetupSignal,
        lot_size: float,
        risk_amount: float = 50.0,
        chart_image_path: Optional[str] = None,
    ) -> bool:
        if not self.enabled or not self.bot:
            logger.info("Telegram notifier disabled or bot not available.")
            return False

        card_text = format_smc_trade_card(signal, lot_size, risk_amount)
        try:
            async with self.bot:
                if chart_image_path:
                    try:
                        with open(chart_image_path, "rb") as photo:
                            await self.bot.send_photo(
                                chat_id=self.chat_id,
                                photo=photo,
                                caption=card_text,
                                parse_mode="Markdown",
                            )
                            return True
                    except Exception as exc:
                        logger.warning("Failed to send photo, falling back to text: %s", exc)

                await self.bot.send_message(
                    chat_id=self.chat_id, text=card_text, parse_mode="Markdown"
                )
                return True
        except Exception as e:
            logger.error("Failed to send Telegram SMC alert: %s", e)
            return False
