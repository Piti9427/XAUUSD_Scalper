"""Cold or malformed SDK history cannot become attested empty-deal evidence."""

import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

PROBE = Path(__file__).resolve().parents[2] / "deploy/c22-demo/oracle_broker_probe.py"


class BrokerProbeTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(
            login=123,
            server="Exness-Demo",
            password="fixture",
            expected_fingerprint=hashlib.sha256(b"Exness-Demo:123").hexdigest()[:16],
        )
        self.deal = NS(
            ticket=1,
            position_id=0,
            magic=0,
            type=2,
            entry=0,
            volume=0,
            time_msc=1000,
            price=0,
            profit=200,
            commission=0,
            fee=0,
            swap=0,
            symbol="",
        )
        account = NS(
            login=123,
            server="Exness-Demo",
            trade_mode=0,
            margin_mode=2,
            currency="USD",
            balance=200,
            equity=200,
            margin_free=200,
            leverage=1000,
            trade_allowed=True,
            trade_expert=True,
        )
        fields = dict(
            trade_contract_size=100,
            trade_tick_size=0.001,
            trade_tick_value=0.1,
            point=0.001,
            digits=3,
            volume_min=0.01,
            volume_max=200,
            volume_step=0.01,
            trade_stops_level=0,
            trade_freeze_level=0,
            trade_mode=4,
            filling_mode=3,
            swap_mode=1,
            swap_long=-490.8,
            swap_short=0,
            swap_rollover3days=3,
            currency_profit="USD",
            currency_margin="XAU",
        )
        self.sdk = NS(
            ACCOUNT_TRADE_MODE_DEMO=0,
            ACCOUNT_MARGIN_MODE_RETAIL_HEDGING=2,
            ORDER_TYPE_BUY=0,
            ORDER_TYPE_SELL=1,
            TRADE_ACTION_DEAL=1,
            ORDER_TIME_GTC=0,
            ORDER_FILLING_FOK=0,
        )
        for name, value in dict(
            initialize=True,
            account_info=account,
            terminal_info=NS(connected=True, trade_allowed=False, tradeapi_disabled=False),
            positions_get=[],
            orders_get=[],
            symbol_info=NS(**fields),
            symbol_info_tick=NS(bid=200, ask=200.2, time_msc=1000),
            history_deals_get=[self.deal],
            history_deals_total=1,
            order_calc_margin=4,
            order_calc_profit=-10,
            order_check=NS(
                retcode=0, comment="Done", balance=200, equity=200, margin=4, margin_free=196
            ),
            shutdown=None,
            order_send=None,
        ).items():
            setattr(self.sdk, name, Mock(return_value=value))

    def run_probe(self, clock=0):
        with (
            patch.dict("sys.modules", {"MetaTrader5": self.sdk}),
            patch.object(Path, "read_text", return_value=json.dumps(self.config)),
            patch.object(Path, "mkdir"),
            patch.object(Path, "write_text") as write,
            patch(
                "time.monotonic",
                side_effect=clock if isinstance(clock, list) else None,
                return_value=clock,
            ),
            patch("time.sleep"),
            patch("builtins.print"),
        ):
            try:
                runpy.run_path(str(PROBE))
            finally:
                self.sdk.order_send.assert_not_called()
                self.sdk.shutdown.assert_called_once()
                self.writes = write.call_count
            return json.loads(write.call_args.args[0])

    def test_cold_empty_history_retries_until_cash_and_count_reconcile(self):
        self.sdk.history_deals_get.side_effect = [[], [self.deal]]
        self.sdk.history_deals_total.side_effect = [0, 1]
        evidence = self.run_probe()
        self.assertEqual(len(evidence["history_deals"]), 1)
        self.assertEqual(self.sdk.history_deals_get.call_count, 2)
        self.assertEqual(evidence["history_start_utc"], "1970-01-01T00:00:00+00:00")
        self.assertFalse(evidence["order_send_called"])

    def test_empty_count_mismatch_and_nonfinite_cash_never_publish_evidence(self):
        for problem in ("empty", "count", "nan"):
            with self.subTest(problem=problem):
                self.setUp()
                if problem == "empty":
                    self.sdk.history_deals_get.return_value = []
                    self.sdk.history_deals_total.return_value = 0
                elif problem == "count":
                    self.sdk.history_deals_total.return_value = 2
                else:
                    self.deal.profit = float("nan")
                with self.assertRaisesRegex(ValueError, "history_not_reconciled_to_balance"):
                    self.run_probe([0, 0, 61])
                self.assertEqual(self.writes, 0)
