"""Independent verifier boundary and corruption regressions; synthetic only."""

from copy import deepcopy
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import types
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import c22_h4_carry_verify as subject
from scripts.research import c22_learning_verify as accounting
from scripts.research.breakout_models import Costs
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_performance_campaign import SEED
from scripts.research.c22_risk_replay import replay
from tests.research.test_c22_risk_replay import (
    BROKER,
    VALID_SWAP,
    cent_variant,
    frame_at,
    native_rules,
    tape_at,
)

END = pd.Timestamp("2026-10-26T20:00Z")


def bars_with_gaps(*, recover=False):
    index = pd.date_range(
        END - pd.Timedelta(hours=800),
        END + pd.Timedelta(hours=12) - pd.Timedelta(minutes=15),
        freq="15min",
    )
    missing = [END + pd.Timedelta(minutes=15), END + pd.Timedelta(hours=8, minutes=15)]
    if not recover:
        missing.append(END + pd.Timedelta(hours=4, minutes=15))
    index = index.drop(missing)
    close = 100 + 0.001 * np.arange(len(index))
    return pd.DataFrame(
        dict(open=close, high=close + 0.1, low=close - 0.1, close=close), index=index
    )


def row_at(rows, opening):
    stamp = int((opening + pd.Timedelta(minutes=15)).value // 10**6)
    return next(row for row in rows if row["signal_ms"] == stamp)


def synthetic_cell(*, guard="raw", tiny_loss=False, held_at_end=False):
    frame = frame_at(["2026-04-07T23:30Z", "2026-04-07T23:45Z", "2026-04-08T00:00Z"], [1, 0, 0])
    costs = Costs(extra_spread=0.2, slippage=0.1, commission_per_lot=7)
    ticks = tape_at(
        ["2026-04-07T23:45Z", "2026-04-08T00:00Z", "2026-04-08T00:15Z"], [100.0, 100.0, 97.0]
    )
    if tiny_loss:
        frame = frame_at(["2026-04-07T12:00Z", "2026-04-07T12:15Z", "2026-04-07T12:30Z"], [1, 0, 1])
        costs = Costs()
        ticks = tape_at(
            ["2026-04-07T12:15Z", "2026-04-07T12:30Z", "2026-04-07T12:45Z", "2026-04-07T13:00Z"],
            [100, 103, 100.196, 100.196],
        )
    if held_at_end:
        frame["direction"] = 1
        ticks = tape_at(
            ["2026-04-07T23:45Z", "2026-04-08T00:00Z", "2026-04-08T00:15Z"], [100.0, 100.0, 100.0]
        )
    rules = native_rules()
    start = frame.index[0].normalize()
    end = pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC") + pd.Timedelta(seconds=1)
    engine = replay if guard == "raw" else cent_variant(replay)
    broker = dict(
        BROKER, swap_mode=1, swap_rollover3days=3, swap_long=-0.4, swap_short=-0.4, point=1.0
    )
    result = engine(
        frame,
        ticks,
        broker,
        rules,
        costs,
        start=start,
        end=end,
        swap_policy=VALID_SWAP,
        capture_events=True,
        capture_context=True,
    )
    minimum = min([200.0] + [r["equity_usd"] for r in result["equity"]])
    risk = accounting.ledger_risk(result, pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC"))
    metrics = {k: result[k] for k in ("net_usd", "final_balance", "max_dd_pct")}
    metrics.update(
        min_observed_equity=minimum,
        max_consecutive_losses=risk["count"],
        survival=bool(
            minimum > 0 and result["final_balance"] > 0 and not result["rejections"]["bankrupt"]
        ),
    )
    protocol = dict(
        broker=broker, start=start.isoformat(), end=end.isoformat(), views={"fee": asdict(costs)}
    )
    arrays = {"time": ticks[0], "bid": ticks[1], "ask": ticks[2]}
    with patch.object(
        accounting.np, "load", side_effect=lambda path, **kw: arrays[Path(path).stem]
    ):
        auditor = subject.IndependentTapeAudit(
            protocol, pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC")
        )
    cell = dict(profile=dict(carry=True), guard=guard, view="fee", result=result, metrics=metrics)
    signals = [
        dict(
            signal_ms=int((stamp + pd.Timedelta(minutes=15)).value // 10**6),
            native_direction=int(row.direction),
            candidate_direction=int(row.direction),
            atr=float(row.atr),
            range_high=float(row.hh),
            range_low=float(row.ll),
        )
        for stamp, row in frame.iterrows()
    ]
    return auditor, cell, signals


class H4IndependentVerifierTests(unittest.TestCase):
    def test_missing_bar_keeps_publication_and_age_exact_eight_refuses(self):
        rows = subject.independent_h4(bars_with_gaps())
        first = row_at(rows, END + pd.Timedelta(hours=3, minutes=45))
        last = row_at(rows, END + pd.Timedelta(hours=7, minutes=30))
        expired = row_at(rows, END + pd.Timedelta(hours=7, minutes=45))
        self.assertEqual(first["source_end_utc"], END.isoformat())
        self.assertEqual(
            (first["age_hours"], last["age_hours"], expired["age_hours"]), (4, 7.75, 8)
        )
        self.assertEqual(first["macro_ema"], last["macro_ema"])
        self.assertEqual(first["status"], "CARRIED_CAUSE_UNKNOWN")
        self.assertEqual(expired["status"], "EXPIRED")
        self.assertIsNone(expired["macro_ema"])

    def test_fresh_complete_publication_replaces_expired_at_same_boundary(self):
        rows = subject.independent_h4(bars_with_gaps(recover=True))
        boundary = row_at(rows, END + pd.Timedelta(hours=7, minutes=45))
        self.assertEqual(boundary["age_hours"], 0)
        self.assertEqual(boundary["source_end_utc"], (END + pd.Timedelta(hours=8)).isoformat())
        self.assertEqual(boundary["status"], "CURRENT_STRICT_H4")

    def test_prefix_future_changes_cannot_leak_into_h4_or_raw(self):
        bars = bars_with_gaps(recover=True)
        cutoff = END + pd.Timedelta(hours=7, minutes=30)
        prefix = bars.loc[:cutoff]
        future = bars.copy()
        future.loc[future.index > cutoff, ["open", "high", "low", "close"]] *= 20
        expected = subject.independent_h4(prefix)
        actual = subject.independent_h4(future)[: len(prefix)]
        for left, right in zip(expected, actual):
            for key in left:
                if key != "strict_ema":
                    self.assertEqual(left[key], right[key])
        seed = subject.read(SEED)
        pd.testing.assert_series_equal(
            subject.independent_raw(prefix, seed)[0],
            subject.independent_raw(future, seed)[0].loc[prefix.index],
        )

    def test_warmup_requires_two_hundred_actual_complete_observations(self):
        bars = bars_with_gaps().iloc[: 199 * 16]
        rows = subject.independent_h4(bars)
        self.assertTrue(
            all(
                r["status"] == "WARMUP" and r["macro_ema"] is None and r["source_end_utc"] is None
                for r in rows
            )
        )
        complete = bars_with_gaps().iloc[: 200 * 16]
        self.assertEqual(subject.independent_h4(complete)[-1]["age_hours"], 0)
        self.assertIsNotNone(subject.independent_h4(complete)[-1]["macro_ema"])

    def test_chronology_and_partial_slots_fail_closed(self):
        bars = bars_with_gaps()
        for invalid in (
            bars.iloc[::-1],
            pd.concat([bars.iloc[:1], bars]),
            bars.set_axis(bars.index.tz_localize(None)),
            bars.set_axis(bars.index + pd.Timedelta(minutes=1)),
        ):
            with self.subTest(index=invalid.index[:2]), self.assertRaises(AssertionError):
                subject.independent_h4(invalid)
        missing = bars.iloc[: 200 * 16].drop(bars.index[100])
        self.assertTrue(all(r["macro_ema"] is None for r in subject.independent_h4(missing)))

    def test_reconstructed_raw_and_native_macro_match_frozen_preparation(self):
        bars = bars_with_gaps()
        # Deterministic oscillating drift exercises both raw directions and EMA warmup.
        points = np.arange(len(bars))
        close = (
            100
            + 0.005 * points
            + np.sin(points / 11)
            + np.random.default_rng(4).normal(0, 0.3, len(bars))
        )
        bars.loc[:, "close"] = close
        bars.loc[:, "open"] = close - 0.01
        bars.loc[:, "high"] = close + 0.1
        bars.loc[:, "low"] = close - 0.1
        native, _ = prepare(bars, subject.read(SEED))
        rows = subject.reconstruct(bars, native, subject.read(SEED))
        self.assertEqual({r["raw_direction"] for r in rows}, {-1, 0, 1})
        tampered = native.copy()
        tampered.iloc[-1, tampered.columns.get_loc("raw_direction")] = (
            1 if native.raw_direction.iloc[-1] != 1 else -1
        )
        with self.assertRaisesRegex(AssertionError, "raw direction drift"):
            subject.reconstruct(bars, tampered, subject.read(SEED))

    def test_context_forged_age_source_direction_and_missing_witness_fail(self):
        row = dict(
            signal_ms=int(END.value // 10**6),
            source_end_utc=(END - pd.Timedelta(hours=4)).isoformat(),
            age_hours=4.0,
            carried=True,
            status="CARRIED_CAUSE_UNKNOWN",
            macro_ema=100.0,
            raw_direction=1,
            native_direction=0,
            candidate_direction=1,
        )
        saved = {k: v for k, v in row.items() if k != "signal_ms"}
        saved["signal_close_utc"] = END.isoformat()
        cell = dict(profile=dict(carry=True), h4_context=[saved])
        self.assertEqual(subject.audit_context(cell, [row])["witnesses"], 1)
        for key, value in (
            ("age_hours", 0.0),
            ("source_end_utc", (END + pd.Timedelta(hours=1)).isoformat()),
            ("candidate_direction", -1),
            ("macro_ema", 101.0),
            ("status", "CURRENT_STRICT_H4"),
        ):
            corrupt = deepcopy(cell)
            corrupt["h4_context"][0][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                subject.audit_context(corrupt, [row])
        with self.assertRaisesRegex(AssertionError, "missing H4 witness"):
            subject.audit_context(dict(profile=dict(carry=True), h4_context=[]), [row])

    def test_ledger_admission_and_first_source_quote_geometry_verified(self):
        auditor, cell, signals = synthetic_cell()
        checked = subject.audit_admissions(auditor, cell, signals)
        self.assertEqual([r["reason"] for r in checked], ["admitted"])
        for key in ("entry", "initial_stop", "target", "range_high", "risk_usd"):
            corrupt = deepcopy(cell)
            corrupt["result"]["ledger"][0][key] += 0.01
            with self.subTest(key=key), self.assertRaises(AssertionError):
                subject.audit_admissions(auditor, corrupt, signals)
        corrupt = deepcopy(cell)
        corrupt["result"]["context_events"][0]["reason"] = "busy"
        with self.assertRaisesRegex(AssertionError, "causal admission reason"):
            subject.audit_admissions(auditor, corrupt, signals)
        corrupt = deepcopy(cell)
        corrupt["result"]["admission_events"][0]["position_open"] = True
        with self.assertRaisesRegex(AssertionError, "admission capacity witness"):
            subject.audit_admissions(auditor, corrupt, signals)

    def test_sample_end_close_cannot_free_capacity_at_last_decision(self):
        auditor, cell, signals = synthetic_cell(held_at_end=True)
        self.assertEqual(cell["result"]["ledger"][0]["reason"], "END_OF_SAMPLE")
        decisions = subject.audit_admissions(auditor, cell, signals)
        self.assertEqual([r["reason"] for r in decisions], ["admitted", "busy", "busy"])
        self.assertTrue(decisions[-1]["position_open"])

    def test_signed_commission_swap_and_accounting_corruption_rejected(self):
        auditor, cell, _ = synthetic_cell()
        auditor.audit_cell(cell)
        subject.audit_cost_fields(auditor, cell)
        self.assertLess(cell["result"]["swap_usd"], 0)
        for key in ("net", "swap_usd", "entry_equity", "volume"):
            corrupt = deepcopy(cell)
            corrupt["result"]["ledger"][0][key] += 0.01
            with self.subTest(key=key), self.assertRaises(AssertionError):
                auditor.audit_cell(corrupt)
        for key in ("commission_usd", "modeled_slippage_usd", "quoted_spread_proxy_usd"):
            corrupt = deepcopy(cell)
            corrupt["result"]["ledger"][0][key] += 0.01
            with self.subTest(key=key), self.assertRaises(AssertionError):
                subject.audit_cost_fields(auditor, corrupt)

    def test_full_tick_dd_minimum_and_source_corruption_rejected(self):
        auditor, cell, _ = synthetic_cell()
        ticks, history = subject.full_tick_and_peaks(auditor, cell)
        self.assertEqual(len(history), 1)
        self.assertGreater(ticks["held_quote_observations"], 1)
        self.assertGreater(history[0]["entry_peak"], 0)
        for field in ("max_dd_pct", "min_observed_equity"):
            corrupt = deepcopy(cell)
            target = corrupt["result"] if field == "max_dd_pct" else corrupt["metrics"]
            target[field] += 0.01
            with self.subTest(field=field), self.assertRaises(AssertionError):
                subject.full_tick_and_peaks(auditor, corrupt)
        auditor.tape["bid"] = auditor.tape["bid"].copy()
        auditor.tape["bid"][1] += 10
        with self.assertRaises(AssertionError):
            subject.full_tick_and_peaks(auditor, cell)

    def test_raw_cent_tiny_negative_changes_only_loss_gate(self):
        raw_audit, raw, raw_signals = synthetic_cell(tiny_loss=True)
        cent_audit, cent, cent_signals = synthetic_cell(guard="cent", tiny_loss=True)
        self.assertLess(raw["result"]["ledger"][0]["net"], 0)
        self.assertGreater(raw["result"]["ledger"][0]["net"], -0.005)
        self.assertEqual(
            subject.audit_admissions(raw_audit, raw, raw_signals)[1]["reason"], "cooldown"
        )
        self.assertEqual(
            subject.audit_admissions(cent_audit, cent, cent_signals)[1]["reason"], "admitted"
        )
        corrupted = deepcopy(cent)
        corrupted["guard"] = "raw"
        with self.assertRaises(AssertionError):
            subject.audit_admissions(cent_audit, corrupted, cent_signals)

    def test_source_and_snapshot_hash_corruption_rejected(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            source = out / "fixture.py"
            source.write_text("value = 1\n")
            relative = str(source.relative_to(subject.ROOT))
            snapshot = out / "source_snapshot" / relative
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(source.read_text())
            pins = {relative: subject.sha(source)}
            subject.audit_source_pins(out, pins)
            source.write_text("value = 2\n")
            with self.assertRaises(AssertionError):
                subject.audit_source_pins(out, pins)
            source.write_text("value = 1\n")
            snapshot.write_text("value = 3\n")
            with self.assertRaises(AssertionError):
                subject.audit_source_pins(out, pins)

    def test_immutable_cell_hash_origin_path_and_fresh_repeat_proof(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            key = subject.BASE + "-base-raw"
            cell = dict(
                profile=dict(name=subject.BASE),
                view="base",
                guard="raw",
                protocol_sha256="frozen",
                result=dict(ledger=[]),
                metrics={},
                diagnostics={},
                summary={},
                h4_context=[],
            )
            path = out / "cells" / (key + ".json.gz")
            path.parent.mkdir()
            with gzip.open(path, "wt") as stream:
                json.dump(cell, stream)
            proof = dict(
                path=str(path.relative_to(subject.ROOT)), sha256=subject.sha(path), origin="new"
            )
            proof_path = out / "cells-integrity" / (key + ".json")
            proof_path.parent.mkdir()
            proof_path.write_text(json.dumps(proof))
            self.assertEqual(subject.read_cell(out, key)[0], cell)
            for field, value in (
                ("origin", "resume"),
                ("sha256", "0" * 64),
                ("path", "runs/wrong-cell.json.gz"),
            ):
                proof_path.write_text(json.dumps(dict(proof, **{field: value})))
                with (
                    self.subTest(field=field),
                    self.assertRaises((AssertionError, FileNotFoundError)),
                ):
                    subject.read_cell(out, key)
            repeat = deepcopy(cell)
            subject.audit_repeat(repeat, cell)
            for field in (
                "result",
                "metrics",
                "diagnostics",
                "summary",
                "h4_context",
                "protocol_sha256",
            ):
                corrupt = deepcopy(repeat)
                corrupt[field] = ["forged"]
                with self.subTest(field=field), self.assertRaises(AssertionError):
                    subject.audit_repeat(corrupt, cell)

    def test_new_loaded_source_omitted_from_freeze_blocks(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            source = Path(temp) / "late_import.py"
            source.write_text("value = 1\n")
            module = types.ModuleType("h4_unbound_audit_fixture")
            module.__file__ = str(source)
            # Ignore other modules by pinning actual origins, then inject exactly
            # one unregistered source. No runtime dependency is omitted silently.
            protocol = dict(sources={}, runtime_sources={})
            for loaded in tuple(subject.sys.modules.values()):
                origin = getattr(loaded, "__file__", None)
                if origin:
                    path = Path(origin).resolve()
                    if path.suffix == ".pyc":
                        path = Path(subject.importlib.util.source_from_cache(str(path)))
                    if path.is_file():
                        inside = path.is_relative_to(subject.ROOT)
                        protocol["sources" if inside else "runtime_sources"][
                            str(path.relative_to(subject.ROOT)) if inside else str(path)
                        ] = subject.sha(path)
            with patch.dict("sys.modules", {module.__name__: module}):
                with self.assertRaisesRegex(AssertionError, "unbound loaded audit dependency"):
                    subject.audit_loaded_sources(protocol)

    def test_selection_requires_all_six_native_nets_and_native_tie(self):
        def rows(net=100.0):
            return {
                g: {
                    v: dict(metrics=dict(net_usd=net, max_dd_pct=20.0, survival=True))
                    for v in subject.VIEWS
                }
                for g in subject.GUARDS
            }

        floors = {g: {v: dict(net_usd=0.0) for v in subject.VIEWS} for g in subject.GUARDS}
        native = rows()
        self.assertEqual(
            subject.choose({subject.BASE: native, "B": rows()}, floors)[0], subject.BASE
        )
        candidate = rows(101.0)
        candidate["cent"]["fee"]["metrics"]["net_usd"] = 99.0
        self.assertEqual(
            subject.choose({subject.BASE: native, "B": candidate}, floors)[0], subject.BASE
        )
        self.assertEqual(subject.choose({subject.BASE: native, "B": rows(101.0)}, floors)[0], "B")
        candidate = rows(101.0)
        candidate["raw"]["stress"]["metrics"]["max_dd_pct"] = 40.00001
        self.assertEqual(
            subject.choose({subject.BASE: native, "B": candidate}, floors)[0], subject.BASE
        )

    def test_opportunity_identities_preserve_lost_new_and_busy_reason(self):
        def event(stamp, reason, holder=None):
            return dict(identity=(stamp, 1), reason=reason, holder_entry_ms=holder)

        native = [event(1, "admitted"), event(2, "admitted"), event(3, "risk_cap")]
        candidate = [
            event(1, "admitted"),
            event(2, "busy", 10),
            event(3, "admitted"),
            event(4, "admitted"),
        ]
        report = subject.opportunity_delta(native, candidate)
        self.assertEqual([x["signal_ms"] for x in report["retained"]], [1])
        self.assertEqual(report["lost"][0]["candidate_reason"], "busy")
        self.assertEqual(report["lost"][0]["candidate_holder_entry_ms"], 10)
        self.assertEqual([x["signal_ms"] for x in report["newly_admitted"]], [3, 4])
        self.assertEqual([x["signal_ms"] for x in report["newly_visible"]], [4])
        self.assertFalse(report["counterfactual_pnl_added"])

    def test_completed_and_censored_ongoing_recovery_are_separate(self):
        result = dict(
            start_utc="2026-04-01T00:00:00+00:00",
            ledger=[
                dict(net=net, exit_time_utc=f"2026-04-0{day}T00:00:00+00:00")
                for day, net in ((2, 10.0), (3, -5.0), (4, 5.0), (5, -1.0))
            ],
        )
        expected = dict(
            completed_count=1,
            longest_completed=dict(
                start="2026-04-02T00:00:00+00:00",
                first_underwater_exit="2026-04-03T00:00:00+00:00",
                previous_peak=210.0,
                end="2026-04-04T00:00:00+00:00",
                recovered_to=210.0,
                days=2.0,
            ),
            ongoing=dict(
                start="2026-04-04T00:00:00+00:00",
                first_underwater_exit="2026-04-05T00:00:00+00:00",
                previous_peak=210.0,
                balance=209.0,
                days=2.0,
            ),
        )
        diagnostics = dict(actual_closing_recovery=expected)
        self.assertEqual(
            subject.audit_closing_recovery(result, diagnostics, "2026-04-06T00:00Z"), expected
        )
        for section in ("longest_completed", "ongoing"):
            corrupt = deepcopy(diagnostics)
            corrupt["actual_closing_recovery"][section]["days"] = 0
            with (
                self.subTest(section=section),
                self.assertRaisesRegex(AssertionError, "closing recovery/censoring drift"),
            ):
                subject.audit_closing_recovery(result, corrupt, "2026-04-06T00:00Z")
        corrupt = deepcopy(diagnostics)
        corrupt["actual_closing_recovery"]["ongoing"] = None
        with self.assertRaises(AssertionError):
            subject.audit_closing_recovery(result, corrupt, "2026-04-06T00:00Z")


if __name__ == "__main__":
    unittest.main()
