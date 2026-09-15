import unittest

from scripts.smc.structure import (
    StructureBias,
    StructureEventKind,
    StructureState,
    apply_close_break,
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


if __name__ == "__main__":
    unittest.main()
