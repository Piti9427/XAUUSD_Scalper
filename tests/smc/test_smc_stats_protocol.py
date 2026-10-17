import unittest

from scripts.smc.stats_protocol import sample_verdict, wilson_interval


class StatsProtocolTests(unittest.TestCase):
    def test_wilson_is_deterministic(self):
        a = wilson_interval(wins=3, n=4)
        b = wilson_interval(wins=3, n=4)
        self.assertEqual(a, b)
        self.assertGreater(a.lower, 0.0)
        self.assertLess(a.upper, 1.0)

    def test_few_trades_inconclusive(self):
        self.assertEqual(sample_verdict(n=10), "INCONCLUSIVE")
        self.assertEqual(sample_verdict(n=100), "EVALUABLE")


if __name__ == "__main__":
    unittest.main()
