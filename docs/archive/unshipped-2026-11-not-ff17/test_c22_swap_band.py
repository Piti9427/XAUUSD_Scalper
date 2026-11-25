"""Owner decision 2026-11-12: tolerate small broker swap-rate drift (selected sender only)."""

from datetime import timedelta
from types import SimpleNamespace as NS
import unittest

from scripts.demo_runtime import costs
from scripts.c22_selected.strategy import SelectedStrategy
from tests.demo.test_c22_cost_diagnostics import FIELDS, NOW, v2_policy
from tests.demo.test_trial30_demo import policy


def validate(spec, **kw):
    return costs.validate_policy(v2_policy(), fingerprint=policy()["account_fingerprint"], now=NOW,
                                 strategy="c22h4", spec=NS(**spec), diagnostics={}, **kw)


def deal(ident, entry, typ, ms, *, swap=0.0, volume=0.01, magic=22261025):
    return NS(position_id=ident, entry=entry, type=typ, time_msc=ms, volume=volume, magic=magic,
              swap=swap, commission=0.0, fee=0.0)


class SwapBandTests(unittest.TestCase):
    def test_exact_match_is_still_the_default(self):
        cost, status = validate(dict(FIELDS, swap_long=-498.9))
        self.assertEqual((cost, status), ({}, "invalid_or_stale"))

    def test_observed_drift_within_band_is_accepted(self):
        for observed in (-498.9, -490.0, -492.0, -466.3, -515.3):   # <=5% of -490.8 either way
            with self.subTest(observed=observed):
                cost, status = validate(dict(FIELDS, swap_long=observed), swap_band=0.05)
                self.assertEqual(status, "attested_demo_assumptions")

    def test_drift_beyond_band_blocks_with_mismatch_diagnostic(self):
        diagnostics = {}
        cost, status = costs.validate_policy(v2_policy(), fingerprint=policy()["account_fingerprint"], now=NOW,
                                             strategy="c22h4", spec=NS(**dict(FIELDS, swap_long=-520.0)),
                                             diagnostics=diagnostics, swap_band=0.05)
        self.assertEqual(status, "invalid_or_stale")
        self.assertEqual(diagnostics["code"], "cost_spec_mismatch")
        self.assertEqual(diagnostics["field"], "swap_long")

    def test_zero_stored_swap_must_stay_zero(self):
        cost, status = validate(dict(FIELDS, swap_short=-1.0), swap_band=0.05)
        self.assertEqual(status, "invalid_or_stale")

    def test_other_fields_stay_exact_under_band(self):
        for key, value in (("swap_rollover3days", 5), ("volume_step", 0.02), ("trade_contract_size", 10.0),
                           ("swap_mode", 2)):
            with self.subTest(field=key):
                cost, status = validate(dict(FIELDS, **{key: value}), swap_band=0.05)
                self.assertEqual(status, "invalid_or_stale")

    def test_band_must_be_a_small_nonnegative_number(self):
        for bad in (-0.01, 0.2, float("nan")):
            with self.subTest(band=bad):
                with self.assertRaises(ValueError):
                    validate(dict(FIELDS), swap_band=bad)

    def observed_case(self, observed_swap, **kw):
        cost, _ = validate(dict(FIELDS), swap_band=0.05)
        rollover = NOW.replace(hour=21)
        opened = int((rollover - timedelta(hours=2)).timestamp() * 1000)
        closed = int((rollover + timedelta(hours=1)).timestamp() * 1000)
        deals = [deal(7, 0, 0, opened), deal(7, 1, 1, closed, swap=observed_swap)]
        return costs.validate_observed_costs(cost, deals, magic=22261025, now=NOW.replace(hour=23), **kw)

    def test_observed_deal_swap_drift(self):
        # Calendar BUY = -49.08 USD/lot -> expected -0.4908 for 0.01 lot.
        self.observed_case(-0.4908)                                   # exact, no band
        with self.assertRaises(ValueError):
            self.observed_case(-0.60)                                 # beyond $0.02, no band
        self.observed_case(-0.5121, swap_band=0.05)                   # 4.3% over, $0.021 -> accepted with band
        with self.assertRaises(ValueError):
            self.observed_case(-0.60, swap_band=0.05)                 # 22% over -> still blocks

    def test_only_selected_strategy_opts_in(self):
        self.assertEqual(SelectedStrategy.swap_band, 0.05)


class SelectedAdmissionSwapDriftTests(unittest.TestCase):
    """End to end: broker swap moves after the policy was reviewed."""

    def run_case(self, factor):
        from tests.demo.test_c22_selected_intrabar_be import SelectedIntrabarBeTests
        from tests.demo.test_c22_selected_armed_trial import monday_broker
        case = SelectedIntrabarBeTests("test_management_off_is_identical_to_native")
        case.setUp()
        self.addCleanup(case.temp.cleanup)
        broker = monday_broker(1)
        runner = case.runner(broker, f"drift-{factor}", management=None)
        broker.info.swap_long = broker.info.swap_long * factor
        return runner.cycle(now=broker.now)

    def test_drift_within_band_still_fills(self):
        self.assertEqual(self.run_case(1.016)["status"], "FILLED")

    def test_drift_beyond_band_blocks_entry(self):
        result = self.run_case(1.08)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "cost_policy_invalid_or_stale")


if __name__ == "__main__":
    unittest.main()
