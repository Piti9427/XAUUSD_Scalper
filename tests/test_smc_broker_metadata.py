"""Foundation: missing broker margin/sizing metadata blocks new risk."""

from __future__ import annotations

import unittest

from scripts.smc.broker_metadata import broker_metadata_allows_new_risk


def _ok_snapshot(**overrides):
    base = {
        "balance": 500.0,
        "equity": 500.0,
        "min_lot": 0.01,
        "max_lot": 10.0,
        "lot_step": 0.01,
        "contract_size": 100.0,
        "margin_free": 480.0,
        "trade_allowed": 1.0,
    }
    base.update(overrides)
    return base


class BrokerMetadataGateTests(unittest.TestCase):
    def test_complete_snapshot_allows(self):
        ok, reason = broker_metadata_allows_new_risk(_ok_snapshot())
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_missing_snapshot_blocks(self):
        ok, reason = broker_metadata_allows_new_risk(None)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_broker_risk_snapshot")

    def test_missing_margin_free_blocks(self):
        snap = _ok_snapshot()
        del snap["margin_free"]
        ok, reason = broker_metadata_allows_new_risk(snap)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_margin_free")

    def test_invalid_contract_blocks(self):
        ok, reason = broker_metadata_allows_new_risk(_ok_snapshot(contract_size=0.0))
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_lot_or_contract_metadata")

    def test_trade_not_allowed_blocks(self):
        ok, reason = broker_metadata_allows_new_risk(_ok_snapshot(trade_allowed=0.0))
        self.assertFalse(ok)
        self.assertEqual(reason, "trade_not_allowed")


if __name__ == "__main__":
    unittest.main()
