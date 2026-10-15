import unittest

from scripts.insight_formatter import (
    build_backtest_insight,
    build_trade_insight,
    format_trade_for_telegram,
)


class InsightFormatterTests(unittest.TestCase):
    def test_trade_insight_contains_actionable_risk(self):
        insight = build_trade_insight(
            {
                "symbol": "XAUUSD",
                "type": "BUY",
                "entry": 2400,
                "tp": 2410,
                "sl": 2395,
                "spread": 12,
                "rsi": 34.8,
                "atr": 4.2,
                "rationale": "MTF align + MSS",
            }
        )

        self.assertEqual(insight["headline"], "BUY XAUUSD")
        self.assertEqual(insight["risk"]["rr"], "1:2.00")
        self.assertIn("Use predefined SL", insight["action"])

    def test_telegram_format_is_compact_and_scannable(self):
        message = format_trade_for_telegram(
            {
                "symbol": "XAUUSD",
                "type": "SELL",
                "entry": 2400,
                "tp": 2390,
                "sl": 2405,
                "spread": 10,
            }
        )

        self.assertIn("Review setup before entry", message)
        self.assertIn("*Risk:* 1:2.00", message)
        self.assertIn("*Action:*", message)
        self.assertLessEqual(len(message.splitlines()), 6)

    def test_backtest_insight_recommends_tuning_for_low_win_rate(self):
        insight = build_backtest_insight(
            [
                {"result": "SL"},
                {"result": "SL"},
                {"result": "TP"},
            ]
        )

        self.assertEqual(insight["decision"], "Needs tuning")
        self.assertIn("Review", insight["action"])


if __name__ == "__main__":
    unittest.main()
