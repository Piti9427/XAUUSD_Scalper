import logging

from scripts.insight_formatter import format_trade_for_telegram

try:
    from telegram import Bot
except ImportError:
    Bot = None


logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, config):
        self.enabled = config.get("enabled", True)
        self.chat_id = config.get("chat_id")
        token = config.get("token")
        if self.enabled and Bot is None:
            raise RuntimeError(
                "python-telegram-bot is not installed. Run pip install -r requirements.txt."
            )
        self.bot = Bot(token=token) if self.enabled else None
        if not self.enabled:
            logger.info("Telegram notifier disabled")

    async def send_message(self, text):
        """Sends a text message to the configured Telegram chat."""
        if not self.enabled:
            logger.info("Telegram disabled; skipped message")
            return

        try:
            async with self.bot:
                await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error("Error sending Telegram message: %s", e)

    async def send_signal_alert(self, signal_type, entry, tp, sl, symbol="XAUUSD"):
        """Backward-compatible wrapper for simple alerts."""
        await self.send_trade_insight(
            {
                "symbol": symbol,
                "type": signal_type,
                "entry": entry,
                "tp": tp,
                "sl": sl,
            }
        )

    async def send_trade_insight(self, trade_data):
        """Sends a compact, actionable trade insight."""
        await self.send_message(format_trade_for_telegram(trade_data))


# Example usage for testing (standalone)
if __name__ == "__main__":
    import yaml

    async def test():
        with open("config/settings.yaml", "r") as f:
            config = yaml.safe_load(f)

        notifier = TelegramNotifier(config["telegram"])
        print("Sending test message...")
        await notifier.send_signal_alert("BUY", 2400.50, 2410.50, 2395.50)

    # To run: python scripts/notifier.py
    # asyncio.run(test())
