"""Opt-in renewal keeps native sender and actual read ownership intact."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.c22_selected.execution import install_execution_review
from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.c22_selected.renewal import _binding
from scripts.c22_selected.trial_costs import build_trial_policy
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_c22_selected_execution import review_fixture
from tests.demo.test_c22_selected_trial_costs import broker_fixture
from tests.demo.test_c22_official_source_packets import captures
from scripts.c22_selected.source_packets import review_source_captures, OFFICIAL_URLS


def raw(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(raw(value)).hexdigest()


class RenewalSenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.broker = SelectedBroker()
        for key, value in dict(
            currency_profit="USD",
            swap_mode=1,
            swap_long=-490.8,
            swap_short=0.0,
            swap_rollover3days=3,
        ).items():
            setattr(self.broker.info, key, value)
        self.initial = self.broker.now
        packet = broker_fixture()
        packet.update(
            account_fingerprint=hashlib.sha256(b"Exness-Demo:123").hexdigest()[:16],
            captured_utc=self.initial.isoformat(),
            history_end_utc=self.initial.isoformat(),
            history_deals_total=1,
            history_deals=[vars(self.broker.deals[0])],
        )
        packet["account"] = dict(currency="USD", balance=200.0, equity=200.0)
        for key in packet["spec"]:
            packet["spec"][key] = getattr(self.broker.info, key)
        sources = {
            key: dict(source=url, checked_utc=self.initial.isoformat())
            for key, url in OFFICIAL_URLS.items()
        }
        self.base = build_trial_policy(raw(packet), now=self.initial, sources=sources)
        self.runner = self.new_runner()
        self.review_path = self.root / "review.json"
        self.review_path.write_bytes(raw(review_fixture(self.runner, self.initial)))
        install_execution_review(self.runner, self.review_path, now=self.initial)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            self.assertEqual(self.runner.cycle(now=self.initial)["status"], "SHADOW_ADMIT")
        self.original_review_sha = hashlib.sha256(self.review_path.read_bytes()).hexdigest()
        self.grant = dict(
            version=1,
            scope="SELECTED_DEMO_SAME_ASSUMPTION_RENEWAL",
            owner_authorized=True,
            owner_instruction="Synthetic test-only standing grant; never installed on VM",
            revoked=False,
            approved_utc=self.initial.isoformat(),
            expires_utc=(self.initial + timedelta(days=30)).isoformat(),
            original_review_sha256=self.original_review_sha,
            original_policy_sha256=digest(self.base),
            binding=_binding(
                dict(
                    policy=self.base,
                    source_sha256=self.runner.release_hash,
                    config_sha256=self.runner.journal.audit_context["config_hash"],
                )
            ),
            limits=dict(
                policy_hours=168,
                prepare_hours=72,
                broker_fresh_seconds=300,
                official_fresh_seconds=86400,
            ),
        )
        self.grant_path = self.root / "grant.json"
        self.grant_path.write_bytes(raw(self.grant))

    def new_runner(self):
        runner = SelectedDemoRunner(
            mt5=self.broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.root / "journal.sqlite3",
            config=selected_config(),
            cost_policy=deepcopy(self.base),
            execute=False,
        )
        self.addCleanup(runner.close)
        return runner

    def enable(self, runner=None):
        runner = runner or self.runner
        runner.configure_renewal(
            grant_path=self.grant_path,
            trusted_grant_sha256=digest(self.grant),
            generation_root=self.root / "generations",
            original_review_path=self.review_path,
            now=self.broker.now,
        )

    def shift(self, delta):
        count = len(self.broker.rates) // 15
        added = int(delta.total_seconds() / 900)
        start = self.broker.rates[-1]["time"] + 60
        for index in range(added):
            price = 200 - (count + index) * 0.01 - (3 if index == added - 1 else 0)
            self.broker.rates.extend(
                dict(
                    time=start + index * 900 + minute * 60,
                    open=price,
                    high=price + 0.5,
                    low=price - 0.5,
                    close=price,
                    tick_volume=1,
                )
                for minute in range(15)
            )
        self.broker.now += delta
        self.broker.tick.time_msc += int(delta.total_seconds() * 1000)
        self.broker.tick.bid = self.broker.rates[-1]["close"]
        self.broker.tick.ask = self.broker.tick.bid + 0.2

    def sources(self):
        value = captures()
        for item in value.values():
            item["requested_utc"] = (self.broker.now - timedelta(seconds=2)).isoformat()
            item["retrieved_utc"] = (self.broker.now - timedelta(seconds=1)).isoformat()
        return value, review_source_captures(value, now=self.broker.now)

    def test_real_sender_renews_then_restarts_after_original_policy_expiry_without_resend(self):
        self.runner.close()
        self.shift(timedelta(days=4))
        self.runner = self.new_runner()
        self.enable()
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            before = self.runner.cycle(now=self.broker.now)
            values, packet = self.sources()
            installed = self.runner.prepare_renewal(
                packet, values, now=self.broker.now, clock=lambda: self.broker.now
            )
        self.assertEqual(before["status"], "SHADOW_ADMIT", before)
        self.assertEqual(installed["status"], "INSTALLED", installed)
        self.assertEqual(
            self.runner.journal.get("selected_execution_review_sha256"), self.original_review_sha
        )
        self.runner.close()
        self.shift(timedelta(days=4))
        restored = self.new_runner()
        self.enable(restored)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            result = restored.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(
            restored.policy["reviewed_utc"], (self.initial + timedelta(days=4)).isoformat()
        )
        self.assertIsNone(restored.journal.get("active"))
        self.assertEqual(
            restored.journal.get("selected_execution_review_sha256"), self.original_review_sha
        )
        self.broker.order_send.assert_not_called()

    def installed(self):
        self.runner.close()
        self.shift(timedelta(days=4))
        self.runner = self.new_runner()
        self.enable()
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            self.runner.cycle(now=self.broker.now)
            values, packet = self.sources()
            result = self.runner.prepare_renewal(
                packet, values, now=self.broker.now, clock=lambda: self.broker.now
            )
        self.assertEqual(result["status"], "INSTALLED", result)
        return self.runner

    def test_real_fill_and_owned_be_continue_after_standing_grant_is_revoked(self):
        self.installed().close()
        self.shift(timedelta(days=4))
        runner = self.new_runner()
        runner.execute = True
        self.enable(runner)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            opened = runner.cycle(now=self.broker.now)
        self.assertEqual(opened["status"], "FILLED", opened)
        pointer = (self.root / "generations/current.json").read_bytes()
        changed = dict(self.grant, revoked=True)
        self.grant_path.write_bytes(raw(changed))
        self.broker.tick.bid -= 10
        self.broker.tick.ask -= 10
        self.broker.next_bar()
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            protected = runner.cycle(now=self.broker.now)
        self.assertEqual(protected["status"], "BE_MOVED", protected)
        self.assertEqual(protected["position_protection"], "confirmed")
        self.assertEqual(protected["execution_review"]["status"], "BLOCKED")
        self.assertEqual(self.broker.order_send.call_count, 2)
        self.assertEqual((self.root / "generations/current.json").read_bytes(), pointer)
        self.assertIsNotNone(runner.journal.get("active"))

    def test_optional_preparation_failure_keeps_old_valid_admission_and_context(self):
        self.runner.close()
        self.shift(timedelta(days=4))
        self.runner = self.new_runner()
        self.enable()
        self.runner.renewal_sources_path = self.root / "missing-source-proof.json"
        old = digest(self.runner.policy)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            result = self.runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(result["renewal"]["status"], "DEFERRED")
        self.assertEqual(digest(self.runner.policy), old)
        self.assertFalse((self.root / "generations/current.json").exists())
        self.assertIsNone(self.runner.journal.get("active"))
        self.broker.order_send.assert_not_called()

    def test_partial_cli_opt_in_never_initializes_a_second_broker_reader(self):
        from scripts.c22_selected.__main__ import main
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import Mock

        sdk = Mock()
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--renewal-grant", "missing.json"], mt5=sdk)
        self.assertEqual(code, 2)
        self.assertEqual(
            json.loads(output.getvalue())["reason"],
            "renewal_runtime_explicit_configuration_required",
        )
        sdk.initialize.assert_not_called()
        sdk.order_send.assert_not_called()

    def test_corrupt_auxiliary_cost_state_on_restart_cannot_abandon_owned_protection(self):
        self.installed().close()
        self.shift(timedelta(days=4))
        runner = self.new_runner()
        runner.execute = True
        self.enable(runner)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            self.assertEqual(runner.cycle(now=self.broker.now)["status"], "FILLED")
        runner.journal.put("selected_cost_generations_v1", {})
        runner.close()
        restored = self.new_runner()
        restored.execute = True
        self.enable(restored)  # Corrupt auxiliary state must not kill startup.
        self.broker.tick.bid -= 10
        self.broker.tick.ask -= 10
        self.broker.next_bar()
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            result = restored.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "BE_MOVED", result)
        self.assertEqual(result["position_protection"], "confirmed")
        # A read-only authority inspection covers review/policy, not mutable
        # cost-state integrity. Restore records the latter independently.
        self.assertEqual(result["execution_review"]["coverage"], "review_and_policy_only")
        self.assertTrue(
            any(
                error["stage"] == "renewal.generation"
                and error["code"] == "cost_generation_state_audit_mismatch"
                and error["details"]["code"] == "cost_generation_state_audit_mismatch"
                for error in result["operational_errors"]
            )
        )
        self.assertEqual(self.broker.order_send.call_count, 2)
        self.assertIsNotNone(restored.journal.get("active"))
        from types import SimpleNamespace

        position = self.broker.positions.pop()
        self.broker.deals.append(
            SimpleNamespace(
                ticket=999,
                position_id=position.identifier,
                time_msc=self.broker.tick.time_msc,
                time=self.broker.tick.time_msc // 1000,
                type=0,
                entry=1,
                volume=0.01,
                magic=0,
                comment="[tp]",
                price=self.broker.tick.ask,
                profit=10.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
            )
        )
        self.broker.account.balance += 10
        self.broker.account.equity = self.broker.account.balance
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            closed = restored.cycle(now=self.broker.now)
            rejected = restored.cycle(now=self.broker.now + timedelta(seconds=1))
        self.assertEqual(closed["status"], "CLOSED", closed)
        self.assertEqual(closed["net"], 10.0)
        self.assertIsNone(restored.journal.get("active"))
        self.assertEqual(rejected["status"], "BLOCKED", rejected)
        self.assertEqual(self.broker.order_send.call_count, 2)

    def test_watching_local_source_bundle_installs_due_generation_without_sdk_side_reader(self):
        import base64

        self.runner.close()
        self.shift(timedelta(days=4))
        self.runner = self.new_runner()
        self.enable()
        values, packet = self.sources()
        path = self.root / "sources.json"
        path.write_bytes(
            raw(
                dict(
                    packet=packet,
                    captures={
                        role: dict(
                            {key: value for key, value in item.items() if key != "body"},
                            body_base64=base64.b64encode(item["body"]).decode(),
                        )
                        for role, item in values.items()
                    },
                )
            )
        )
        self.runner.renewal_sources_path = path
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            result = self.runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(result["renewal"]["status"], "INSTALLED", result)
        self.assertEqual(self.runner.policy["reviewed_utc"], self.broker.now.isoformat())
        self.assertEqual(
            self.runner.journal.get("selected_execution_review_sha256"), self.original_review_sha
        )
        self.broker.order_send.assert_not_called()

    def test_slow_history_cannot_relabel_cached_flat_exposure_as_fresh_for_install(self):
        from types import SimpleNamespace

        self.runner.close()
        self.shift(timedelta(days=4))
        self.runner = self.new_runner()
        self.enable()
        elapsed = [0.0]
        original_history = self.broker.history_deals_get

        def delayed(*args, **kwargs):
            value = original_history(*args, **kwargs)
            elapsed[0] = 180.0
            self.broker.orders = [SimpleNamespace(ticket=12345)]
            return value

        self.broker.history_deals_get = delayed
        original_tick = self.broker.symbol_info_tick

        def tick(*args, **kwargs):
            value = original_tick(*args, **kwargs)
            value.time_msc = int(
                (self.broker.now + timedelta(seconds=elapsed[0])).timestamp() * 1000
            )
            return value

        self.broker.symbol_info_tick = tick
        with patch(
            "scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: 100 + elapsed[0]
        ):
            self.runner.cycle(now=self.broker.now)
            end = self.broker.now + timedelta(seconds=180)
            values, _ = self.sources()
            for item in values.values():
                item["requested_utc"] = (end - timedelta(seconds=2)).isoformat()
                item["retrieved_utc"] = (end - timedelta(seconds=1)).isoformat()
            packet = review_source_captures(values, now=end)
            rejected = self.runner.prepare_renewal(packet, values, now=end, clock=lambda: end)
        self.assertEqual(rejected["status"], "DEFERRED", rejected)
        self.assertEqual(rejected["reason"], "generation_fresh_flat_window_required")
        self.assertFalse((self.root / "generations/current.json").exists())
        self.assertEqual(self.runner.policy, self.base)
        self.assertEqual(len(self.broker.orders), 1)
        self.broker.order_send.assert_not_called()

    def test_cli_restart_can_read_complete_generation_when_legacy_policy_file_is_missing(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import Mock
        from scripts.c22_selected.__main__ import main

        self.installed().close()
        self.shift(timedelta(days=4))
        self.broker.initialize = Mock(return_value=True)
        self.broker.shutdown = Mock()
        config = self.root / "config.json"
        config.write_bytes(raw(selected_config()))
        output = StringIO()
        with (
            patch(
                "scripts.smc.mt5_init.resolve_mt5_account_kwargs",
                return_value={
                    "login": 123,
                    "server": "Exness-Demo",
                    "password": "synthetic-test-only",
                },
            ),
            patch("scripts.demo_runtime.cli.clock_now", return_value=self.broker.now),
            patch("scripts.demo_runtime.runner.time.monotonic", return_value=100),
            redirect_stdout(output),
        ):
            code = main(
                [
                    "--once",
                    "--config",
                    str(config),
                    "--journal",
                    str(self.root / "journal.sqlite3"),
                    "--cost-policy",
                    str(self.root / "missing-legacy.json"),
                    "--execution-review",
                    str(self.review_path),
                    "--renewal-grant",
                    str(self.grant_path),
                    "--renewal-grant-sha256",
                    digest(self.grant),
                    "--renewal-generation-root",
                    str(self.root / "generations"),
                    "--renewal-sources",
                    str(self.root / "missing-source.json"),
                ],
                mt5=self.broker,
                runner_class=lambda **kwargs: SelectedDemoRunner(
                    **(kwargs | {"account_guard_dir": self.root})
                ),
            )
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue().strip().splitlines()[-1])
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(
            result["execution_review"]["policy_reviewed_utc"],
            (self.initial + timedelta(days=4)).isoformat(),
        )
        self.assertTrue(
            any(error["stage"] == "cli.policy_reload" for error in result["operational_errors"])
        )
        self.assertEqual(self.broker.initialize.call_count, 1)
        self.broker.order_send.assert_not_called()
