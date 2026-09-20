"""Unit tests for clock risk-halt observe + flatten helpers."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state
from scripts.webhook.clock_risk_halt import flatten_on_risk_halt, observe_and_persist_risk_halt


def _rt(*, halted: bool, adapter) -> SimpleNamespace:
    state = new_risk_halt_state(10000.0)
    if halted:
        state.drawdown_halt = True
    halt_path = Path(tempfile.mkstemp(suffix=".json")[1])
    save_risk_halt_state(halt_path, state)
    return SimpleNamespace(
        risk_halt=state,
        halt_path=halt_path,
        account_balance=10000.0,
        adapter=adapter,
        setup_registry=SimpleNamespace(mark_terminal=Mock()),
    )


class ClockRiskHaltHelperTests(unittest.TestCase):
    def tearDown(self):
        # Best-effort cleanup of halt files created in tests.
        pass

    def test_observe_noop_without_halt_config(self):
        rt = SimpleNamespace(risk_halt=None, halt_path=None, adapter=Mock(), account_balance=1.0)
        asyncio.run(
            observe_and_persist_risk_halt(
                rt,
                now_utc=datetime.now(timezone.utc),
                broker_closes=[],
            )
        )

    def test_flatten_noop_when_not_halted(self):
        adapter = SimpleNamespace(
            dry_run=True,
            list_open_fills=Mock(return_value=[]),
            list_unfilled_pendings=Mock(return_value=["P1"]),
            execute_intent=Mock(),
        )
        rt = _rt(halted=False, adapter=adapter)
        try:
            still, cancels, closes = asyncio.run(flatten_on_risk_halt(rt, pending_ids=["P1"]))
            self.assertEqual(still, ["P1"])
            self.assertEqual(cancels, [])
            self.assertEqual(closes, [])
            adapter.execute_intent.assert_not_called()
        finally:
            rt.halt_path.unlink(missing_ok=True)

    def test_flatten_cancels_pending_when_halted(self):
        adapter = SimpleNamespace(
            dry_run=True,
            list_open_fills=Mock(return_value=[]),
            list_unfilled_pendings=Mock(return_value=["P1"]),
            execute_intent=Mock(return_value=SimpleNamespace(success=True, message="ok")),
            log_lifecycle_event=Mock(),
            finish_setup=Mock(),
        )
        rt = _rt(halted=True, adapter=adapter)
        try:
            still, cancels, closes = asyncio.run(flatten_on_risk_halt(rt, pending_ids=["P1"]))
            self.assertEqual(still, [])
            self.assertEqual(len(cancels), 1)
            self.assertEqual(cancels[0]["order_id"], "P1")
            self.assertEqual(cancels[0]["reason"], "foundation_risk_halt")
            self.assertEqual(closes, [])
            adapter.finish_setup.assert_called_once_with("P1")
        finally:
            rt.halt_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
