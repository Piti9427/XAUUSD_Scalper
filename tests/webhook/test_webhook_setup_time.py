"""UTC event-time parsing for SETUP_PENDING admission."""

import unittest
from datetime import datetime, timezone

from scripts.webhook.setup_time import parse_setup_event_time


class SetupTimeParseTests(unittest.TestCase):
    def test_iso_naive_becomes_utc(self):
        dt = parse_setup_event_time("2026-03-02 08:15:00")
        self.assertEqual(dt, datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc))

    def test_epoch_ms(self):
        # 2026-03-02 08:15:00 UTC
        ms = 1772439300000
        dt = parse_setup_event_time(ms)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt.year, 2026)

    def test_missing_uses_fallback(self):
        fb = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(parse_setup_event_time(None, fallback_now=fb), fb)

    def test_invalid_uses_fallback(self):
        fb = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(parse_setup_event_time("not-a-time", fallback_now=fb), fb)


if __name__ == "__main__":
    unittest.main()
