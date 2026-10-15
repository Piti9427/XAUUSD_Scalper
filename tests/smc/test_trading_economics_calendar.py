import unittest
from datetime import datetime, timezone

from scripts.trading_economics_calendar import build_calendar_artifact


class CalendarArtifactTests(unittest.TestCase):
    def test_filters_usd_high_impact_and_emits_utc_pine(self):
        rows = [
            {
                "event_id": "nfp",
                "event_time_utc": "2026-09-04T12:30:00Z",
                "title": "NFP",
                "currency": "USD",
                "impact": 3,
            },
            {
                "event_id": "eur",
                "event_time_utc": "2026-09-04T10:00:00Z",
                "title": "EU",
                "currency": "EUR",
                "impact": 3,
            },
        ]
        artifact = build_calendar_artifact(
            rows,
            datetime(2026, 9, 1, tzinfo=timezone.utc),
            datetime(2026, 9, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(1, artifact.event_count)
        self.assertIn('timestamp("UTC", 2026, 9, 4, 12, 30)', artifact.pine)
        self.assertEqual(64, len(artifact.sha256))

    def test_rejects_naive_event_time(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            build_calendar_artifact(
                [
                    {
                        "event_id": "x",
                        "event_time_utc": "2026-09-04T12:30:00",
                        "title": "x",
                        "currency": "USD",
                        "impact": 3,
                    }
                ],
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            )

    def test_rejects_usd_high_impact_event_outside_coverage(self):
        row = {
            "event_id": "x",
            "event_time_utc": "2026-10-01T12:30:00Z",
            "title": "x",
            "currency": "USD",
            "impact": 3,
        }
        with self.assertRaisesRegex(ValueError, "outside"):
            build_calendar_artifact(
                [row],
                datetime(2026, 9, 1, tzinfo=timezone.utc),
                datetime(2026, 9, 30, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
