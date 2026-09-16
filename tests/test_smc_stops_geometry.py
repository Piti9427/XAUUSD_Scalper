"""Tests for broker stops_level geometry gate."""

from __future__ import annotations

import unittest

from scripts.smc.stops_geometry import (
    min_stop_distance_price,
    pending_stops_geometry_allows,
    sl_modify_freeze_allows,
)


class StopsGeometryTests(unittest.TestCase):
    def test_min_distance_from_points(self):
        self.assertAlmostEqual(
            min_stop_distance_price(point=0.01, stops_level=50),
            0.5,
        )

    def test_sl_inside_stops_level_blocks(self):
        ok, reason = pending_stops_geometry_allows(
            entry_price=2000.0,
            sl_price=1999.9,
            tp_price=2010.0,
            point=0.01,
            stops_level=50,  # 0.50 min
        )
        self.assertFalse(ok)
        self.assertIn("sl_inside_stops_level", reason)

    def test_valid_geometry_allows(self):
        ok, reason = pending_stops_geometry_allows(
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            point=0.01,
            stops_level=50,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_missing_point_blocks(self):
        ok, reason = pending_stops_geometry_allows(
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=None,
            point=0.0,
            stops_level=50,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_point")

    def test_freeze_level_blocks_near_market_sl(self):
        ok, reason = sl_modify_freeze_allows(
            new_sl=2000.0,
            market_bid=2000.1,
            market_ask=2000.3,
            point=0.01,
            freeze_level=50,  # 0.50
        )
        self.assertFalse(ok)
        self.assertIn("sl_inside_freeze_level", reason)

    def test_freeze_level_zero_allows(self):
        ok, reason = sl_modify_freeze_allows(
            new_sl=2000.0,
            market_bid=2000.1,
            market_ask=2000.3,
            point=0.01,
            freeze_level=0,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
