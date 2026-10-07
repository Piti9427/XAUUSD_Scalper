"""Trade notes explain blocks, entries, and planned exits without retuning."""

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from scripts.c22h4.strategy import BarCache
from scripts.c22h4.trade_log import explain_block, render_exit, review_exit
from scripts.trial30.broker import BrokerView
from scripts.trial30.costs import validate_policy
from test_c22h4_strategy import bars


class TradeLogTests(unittest.TestCase):
    def test_stale_cost_policy_and_midnight_hold_are_the_entry_blocks(self):
        now = datetime(2026, 10, 5, 18, 55, tzinfo=timezone.utc)
        policy = json.loads(Path("data/trial30-demo-cost-policy.json").read_text())
        cost, status = validate_policy(policy, fingerprint=policy["account_fingerprint"], now=now)
        self.assertEqual(cost, {})
        self.assertEqual(status, "invalid_or_stale")
        self.assertIn("24 ชั่วโมง", explain_block("cost_policy_" + status))

        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        boundary = int(midnight.timestamp() * 1000)

        def deal(ticket, typ, volume, position_id, when, profit):
            return NS(
                ticket=ticket,
                type=typ,
                volume=volume,
                position_id=position_id,
                time_msc=when,
                profit=profit,
                commission=0.0,
                swap=0.0,
                fee=0.0,
            )

        deals = [
            deal(1, 2, 0, 0, boundary - 86_400_000, 200.07),
            deal(2, 0, 0.01, 11, boundary - 3_600_000, 0.0),
            deal(3, 1, 0.01, 11, boundary + 60_000, 30.43),
        ]

        class Journal:
            def __init__(self):
                self.data = {}

            def get(self, key, default=None):
                return self.data.get(key, default)

            def put(self, key, value):
                self.data[key] = value

        view = BrokerView(None, 1, "Exness-Demo", "XAUUSDm", "abc", Journal())
        with self.assertRaisesRegex(ValueError, "day_start_floating_unknown"):
            view._baseline(NS(balance=230.50, equity=230.50), [], deals, now)
        self.assertIn("00:00 UTC", explain_block("day_start_floating_unknown"))

        restarted = BrokerView(
            None, 1, "Exness-Demo", "XAUUSDm", "abc", view.journal, restart_unknown_baseline=True
        )
        self.assertEqual(
            restarted._baseline(NS(balance=230.50, equity=230.50), [], deals, now), 230.50
        )
        self.assertEqual(view.journal.get("day")["source"], "restart_equity")
        self.assertEqual(
            restarted._baseline(NS(balance=230.50, equity=210.0), [], deals, now), 230.50
        )
        view.journal.put("day", {"day": now.date().isoformat(), "equity": 999.0, "source": "stale"})
        again = BrokerView(
            None, 1, "Exness-Demo", "XAUUSDm", "abc", view.journal, restart_unknown_baseline=True
        )
        self.assertEqual(again._baseline(NS(balance=230.50, equity=230.50), [], deals, now), 230.50)
        self.assertEqual(view.journal.get("day")["source"], "restart_equity")

    def test_target_profit_and_planned_stop_do_not_request_a_contract_change(self):
        win = review_exit(
            side="SELL",
            fill=2650.0,
            stop=2660.0,
            target=2640.0,
            exit_price=2640.1,
            net=12.0,
            profit=12.4,
            commission=0.0,
            swap=-0.4,
            fee=0.0,
        )
        loss = review_exit(
            side="SELL",
            fill=2650.0,
            stop=2660.0,
            target=2640.0,
            exit_price=2660.0,
            net=-10.2,
            profit=-10.0,
            commission=0.0,
            swap=-0.2,
            fee=0.0,
        )
        self.assertIn("TP", win["because"])
        self.assertIn("ไม่มี", win["mistake"])
        self.assertIn("ไม่ปรับ", win["next"])
        self.assertIn("SL 2660.000", loss["because"])
        self.assertIn("ไม่ใช่การเข้าผิดกฎ", loss["mistake"])
        self.assertIn("สัญญาเดิม", loss["next"])

    def test_cost_drag_and_safety_close_name_the_actual_cause(self):
        drag = review_exit(
            side="BUY",
            fill=100.0,
            stop=99.0,
            target=102.0,
            exit_price=100.4,
            net=-0.2,
            profit=0.4,
            commission=-0.3,
            swap=-0.3,
            fee=0.0,
        )
        safety = review_exit(
            side="BUY",
            fill=100.0,
            stop=99.0,
            target=102.0,
            exit_price=100.0,
            net=-1.0,
            profit=-1.0,
            commission=0.0,
            swap=0.0,
            fee=0.0,
            safety_reason="filled_risk_violation",
        )
        self.assertIn("ต้นทุน", drag["because"])
        self.assertEqual(safety["mistake"], "filled_risk_violation")
        title, body, record = render_exit(
            "2026-10-06T00:00:00+00:00", {"why": "สัญญาณ", "side": "BUY"}, safety, fill=100.0
        )
        self.assertIn("filled_risk_violation", body)
        self.assertEqual(record["kind"], "EXIT")
        self.assertIn("EXIT", title)

    def test_sell_thesis_cites_close_prior_low_and_macro(self):
        from scripts.c22h4.runner import C22H4Strategy

        config = json.loads(Path("config/c22h4-demo.json").read_text())
        strategy = C22H4Strategy(config)
        strategy.cache = BarCache()
        strategy.cache.append(bars())
        thesis = strategy.entry_thesis()
        self.assertEqual(thesis["side"], "SELL")
        self.assertIn("prior 96", thesis["why"])
        self.assertIn(f"{thesis['close']:.3f}", thesis["why"])
        self.assertIn(f"{thesis['macro_ema']:.3f}", thesis["why"])

    def test_block_note_is_written_once_per_reason_each_utc_day(self):
        from scripts.c22h4.runner import C22H4DemoRunner

        now = datetime(2026, 10, 5, 18, 55, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "c22h4-demo.sqlite3"

            class Journal:
                def __init__(self):
                    self.data = {}

                def get(self, key, default=None):
                    return self.data.get(key, default)

                def put(self, key, value):
                    self.data[key] = value

            runner = C22H4DemoRunner.__new__(C22H4DemoRunner)
            runner.journal = Journal()
            runner.trade_log_path = path.with_name(path.stem + "-trades.md")
            result = {"status": "BLOCKED", "reason": "day_start_floating_unknown"}
            runner._record_trade_note(None, result, now)
            runner._record_trade_note(None, result, now)
            text = runner.trade_log_path.read_text()
            self.assertEqual(text.count("day_start_floating_unknown"), 1)
            self.assertIn("00:00 UTC", text)
