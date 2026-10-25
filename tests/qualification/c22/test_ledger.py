"""Offline broker ledger boundaries; expected cash values are hand calculated."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.qualification.c22.ledger import reconcile_export


def deal(ticket, position, side, entry, volume, stamp, **amounts):
    row = dict(
        ticket=ticket, position_id=position, magic=22261004, type=side, entry=entry,
        volume=volume, time_msc=int(datetime.fromisoformat(stamp).timestamp() * 1000),
        price=2000.0, profit=0.0, commission=0.0, fee=0.0, swap=0.0,
        symbol="XAUUSDm",
    )
    row.update(amounts)
    return row


def export(deals, currency="USD"):
    return dict(
        captured_utc="2026-10-24T07:55:34+00:00",
        history_start_utc="2026-07-01T00:00:00+00:00",
        account_fingerprint="test-account", account={"currency": currency},
        history_deals=deals,
    )


def policy():
    def bind(document):
        return dict(document=document, sha256=hashlib.sha256(
            json.dumps(document, sort_keys=True, allow_nan=False).encode()
        ).hexdigest())

    period = dict(
        effective_from_utc="2026-10-01T00:00:00+00:00",
        effective_until_utc="2026-10-04T00:00:00+00:00",
    )
    return dict(
        version=2, status="SUPPORTED_HISTORICAL_DOCUMENTS", pending_checks=[],
        account_fingerprint="test-account", commission_per_lot=2.0,
        reviewed_utc="2026-10-03T00:00:00+00:00",
        evidence=dict(
            tariff=bind(dict(source="fixture dated tariff", **period,
                             commission_per_lot=2.0, unit="USD_per_lot_round_trip")),
            spec=bind(dict(source="fixture dated spec", **period, fields=dict(
                trade_contract_size=100, trade_tick_size=0.01, volume_min=0.01,
                volume_max=100, volume_step=0.01, swap_mode=1, swap_long=-100,
                swap_short=0, swap_rollover3days=3,
            ))),
            swap_calendar=bind(dict(source="fixture dated broker calendar",
                unit="USD_per_lot", days={
                    "2026-10-01": dict(rollover_utc="2026-10-01T00:00:00+00:00", buy=-10, sell=0),
                    "2026-10-02": dict(rollover_utc="2026-10-02T00:00:00+00:00", buy=-10, sell=0),
                })),
        ),
    )


def rebind(raw, name):
    item = raw["evidence"][name]
    item["sha256"] = hashlib.sha256(json.dumps(
        item["document"], sort_keys=True, allow_nan=False
    ).encode()).hexdigest()


class LedgerTests(unittest.TestCase):
    def run_report(self, raw, assumptions=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broker.json"
            path.write_text(json.dumps(raw))
            costs = None
            if assumptions is not None:
                costs = Path(directory) / "policy.json"
                costs.write_text(json.dumps(assumptions))
            return reconcile_export(path, costs)

    def partial(self):
        return [
            deal(1, 10, 0, 0, 0.03, "2026-10-01T20:00:00+00:00", commission=-0.03),
            deal(2, 10, 1, 1, 0.01, "2026-10-02T00:00:00+00:00", profit=4, commission=-0.01),
            deal(3, 10, 1, 1, 0.02, "2026-10-02T12:00:00+00:00", profit=6, commission=-0.02, swap=-0.2),
        ]

    def test_partial_closes_preserve_signed_cash_and_expose_missing_cost_evidence(self):
        result = self.run_report(export(self.partial()))
        row = result["data"]["positions"][0]
        self.assertEqual(result["status"], "COST_INCONCLUSIVE")
        self.assertEqual(row["status"], "COMPLETE")
        self.assertAlmostEqual(row["entry_volume"], 0.03)
        self.assertAlmostEqual(row["exit_volume"], 0.03)
        self.assertEqual(row["observed"]["profit"], 10)
        self.assertAlmostEqual(row["observed"]["commission"], -0.06)
        self.assertAlmostEqual(row["observed"]["net"], 9.74)
        self.assertEqual(row["slippage"]["status"], "NOT_MEASURED")
        self.assertEqual(result["coverage"]["complete_positions"], 1)

    def test_dated_calendar_applies_remaining_volume_at_exact_partial_exit_rollover(self):
        result = self.run_report(export(self.partial()), policy())
        row = result["data"]["positions"][0]
        self.assertEqual(result["status"], "OBSERVED_COSTS_MATCH")
        self.assertAlmostEqual(row["comparison"]["modeled_swap"], -0.2)
        self.assertAlmostEqual(row["comparison"]["observed_charges"], 0.06)
        self.assertAlmostEqual(row["comparison"]["charge_allowance"], 0.06)
        self.assertEqual(result["coverage"]["pre_review_positions"], 1)
        self.assertEqual(result["coverage"]["compared_positions"], 1)

    def test_dated_triple_rate_is_used_without_weekday_guessing(self):
        costs = policy()
        costs["evidence"]["swap_calendar"]["document"]["days"]["2026-10-02"]["buy"] = -30
        rebind(costs, "swap_calendar")
        rows = self.partial()
        rows[-1]["swap"] = -0.6
        result = self.run_report(export(rows), costs)
        self.assertEqual(result["status"], "OBSERVED_COSTS_MATCH")
        self.assertAlmostEqual(result["data"]["positions"][0]["comparison"]["modeled_swap"], -0.6)

    def test_entry_exactly_at_rollover_is_not_charged_that_rollover(self):
        rows = [deal(1, 10, 0, 0, 0.01, "2026-10-02T00:00:00+00:00"),
                deal(2, 10, 1, 1, 0.01, "2026-10-02T12:00:00+00:00")]
        result = self.run_report(export(rows), policy())
        self.assertEqual(result["status"], "OBSERVED_COSTS_MATCH")
        self.assertEqual(result["data"]["positions"][0]["comparison"]["modeled_swap"], 0)

    def test_missing_calendar_and_current_spec_never_backcast_or_zero_fill(self):
        for missing in ("calendar", "historical_period", "draft", "hash"):
            with self.subTest(missing=missing):
                costs = policy()
                if missing == "calendar":
                    del costs["evidence"]["swap_calendar"]["document"]["days"]["2026-10-02"]
                    rebind(costs, "swap_calendar")
                elif missing == "historical_period":
                    del costs["evidence"]["spec"]["document"]["effective_from_utc"]
                    rebind(costs, "spec")
                elif missing == "draft":
                    costs["status"] = "DRAFT_NOT_ATTESTED"
                else:
                    costs["evidence"]["tariff"]["sha256"] = "0" * 64
                result = self.run_report(export(self.partial()), costs)
                self.assertEqual(result["status"], "COST_INCONCLUSIVE")
                self.assertEqual(result["coverage"]["compared_positions"], 0)
                self.assertNotIn("modeled_swap", result["data"]["positions"][0]["comparison"])

    def test_supported_swap_and_charge_drift_remain_visible(self):
        rows = self.partial()
        rows[-1].update(swap=-0.5, fee=-0.1)
        result = self.run_report(export(rows), policy())
        row = result["data"]["positions"][0]
        self.assertEqual(result["status"], "COST_DRIFT")
        self.assertAlmostEqual(row["comparison"]["swap_delta"], -0.3)
        self.assertAlmostEqual(row["comparison"]["observed_charges"], 0.16)
        self.assertIn("swap_drift", row["comparison"]["reasons"])
        self.assertIn("charge_allowance_exceeded", row["comparison"]["reasons"])
        self.assertAlmostEqual(row["observed"]["net"], 9.34)

    def test_duplicate_deals_are_deduplicated_before_chronological_partial_close(self):
        rows = self.partial()
        result = self.run_report(export([rows[2], rows[0], rows[1], dict(rows[1])]))
        self.assertEqual(result["coverage"]["duplicates_dropped"], 1)
        self.assertEqual(result["coverage"]["unique_deals"], 3)
        self.assertEqual(result["data"]["positions"][0]["status"], "COMPLETE")
        self.assertAlmostEqual(result["data"]["positions"][0]["observed"]["net"], 9.74)

    def test_conflicting_duplicate_ticket_blocks_financial_aggregation(self):
        rows = self.partial()
        conflict = dict(rows[-1], profit=999)
        result = self.run_report(export(rows + [conflict]))
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("conflicting_duplicate_ticket", result["reasons"])
        self.assertEqual(result["data"]["positions"][0]["status"], "INVALID")
        self.assertIsNone(result["data"]["positions"][0]["observed"])

    def test_open_orphan_unsupported_and_nontrade_records_have_explicit_coverage(self):
        rows = [deal(1, 10, 0, 0, 0.03, "2026-10-01T20:00:00+00:00"),
                deal(2, 20, 1, 1, 0.01, "2026-10-02T00:00:00+00:00", profit=-2),
                deal(3, 30, 0, 2, 0.01, "2026-10-02T12:00:00+00:00", profit=3),
                deal(4, 0, 2, 0, 0, "2026-10-02T13:00:00+00:00", profit=200)]
        result = self.run_report(export(rows))
        self.assertEqual(result["status"], "COST_INCONCLUSIVE")
        self.assertEqual(result["coverage"]["open_positions"], 1)
        self.assertEqual(result["coverage"]["orphan_positions"], 1)
        self.assertEqual(result["coverage"]["unsupported_positions"], 1)
        self.assertEqual(result["coverage"]["nontrade_deals"], 1)
        self.assertEqual(result["coverage"]["complete_positions"], 0)
        self.assertEqual(result["data"]["nontrade_records"][0]["observed"]["net"], 200)

    def test_missing_nonfinite_charges_and_naive_utc_are_invalid(self):
        for bad in ("missing", "nonfinite", "naive"):
            with self.subTest(bad=bad):
                rows = self.partial()
                raw = export(rows)
                if bad == "missing":
                    del rows[-1]["swap"]
                elif bad == "nonfinite":
                    rows[-1]["fee"] = float("nan")
                else:
                    raw["captured_utc"] = "2026-10-24T07:55:34"
                result = self.run_report(raw)
                self.assertEqual(result["status"], "INVALID")
                self.assertTrue(result["reasons"])

    def test_non_usd_or_missing_currency_does_not_relabel_native_cash_as_usd(self):
        for currency in (None, "EUR"):
            with self.subTest(currency=currency):
                result = self.run_report(export(self.partial(), currency), policy())
                self.assertEqual(result["status"], "COST_INCONCLUSIVE")
                self.assertEqual(result["data"]["currency"], currency)
                self.assertEqual(result["coverage"]["compared_positions"], 0)
                self.assertAlmostEqual(result["data"]["positions"][0]["observed"]["net"], 9.74)

    def test_sell_rebates_and_negative_profit_keep_signed_cash_and_sell_calendar(self):
        rows = self.partial()
        for row in rows:
            row["type"] = 1 - row["type"]
        rows[1]["profit"] = -4
        rows[-1].update(profit=-6, swap=-0.01, fee=0.02)
        costs = policy()
        costs["evidence"]["swap_calendar"]["document"]["days"]["2026-10-02"]["sell"] = -0.5
        rebind(costs, "swap_calendar")
        result = self.run_report(export(rows), costs)
        row = result["data"]["positions"][0]
        self.assertEqual(result["status"], "OBSERVED_COSTS_MATCH")
        self.assertEqual(row["side"], "SELL")
        self.assertAlmostEqual(row["observed"]["net"], -10.05)
        self.assertAlmostEqual(row["comparison"]["modeled_swap"], -0.01)
        self.assertAlmostEqual(row["comparison"]["observed_charges"], 0.06)

    def test_no_complete_position_has_unknown_total_rather_than_zero_profit(self):
        result = self.run_report(export([self.partial()[0]]))
        self.assertIsNone(result["data"]["complete_position_cash"])
        self.assertEqual(result["data"]["scope"], "ALL_EXPORTED_POSITIONS_NO_STRATEGY_FILTER")
        self.assertIsNone(result["candidate_id"])

    def test_missing_entry_order_and_wrong_close_direction_cannot_form_complete_ledger(self):
        for mutation in ("early_exit", "wrong_direction"):
            with self.subTest(mutation=mutation):
                rows = self.partial()
                if mutation == "early_exit":
                    rows[-1]["time_msc"] = rows[0]["time_msc"] - 1
                else:
                    rows[-1]["type"] = rows[0]["type"]
                result = self.run_report(export(rows))
                self.assertEqual(result["status"], "INVALID")
                self.assertEqual(result["coverage"]["invalid_positions"], 1)
                self.assertIsNone(result["data"]["positions"][0]["observed"])

    def test_negative_tariff_and_deals_outside_declared_window_fail_closed(self):
        costs = policy()
        costs["commission_per_lot"] = -1
        costs["evidence"]["tariff"]["document"]["commission_per_lot"] = -1
        rebind(costs, "tariff")
        result = self.run_report(export(self.partial()), costs)
        self.assertEqual(result["status"], "COST_INCONCLUSIVE")
        self.assertEqual(result["coverage"]["compared_positions"], 0)
        for field, value in (("captured_utc", "2026-10-01T00:00:00+00:00"),
                             ("history_start_utc", "2026-10-03T00:00:00+00:00")):
            with self.subTest(field=field):
                raw = export(self.partial())
                raw[field] = value
                result = self.run_report(raw)
                self.assertEqual(result["status"], "INVALID")
                self.assertTrue(result["reasons"])


if __name__ == "__main__":
    unittest.main()
