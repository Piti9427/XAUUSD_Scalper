"""Contract regressions through public cycles, with synthetic broker only."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
from datetime import timedelta
import hashlib
import json
import subprocess
import unittest

from scripts.c22h4.runner import C22H4DemoRunner
from tests.demo.test_c22h4_demo import CandidateBroker
from tests.demo.test_trial30_demo import policy
from scripts.demo_runtime.costs import validate_policy
from scripts.demo_runtime.market_data import completed_m15_from_m1


class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "demo.sqlite3"
        self.broker = CandidateBroker(1)

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

    def test_post_fill_widened_stop_is_contained(self):
        runner = self.runner()
        self.assertEqual(runner.cycle(now=self.broker.now)["status"], "FILLED")
        self.broker.positions[0].sl -= 30
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SAFETY_CLOSED", result)
        self.assertTrue(runner.journal.get("safety_halt"))
        self.assertFalse(self.broker.positions)

    def test_comment_collision_cannot_replace_stable_identifier(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        foreign = NS(**(vars(self.broker.positions[0]) | {"identifier": 888, "ticket": 888}))
        self.broker.positions = [foreign]
        foreign.sl -= 30
        result = runner.cycle(now=self.broker.now)
        self.assertIn(result["status"], ("BLOCKED", "UNKNOWN"), result)
        self.assertEqual(self.broker.order_send.call_count, 1)
        self.assertEqual(self.broker.positions, [foreign])

    def test_ticket_change_preserves_identifier(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.broker.positions[0].ticket = 999
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "MANAGING", result)
        self.assertEqual(runner.journal.get("active")["ticket"], 999)

    def test_note_failure_does_not_escape_cycle_and_retries_after_restart(self):
        runner = self.runner()
        with patch("scripts.c22h4.runner.append_note", side_effect=OSError("disk")):
            result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "FILLED", result)
        self.assertEqual(result["notes"], "pending_retry")
        runner.close()
        restarted = self.runner()
        self.assertEqual(restarted.cycle(now=self.broker.now)["status"], "MANAGING")
        self.assertIn("ENTRY", restarted.trade_log_path.read_text())
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_nan_free_margin_blocks_before_send(self):
        self.broker.account.margin_free = float("nan")
        result = self.runner().cycle(now=self.broker.now)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.broker.order_send.assert_not_called()

    def test_nan_opening_volume_never_mutates_or_confirms_protection(self):
        self.broker = CandidateBroker(-1)
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.broker.deals[-1].volume = float("nan")
        self.broker.tick.bid -= 5
        self.broker.tick.ask -= 5
        self.broker.next_bar()
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result["position_protection"], "unknown")
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_fresh_safety_ledger_mismatch_blocks_first_close(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.broker.positions[0].sl = 0
        calls = 0
        original = self.broker.positions_get

        def changed(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.broker.positions[0].volume = 0.02
            return original(**kwargs)

        self.broker.positions_get = changed
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertEqual(self.broker.order_send.call_count, 1)
        self.assertEqual(self.broker.positions[0].volume, 0.02)

    def test_stop_and_target_failure_matrix_after_fill(self):
        for side in (-1, 1):
            for field, value in (
                ("sl", 0),
                ("sl", float("nan")),
                ("sl", None),
                ("tp", float("inf")),
                ("tp", 1.0),
            ):
                with self.subTest(side=side, field=field, value=value):
                    self.path = Path(self.temp.name) / f"{side}-{field}-{value}.sqlite3"
                    self.broker = CandidateBroker(side)
                    runner = self.runner()
                    self.assertEqual(runner.cycle(now=self.broker.now)["status"], "FILLED")
                    setattr(self.broker.positions[0], field, value)
                    result = runner.cycle(now=self.broker.now)
                    self.assertEqual(result["status"], "SAFETY_CLOSED", result)
                    observed = runner.journal.conn.execute(
                        "SELECT payload FROM audit_events WHERE json_extract(payload,'$.kind')='CONTRACT_VIOLATION'"
                    ).fetchone()
                    self.assertIsNotNone(observed)
                    json.loads(observed[0])
                    runner.close()

    def test_valid_tightening_and_be_survive_restart_then_never_widen(self):
        self.broker = CandidateBroker(-1)
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        p = self.broker.positions[0]
        p.sl = p.price_open - 0.1
        self.assertEqual(runner.cycle(now=self.broker.now)["status"], "MANAGING")
        runner.close()
        restarted = self.runner()
        self.assertEqual(restarted.cycle(now=self.broker.now)["status"], "MANAGING")
        p.sl += 0.01
        self.assertEqual(restarted.cycle(now=self.broker.now)["status"], "SAFETY_CLOSED")

    def test_sub_tick_widening_cannot_ratchet_confirmed_stop(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        initial = self.broker.positions[0].sl
        self.broker.positions[0].sl -= 0.0004
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SAFETY_CLOSED", result)
        closed = [
            json.loads(r[0])
            for r in runner.journal.conn.execute(
                "SELECT payload FROM audit_events WHERE json_extract(payload,'$.kind')='LIFECYCLE'"
            )
        ]
        self.assertEqual(closed[-1]["active"]["confirmed_sl"], initial)

    def test_fresh_journal_never_calls_existing_broker_exposure_flat(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        runner.close()
        self.path = Path(self.temp.name) / "fresh.sqlite3"
        restarted = self.runner()
        start = self.broker.now
        first = restarted.cycle(now=start)
        self.assertEqual(first["position_protection"], "unknown")
        self.broker.tick.time_msc += 181000
        result = restarted.cycle(now=start + timedelta(seconds=181))
        self.assertTrue(result["critical"])
        self.assertEqual(result["observed_positions"], 1)
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_foreign_exposure_does_not_hide_behind_owned_position_protection(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.broker.positions.append(
            NS(
                **(
                    vars(self.broker.positions[0])
                    | {"identifier": 888, "ticket": 888, "magic": 99, "comment": "foreign"}
                )
            )
        )
        first = runner.cycle(now=self.broker.now)
        self.assertEqual(first["status"], "MANAGING")
        self.assertEqual(first["position_protection"], "unknown")
        self.assertEqual(first["owned_position_protection"], "confirmed")
        self.broker.tick.time_msc += 181000
        result = runner.cycle(now=self.broker.now + timedelta(seconds=181))
        self.assertTrue(result["critical"])
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_torn_note_outputs_recover_without_missing_body_or_duplicate_json(self):
        from scripts.c22h4.trade_log import append_note

        path = Path(self.temp.name) / "note.md"
        path.write_text("## partial\n\n")
        path.with_suffix(".jsonl").write_text('{"event_id":"torn"')
        record = dict(event_id="torn", kind="FILLED")
        append_note(path, "entry", "complete entry body", record)
        append_note(path, "entry", "complete entry body", record)
        self.assertEqual(path.read_text().count("complete entry body"), 1)
        rows = [json.loads(line) for line in path.with_suffix(".jsonl").read_text().splitlines()]
        self.assertEqual(rows, [record])

    def test_account_switch_at_final_mutation_gate_never_sends(self):
        runner = self.runner()
        original = runner.journal.audit

        def switched(kind, **facts):
            event = original(kind, **facts)
            if kind == "REQUEST":
                self.broker.account.login = 456
            return event

        with patch.object(runner.journal, "audit", side_effect=switched):
            result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["reason"], "demo_identity_required")
        self.broker.order_send.assert_not_called()
        self.assertIsNotNone(runner.journal.get("active"))

    def test_financial_persistence_failure_blocks_new_mutation(self):
        runner = self.runner()
        original = runner.journal.audit

        def failed(kind, **facts):
            if kind == "REQUEST":
                raise OSError("financial disk failure")
            return original(kind, **facts)

        with patch.object(runner.journal, "audit", side_effect=failed):
            result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "BLOCKED")
        self.broker.order_send.assert_not_called()
        runner.close()
        self.assertEqual(self.runner().cycle(now=self.broker.now)["status"], "UNKNOWN")
        self.broker.order_send.assert_not_called()

    def test_persisted_day_baseline_survives_restart_and_old_latch_is_blocked(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        day = runner.journal.get("day")
        self.assertEqual(day["equity"], 200)
        runner.close()
        self.broker.account.equity = 250
        restarted = self.runner()
        restarted.cycle(now=self.broker.now)
        self.assertEqual(restarted.journal.get("day"), day)
        self.assertEqual(day["account_fingerprint"], restarted.fingerprint)
        restarted.journal.put("day", day | {"source": "restart_equity"})
        self.broker.send(
            dict(action=1, position=777, type=1, volume=0.01, price=self.broker.tick.bid)
        )
        restarted.cycle(now=self.broker.now)
        result = restarted.cycle(now=self.broker.now)
        self.assertEqual(result["reason"], "unproven_day_baseline")

    def test_missing_midnight_baseline_blocks_entry_but_manages_held_position(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        prior_day = runner.journal.get("day")
        later = (self.broker.now + timedelta(days=1)).replace(hour=0, minute=0, second=5)
        self.broker.now = later
        self.broker.tick.time_msc = int(later.timestamp() * 1000)
        self.assertEqual(runner.cycle(now=later)["status"], "MANAGING")
        self.assertEqual(runner.journal.get("day"), prior_day)
        runner.close()
        restarted = self.runner()
        self.assertEqual(restarted.cycle(now=later)["status"], "MANAGING")
        self.broker.send(
            dict(action=1, position=777, type=1, volume=0.01, price=self.broker.tick.bid)
        )
        self.assertEqual(restarted.cycle(now=later)["status"], "CLOSED")
        self.assertEqual(restarted.cycle(now=later)["reason"], "day_start_floating_unknown")
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_audit_is_append_only_and_report_preserves_real_net_costs(self):
        from scripts.demo_runtime.evidence import report
        from scripts.demo_runtime.backup import backup, verify
        import sqlite3

        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.broker.send(
            dict(action=1, position=777, type=1, volume=0.01, price=self.broker.tick.bid)
        )
        self.broker.deals[-1].swap = -0.3
        self.broker.account.balance -= 0.3
        self.broker.account.equity = self.broker.account.balance
        runner.cycle(now=self.broker.now)
        row = report(runner.journal.conn)["cohorts"][0]
        self.assertEqual(row["trades"], 1)
        self.assertAlmostEqual(row["net_pnl"], -1.3)
        self.assertAlmostEqual(row["expectancy_usd"], -1.3)
        self.assertEqual(row["profitability"], "INCONCLUSIVE")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append_only"):
            runner.journal.conn.execute("DELETE FROM audit_events")
        runner.journal.conn.rollback()
        counts = runner.journal.conn.execute("SELECT count(*) FROM audit_events").fetchone()[0]
        for _ in range(8):
            path, manifest = backup(self.path, Path(self.temp.name) / "backups")
        self.assertTrue(manifest["restore_verified"])
        self.assertEqual(verify(path)["audit_events"], counts)
        self.assertEqual(len(list(path.parent.glob("*.sqlite3"))), 7)
        self.assertEqual(len(list(path.parent.glob("*.json"))), 7)

    def test_unreconciled_protection_alert_at_180_seconds_not_hidden_by_heartbeat(self):
        runner = self.runner()
        runner.cycle(now=self.broker.now)
        start = self.broker.now
        self.broker.positions_get = lambda **kwargs: None
        self.assertFalse(runner.cycle(now=start)["critical"])
        self.assertFalse(runner.cycle(now=start + timedelta(seconds=179))["critical"])
        result = runner.cycle(now=start + timedelta(seconds=180))
        self.assertTrue(result["process_alive"])
        self.assertTrue(result["critical"])
        self.assertEqual(result["position_protection"], "unknown")
        alerts = [
            json.loads(r[0]) for r in runner.journal.conn.execute("SELECT payload FROM events")
        ]
        self.assertEqual(sum(e["kind"] == "CRITICAL" for e in alerts), 1)

    def test_closed_m1_invalid_price_rejected_before_aggregation(self):
        rates = [dict(r) for r in self.broker.rates[-30:]]
        rates[0]["high"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid_closed_M1_OHLC"):
            completed_m15_from_m1(rates, now=self.broker.now)
        rates[0]["high"] = rates[0]["low"] - 1
        with self.assertRaisesRegex(ValueError, "invalid_closed_M1_OHLC"):
            completed_m15_from_m1(rates, now=self.broker.now)

    def test_make_shadow_targets_ignore_all_inherited_order_gate_values(self):
        for gate in ("", "0", "1", "true"):
            for target in ("bot-run", "bot-start"):
                output = subprocess.check_output(
                    ["make", "-n", target],
                    text=True,
                    env={"PATH": "/usr/bin:/bin", "MT5_ENABLE_DEMO_ORDER_SEND": gate},
                )
                command = next(
                    line for line in output.splitlines() if "--watch" in line and "python" in line
                )
                self.assertNotIn("--execute", command)
                self.assertIn("MT5_ENABLE_DEMO_ORDER_SEND=0", command)


def policy_v2(now, spec):
    raw = policy() | {"version": 2, "reviewed_utc": now.isoformat()}
    docs = {
        "tariff": {
            "source": "synthetic tariff",
            "unit": "USD_per_lot_round_trip",
            "commission_per_lot": 0.0,
        },
        "spec": {
            "source": "synthetic broker spec",
            "fields": {
                k: getattr(spec, k, 0)
                for k in (
                    "trade_contract_size",
                    "trade_tick_size",
                    "volume_min",
                    "volume_max",
                    "volume_step",
                    "swap_mode",
                    "swap_long",
                    "swap_short",
                    "swap_rollover3days",
                )
            },
        },
        "swap_calendar": {
            "source": "synthetic dated schedule",
            "unit": "USD_per_lot",
            "days": {
                now.date().isoformat(): {
                    "rollover_utc": now.replace(
                        hour=21, minute=0, second=0, microsecond=0
                    ).isoformat(),
                    "buy": -10.0,
                    "sell": -5.0,
                }
            },
        },
    }
    raw["evidence"] = {
        name: {
            "document": doc,
            "sha256": hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest(),
        }
        for name, doc in docs.items()
    }
    return raw


class CostPolicyTests(unittest.TestCase):
    def test_modeled_swap_is_mandatory_and_actual_deal_drift_blocks(self):
        from scripts.demo_runtime.costs import validate_observed_costs
        from tests.demo.test_trial30_demo import Broker, NOW

        raw = policy_v2(NOW, Broker().info)
        entry = NOW.replace(hour=20)
        exit_at = NOW.replace(hour=22)
        deals = [
            NS(
                position_id=777,
                magic=123,
                entry=0,
                type=0,
                volume=0.01,
                time_msc=int(entry.timestamp() * 1000),
                commission=0,
                fee=0,
                swap=0,
            ),
            NS(
                position_id=777,
                magic=0,
                entry=1,
                type=1,
                volume=0.01,
                time_msc=int(exit_at.timestamp() * 1000),
                commission=0,
                fee=0,
                swap=-0.10,
            ),
        ]
        validate_observed_costs(raw, deals, magic=123, now=exit_at)
        deals[-1].swap = -0.20
        with self.assertRaisesRegex(ValueError, "cost_broker_deal_drift"):
            validate_observed_costs(raw, deals, magic=123, now=exit_at)
        raw["evidence"]["swap_calendar"]["document"]["days"] = {}
        with self.assertRaisesRegex(ValueError, "cost_swap_calendar_missing"):
            validate_observed_costs(raw, deals, magic=123, now=exit_at)

    def test_v2_168_hours_c22_only_v1_stays_24_hours(self):
        from tests.demo.test_trial30_demo import Broker, NOW

        raw = policy_v2(NOW, Broker().info)
        for hours, valid in ((24, True), (168, True), (168.001, False)):
            result, _ = validate_policy(
                raw,
                fingerprint=raw["account_fingerprint"],
                now=NOW + timedelta(hours=hours),
                strategy="c22h4",
            )
            self.assertEqual(bool(result), valid)
        self.assertFalse(validate_policy(raw, fingerprint=raw["account_fingerprint"], now=NOW)[0])
        self.assertFalse(
            validate_policy(
                policy(),
                fingerprint=raw["account_fingerprint"],
                now=NOW + timedelta(hours=25),
                strategy="c22h4",
            )[0]
        )

    def test_missing_changed_evidence_and_broker_spec_drift_block(self):
        from tests.demo.test_trial30_demo import Broker, NOW

        broker = Broker()
        for key in ("swap_mode", "swap_long", "swap_short", "swap_rollover3days"):
            setattr(broker.info, key, 0)
        raw = policy_v2(NOW, broker.info)

        def check(p):
            return validate_policy(
                p,
                fingerprint=raw["account_fingerprint"],
                now=NOW,
                strategy="c22h4",
                spec=broker.info,
            )[0]

        self.assertTrue(check(raw))
        self.assertFalse(check(raw | {"evidence": {}}))
        raw["evidence"]["swap_calendar"]["document"]["source"] = "changed"
        self.assertFalse(check(raw))
        raw = policy_v2(NOW, broker.info)
        broker.info.swap_long = -1
        self.assertFalse(check(raw))


class WeeklyEvidenceTests(unittest.TestCase):
    def test_weekly_window_separates_containment_net_from_lifetime(self):
        from scripts.demo_runtime.evidence import report
        from scripts.demo_runtime.journal import Journal
        from tests.demo.test_trial30_demo import NOW

        with TemporaryDirectory() as temp:
            journal = Journal(Path(temp) / "evidence.sqlite3")
            self.addCleanup(journal.close)
            journal.audit_context = dict(release_hash="release", config_hash="config")
            for stamp, kind, net in (
                (NOW, "CLOSED", 3),
                (NOW + timedelta(days=7), "SAFETY_CLOSED", -1),
            ):
                with patch("scripts.demo_runtime.journal.datetime") as clock:
                    clock.now.return_value = stamp
                    journal.audit(
                        "LIFECYCLE",
                        active=dict(cohort_id="release:config"),
                        event=dict(kind=kind, net=net, reason="filled_risk_violation"),
                    )
            weekly = report(journal.conn, since=NOW, until=NOW + timedelta(days=1))["cohorts"][0]
            lifetime = report(journal.conn)["cohorts"][0]
            self.assertEqual(weekly["net_pnl"], 3)
            self.assertEqual(weekly["safety_closures"], 0)
            self.assertEqual(lifetime["net_pnl"], 2)
            self.assertEqual(lifetime["safety_net_pnl"], -1)
            self.assertEqual(lifetime["containment_reasons"], {"filled_risk_violation": 1})
            journal.close()
