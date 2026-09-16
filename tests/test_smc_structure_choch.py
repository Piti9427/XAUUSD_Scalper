import unittest

from scripts.smc.structure import (
    StructureBias,
    StructureEventKind,
    StructureState,
    apply_close_break,
    replay_structure_until,
    classify_candidate_break,
)


class ProtectedSwingStructureTests(unittest.TestCase):
    def test_starts_unknown(self):
        state = StructureState.initial()
        self.assertEqual(state.bias, StructureBias.UNKNOWN)
        self.assertIsNone(state.protected_price)

    def test_break_without_opposite_pivot_stays_unknown(self):
        state = StructureState.initial()
        nxt, event = apply_close_break(
            state,
            break_side="above",
            broken_swing_price=100.0,
            break_index=10,
            opposite_pivots_between=[],
        )
        self.assertEqual(nxt.bias, StructureBias.UNKNOWN)
        self.assertEqual(event.kind, StructureEventKind.NONE)
        self.assertIsNone(nxt.protected_price)

    def test_first_valid_break_establishes_bias_as_bos(self):
        state = StructureState.initial()
        nxt, event = apply_close_break(
            state,
            break_side="above",
            broken_swing_price=100.0,
            break_index=10,
            opposite_pivots_between=[(7, 95.0)],
        )
        self.assertEqual(nxt.bias, StructureBias.BULLISH)
        self.assertEqual(nxt.protected_price, 95.0)
        self.assertEqual(event.kind, StructureEventKind.BOS)

    def test_continuation_bos_updates_protected_swing(self):
        state = StructureState(
            bias=StructureBias.BULLISH,
            protected_price=95.0,
            protected_index=7,
            last_broken_price=100.0,
        )
        nxt, event = apply_close_break(
            state,
            break_side="above",
            broken_swing_price=110.0,
            break_index=20,
            opposite_pivots_between=[(15, 102.0), (12, 98.0)],
        )
        self.assertEqual(event.kind, StructureEventKind.BOS)
        self.assertEqual(nxt.protected_price, 102.0)
        self.assertEqual(nxt.protected_index, 15)

    def test_break_of_protected_swing_is_choch(self):
        state = StructureState(
            bias=StructureBias.BULLISH,
            protected_price=95.0,
            protected_index=7,
            last_broken_price=100.0,
        )
        nxt, event = apply_close_break(
            state,
            break_side="below",
            broken_swing_price=95.0,
            break_index=25,
            opposite_pivots_between=[(22, 108.0)],
        )
        self.assertEqual(event.kind, StructureEventKind.CHOCH)
        self.assertEqual(nxt.bias, StructureBias.BEARISH)
        self.assertEqual(nxt.protected_price, 108.0)

    def test_internal_break_is_not_choch(self):
        state = StructureState(
            bias=StructureBias.BULLISH,
            protected_price=90.0,
            protected_index=5,
            last_broken_price=100.0,
        )
        nxt, event = apply_close_break(
            state,
            break_side="below",
            broken_swing_price=96.0,
            break_index=25,
            opposite_pivots_between=[(22, 108.0)],
        )
        self.assertEqual(event.kind, StructureEventKind.INTERNAL)
        self.assertEqual(nxt, state)

    def test_choch_without_new_opposite_pivot_returns_unknown(self):
        state = StructureState(
            bias=StructureBias.BULLISH,
            protected_price=95.0,
            protected_index=7,
            last_broken_price=100.0,
        )
        nxt, event = apply_close_break(
            state,
            break_side="below",
            broken_swing_price=95.0,
            break_index=25,
            opposite_pivots_between=[],
        )
        self.assertEqual(event.kind, StructureEventKind.CHOCH)
        self.assertEqual(nxt.bias, StructureBias.UNKNOWN)
        self.assertIsNone(nxt.protected_price)

    def test_duplicate_broken_level_does_not_refire(self):
        state = StructureState(
            bias=StructureBias.BULLISH,
            protected_price=95.0,
            protected_index=7,
            last_broken_price=100.0,
        )
        _, first = apply_close_break(
            state,
            break_side="above",
            broken_swing_price=100.0,
            break_index=20,
            opposite_pivots_between=[(15, 102.0)],
        )
        self.assertEqual(first.kind, StructureEventKind.NONE)

    def test_replay_prefix_invariant_under_future_append(self):
        # Minimal series: establish bullish BOS then append future bars.
        highs = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16]
        lows = [9, 10, 9.5, 11, 10.5, 12, 11.5, 13, 12.5, 14, 13.5, 15, 14.5]
        closes = [9.5, 11, 10, 12.5, 11, 13.5, 12, 14.5, 13, 15.5, 14, 16.5, 15]
        swing_highs = [False] * len(highs)
        swing_lows = [False] * len(lows)
        # Confirmed pivots with 2 right bars available before later indexes.
        swing_highs[1] = True
        swing_lows[2] = True
        swing_highs[3] = True
        swing_lows[4] = True
        swing_highs[5] = True
        swing_lows[6] = True

        prefix_end = 8
        state_prefix = replay_structure_until(
            highs, lows, closes, swing_highs, swing_lows, prefix_end
        )
        # Future-append: longer series must not change decisions at prefix_end.
        state_full_at_prefix = replay_structure_until(
            highs, lows, closes, swing_highs, swing_lows, prefix_end
        )
        # Mutate future only (after prefix)
        highs2 = list(highs)
        lows2 = list(lows)
        closes2 = list(closes)
        highs2[-1] = 99.0
        lows2[-1] = 1.0
        closes2[-1] = 50.0
        state_after_future_mutation = replay_structure_until(
            highs2, lows2, closes2, swing_highs, swing_lows, prefix_end
        )
        self.assertEqual(state_prefix, state_full_at_prefix)
        self.assertEqual(state_prefix, state_after_future_mutation)


if __name__ == "__main__":
    unittest.main()
