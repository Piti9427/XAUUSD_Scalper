"""Read-only MT5 seam: a closed bar produces one auditable Pure B1 decision."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import pandas as pd

from scripts.pure_b1.shadow import shadow_cycle


class PureB1ShadowTests(unittest.TestCase):
    def setUp(self):
        opens = pd.date_range(end="2026-09-28 23:45:00+00:00", periods=1000, freq="15min", tz="UTC")
        self.rates = []
        for i, ts in enumerate(opens):
            close = 103.0 if i == 999 else 100.0 + i % 2
            self.rates.append(
                {
                    "time": int(ts.timestamp()),
                    "open": close,
                    "high": close if i == 999 else close + 1,
                    "low": close - 1,
                    "close": close,
                    "tick_volume": 10,
                }
            )
        self.m1_rates = [
            {
                "time": row["time"] + minute * 60,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "tick_volume": 1,
            }
            for row in self.rates
            for minute in range(15)
        ]
        self.mt5 = Mock(TIMEFRAME_M1=1, ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1)
        self.mt5.ACCOUNT_TRADE_MODE_DEMO = 0
        self.mt5.SYMBOL_TRADE_MODE_FULL = 4
        self.mt5.account_info.return_value = SimpleNamespace(
            login=123,
            server="Exness-Demo",
            trade_mode=0,
            margin_mode=2,
            currency="USD",
            balance=200.0,
            equity=200.0,
            margin_free=200.0,
        )
        self.mt5.symbol_info.return_value = SimpleNamespace(
            name="XAUUSDm",
            trade_mode=4,
            trade_stops_level=0,
            trade_freeze_level=0,
            point=0.01,
            trade_contract_size=100.0,
            trade_tick_size=0.01,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
        self.mt5.symbol_info_tick.return_value = SimpleNamespace(
            bid=103.0,
            ask=103.2,
            time_msc=int(
                datetime(2026, 9, 29, 0, 0, 0, 100000, tzinfo=timezone.utc).timestamp() * 1000
            ),
        )
        self.mt5.copy_rates_from_pos.return_value = self.m1_rates
        self.mt5.positions_get.return_value = ()
        self.mt5.orders_get.return_value = ()
        self.mt5.order_calc_margin.return_value = 5.0
        self.mt5.order_calc_profit.side_effect = lambda action, symbol, volume, entry, stop: (
            (stop - entry) * volume * 100 if action == 0 else (entry - stop) * volume * 100
        )
        self.cost = {
            "version": 1,
            "account_fingerprint": hashlib.sha256(b"Exness-Demo:123").hexdigest()[:16],
            "account_type": "Standard Demo",
            "source": "Exness tariff checked 2026-09-29",
            "reviewed_utc": "2026-09-28T23:00:00+00:00",
            "commission_per_lot": 0.0,
            "commission_unit": "USD_per_lot_round_trip",
            "account_evidence_sha256": "a" * 64,
            "slippage_allowance_price": 0.5,
            "swap_free_qualified": True,
        }

    def test_one_closed_bar_is_logged_once_without_orders_or_alerts(self):
        now = datetime(2026, 9, 29, 0, 0, 0, 500000, tzinfo=timezone.utc)
        self.mt5.symbol_info_tick.return_value.time_msc = int(now.timestamp() * 1000)
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "shadow.jsonl"
            state = Path(tmp) / "day.json"
            result = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=log,
                state_path=state,
            )
            self.assertTrue(result["admit"], result)
            self.assertFalse(result["order_api_called"])
            self.assertEqual(result["direction"], 1)
            duplicate = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=log,
                state_path=state,
            )
            self.assertEqual(duplicate["reason"], "duplicate_bar")
            lines = log.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            logged = json.loads(lines[0])
            self.assertEqual(logged["day_start_equity"], 200.0)
            self.assertEqual(logged["indicators"]["atr"], result["atr"])
            self.assertEqual(len(logged["bar_data_sha256"]), 64)
            self.assertEqual(len(logged["contract_sha256"]), 64)
        self.mt5.order_send.assert_not_called()
        self.mt5.order_check.assert_not_called()

    def test_foreign_position_and_missing_day_start_fail_closed(self):
        now = datetime(2026, 9, 29, 12, 0, 30, tzinfo=timezone.utc)
        self.mt5.symbol_info_tick.return_value.time_msc = int(
            datetime(2026, 9, 29, 12, 0, 10, tzinfo=timezone.utc).timestamp() * 1000
        )
        shift = 12 * 3600
        for row in self.m1_rates:
            row["time"] += shift
        self.mt5.positions_get.return_value = (SimpleNamespace(comment="FOREIGN"),)
        with TemporaryDirectory() as tmp:
            result = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=Path(tmp) / "shadow.jsonl",
                state_path=Path(tmp) / "day.json",
            )
            self.assertEqual(result["reason"], "symbol_exposure")
            self.assertFalse(result["admit"])
        self.mt5.positions_get.return_value = ()
        self.cost["reviewed_utc"] = "2026-09-29T11:00:00+00:00"
        with TemporaryDirectory() as tmp:
            result = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=Path(tmp) / "shadow.jsonl",
                state_path=Path(tmp) / "day.json",
            )
            self.assertEqual(result["reason"], "day_start_unknown")
            self.assertFalse(result["admit"])
        self.mt5.order_send.assert_not_called()

    def test_missing_broker_profit_check_blocks_admission(self):
        self.mt5.order_calc_profit.return_value = None
        self.mt5.order_calc_profit.side_effect = None
        with TemporaryDirectory() as tmp:
            result = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=datetime(2026, 9, 29, 0, 0, 0, 500000, tzinfo=timezone.utc),
                log_path=Path(tmp) / "shadow.jsonl",
                state_path=Path(tmp) / "day.json",
            )
            self.assertFalse(result["admit"])
            self.assertEqual(result["reason"], "broker_profit_unknown")

    def test_stale_or_wrong_account_cost_policy_cannot_admit(self):
        for changed in (
            {"reviewed_utc": "2026-09-20T00:00:00+00:00"},
            {"account_fingerprint": "wrong"},
            {"swap_free_qualified": False},
            {"commission_unit": "USD_per_lot_per_side"},
            {"account_evidence_sha256": "missing"},
        ):
            with self.subTest(changed=changed), TemporaryDirectory() as tmp:
                result = shadow_cycle(
                    self.mt5,
                    symbol="XAUUSDm",
                    expected_login=123,
                    expected_server="Exness-Demo",
                    cost_policy=self.cost | changed,
                    now=datetime(2026, 9, 29, 0, 0, 0, 500000, tzinfo=timezone.utc),
                    log_path=Path(tmp) / "shadow.jsonl",
                    state_path=Path(tmp) / "day.json",
                )
                self.assertFalse(result["admit"])
                self.assertEqual(result["reason"], "cost_model_missing")

    def test_changed_balance_and_nontradeable_symbol_fail_closed(self):
        now = datetime(2026, 9, 29, 0, 0, 0, 500000, tzinfo=timezone.utc)
        self.mt5.symbol_info_tick.return_value.time_msc = int(now.timestamp() * 1000)
        with TemporaryDirectory() as tmp:
            log, state = Path(tmp) / "log.jsonl", Path(tmp) / "day.json"
            first = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=log,
                state_path=state,
            )
            self.assertTrue(first["admit"], first)
            self.mt5.account_info.return_value.balance = 220.0
            later = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now + pd.Timedelta(seconds=1),
                log_path=Path(tmp) / "later.jsonl",
                state_path=state,
            )
            self.assertEqual(later["reason"], "balance_changed")
            self.assertFalse(later["admit"])
        self.mt5.symbol_info.return_value.trade_mode = 0
        with TemporaryDirectory() as tmp:
            blocked = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=Path(tmp) / "log.jsonl",
                state_path=Path(tmp) / "day.json",
            )
            self.assertEqual(blocked["reason"], "market_unavailable")

    def test_late_midnight_snapshot_does_not_set_day_start(self):
        now = datetime(2026, 9, 29, 0, 0, 30, tzinfo=timezone.utc)
        self.mt5.symbol_info_tick.return_value.time_msc = int(now.timestamp() * 1000)
        with TemporaryDirectory() as tmp:
            state = Path(tmp) / "day.json"
            result = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=Path(tmp) / "log.jsonl",
                state_path=state,
            )
            self.assertEqual(result["reason"], "day_start_unknown")
            self.assertFalse(state.exists())

    def test_other_symbol_position_blocks_account_equity_guard(self):
        now = datetime(2026, 9, 29, 0, 0, 0, 500000, tzinfo=timezone.utc)
        self.mt5.symbol_info_tick.return_value.time_msc = int(now.timestamp() * 1000)
        self.mt5.positions_get.side_effect = lambda symbol=None: (
            () if symbol else (SimpleNamespace(symbol="EURUSD"),)
        )
        with TemporaryDirectory() as tmp:
            result = shadow_cycle(
                self.mt5,
                symbol="XAUUSDm",
                expected_login=123,
                expected_server="Exness-Demo",
                cost_policy=self.cost,
                now=now,
                log_path=Path(tmp) / "log.jsonl",
                state_path=Path(tmp) / "day.json",
            )
            self.assertEqual(result["reason"], "foreign_exposure")
            self.assertFalse(result["admit"])


if __name__ == "__main__":
    unittest.main()
