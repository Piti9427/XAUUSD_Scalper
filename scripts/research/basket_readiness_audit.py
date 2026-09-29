"""Executable offline reproductions of current BasketManager execution blockers."""

import json
from datetime import datetime, timezone

from scripts.smc.basket_manager import BasketConfig, BasketManager
from scripts.smc.mt5_adapter.execution import ExecutionMixin
from scripts.smc.orchestrator import StrategyOrchestrator
from scripts.smc.types import AccountState, Direction, Position


def main():
    now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)

    def opened():
        mgr = BasketManager(BasketConfig())
        mgr.on_new_signal(Direction.BUY, 2000., 1940., 2150., 200., now)
        return mgr

    manager = opened()
    order = manager.on_bar(-31., 169., now)[0]
    adapter = ExecutionMixin()
    adapter.dry_run = False
    # Target validation exits before any broker dependency or call.
    result = adapter.execute_intent(order)
    assert result.success is False
    snapshot = manager.basket
    manager.on_leg_closed(0, -31.)
    assert snapshot.net_realized_pnl == 0.0

    manager2 = opened()
    account = AccountState(balance=200., equity=169.)
    account.open_position = Position(Direction.BUY, 2000., 1940., 2150., .01, now, 60.)
    intents = StrategyOrchestrator(basket_manager=manager2).on_bar(
        {'time': now, 'open': 1969., 'high': 1970., 'low': 1968., 'close': 1969.},
        account, floating_pnl=-31.)
    assert intents == []
    assert manager2.basket.open_legs

    manager3 = opened()
    manager3.on_bar(-30., 160., now)
    after_both = manager3.state.value
    assert after_both == 'CLOSE_PENDING'
    print(json.dumps({
        'close_without_target_rejected': result.message,
        'close_intent_ticket': order.ticket, 'close_intent_order_id': order.order_id,
        'broker_callback_loss_recorded': snapshot.net_realized_pnl,
        'expected_broker_callback_loss': -31.,
        'open_position_bypasses_basket_stop': len(intents) == 0,
        'simultaneous_basket_stop_and_hwm_state': after_both,
        'note': 'Offline synthetic lifecycle probes, not market data or performance results',
        'order_api_called': False,
    }, indent=2))


if __name__ == '__main__':
    main()
