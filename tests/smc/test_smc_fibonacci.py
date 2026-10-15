import unittest

from scripts.smc.fibonacci import compute_fibonacci_features


class FibonacciFeatureTests(unittest.TestCase):
    def test_buy_ote_membership_at_boundaries(self):
        # Range 100..0 mirrored as high=100 low=0; entry at 38% from high = 62% retracement
        feat = compute_fibonacci_features(
            direction="BUY",
            swing_high=100.0,
            swing_low=0.0,
            entry=38.0,
        )
        self.assertTrue(feat.available)
        self.assertAlmostEqual(feat.retracement, 0.62)
        self.assertTrue(feat.in_ote)

        feat79 = compute_fibonacci_features(
            direction="BUY",
            swing_high=100.0,
            swing_low=0.0,
            entry=21.0,
        )
        self.assertAlmostEqual(feat79.retracement, 0.79)
        self.assertTrue(feat79.in_ote)

        outside = compute_fibonacci_features(
            direction="BUY",
            swing_high=100.0,
            swing_low=0.0,
            entry=50.0,
        )
        self.assertAlmostEqual(outside.retracement, 0.50)
        self.assertFalse(outside.in_ote)

    def test_zero_width_unavailable_does_not_filter(self):
        feat = compute_fibonacci_features(
            direction="SELL",
            swing_high=10.0,
            swing_low=10.0,
            entry=10.0,
        )
        self.assertFalse(feat.available)
        self.assertIsNone(feat.retracement)
        self.assertFalse(feat.in_ote)


if __name__ == "__main__":
    unittest.main()
