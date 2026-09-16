import unittest

from scripts.smc.warmup import (
    H1_WARMUP_BARS,
    M5_WARMUP_BARS,
    assert_warmup_coverage,
    h1_warmup_ok,
    recommended_h1_request_count,
    warmup_coverage_ok,
)


class WarmupConventionTests(unittest.TestCase):
    def test_locked_h1_floor(self):
        self.assertEqual(H1_WARMUP_BARS, 1000)
        self.assertEqual(M5_WARMUP_BARS, 500)
        self.assertFalse(h1_warmup_ok(999))
        self.assertTrue(h1_warmup_ok(1000))
        self.assertTrue(warmup_coverage_ok(500, required=M5_WARMUP_BARS))

    def test_assert_raises_when_short(self):
        with self.assertRaises(ValueError):
            assert_warmup_coverage(list(range(10)), required=20, label="H1")

    def test_recommended_request_includes_extra(self):
        self.assertEqual(recommended_h1_request_count(50), 1050)


if __name__ == "__main__":
    unittest.main()
