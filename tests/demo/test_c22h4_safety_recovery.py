"""Public-cycle safety-close recovery; synthetic broker, no real MT5 calls."""

import json
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS

from scripts.c22h4.runner import C22H4DemoRunner
from tests.demo.test_c22h4_demo import CandidateBroker
from tests.demo.test_trial30_demo import policy


class SafetyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "demo.sqlite3"
        self.broker = CandidateBroker(1)
        self.original_send = self.broker.send
        self.close_requests = []

    def runner(self):
        runner = C22H4DemoRunner(
            mt5=self.broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.path,
            cost_policy=policy() | {"reviewed_utc": self.broker.now.isoformat()},
            execute=True,
        )
        self.addCleanup(runner.close)
        return runner

    def install_fault(self, first_close="partial"):
        def send(request):
            if not request.get("position"):
                result = self.original_send(request)
                self.broker.positions[-1].volume = 0.02
                self.broker.deals[-1].volume = 0.02
                return result
            self.close_requests.append(dict(request))
            if len(self.close_requests) == 1:
                if first_close in ("timeout", "placed", "none"):
                    return (
                        None
                        if first_close == "none"
                        else NS(retcode=10012 if first_close == "timeout" else 10008, order=900)
                    )
                if first_close == "rejected":
                    return NS(retcode=10006)
                if first_close == "partial":
                    position = self.broker.positions[0]
                    position.volume -= 0.01
                    self.broker.deals.append(
                        NS(
                            ticket=3,
                            order=900,
                            time_msc=self.broker.tick.time_msc,
                            time=self.broker.tick.time_msc // 1000,
                            type=request["type"],
                            entry=1,
                            volume=0.01,
                            position_id=position.identifier,
                            profit=-1.0,
                            commission=0.0,
                            swap=0.0,
                            fee=0.0,
                            magic=0,
                            comment="safety partial",
                            price=request["price"],
                        )
                    )
                    self.broker.account.balance -= 1.0
                    self.broker.account.equity = self.broker.account.balance
                    return NS(retcode=10010, order=900, volume=0.01)
            result = self.original_send(request)
            if first_close == "costed":
                self.add_close_costs()
            return result

        self.broker.order_send.side_effect = send

    def add_close_costs(self):
        deal = self.broker.deals[-1]
        deal.commission, deal.swap, deal.fee = -0.2, -0.3, -0.1
        deal.price -= 0.05
        self.broker.account.balance -= 0.6
        self.broker.account.equity = self.broker.account.balance

    def cycle(self, runner):
        self.broker.now += timedelta(seconds=1)
        self.broker.tick.time_msc = int(self.broker.now.timestamp() * 1000) - 100
        return runner.cycle(now=self.broker.now)

    def events(self, runner):
        return [
            json.loads(row[0]) for row in runner.journal.conn.execute("SELECT payload FROM events")
        ]

    def assert_flat_safety_close(self, runner, result):
        self.assertEqual(result["status"], "SAFETY_CLOSED", result)
        self.assertFalse(self.broker.positions)
        self.assertIsNone(runner.journal.get("active"))
        self.assertEqual(runner.journal.get("safety_halt"), "filled_position_contract_violation")
        self.assertEqual([event["kind"] for event in self.events(runner)], ["SAFETY_CLOSED"])
        self.assertTrue(all(request["position"] == 777 for request in self.close_requests))

    def test_confirmed_partial_close_recovers_only_owned_residual(self):
        self.install_fault()
        runner = self.runner()
        self.assertEqual(runner.cycle(now=self.broker.now)["status"], "UNKNOWN")
        self.assertEqual(self.broker.positions[0].volume, 0.01)
        result = self.cycle(runner)
        self.assert_flat_safety_close(runner, result)
        self.assertEqual([request["volume"] for request in self.close_requests], [0.02, 0.01])
        self.assertEqual(self.broker.order_send.call_count, 3)
        self.assertEqual(self.cycle(runner)["reason"], "safety_halt")
        self.assertEqual(self.broker.order_send.call_count, 3)

    def test_restart_preserves_partial_close_evidence_without_new_entry(self):
        self.install_fault()
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        runner.close()
        restarted = self.runner()
        self.assert_flat_safety_close(restarted, self.cycle(restarted))
        self.assertEqual(self.broker.order_send.call_count, 3)
        self.assertEqual(len(self.close_requests), 2)

    def test_sell_partial_retry_uses_buy_close_on_owned_ticket(self):
        self.broker = CandidateBroker(-1)
        self.original_send = self.broker.send
        self.install_fault()
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.assert_flat_safety_close(runner, self.cycle(runner))
        self.assertEqual([request["type"] for request in self.close_requests], [0, 0])
        self.assertEqual([request["volume"] for request in self.close_requests], [0.02, 0.01])

    def test_partial_retry_leaves_foreign_position_untouched(self):
        self.install_fault()
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        foreign = NS(
            ticket=888,
            identifier=888,
            symbol="XAUUSDm",
            magic=99,
            comment="foreign",
            type=1,
            volume=0.01,
            price_open=200.0,
            sl=210.0,
            tp=190.0,
        )
        self.broker.positions.append(foreign)
        self.assertEqual(self.cycle(runner)["status"], "SAFETY_CLOSED")
        self.assertEqual(self.broker.positions, [foreign])
        self.assertEqual([request["position"] for request in self.close_requests], [777, 777])
        self.assertEqual([event["kind"] for event in self.events(runner)], ["SAFETY_CLOSED"])

    def test_pending_order_and_incomplete_ledger_block_partial_retry(self):
        self.install_fault()
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        closing_deal = self.broker.deals.pop()
        self.assertEqual(self.cycle(runner)["status"], "UNKNOWN")
        self.assertEqual(len(self.close_requests), 1)
        self.broker.deals.append(closing_deal)
        self.broker.orders = [NS(ticket=900)]
        self.assertEqual(self.cycle(runner)["status"], "UNKNOWN")
        self.assertEqual(len(self.close_requests), 1)
        self.broker.orders = []
        self.assert_flat_safety_close(runner, self.cycle(runner))

    def test_residual_volume_growth_blocks_partial_retry(self):
        self.install_fault()
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.broker.positions[0].volume = 0.02
        extra = NS(**vars(self.broker.deals[1]))
        extra.ticket, extra.volume = 4, 0.01
        self.broker.deals.append(extra)
        self.assertEqual(self.cycle(runner)["status"], "UNKNOWN")
        self.assertEqual(len(self.close_requests), 1)
        self.assertTrue(runner.journal.get("active")["safety_close_pending"])

    def test_ambiguous_and_legacy_pending_never_blindly_resubmit(self):
        self.install_fault("timeout")
        runner = self.runner()
        self.assertEqual(runner.cycle(now=self.broker.now)["status"], "UNKNOWN")
        for retcode in (10008, None):
            active = runner.journal.get("active")
            attempt = active.get("safety_close_attempt", {})
            attempt["retcode"] = retcode
            active["safety_close_attempt"] = attempt
            runner.journal.put("active", active)
            self.assertEqual(self.cycle(runner)["status"], "UNKNOWN")
        active = runner.journal.get("active")
        active.pop("safety_close_attempt", None)
        runner.journal.put("active", active)
        runner.close()
        restarted = self.runner()
        self.assertEqual(self.cycle(restarted)["status"], "UNKNOWN")
        self.assertEqual(len(self.close_requests), 1)
        self.assertEqual(self.broker.order_send.call_count, 2)

    def test_definitively_rejected_safety_close_retries_owned_position(self):
        self.install_fault("rejected")
        runner = self.runner()
        self.assertEqual(runner.cycle(now=self.broker.now)["status"], "UNKNOWN")
        self.assert_flat_safety_close(runner, self.cycle(runner))
        self.assertEqual([request["volume"] for request in self.close_requests], [0.02, 0.02])

    def test_safety_close_reports_actual_cash_components_and_exit_deal(self):
        self.install_fault("costed")
        runner = self.runner()
        result = runner.cycle(now=self.broker.now)
        self.assert_flat_safety_close(runner, result)
        for field, expected in {
            "profit": -1.0,
            "commission": -0.2,
            "swap": -0.3,
            "fee": -0.1,
            "net": -1.6,
        }.items():
            self.assertAlmostEqual(result[field], expected)
        self.assertEqual(result["exit_price"], self.broker.deals[-1].price)
        event = self.events(runner)[0]
        self.assertEqual(event["exit_price"], result["exit_price"])
        self.assertAlmostEqual(event["swap"], -0.3)

    def test_late_safety_completion_keeps_safety_kind_and_actual_costs(self):
        self.install_fault("timeout")
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.original_send(self.close_requests[0])
        self.add_close_costs()
        runner.close()
        restarted = self.runner()
        result = self.cycle(restarted)
        self.assert_flat_safety_close(restarted, result)
        self.assertAlmostEqual(result["net"], -1.6)
        self.assertAlmostEqual(result["profit"], -1.0)
        self.assertAlmostEqual(result["swap"], -0.3)
        self.assertEqual(result["exit_price"], self.broker.deals[-1].price)
        self.assertEqual(self.broker.order_send.call_count, 2)


if __name__ == "__main__":
    unittest.main()
