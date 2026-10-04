"""Read-only history probe cannot pass on direction-only or empty evidence."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.ops.c22h4_history_probe import probe
from test_c22h4_demo import CandidateBroker, buy_bars


class HistoryProbeTests(unittest.TestCase):
    def test_matching_bars_pass_and_probe_never_checks_or_sends_order(self):
        broker = CandidateBroker(1)
        with TemporaryDirectory() as tmp:
            archive = Path(tmp) / "archive.csv"
            buy_bars().to_csv(archive)
            result = probe(broker, now=broker.now, archive=archive, output=Path(tmp) / "probe")
            self.assertTrue(result["history_gate"])
            self.assertTrue(result["parity_gate"])
            self.assertEqual(result["admission_divergences"], 0)
        broker.order_send.assert_not_called()
        broker.order_check.assert_not_called()

    def test_no_overlap_cannot_pass(self):
        from scripts.ops.c22h4_history_probe import compare

        source = buy_bars()
        reference = source.copy()
        reference.index += __import__("pandas").Timedelta(days=100)
        _, _, admissions = compare(
            source,
            reference,
            spec=dict(trade_tick_size=0.001, trade_contract_size=100, leverage=2000),
        )
        self.assertTrue(admissions.empty)

    def test_matching_direction_with_different_risk_admission_diverges(self):
        from scripts.ops.c22h4_history_probe import compare

        source = buy_bars()
        reference = source.copy()
        # Same close/RSI/direction/macro, drastically different ATR/cap geometry.
        reference["high"] += 40
        reference["low"] -= 40
        _, directions, admissions = compare(
            source,
            reference,
            spec=dict(trade_tick_size=0.001, trade_contract_size=100, leverage=2000),
        )
        self.assertTrue(directions.empty)
        self.assertTrue(admissions.admission_diverges.any())

    def test_identical_prefix_labels_match_and_small_geometry_drift_is_counted(self):
        from scripts.ops.c22h4_history_probe import compare

        source = buy_bars()
        spec = dict(trade_tick_size=0.001, trade_contract_size=100, leverage=2000)
        _, _, matched = compare(source, source, spec=spec)
        self.assertTrue((matched.evidence == "match").all())
        self.assertFalse(matched.geometry_diverges.any())
        reference = source.copy()
        reference["high"] += 0.05
        reference["low"] -= 0.05
        _, _, changed = compare(source, reference, spec=spec)
        self.assertTrue(changed.geometry_diverges.any())
        self.assertTrue(changed.indicator_diverges.any())
