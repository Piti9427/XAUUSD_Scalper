"""Public contract/parity boundaries; fixtures never evaluate economics."""

from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.qualification.c22 import contract


DOMAINS = {
    "buy_target_rr": [1.35, 1.5, 2.0, 3.0],
    "target_rr": [1.25, 1.35, 1.4, 1.45, 1.5, 2.0],
    "cooldown_bars": [0, 1, 2, 4],
    "stop_atr": [1.5, 2.0, 2.5],
    "buy_stop_atr": [1.5, 2.0, 2.5],
    "protect_after_r": [0.5, 1.0, 1.5],
    "buy_protect_mode": ["off", "break_even"],
}
RULES = dict(
    failed_closes=0, reset_after_exit=False, stagnant_bars=0,
    entry_mode="immediate", stop_mode="atr", protect_mode="break_even",
    entry_guard="off", buy_pause_drawdown=0.0, risk_mode="static", risk_cap=0.1,
    daily_loss_limit=0.1, target_atr=3.0, min_depth_atr=0.0, target_rr=1.35,
    cooldown_bars=2, session_mode="all", max_daily_losses=2, protect_after_r=1.0,
    stop_atr=2.5, buy_stop_atr=2.5, buy_target_rr=3.0,
    buy_protect_mode="break_even", sizing_mode="fixed", holding_mode="legacy",
    buy_stop_mode=None, buy_risk_cap=None, buy_sizing_mode=None, sell_stop_mode=None,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:16]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False))


def events(role="research", source="1" * 64):
    return {
        "schema_version": 1,
        "candidate_id": identity(RULES),
        "implementation": {"role": role, "source_sha256": source,
                           "source_path": "research.py" if role == "research" else "runtime.py"},
        "context": {key: "3" * 64 for key in (
            "bars_sha256", "quotes_sha256", "spec_sha256", "costs_sha256",
            "account_state_sha256", "day_state_sha256",
        )},
        "events": [
            dict(event_id="buy-entry", time_utc="2026-10-26T23:45:00+00:00",
                 kind="admission", side="BUY", entry=3000.1, stop=2990.0,
                 target=3030.4, admitted=True, reason="admitted", risk_usd=10.2,
                 cooldown_until_utc=None, protection="inactive", net_usd=None),
            dict(event_id="negative-be", time_utc="2026-10-27T00:00:00+00:00",
                 kind="protection", side="BUY", entry=3000.1, stop=3000.2,
                 target=3030.4, admitted=False, reason="negative_net_be",
                 risk_usd=10.2, cooldown_until_utc="2026-10-27T00:30:00+00:00",
                 protection="done", net_usd=-0.01),
            dict(event_id="sell-rejected", time_utc="2026-10-27T00:15:00+00:00",
                 kind="admission", side="SELL", entry=3005.0, stop=3015.0,
                 target=2991.5, admitted=False, reason="cooldown", risk_usd=10.2,
                 cooldown_until_utc="2026-10-27T00:30:00+00:00",
                 protection="inactive", net_usd=None),
        ],
    }


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = []
        for values in product(*DOMAINS.values()):
            rules = RULES | dict(zip(DOMAINS, values))
            cls.cases.append({"name": identity(rules), "rules": rules})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.campaign = self.root / "runs/campaign"
        self.patcher = patch.object(contract, "ROOT", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        seed = self.root / "config/research-c22-terminal-profit-9e511d195c52ef3d.json"
        save(seed, dict(strategy="reward156", formula="archived", rsi_period=7,
                        rsi_threshold=30, sell_lookback=48, sell_ema=50,
                        macro_span=200, entry_session="all"))
        source = self.root / "scripts/c22h4/strategy.py"
        source.parent.mkdir(parents=True)
        source.write_text("# frozen source fixture\n")
        manifest = self.root / "runs/c22-real-data-audit-2026-10-24/input/manifest.json"
        save(manifest, dict(first_quote_utc="2024-09-01T22:05:06.129Z",
                            last_quote_utc="2026-10-23T20:57:59.517Z", ticks=171171013))
        catalog = dict(schema=1, axes=list(DOMAINS), finite_domain=5184, cases=self.cases)
        save(self.campaign / "catalog.json", catalog)
        self.protocol = dict(
            schema=1, algorithm="exhaustive_native_grid_v1",
            sources={str(p.relative_to(self.root)): digest(p) for p in [seed, source]},
            input_hashes={"tape/time.npy": "4" * 64, "bars.csv": "5" * 64},
            input_manifest_sha256=digest(manifest), parent_complete_sha256="6" * 64,
            parent_results_sha256="7" * 64, parent_audit_sha256="8" * 64,
            parent_cell_bindings={}, broker={"swap_mode": 1},
            views={"base": {}, "stress": {}, "fee": {}},
            start="2024-09-01T00:00:00+00:00", end="2026-10-24T00:00:00+00:00",
            original_floors={}, benchmark_hashes={}, domains=DOMAINS,
            finite_domain=5184, initial=identity(RULES), lanes=["profit", "repair"],
            risk_fields=["dd", "recovery", "severity", "streak"],
            catalog_sha256=digest(self.campaign / "catalog.json"), batch_size=32,
            cost_status="COST_INCONCLUSIVE", holdout=False, claim="frozen grid only",
        )
        save(self.campaign / "protocol.json", self.protocol)
        save(self.campaign / "checkpoint.json", dict(
            protocol_sha256=digest(self.campaign / "protocol.json"),
            selected={"profit": identity(RULES), "repair": identity(RULES)},
            status="PARTIAL", visited_cases=123, finite_domain=5184,
        ))

    def test_partial_manifest_preserves_native_rules_and_large_input_declarations(self):
        report = contract.build_manifest(self.campaign)
        self.assertEqual(report["status"], "PROVISIONAL")
        self.assertEqual(report["candidate_id"], identity(RULES))
        manifest = report["data"]["manifest"]
        self.assertEqual(manifest["rules"], RULES)
        self.assertFalse(manifest["runtime_qualified"])
        self.assertEqual(manifest["adapter_parity"], "NOT_TESTED")
        self.assertEqual(manifest["inputs"]["hash_status"], "DECLARED_NOT_REHASHED")
        gaps = {row["capability"] for row in report["data"]["compatibility"] if row["status"] == "GAP"}
        self.assertTrue({"candidate_contract", "daily_loss_count", "post_loss_cooldown", "buy_protection"} <= gaps)
        self.assertTrue({"detector_rsi_period", "detector_rsi_threshold", "detector_sell_lookback"} <= gaps)

    def test_source_drift_and_catalog_tamper_fail_closed(self):
        source = self.root / "scripts/c22h4/strategy.py"
        source.write_text("# changed source\n")
        with self.assertRaisesRegex(ValueError, "[Dd]rift|hash"):
            contract.build_manifest(self.campaign)

    def test_unknown_missing_and_wrong_type_rule_fields_fail_closed(self):
        for change in (lambda r: r.update(unknown=1), lambda r: r.pop("cooldown_bars"),
                       lambda r: r.update(max_daily_losses=True)):
            with self.subTest(change=change):
                cases = deepcopy(self.cases)
                target = next(c for c in cases if c["name"] == identity(RULES))
                change(target["rules"])
                target["name"] = identity(target["rules"])
                catalog = dict(schema=1, axes=list(DOMAINS), finite_domain=5184, cases=cases)
                save(self.campaign / "catalog.json", catalog)
                self.protocol["catalog_sha256"] = digest(self.campaign / "catalog.json")
                save(self.campaign / "protocol.json", self.protocol)
                with self.assertRaises(ValueError):
                    contract.build_manifest(self.campaign, target["name"])

    def test_unknown_candidate_or_unbound_final_audit_cannot_freeze(self):
        with self.assertRaisesRegex(ValueError, "[Cc]andidate"):
            contract.build_manifest(self.campaign, "0" * 16)
        save(self.campaign / "independent-verification.json", {"status": "PASS"})
        report = contract.build_manifest(self.campaign)
        self.assertEqual(report["status"], "PROVISIONAL")
        self.assertIn("FINAL_AUDIT_NOT_BOUND", report["reasons"])

    def finish_fixture(self):
        selected = {"profit": identity(RULES), "repair": identity(RULES)}
        save(self.campaign / "results.json", dict(status="EXHAUSTIVE_COMPLETE", selected=selected))
        complete = dict(status="EXHAUSTIVE_COMPLETE", visited_cases=5184,
                        processed_batches=162, selected=selected, fresh_repeats=6,
                        artifacts={name: digest(self.campaign / name) for name in (
                            "protocol.json", "catalog.json", "results.json")})
        save(self.campaign / "COMPLETE.json", complete)
        audit_source = self.root / "scripts/research/c22_exhaustive_verify.py"
        helper_source = self.root / "scripts/research/c22_learning_verify.py"
        audit_source.parent.mkdir(parents=True, exist_ok=True)
        audit_source.write_text("# independent audit fixture\n")
        helper_source.write_text("# independent helper fixture\n")
        audit = dict(status="PASS", finite_domain=5184, visited_cases=5184,
                     processed_batches=162, raw_cells=15552, raw_qualified=1,
                     cent_cells=3, cells=15555, selected=selected,
                     parent_completion_sha256=digest(self.campaign / "COMPLETE.json"),
                     input_manifest_sha256=self.protocol["input_manifest_sha256"],
                     source_sha256=digest(audit_source), helper_sha256=digest(helper_source),
                     independent_full_tick_dd={f"{identity(RULES)}-{view}-{guard}": {"max_dd_pct": 1.0}
                                              for view in ("base", "stress", "fee")
                                              for guard in ("raw", "cent")})
        save(self.campaign / "independent-verification.json", audit)
        return audit

    def test_final_selected_candidate_binds_matching_complete_audit_without_runtime_claim(self):
        self.finish_fixture()
        report = contract.build_manifest(self.campaign)
        self.assertEqual(report["status"], "RESEARCH_BOUND")
        self.assertTrue(report["data"]["manifest"]["research_audit_bound"])
        self.assertFalse(report["data"]["manifest"]["runtime_qualified"])
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(report["data"]["manifest"]["data_cutoff_utc"], "2026-10-24T00:00:00+00:00")

    def test_incomplete_or_stale_pass_audit_cannot_bind(self):
        for key, value in (("raw_cells", 15551), ("cent_cells", 0),
                           ("parent_completion_sha256", "0" * 64),
                           ("independent_full_tick_dd", {})):
            with self.subTest(field=key):
                audit = self.finish_fixture()
                audit[key] = value
                save(self.campaign / "independent-verification.json", audit)
                with self.assertRaisesRegex(ValueError, "binding"):
                    contract.build_manifest(self.campaign)

    def test_audited_unselected_profile_remains_provisional(self):
        self.finish_fixture()
        other = next(case["name"] for case in self.cases if case["name"] != identity(RULES))
        report = contract.build_manifest(self.campaign, other)
        self.assertEqual(report["status"], "PROVISIONAL")
        self.assertIn("CANDIDATE_NOT_FINAL_SELECTION", report["reasons"])

    def test_final_metadata_above_32_mib_is_bound_without_large_input_rehash(self):
        self.finish_fixture()
        results = self.campaign / "results.json"
        remaining = 33 * 1024 * 1024 - results.stat().st_size
        with results.open("ab") as stream:
            block = b" " * (1024 * 1024)
            while remaining:
                piece = block[:min(remaining, len(block))]
                stream.write(piece)
                remaining -= len(piece)
        complete_path = self.campaign / "COMPLETE.json"
        complete = json.loads(complete_path.read_text())
        complete["artifacts"]["results.json"] = digest(results)
        save(complete_path, complete)
        audit_path = self.campaign / "independent-verification.json"
        audit = json.loads(audit_path.read_text())
        audit["parent_completion_sha256"] = digest(complete_path)
        save(audit_path, audit)
        report = contract.build_manifest(self.campaign)
        self.assertEqual(report["status"], "RESEARCH_BOUND")
        refs = report["data"]["manifest"]["final_artifacts"]
        result_ref = next(ref for ref in refs if ref["path"] == str(results.resolve()))
        self.assertGreater(result_ref["size_bytes"], 32 * 1024 * 1024)
        self.assertEqual(result_ref["hash_status"], "VERIFIED")
        self.assertEqual(report["data"]["manifest"]["inputs"]["hash_status"], "DECLARED_NOT_REHASHED")

    def test_metadata_above_256_mib_is_rejected_before_json_read(self):
        catalog = self.campaign / "catalog.json"
        with catalog.open("r+b") as stream:
            stream.truncate(256 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "bounded hash limit"):
            contract.build_manifest(self.campaign)


class EventParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reference = self.root / "reference.json"
        self.observed = self.root / "runtime.json"
        self.research_source = self.root / "research.py"
        self.runtime_source = self.root / "runtime.py"
        self.research_source.write_text("# research fixture source\n")
        self.runtime_source.write_text("# independent adapter fixture source\n")
        self.ref = events(source=digest(self.research_source))
        self.obs = self.adapter_events()
        save(self.reference, self.ref)
        save(self.observed, self.obs)

    def adapter_events(self):
        return events("runtime_adapter", digest(self.runtime_source))

    def compare(self):
        save(self.observed, self.obs)
        return contract.compare_events(self.reference, self.observed)

    def test_independent_adapter_matching_events_pass_code_agreement_only(self):
        report = self.compare()
        self.assertEqual(report["status"], "PARITY_PASS")
        self.assertFalse(report["execution_authorized"])
        self.assertEqual(report["coverage"]["events_compared"], 3)
        self.assertFalse(report["data"]["broker_fill_parity"])

    def test_changed_buy_sell_geometry_admission_risk_cooldown_or_protection_fails(self):
        for index, key, value in (
            (0, "stop", 2989.99), (2, "target", 2991.49), (2, "admitted", True),
            (0, "risk_usd", 10.21), (1, "cooldown_until_utc", "2026-10-27T00:15:00+00:00"),
            (1, "protection", "inactive"), (1, "net_usd", 0.0),
        ):
            with self.subTest(field=key):
                self.obs = self.adapter_events()
                self.obs["events"][index][key] = value
                report = self.compare()
                self.assertEqual(report["status"], "PARITY_FAIL")
                self.assertTrue(report["data"]["mismatches"])

    def test_self_same_source_or_missing_adapter_never_passes(self):
        self.assertEqual(contract.compare_events(self.reference, self.reference)["status"], "NOT_TESTED")
        self.obs["implementation"]["source_sha256"] = self.ref["implementation"]["source_sha256"]
        self.obs["implementation"]["source_path"] = self.ref["implementation"]["source_path"]
        self.assertEqual(self.compare()["status"], "NOT_TESTED")
        self.obs = self.adapter_events()
        self.obs["implementation"]["role"] = "research"
        self.assertEqual(self.compare()["status"], "GAP")

    def test_context_mismatch_is_not_strategy_parity(self):
        self.obs["context"]["quotes_sha256"] = "4" * 64
        self.assertEqual(self.compare()["status"], "GAP")

    def test_missing_unknown_naive_nonfinite_duplicate_and_unordered_events_reject(self):
        for mutate in (
            lambda d: d.update(unknown="field"),
            lambda d: d["events"][0].pop("risk_usd"),
            lambda d: d["events"][0].update(time_utc="2026-10-26T23:45:00"),
            lambda d: d["events"][0].update(risk_usd=float("nan")),
            lambda d: d["events"].append(deepcopy(d["events"][0])),
            lambda d: d["events"].reverse(),
        ):
            with self.subTest(mutate=mutate):
                self.obs = self.adapter_events()
                mutate(self.obs)
                self.observed.write_text(json.dumps(self.obs))
                report = contract.compare_events(self.reference, self.observed)
                self.assertEqual(report["status"], "INVALID")

    def test_empty_events_and_wrong_candidate_never_pass(self):
        self.obs["events"] = []
        self.ref["events"] = []
        save(self.reference, self.ref)
        self.assertEqual(self.compare()["status"], "NOT_TESTED")
        self.obs = self.adapter_events()
        self.obs["candidate_id"] = "0" * 16
        self.assertEqual(self.compare()["status"], "GAP")

    def test_forged_implementation_source_or_admitted_without_geometry_rejects(self):
        self.obs["implementation"]["source_sha256"] = "0" * 64
        self.assertEqual(self.compare()["status"], "INVALID")
        self.obs = self.adapter_events()
        self.obs["events"][0]["stop"] = None
        self.assertEqual(self.compare()["status"], "INVALID")

    def test_missing_observed_artifact_is_not_tested(self):
        self.observed.unlink()
        report = contract.compare_events(self.reference, self.observed)
        self.assertEqual(report["status"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
