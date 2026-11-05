"""Synthetic public-seam H4 B regressions; no historical economic campaign."""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import fcntl
import json
import os
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import c22_h4_carry as subject
from scripts.research.breakout_models import Costs
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_performance_campaign import SEED, read
from scripts.research.c22_risk_replay import replay
from scripts.research.reward156_tuning import closed_h4_ema
from tests.research.test_c22_risk_replay import (
    BROKER,
    VALID_SWAP,
    cent_variant,
    frame_at,
    native_rules,
    tape_at,
)

END = pd.Timestamp("2026-10-26T20:00:00Z")


def bars_with_gap(*, recover=False):
    index = pd.date_range(
        END - pd.Timedelta(hours=800),
        END + pd.Timedelta(hours=12) - pd.Timedelta(minutes=15),
        freq="15min",
    )
    missing = [END + pd.Timedelta(minutes=15), END + pd.Timedelta(hours=8, minutes=15)]
    if not recover:
        missing.append(END + pd.Timedelta(hours=4, minutes=15))
    index = index.drop(missing)
    close = 100 + np.arange(len(index)) * 0.001
    return pd.DataFrame(
        dict(open=close, high=close + 0.1, low=close - 0.1, close=close), index=index
    )


class H4CarryTests(unittest.TestCase):
    def test_uses_bar_close_clock_and_refuses_exact_eight_hours(self):
        bars = bars_with_gap()
        context = subject.h4_context(bars)
        before_close = END + pd.Timedelta(hours=3, minutes=30)
        first_carry = END + pd.Timedelta(hours=3, minutes=45)
        last_carry = END + pd.Timedelta(hours=7, minutes=30)
        exact_eight = END + pd.Timedelta(hours=7, minutes=45)
        self.assertEqual(context.at[before_close, "status"], "CURRENT_STRICT_H4")
        self.assertEqual(context.at[first_carry, "age_hours"], 4.0)
        self.assertEqual(context.at[first_carry, "status"], "CARRIED_CAUSE_UNKNOWN")
        self.assertEqual(context.at[last_carry, "age_hours"], 7.75)
        self.assertEqual(context.at[exact_eight, "age_hours"], 8.0)
        self.assertEqual(context.at[exact_eight, "status"], "EXPIRED")
        self.assertTrue(pd.isna(context.at[exact_eight, "macro_ema"]))
        self.assertEqual(context.at[last_carry, "source_end_utc"], END)
        self.assertTrue(pd.isna(closed_h4_ema(bars, 200).at[first_carry]))

    def test_new_complete_h4_replaces_old_context_at_same_boundary(self):
        bars = bars_with_gap(recover=True)
        context = subject.h4_context(bars)
        opened = END + pd.Timedelta(hours=7, minutes=45)
        self.assertEqual(context.at[opened, "source_end_utc"], END + pd.Timedelta(hours=8))
        self.assertEqual(context.at[opened, "age_hours"], 0.0)
        self.assertEqual(context.at[opened, "status"], "CURRENT_STRICT_H4")
        self.assertEqual(context.at[opened, "macro_ema"], closed_h4_ema(bars, 200).at[opened])

    def test_partial_bucket_does_not_update_ema_or_create_bars(self):
        bars = bars_with_gap()
        original = bars.copy(deep=True)
        context = subject.h4_context(bars)
        published = closed_h4_ema(bars, 200).at[END - pd.Timedelta(minutes=15)]
        carried = context.loc[context.carried]
        self.assertTrue(len(carried) > 1)
        self.assertTrue(carried.macro_ema.eq(published).all())
        self.assertTrue(carried.source_end_utc.eq(END).all())
        pd.testing.assert_frame_equal(bars, original)
        self.assertTrue(context.index.equals(bars.index))

    def test_future_values_and_prefix_cannot_change_prior_context(self):
        bars = bars_with_gap(recover=True)
        cutoff = END + pd.Timedelta(hours=7, minutes=30)
        prefix = bars.loc[:cutoff]
        expected = subject.h4_context(prefix)
        future = bars.copy()
        future.loc[future.index > cutoff, ["open", "high", "low", "close"]] *= 2
        pd.testing.assert_frame_equal(expected, subject.h4_context(future).loc[prefix.index])

    def test_research_span200_warmup_remains_unavailable(self):
        bars = bars_with_gap().iloc[: 199 * 16]
        context = subject.h4_context(bars)
        self.assertTrue(context.macro_ema.isna().all())
        self.assertTrue(context.source_end_utc.isna().all())
        self.assertTrue(context.status.eq("WARMUP").all())

    def test_raw_buy_and_sell_are_restored_before_macro_mask_only_inside_age(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                bars = bars_with_gap()
                opened = END + pd.Timedelta(hours=3, minutes=45)
                expired = END + pd.Timedelta(hours=7, minutes=45)
                if direction == -1:
                    bars.loc[[opened, expired], ["open", "high", "low", "close"]] = 50.0
                native, _ = prepare(bars, read(SEED))
                native.loc[[opened, expired], "raw_direction"] = direction
                native.loc[[opened, expired], "direction"] = 0
                original = native.copy(deep=True)
                actual, context = subject.carry_frame(bars, native, enabled=True)
                self.assertEqual(actual.at[opened, "direction"], direction)
                self.assertFalse(actual.at[opened, "macro_unavailable"])
                self.assertEqual(actual.at[expired, "direction"], 0)
                self.assertTrue(actual.at[expired, "macro_unavailable"])
                self.assertTrue(actual.at[expired, "h4_incomplete"])
                self.assertEqual(context.at[opened, "status"], "CARRIED_CAUSE_UNKNOWN")
                pd.testing.assert_frame_equal(native, original)
                pd.testing.assert_frame_equal(actual[["open", "high", "low", "close"]], bars)

    def test_disabled_frame_matches_native_complete_frame_and_six_swap_results(self):
        frame = frame_at(["2026-04-07T23:30Z", "2026-04-07T23:45Z", "2026-04-08T00:00Z"], [1, 0, 0])
        frame["raw_direction"] = frame.direction
        bars = frame[["open", "high", "low", "close"]]
        actual, witness = subject.carry_frame(bars, frame, enabled=False)
        pd.testing.assert_frame_equal(actual, frame)
        self.assertIsNone(witness)
        ticks = tape_at(
            ["2026-04-07T23:45Z", "2026-04-08T00:00Z", "2026-04-08T00:15Z"], [100.0, 100.0, 98.0]
        )
        for guard in ("raw", "cent"):
            engine = replay if guard == "raw" else cent_variant(replay)
            for name, costs in (
                ("base", Costs()),
                ("stress", Costs(extra_spread=0.2, slippage=0.1)),
                ("fee", Costs(extra_spread=0.2, slippage=0.1, commission_per_lot=7)),
            ):
                with self.subTest(guard=guard, view=name):
                    kw = dict(
                        start=frame.index[0].normalize(),
                        end=pd.Timestamp("2026-04-08T00:16Z"),
                        swap_policy=VALID_SWAP,
                        capture_events=True,
                        capture_context=True,
                    )
                    expected = engine(frame, ticks, BROKER, native_rules(), costs, **kw)
                    observed = engine(actual, ticks, BROKER, native_rules(), costs, **kw)
                    self.assertEqual(observed, expected)
                    self.assertIsNotNone(observed["swap_policy"])
                    self.assertEqual(observed["trades"], 1)

    def test_frame_and_clock_invalidity_fail_closed(self):
        bars = bars_with_gap()
        native, _ = prepare(bars, read(SEED))
        for flag in (1, None, "true"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                subject.carry_frame(bars, native, enabled=flag)
        for invalid in (
            bars.iloc[::-1],
            bars.set_axis(bars.index.tz_localize(None)),
            pd.concat([bars.iloc[:1], bars]),
            bars.set_axis(bars.index + pd.Timedelta(minutes=1)),
        ):
            with self.subTest(index=invalid.index[:2]), self.assertRaises(ValueError):
                subject.h4_context(invalid)
        altered = bars.copy()
        altered.iloc[-1, altered.columns.get_loc("close")] += 1
        with self.assertRaisesRegex(ValueError, "ohlc_mismatch"):
            subject.carry_frame(altered, native, enabled=False)

    def test_candidate_identity_binds_policy_beyond_native_rules(self):
        rules = read(subject.PARENT / "protocol.json")["native_rules"]
        initial = subject.catalog(rules)
        self.assertEqual(len(initial["profiles"]), 2)
        candidate = initial["profiles"][1]
        self.assertNotEqual(candidate["name"], subject.BASE)
        self.assertEqual(candidate["descriptor"]["native_rules"], rules)
        with patch.object(subject, "POLICY", dict(subject.POLICY, max_age_hours_exclusive=4)):
            self.assertNotEqual(subject.catalog(rules)["profiles"][1]["name"], candidate["name"])

    def test_source_guard_rejects_changed_or_new_loaded_repo_dependency(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            path = Path(temp) / "dependency.py"
            path.write_text("unchanged = True\n")
            module = types.ModuleType("h4_dependency_fixture")
            module.__file__ = str(path)
            before = subject.loaded_repo_sources()
            runtime = subject.loaded_runtime_sources()
            with patch.dict("sys.modules", {module.__name__: module}):
                with self.assertRaisesRegex(ValueError, "unpinned_or_changed"):
                    subject.check_loaded(dict(sources=before, runtime_sources=runtime))
                pins = subject.loaded_repo_sources()
                subject.check_loaded(dict(sources=pins, runtime_sources=runtime))
                path.write_text("changed = True\n")
                with self.assertRaisesRegex(ValueError, "unpinned_or_changed"):
                    subject.check_loaded(dict(sources=pins, runtime_sources=runtime))

    def test_choice_preserves_every_native_view_and_native_ties(self):
        def row(value):
            return {
                g: {
                    v: dict(metrics=dict(net_usd=value, max_dd_pct=20.0, survival=True))
                    for v in subject.VIEWS
                }
                for g in subject.GUARDS
            }

        baseline = row(100.0)
        protocol = dict(
            original_floors={
                g: {v: dict(net_usd=50.0) for v in subject.VIEWS} for g in subject.GUARDS
            }
        )
        self.assertEqual(
            subject.choose(protocol, {subject.BASE: baseline, "B": row(100.0)})[0], subject.BASE
        )
        worse_fee = row(101.0)
        worse_fee["cent"]["fee"]["metrics"]["net_usd"] = 99.0
        self.assertEqual(
            subject.choose(protocol, {subject.BASE: baseline, "B": worse_fee})[0], subject.BASE
        )
        for change in (dict(max_dd_pct=40.0001), dict(survival=False)):
            rejected = row(101.0)
            rejected["raw"]["stress"]["metrics"].update(change)
            self.assertEqual(
                subject.choose(protocol, {subject.BASE: baseline, "B": rejected})[0], subject.BASE
            )
        self.assertEqual(
            subject.choose(protocol, {subject.BASE: baseline, "B": row(101.0)})[0], "B"
        )

    def test_run_does_not_implicitly_freeze_or_start_unregistered_campaign(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            with self.assertRaisesRegex(ValueError, "reviewed_source_freeze_required"):
                subject.run(Path(temp))
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_freeze_and_run_refuse_a_second_campaign_writer(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            protocol = dict(
                algorithm=subject.ALGORITHM,
                policy=subject.POLICY,
                baseline_id=subject.BASE,
                execution_authorized=False,
            )
            (out / "protocol.json").write_text(json.dumps(protocol))
            with (out / "campaign.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(subject, "validate") as validate:
                    for action in (subject.freeze, subject.run):
                        with (
                            self.subTest(action=action.__name__),
                            self.assertRaises(BlockingIOError),
                        ):
                            action(out)
                    self.assertEqual(validate.call_count, 2)

    def test_forbidden_destinations_refuse_before_lock_protocol_or_directory_writes(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            unrelated = Path(temp)
            sentinel = unrelated / "unrelated.txt"
            sentinel.write_text("preserve unrelated evidence")
            forbidden = [
                subject.ROOT / "runs",
                subject.INPUT,
                subject.INPUT.parent,
                subject.PARENT,
                subject.PARENT / "child",
                unrelated,
            ]
            with (
                patch.object(Path, "mkdir", side_effect=AssertionError("unexpected_mkdir")),
                patch.object(Path, "open", side_effect=AssertionError("unexpected_open")),
                patch.object(subject.fcntl, "flock", side_effect=AssertionError("unexpected_lock")),
            ):
                for path in forbidden:
                    for action in (subject.freeze, subject.run):
                        with (
                            self.subTest(path=str(path), action=action.__name__),
                            self.assertRaises(ValueError),
                        ):
                            action(path)
            self.assertEqual(sentinel.read_text(), "preserve unrelated evidence")
            self.assertEqual({p.name for p in unrelated.iterdir()}, {"unrelated.txt"})

    def test_existing_own_destination_requires_exact_protocol_validation(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            protocol = dict(
                algorithm=subject.ALGORITHM,
                policy=subject.POLICY,
                baseline_id=subject.BASE,
                execution_authorized=False,
            )
            (out / "protocol.json").write_text(json.dumps(protocol))
            with patch.object(subject, "validate") as validate:
                self.assertEqual(subject.safe_out(out), out)
                validate.assert_called_once_with(protocol, out)
            with patch.object(subject, "validate", side_effect=ValueError("source_drift")):
                with self.assertRaisesRegex(ValueError, "invalid_campaign_destination"):
                    subject.safe_out(out)

    def test_reviewed_empty_lock_can_resume_without_deleting_or_replacing_it(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            lock = out / "campaign.lock"
            lock.touch()
            inode = lock.stat().st_ino
            with patch.object(subject, "_freeze_locked", return_value={"reviewed": True}) as freeze:
                with self.assertRaisesRegex(ValueError, "nonempty_unrelated"):
                    subject.freeze(out)
                freeze.assert_not_called()
                self.assertEqual(subject.freeze(out, resume_empty_freeze=True), {"reviewed": True})
                freeze.assert_called_once_with(out)
            self.assertEqual(lock.stat().st_ino, inode)
            self.assertEqual(lock.read_bytes(), b"")
            self.assertEqual({p.name for p in out.iterdir()}, {"campaign.lock"})

    def test_empty_lock_resume_still_requires_exclusive_lock(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            with (out / "campaign.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(subject, "_freeze_locked") as freeze:
                    with self.assertRaises(BlockingIOError):
                        subject.freeze(out, resume_empty_freeze=True)
                    freeze.assert_not_called()

    def test_empty_lock_resume_refuses_links_contents_or_unrelated_artifacts(self):
        for kind in ("symlink", "hardlink", "nonempty", "directory", "orphan"):
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp,
                tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as targets,
            ):
                out = Path(temp)
                lock = out / "campaign.lock"
                target = Path(targets) / "preserved"
                target.write_bytes(b"")
                if kind == "symlink":
                    lock.symlink_to(target)
                elif kind == "hardlink":
                    os.link(target, lock)
                elif kind == "directory":
                    lock.mkdir()
                else:
                    lock.write_bytes(b"unrelated" if kind == "nonempty" else b"")
                if kind == "orphan":
                    (out / "catalog.json").write_text("{}")
                with (
                    patch.object(subject, "_freeze_locked") as freeze,
                    patch.object(
                        subject.fcntl,
                        "flock",
                        side_effect=AssertionError("must_refuse_before_lock"),
                    ),
                ):
                    with self.assertRaises(ValueError):
                        subject.freeze(out, resume_empty_freeze=True)
                    freeze.assert_not_called()
                self.assertEqual(target.read_bytes(), b"")

    def test_freeze_rechecks_destination_after_exclusive_lock_before_writes(self):
        with tempfile.TemporaryDirectory(dir=subject.ROOT / "runs") as temp:
            out = Path(temp)
            (out / "campaign.lock").touch()
            original = subject.fcntl.flock

            def acquire_and_inject(*args):
                original(*args)
                (out / "unexpected.json").write_text("preserve")

            with (
                patch.object(subject.fcntl, "flock", side_effect=acquire_and_inject),
                patch.object(subject, "_freeze_locked") as freeze,
            ):
                with self.assertRaisesRegex(ValueError, "nonempty_unrelated"):
                    subject.freeze(out, resume_empty_freeze=True)
                freeze.assert_not_called()
            self.assertEqual((out / "unexpected.json").read_text(), "preserve")

    def test_empty_freeze_review_requires_explicit_boolean_and_freeze_command(self):
        for flag in (1, "yes", None):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "explicit_boolean"):
                subject.safe_out(subject.DEFAULT_OUT, resume_empty_freeze=flag)
        for command in ("preflight", "run", "check"):
            with (
                self.subTest(command=command),
                patch("sys.argv", ["carry", command, "--resume-empty-freeze"]),
                patch.object(subject, "plan") as plan,
                patch.object(subject, "run") as run,
                patch.object(subject, "validate") as validate,
                redirect_stderr(StringIO()),
            ):
                with self.assertRaises(SystemExit) as error:
                    subject.main()
                self.assertEqual(error.exception.code, 2)
                plan.assert_not_called()
                run.assert_not_called()
                validate.assert_not_called()

    def test_dependency_warmup_exercises_six_swap_views_without_saving_cells(self):
        protocol = read(subject.PARENT / "protocol.json")
        previous_worker = subject.parent_engine._WORKER
        with patch.object(
            subject, "write", side_effect=AssertionError("warmup_must_not_save_cells")
        ):
            subject.warm_dependencies(protocol)
        self.assertIs(subject.parent_engine._WORKER, previous_worker)


if __name__ == "__main__":
    unittest.main()
