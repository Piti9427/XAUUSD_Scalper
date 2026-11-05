"""Actual source bytes, rather than a refreshed timestamp, establish evidence."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import unittest

from tests.demo.test_c22_selected_trial_costs import NOW


def captures():
    bodies = {
        "tariff": b"<h1>Trading accounts: Standard</h1><dt>Commission</dt><dd>No commission</dd>",
        "swap": (
            b"<p>MetaTrader platforms calculate them in points.</p><table><tr>"
            b"<td>Metals (commodities)</td><td>21:00 GMT+0 (summer) / 22:00 GMT+0 (winter), Mon-Fri</td>"
            b"<td>Wednesday</td><td>None weekdays; not applied Sat-Sun</td></tr></table>"
            b"<p>There might be additional changes in the swap schedule due to public/bank holidays.</p>"
        ),
        "calendar": (
            b"<h1>Instrument trading hours</h1><table><tr><td>Summer</td><td>Second Sunday in March</td>"
            b"<td>First Sunday in November</td></tr><tr><td>Winter</td><td>First Sunday in November</td>"
            b"<td>Second Sunday in March</td></tr></table><p>Most instruments follow US DST.</p>"
        ),
    }
    from scripts.c22_selected.source_packets import OFFICIAL_URLS

    return {
        role: dict(
            source=OFFICIAL_URLS[role],
            final_url=OFFICIAL_URLS[role],
            http_status=200,
            content_type="text/html; charset=utf-8",
            body=body,
            requested_utc=(NOW - timedelta(seconds=2)).isoformat(),
            retrieved_utc=(NOW - timedelta(seconds=1)).isoformat(),
            content_sha256=hashlib.sha256(body).hexdigest(),
        )
        for role, body in bodies.items()
    }


class OfficialSourcePacketTests(unittest.TestCase):
    def test_current_explicit_claims_produce_hash_bound_assumptions_without_entitlement(self):
        from scripts.c22_selected.source_packets import review_source_captures, sources_for_policy

        value = captures()
        original = deepcopy(value)
        result = review_source_captures(value, now=NOW)
        self.assertEqual(result["status"], "VALIDATED_PUBLISHED_ASSUMPTIONS", result)
        self.assertEqual(result["claims"]["commission_per_lot"], 0)
        self.assertEqual(result["claims"]["triple_weekday_mt5"], 3)
        self.assertEqual(
            result["claims"]["calendar_formula"], "REGULAR_POINTS_NY17_WED3_WEEKEND0_V1"
        )
        self.assertEqual(result["swap_entitlement"], "UNKNOWN")
        self.assertEqual(result["economic_qualification"], "COST_INCONCLUSIVE")
        self.assertFalse(result["broker_holiday_exceptions_verified"])
        self.assertFalse(result["execution_authorized"])
        sources = sources_for_policy(result, value, now=NOW)
        self.assertEqual(sources["tariff"]["checked_utc"], value["tariff"]["retrieved_utc"])
        self.assertEqual(
            result["sources"]["swap"]["content_sha256"], value["swap"]["content_sha256"]
        )
        self.assertEqual(value, original)

    def test_timestamp_only_html_shell_and_changed_or_conflicting_claims_defer(self):
        from scripts.c22_selected.source_packets import review_source_captures

        for kind in ("shell", "changed", "ambiguous", "hidden", "missing"):
            with self.subTest(kind=kind):
                value = captures()
                if kind == "shell":
                    value["tariff"]["body"] = b"<html><div id='app'></div></html>"
                elif kind == "changed":
                    value["tariff"]["body"] = (
                        b"<h1>Trading accounts: Standard</h1><p>Commission</p><p>USD 1</p>"
                    )
                elif kind == "ambiguous":
                    value["tariff"]["body"] += b"<p>Commission</p><p>USD 1</p>"
                elif kind == "hidden":
                    value["tariff"]["body"] = (
                        b"<script>Trading accounts: Standard Commission No commission</script>"
                    )
                else:
                    del value["tariff"]
                if "tariff" in value:
                    value["tariff"]["content_sha256"] = hashlib.sha256(
                        value["tariff"]["body"]
                    ).hexdigest()
                result = review_source_captures(value, now=NOW)
                self.assertEqual(result["status"], "DEFERRED", result)
                self.assertIn("tariff", result["blockers"])
                self.assertFalse(result["execution_authorized"])

    def test_freshness_final_domain_content_and_bytes_cannot_be_fabricated_by_timestamp(self):
        from scripts.c22_selected.source_packets import review_source_captures, sources_for_policy

        for kind in (
            "stale",
            "future",
            "naive",
            "redirect",
            "http",
            "hash",
            "content_type",
            "missing_body",
        ):
            with self.subTest(kind=kind):
                value = captures()
                item = value["swap"]
                if kind == "stale":
                    item["requested_utc"] = (NOW - timedelta(hours=24, seconds=2)).isoformat()
                    item["retrieved_utc"] = (NOW - timedelta(hours=24, microseconds=1)).isoformat()
                elif kind == "future":
                    item["retrieved_utc"] = (NOW + timedelta(seconds=1)).isoformat()
                elif kind == "naive":
                    item["retrieved_utc"] = NOW.replace(tzinfo=None).isoformat()
                elif kind == "redirect":
                    item["final_url"] = "https://untrusted.example/"
                elif kind == "http":
                    item["http_status"] = 503
                elif kind == "hash":
                    item["content_sha256"] = "0" * 64
                elif kind == "content_type":
                    item["content_type"] = "application/json"
                else:
                    del item["body"]
                result = review_source_captures(value, now=NOW)
                self.assertEqual(result["status"], "DEFERRED", result)
                self.assertIn("swap", result["blockers"])
                with self.assertRaises(ValueError):
                    sources_for_policy(result, value, now=NOW)

    def test_snapshot_replay_cannot_refresh_or_substitute_reviewed_content(self):
        from scripts.c22_selected.source_packets import review_source_captures, sources_for_policy

        value = captures()
        result = review_source_captures(value, now=NOW)
        with self.assertRaisesRegex(ValueError, "source_packet_invalid_or_stale"):
            sources_for_policy(result, value, now=NOW + timedelta(hours=24))
        changed = deepcopy(value)
        changed["tariff"]["body"] += b"<p>Changed after review</p>"
        changed["tariff"]["content_sha256"] = hashlib.sha256(changed["tariff"]["body"]).hexdigest()
        with self.assertRaisesRegex(ValueError, "source_packet_binding_changed"):
            sources_for_policy(result, changed, now=NOW)

    def test_dated_calendar_uses_native_points_conversion_and_us_dst_without_missing_zero(self):
        from scripts.c22_selected.source_packets import (
            review_source_captures,
            build_source_bound_policy,
        )
        from tests.demo.test_c22_selected_trial_costs import broker_fixture
        import json

        value = captures()
        reviewed = review_source_captures(value, now=NOW)
        candidate = build_source_bound_policy(
            json.dumps(broker_fixture()).encode(), reviewed, value, now=NOW
        )
        days = candidate["evidence"]["swap_calendar"]["document"]["days"]
        self.assertEqual(len(days), 8)
        self.assertEqual(days["2026-10-30"]["rollover_utc"], "2026-10-30T21:00:00+00:00")
        self.assertEqual(days["2026-11-01"]["rollover_utc"], "2026-11-01T22:00:00+00:00")
        self.assertAlmostEqual(days["2026-11-04"]["buy"], -147.24)
        broker = broker_fixture()
        del broker["spec"]["swap_long"]
        with self.assertRaises(ValueError):
            build_source_bound_policy(json.dumps(broker).encode(), reviewed, value, now=NOW)

    def test_hidden_or_other_account_terms_cannot_prove_standard_commission(self):
        from scripts.c22_selected.source_packets import review_source_captures

        for body in (
            b"<section style='visibility:hidden'><h1>Trading accounts: Standard</h1><dt>Commission</dt><dd>No commission</dd></section>",
            b"<h1>Trading accounts: Standard</h1><p>Commission: USD5</p><h2>Another account</h2><dt>Commission</dt><dd>No commission</dd>",
            b"<h1>Trading accounts: Standard</h1><p>Read terms for this account.</p><h3>Another account</h3><dt>Commission</dt><dd>No commission</dd>",
        ):
            with self.subTest(body=body):
                value = captures()
                value["tariff"]["body"] = body
                value["tariff"]["content_sha256"] = hashlib.sha256(body).hexdigest()
                self.assertEqual(review_source_captures(value, now=NOW)["status"], "DEFERRED")

    def test_source_content_hash_survives_into_policy_and_changes_its_bound_identity(self):
        from scripts.c22_selected.source_packets import (
            review_source_captures,
            build_source_bound_policy,
        )
        from tests.demo.test_c22_selected_trial_costs import broker_fixture
        from scripts.c22_selected.renewal import economic_scope
        import json

        value = captures()
        first = review_source_captures(value, now=NOW)
        broker = json.dumps(broker_fixture()).encode()
        a = build_source_bound_policy(broker, first, value, now=NOW)
        value["tariff"]["body"] += b"<p>New non-economic publication note</p>"
        value["tariff"]["content_sha256"] = hashlib.sha256(value["tariff"]["body"]).hexdigest()
        second = review_source_captures(value, now=NOW)
        b = build_source_bound_policy(broker, second, value, now=NOW)
        self.assertNotEqual(a, b)
        self.assertEqual(
            a["evidence"]["tariff"]["document"]["content_sha256"],
            first["sources"]["tariff"]["content_sha256"],
        )
        self.assertEqual(
            b["evidence"]["tariff"]["document"]["packet_sha256"], second["packet_sha256"]
        )
        self.assertEqual(economic_scope(a), economic_scope(b))
