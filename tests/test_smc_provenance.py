import unittest

from scripts.smc.provenance import classify_dataset_provenance


class ProvenanceTests(unittest.TestCase):
    def test_missing_coverage_codes_are_distinct(self):
        self.assertEqual(
            classify_dataset_provenance(
                has_m5=False, has_h1=True, has_ticks=False, timezone_aware_utc=True
            ).code,
            "DATA_INSUFFICIENT_M5",
        )
        self.assertEqual(
            classify_dataset_provenance(
                has_m5=True, has_h1=False, has_ticks=False, timezone_aware_utc=True
            ).code,
            "DATA_INSUFFICIENT_H1",
        )
        self.assertEqual(
            classify_dataset_provenance(
                has_m5=True, has_h1=True, has_ticks=False, timezone_aware_utc=False
            ).code,
            "DATA_BAD_TIMEZONE",
        )
        self.assertEqual(
            classify_dataset_provenance(
                has_m5=True,
                has_h1=True,
                has_ticks=True,
                timezone_aware_utc=True,
                is_proxy=True,
                source_label="yfinance",
            ).code,
            "DATA_PROXY_FEED",
        )
        self.assertEqual(
            classify_dataset_provenance(
                has_m5=True, has_h1=True, has_ticks=False, timezone_aware_utc=True
            ).code,
            "DATA_OHLC_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
