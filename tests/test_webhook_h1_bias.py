"""Unit tests for webhook H1 bias payload parsing."""

from __future__ import annotations

import unittest

from scripts.webhook.h1_bias import parse_h1_bias_fields


class TestParseH1BiasFields(unittest.TestCase):
    def test_missing_keys_unknown(self):
        bias, known = parse_h1_bias_fields({})
        self.assertIsNone(bias)
        self.assertFalse(known)

    def test_explicit_known_with_direction(self):
        bias, known = parse_h1_bias_fields({"h1_bias": "buy", "h1_bias_known": True})
        self.assertEqual(bias, "BUY")
        self.assertTrue(known)

    def test_flat_bias_known(self):
        bias, known = parse_h1_bias_fields({"h1_bias": "FLAT", "h1_bias_known": True})
        self.assertIsNone(bias)
        self.assertTrue(known)

    def test_h1_bias_alone_implies_known(self):
        bias, known = parse_h1_bias_fields({"h1_bias": "SELL"})
        self.assertEqual(bias, "SELL")
        self.assertTrue(known)

    def test_coalesce_prefers_payload_over_live(self):
        from scripts.webhook.h1_bias import coalesce_h1_bias

        bias, known = coalesce_h1_bias(
            {"h1_bias": "BUY", "h1_bias_known": True},
            live_bias="SELL",
            live_known=True,
        )
        self.assertEqual(bias, "BUY")
        self.assertTrue(known)

    def test_coalesce_falls_back_to_live(self):
        from scripts.webhook.h1_bias import coalesce_h1_bias

        bias, known = coalesce_h1_bias({}, live_bias="SELL", live_known=True)
        self.assertEqual(bias, "SELL")
        self.assertTrue(known)


if __name__ == "__main__":
    unittest.main()
