"""Public replay/accounting seam: synthetic checks, not economic qualification."""

import unittest

import pandas as pd

from scripts.research.breakout_models import Costs
from scripts.research.breakout_replay import replay as native_replay
from scripts.research.rollover import SwapPolicy
from scripts.research.c22_profit_preservation import replay
from tests.research.test_c22_risk_replay import (
    BROKER, VALID_SWAP, frame_at, native_rules, tape_at,
)


class PreservationReplayTests(unittest.TestCase):
    def test_stop_width_override_reduces_risk_without_changing_other_side_or_lot(self):
        for direction in (1, -1):
            frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [direction, 0])
            ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z'], [100, 100])
            args = (frame, ticks, BROKER, native_rules(), Costs())
            kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                          end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
            native = replay(*args, **kwargs)
            side = 'buy_stop_atr' if direction == 1 else 'sell_stop_atr'
            opposite = 'sell_stop_atr' if direction == 1 else 'buy_stop_atr'
            changed = replay(*args, **kwargs, **{side: 2.0})
            unaffected = replay(*args, **kwargs, **{opposite: 2.0})
            self.assertEqual(unaffected['ledger'], native['ledger'])
            self.assertEqual(changed['ledger'][0]['volume'], .01)
            self.assertEqual(changed['ledger'][0]['entry'], native['ledger'][0]['entry'])
            self.assertAlmostEqual(changed['ledger'][0]['risk_usd'], 2.0)
            self.assertLess(changed['ledger'][0]['risk_usd'], native['ledger'][0]['risk_usd'])
        with self.assertRaises(ValueError):
            replay(*args, **kwargs, buy_stop_atr=.5)

    def test_conditional_buy_target_uses_entry_equity_and_keeps_low_risk_native(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z',
                          '2026-04-07T12:30Z'], [1, 0, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z',
                         '2026-04-07T12:45Z'], [100, 105.3, 100])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:46Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        excluded = replay(*args, **kwargs, buy_target_rr=2, min_buy_target_risk_pct=2)
        included = replay(*args, **kwargs, buy_target_rr=2, min_buy_target_risk_pct=1)
        self.assertEqual(excluded['ledger'], native['ledger'])
        self.assertEqual(included['ledger'][0]['reason'], 'TP')
        self.assertAlmostEqual(included['ledger'][0]['net'], 5)
        self.assertEqual(included['ledger'][0]['risk_usd'], native['ledger'][0]['risk_usd'])

    def test_bar_quality_guard_rejects_weak_signal_before_entry_and_risk_allocation(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [1, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z'], [100, 100])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
        self.assertEqual(replay(*args, **kwargs)['trades'], 1)
        for guard in ('body_dominant', 'close_extreme'):
            rejected = replay(*args, **kwargs, entry_guard=guard)
            self.assertEqual(rejected['ledger'], [])
            self.assertEqual(rejected['rejections']['entry_guard'], 1)
            self.assertEqual(rejected['final_balance'], 200)

    def test_rollover_recipe_suppresses_entries_without_removing_management_bars(self):
        from scripts.research.c22_profit_preservation_campaign import entry_recipe
        from scripts.research.c22_frequency_adapter import baseline_config, prepare
        from tests.research.test_c22_frequency import bars
        seed = dict(baseline_config(), rsi_period=7, rsi_threshold=30,
                    sell_lookback=48, macro_span=0)
        original, rules = prepare(bars(), seed)
        filtered, filtered_rules = prepare(bars(), entry_recipe(
            seed, {'entry_overrides': {'entry_session': 'avoid_rollover'}}))
        late = (filtered.index + pd.Timedelta(minutes=15)).hour >= 21
        self.assertTrue((original.direction[late] != 0).any())
        self.assertTrue((filtered.direction[late] == 0).all())
        self.assertTrue(original.index.equals(filtered.index))
        self.assertTrue(original.close.equals(filtered.close))
        self.assertEqual(rules, filtered_rules)

    def test_m15_ema_entry_overrides_keep_other_side_and_exit_rules(self):
        from scripts.research.c22_profit_preservation_campaign import entry_recipe
        from scripts.research.c22_frequency_adapter import baseline_config, prepare
        from tests.research.test_c22_frequency import bars
        seed = dict(baseline_config(), rsi_period=7, rsi_threshold=30,
                    sell_lookback=48, macro_span=0)
        original, rules = prepare(bars(), seed)
        off, off_rules = prepare(bars(), entry_recipe(seed, {'entry_overrides': {'buy_ema': 0}}))
        self.assertEqual(rules, off_rules)
        self.assertGreater(int((off.direction == 1).sum()), int((original.direction == 1).sum()))
        self.assertTrue(((off.direction == -1) == (original.direction == -1)).all())
        slow, slow_rules = prepare(bars(), entry_recipe(seed, {'entry_overrides': {'sell_ema': 200}}))
        self.assertEqual(rules, slow_rules)
        self.assertTrue(((slow.direction == 1) == (original.direction == 1)).all())
        with self.assertRaises(ValueError):
            entry_recipe(seed, {'entry_overrides': {'macro_span': 50}})

    def test_authorized_h4_recipes_change_only_filter_and_use_closed_history(self):
        from scripts.research.c22_profit_preservation_campaign import entry_recipe
        from scripts.research.c22_frequency_adapter import baseline_config, prepare
        from tests.research.test_c22_frequency import bars
        seed = dict(baseline_config(), rsi_period=7, rsi_threshold=30,
                    sell_lookback=48, macro_span=200)
        source = bars(6000)
        original, rules = prepare(source, seed)
        cutoff = source.index[-500]
        changed_future = source.copy()
        changed_future.loc[cutoff:, ['open', 'high', 'low', 'close']] += 500
        for span in (100, 0):
            recipe = entry_recipe(seed, {'entry_overrides': {'macro_span': span}})
            variant, variant_rules = prepare(source, recipe)
            future, _ = prepare(changed_future, recipe)
            self.assertEqual(rules, variant_rules)
            self.assertEqual(seed['macro_span'], 200)
            self.assertTrue(variant.index.equals(original.index))
            self.assertTrue(variant.raw_direction.equals(original.raw_direction))
            self.assertTrue((variant.direction != original.direction).any())
            pd.testing.assert_series_equal(variant.direction.loc[variant.index < cutoff],
                                           future.direction.loc[future.index < cutoff])
            if span == 0:
                self.assertTrue(variant.direction.equals(variant.raw_direction))

    def test_native_reference_requires_selected_signal_recipe(self):
        from scripts.research.c22_profit_preservation_campaign import require_native_entry_recipe
        native = dict(strategy='reward156', formula='archived', rsi_period=7,
                      rsi_threshold=30, sell_lookback=48, sell_ema=50,
                      buy_ema=50, macro_span=200, entry_session='all')
        require_native_entry_recipe(native)
        for delta in ({'rsi_period': 14}, {'rsi_threshold': 25}, {'sell_lookback': 96},
                      {'buy_ema': 0}, {'macro_span': 0}):
            with self.assertRaisesRegex(ValueError, 'native reference entry'):
                require_native_entry_recipe(native | delta)

    def test_catalog_cannot_redefine_or_omit_native_reference(self):
        from scripts.research.c22_profit_preservation_campaign import require_native_reference
        for catalog in ({}, {'candidate': {}}, {'native': None},
                        {'native': {'entry_overrides': {'rsi_period': 14}}},
                        {'native': {'buy_target_rr': 2}}):
            with self.assertRaisesRegex(ValueError, 'native reference'):
                require_native_reference(catalog)
        require_native_reference({'native': {}, 'candidate': {'buy_target_rr': 2}})

    def test_rsi_period_recipe_changes_buy_signals_and_keeps_sell_and_risk(self):
        from scripts.research.c22_profit_preservation_campaign import entry_recipe
        from scripts.research.c22_frequency_adapter import baseline_config, prepare
        from tests.research.test_c22_frequency import bars
        seed = dict(baseline_config(), rsi_period=7, rsi_threshold=30, sell_lookback=48)
        variant = entry_recipe(seed, {'entry_overrides': {'rsi_period': 14}})
        original, rules = prepare(bars(), seed)
        changed, changed_rules = prepare(bars(), variant)
        self.assertEqual(rules, changed_rules)
        self.assertTrue(((changed.direction == -1) == (original.direction == -1)).all())
        self.assertTrue(((changed.direction == 1) != (original.direction == 1)).any())

    def test_account_carry_rejects_switching_entry_recipe(self):
        frame = frame_at(['2026-04-07T00:00Z', '2026-04-08T00:00Z'], [0, 0])
        ticks = tape_at(['2026-04-07T00:15Z', '2026-04-08T00:15Z'], [100, 100])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        first = replay(*args, start=pd.Timestamp('2026-04-07T00:00Z'),
                       end=pd.Timestamp('2026-04-08T00:00Z'), swap_policy=VALID_SWAP,
                       entry_recipe_id='native', finalize=False)
        with self.assertRaisesRegex(ValueError, 'changed account contract'):
            replay(*args, start=pd.Timestamp('2026-04-08T00:00Z'),
                   end=pd.Timestamp('2026-04-09T00:00Z'), swap_policy=VALID_SWAP,
                   entry_recipe_id='changed', state=first['carry_state'])

    def test_entry_recipe_changes_real_donchian_signals_without_changing_buy_or_risk(self):
        from scripts.research.c22_profit_preservation_campaign import entry_recipe
        from scripts.research.c22_frequency_adapter import baseline_config, prepare
        from tests.research.test_c22_frequency import bars
        seed = dict(baseline_config(), rsi_period=7, rsi_threshold=30, sell_lookback=48)
        unchanged = dict(seed)
        variant = entry_recipe(seed, {'entry_overrides': {'sell_lookback': 96}})
        original, rules = prepare(bars(), seed)
        changed, changed_rules = prepare(bars(), variant)
        self.assertEqual(seed, unchanged)
        self.assertEqual(rules, changed_rules)
        self.assertTrue(((changed.direction != -1) | (original.direction == -1)).all())
        self.assertLess(int((changed.direction == -1).sum()), int((original.direction == -1).sum()))
        self.assertTrue(((changed.direction == 1) == (original.direction == 1)).all())
        for overrides in ({'risk_cap': .2}, {'buy_target_rr': 2.0}, {'sell_lookback': 0}):
            with self.assertRaises(ValueError):
                entry_recipe(seed, {'entry_overrides': overrides})

    def test_coupled_sell_be_is_limited_to_original_risk_band(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z',
                          '2026-04-07T12:30Z'], [-1, 0, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z',
                         '2026-04-07T12:30:01Z', '2026-04-07T12:45Z'],
                        [100, 98.3, 100.1, 103])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:46Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        excluded = replay(*args, **kwargs, sell_target_rr=3, min_sell_target_risk_usd=100,
                          conditional_sell_protect_after_r=.5)
        included = replay(*args, **kwargs, sell_target_rr=3, min_sell_target_risk_usd=1,
                          conditional_sell_protect_after_r=.5)
        self.assertEqual(excluded['ledger'], native['ledger'])
        self.assertGreater(included['final_balance'], native['final_balance'])
        self.assertTrue(included['ledger'][0]['protection_active'])
        self.assertEqual(included['ledger'][0]['risk_usd'], native['ledger'][0]['risk_usd'])

    def test_conditional_sell_target_uses_original_risk_without_changing_admission(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [-1, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z'], [100, 100])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        excluded = replay(*args, **kwargs, sell_target_rr=3.0, min_sell_target_risk_usd=100)
        included = replay(*args, **kwargs, sell_target_rr=3.0, min_sell_target_risk_usd=1)
        self.assertEqual(excluded['ledger'], native['ledger'])
        self.assertAlmostEqual(included['ledger'][0]['target'], 92.5)
        for key in ('entry', 'initial_stop', 'volume', 'risk_usd', 'risk_pct'):
            self.assertEqual(included['ledger'][0][key], native['ledger'][0][key])

    def test_sell_target_tuning_leaves_buy_geometry_and_both_risk_caps_intact(self):
        for direction in (1, -1):
            frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [direction, 0])
            ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z'], [100, 100])
            args = (frame, ticks, BROKER, native_rules(), Costs())
            kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                          end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
            native = replay(*args, **kwargs)
            changed = replay(*args, **kwargs, sell_target_rr=1.5)
            if direction == 1:
                self.assertEqual(changed['ledger'], native['ledger'])
            else:
                self.assertAlmostEqual(changed['ledger'][0]['target'], 96.25)
                for key in ('entry', 'initial_stop', 'volume', 'risk_usd', 'risk_pct'):
                    self.assertEqual(changed['ledger'][0][key], native['ledger'][0][key])

    def test_buy_target_tuning_preserves_entry_stop_lot_and_risk(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z',
                          '2026-04-07T12:30Z'], [1, 0, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z',
                         '2026-04-07T12:45Z'], [100, 105.3, 100])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:46Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        changed = replay(*args, **kwargs, buy_target_rr=2.0)
        self.assertEqual(changed['ledger'][0]['reason'], 'TP')
        self.assertAlmostEqual(changed['ledger'][0]['net'], 5.0)
        for key in ('entry_time_utc', 'entry', 'initial_stop', 'volume', 'risk_usd', 'risk_pct'):
            self.assertEqual(changed['ledger'][0][key], native['ledger'][0][key])

    def test_unexecutable_swap_coverage_falls_back_to_native_be(self):
        frame = frame_at(['2026-04-07T23:30Z', '2026-04-07T23:45Z',
                          '2026-04-08T00:00Z'], [1, 0, 0])
        ticks = tape_at(['2026-04-07T23:45Z', '2026-04-08T00:00Z',
                         '2026-04-08T00:00:01Z', '2026-04-08T00:15Z'],
                        [100, 103, 100.1, 97])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-08T00:16Z'),
                      swap_policy=SwapPolicy(-4, 0, 1))
        native = replay(*args, **kwargs)
        changed = replay(*args, **kwargs, buy_swap_be_fraction=1)
        self.assertEqual(changed['ledger'], native['ledger'])
        self.assertAlmostEqual(changed['final_balance'], 195.9)

    def test_zero_swap_cannot_change_native_be_rounding(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [1, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:30Z',
                         '2026-04-07T12:30:01Z', '2026-04-07T12:30:02Z'],
                        [999.703, 1003.1, 1000.1035, 1000.0])
        args = (frame, ticks, BROKER, native_rules(), Costs(slippage=.1))
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        changed = replay(*args, **kwargs, buy_swap_be_fraction=1)
        self.assertEqual(changed['ledger'], native['ledger'])
        self.assertAlmostEqual(native['final_balance'], 200.0005)

    def test_swap_be_uses_only_accrued_debit_and_preserves_native_activation(self):
        frame = frame_at(['2026-04-07T23:30Z', '2026-04-07T23:45Z',
                          '2026-04-08T00:00Z'], [1, 0, 0])
        ticks = tape_at(['2026-04-07T23:45Z', '2026-04-08T00:00Z',
                         '2026-04-08T00:00:01Z', '2026-04-08T00:15Z'],
                        [100, 103.5, 100.5, 97])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-08T00:16Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        changed = replay(*args, **kwargs, buy_swap_be_fraction=1.0)
        guarded = replay(*args, **kwargs, buy_swap_be_fraction=1.0,
                         buy_swap_be_min_cost_r=0.5)
        self.assertEqual(guarded['ledger'], native['ledger'])
        self.assertGreater(changed['final_balance'], native['final_balance'])
        self.assertAlmostEqual(changed['ledger'][0]['stop'], 100.6)
        self.assertAlmostEqual(changed['ledger'][0]['swap_usd'], -0.4)
        self.assertEqual(changed['ledger'][0]['entry_time_utc'], native['ledger'][0]['entry_time_utc'])

    def test_buy_be_headroom_uses_entry_risk_and_keeps_native_protection(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [1, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:15:05Z',
                         '2026-04-07T12:15:10Z', '2026-04-07T12:30Z'],
                        [100, 103, 100.1, 97])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
        native = replay(*args, **kwargs)
        blocked = replay(*args, **kwargs, buy_be=(1, 5), buy_be_max_risk_pct=1.0)
        enabled = replay(*args, **kwargs, buy_be=(1, 5), buy_be_max_risk_pct=5.0)
        self.assertEqual(blocked['ledger'], native['ledger'])
        self.assertGreater(enabled['final_balance'], native['final_balance'])
        self.assertAlmostEqual(enabled['ledger'][0]['risk_pct'], 1.25)
        for invalid in (0, -1, 10.1, float('nan')):
            with self.assertRaises(ValueError):
                replay(*args, **kwargs, buy_be=(1, 5), buy_be_max_risk_pct=invalid)

    def test_split_inside_poll_bucket_cannot_create_an_extra_buy_poll(self):
        frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'], [1, 0])
        ticks = tape_at(['2026-04-07T12:15Z', '2026-04-07T12:15:05Z',
                         '2026-04-07T12:15:07Z', '2026-04-07T12:15:08Z',
                         '2026-04-07T12:15:10Z', '2026-04-07T12:30Z'],
                        [100, 101, 103, 100.1, 97, 97])
        args = (frame, ticks, BROKER, native_rules(), Costs())
        start, split, end = map(pd.Timestamp, ['2026-04-07T00:00Z',
                                              '2026-04-07T12:15:06Z', '2026-04-07T12:31Z'])
        options = dict(swap_policy=VALID_SWAP, buy_be=(1, 5))
        whole = replay(*args, start=start, end=end, **options)
        first = replay(*args, start=start, end=split, finalize=False, **options)
        second = replay(*args, start=split, end=end, state=first['carry_state'], **options)
        self.assertEqual(first['ledger'] + second['ledger'], whole['ledger'])
        self.assertEqual(second['final_balance'], whole['final_balance'])

    def test_selection_uses_training_only_and_falls_back_to_native(self):
        from scripts.research.c22_profit_preservation import select
        cells = {'native': {}, 'buy_be': {}}
        for view in ('base', 'stress'):
            cells['native'][('train', view)] = dict(net=0, dd=10)
            cells['native'][('heldout', view)] = dict(net=100, dd=10)
            cells['buy_be'][('train', view)] = dict(net=1, dd=9)
            cells['buy_be'][('heldout', view)] = dict(net=-100, dd=99)
        self.assertEqual(select(cells, ['train']), 'buy_be')
        self.assertEqual(select(cells, ['heldout']), 'native')

    def test_missing_swap_and_noncontiguous_carry_fail_closed(self):
        frame = frame_at(['2026-04-07T00:00Z'], [0])
        ticks = tape_at(['2026-04-07T00:15Z'], [100])
        kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-08T00:00Z'))
        args = (frame, ticks, BROKER, native_rules(), Costs())
        with self.assertRaisesRegex(ValueError, 'swap metadata'):
            replay(*args, **kwargs, swap_policy=None)
        previous = replay(*args, **kwargs, swap_policy=VALID_SWAP, finalize=False)
        with self.assertRaisesRegex(ValueError, 'non-contiguous'):
            replay(*args, **kwargs, swap_policy=VALID_SWAP, state=previous['carry_state'])

    def test_daily_losses_and_cooldown_survive_chunk_boundary(self):
        frame = frame_at(['2026-04-07T00:00Z', '2026-04-07T00:30Z',
                          '2026-04-07T01:00Z'], [1, 1, 1])
        ticks = tape_at(['2026-04-07T00:15Z', '2026-04-07T00:29Z',
                         '2026-04-07T00:45Z', '2026-04-07T01:15Z'], [100, 97, 100, 100])
        args = (frame, ticks, BROKER, native_rules(max_daily_losses=1), Costs())
        start, split, end = map(pd.Timestamp, ['2026-04-07T00:00Z',
                                              '2026-04-07T00:30Z', '2026-04-07T01:16Z'])
        whole = replay(*args, start=start, end=end, swap_policy=VALID_SWAP)
        first = replay(*args, start=start, end=split, swap_policy=VALID_SWAP, finalize=False)
        second = replay(*args, start=split, end=end, swap_policy=VALID_SWAP,
                        state=first['carry_state'])
        self.assertEqual(first['ledger'] + second['ledger'], whole['ledger'])
        self.assertEqual(second['final_balance'], whole['final_balance'])
        self.assertEqual(second['rejections']['daily_loss_count'], 1)
        self.assertEqual(second['rejections']['cooldown'], 1)

    def test_strict_gate_rejects_one_bad_year_and_no_change(self):
        from scripts.research.c22_profit_preservation import passes
        baseline = {('2020', v): dict(net=-10.0, dd=20.0) for v in ('base', 'stress')}
        improved = {key: dict(net=-9.0, dd=19.0) for key in baseline}
        self.assertTrue(passes(improved, baseline))
        self.assertFalse(passes(baseline, baseline))
        improved[('2020', 'stress')]['dd'] = 20.1
        self.assertFalse(passes(improved, baseline))
        improved[('2020', 'stress')] = dict(net=float('nan'), dd=19.0)
        self.assertFalse(passes(improved, baseline))

    def test_buy_tick_be_saves_retracement_without_changing_sell_management(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                frame = frame_at(['2026-04-07T12:00Z', '2026-04-07T12:15Z'],
                                 [direction, 0])
                ticks = tape_at([
                    '2026-04-07T12:15Z', '2026-04-07T12:15:05Z',
                    '2026-04-07T12:15:10Z', '2026-04-07T12:30Z',
                ], [100, 103, 100.1, 97] if direction == 1 else [100, 97, 103, 100])
                kwargs = dict(start=pd.Timestamp('2026-04-07T00:00Z'),
                              end=pd.Timestamp('2026-04-07T12:31Z'), swap_policy=VALID_SWAP)
                args = (frame, ticks, BROKER, native_rules(), Costs())
                native = replay(*args, **kwargs)
                changed = replay(*args, **kwargs, buy_be=(1.0, 5))
                if direction == 1:
                    self.assertGreater(changed['final_balance'], native['final_balance'])
                    self.assertTrue(changed['ledger'][0]['protection_active'])
                    self.assertEqual(changed['ledger'][0]['exit_time_utc'],
                                     '2026-04-07T12:15:10+00:00')
                else:
                    self.assertEqual(changed['ledger'], native['ledger'])

    def test_off_matches_native_and_split_carries_open_trade_swap_and_daily_state(self):
        frame = frame_at([
            "2026-04-07T23:30Z", "2026-04-07T23:45Z", "2026-04-08T00:00Z",
            "2026-04-08T23:45Z", "2026-04-09T00:00Z",
        ], [1, 0, 1, 0, 1])
        ticks = tape_at([
            "2026-04-07T23:45Z", "2026-04-07T23:59:59Z", "2026-04-08T00:00Z",
            "2026-04-08T00:15Z", "2026-04-09T00:00Z", "2026-04-09T00:15Z",
        ], [100, 101, 103.5, 103.6, 100, 100])
        start = pd.Timestamp("2026-04-07T00:00Z")
        split = pd.Timestamp("2026-04-08T00:00Z")
        end = pd.Timestamp("2026-04-09T00:16Z")
        costs = Costs(slippage=0.1, commission_per_lot=20)
        args = (frame, ticks, BROKER, native_rules(), costs)
        kwargs = dict(start=start, end=end, swap_policy=VALID_SWAP, capture_events=True)
        native = native_replay(*args, **kwargs)
        whole = replay(*args, **kwargs)
        self.assertEqual(whole['ledger'], native['ledger'])
        self.assertEqual(whole['admission_events'], native['admission_events'])
        self.assertEqual(whole['final_balance'], native['final_balance'])
        first = replay(*args, start=start, end=split, swap_policy=VALID_SWAP, finalize=False)
        self.assertEqual(first['ledger'], [])
        self.assertIsNotNone(first['carry_state']['position'])
        second = replay(*args, start=split, end=end, swap_policy=VALID_SWAP,
                        state=first['carry_state'])
        self.assertEqual(second['ledger'], whole['ledger'])
        self.assertAlmostEqual(second['final_balance'], whole['final_balance'])
        self.assertAlmostEqual(second['max_dd_pct'], whole['max_dd_pct'])
        self.assertAlmostEqual(second['final_balance'], 200 + sum(t['net'] for t in second['ledger']))


if __name__ == '__main__':
    unittest.main()
