import unittest
from datetime import datetime, timezone, timedelta, date
import pandas as pd
from scripts.smc.backtester import SMCBacktester, BacktestSummary


class TestSMCBacktester(unittest.TestCase):
    def setUp(self):
        # Create minimal 2-day synthetic dataset with a clear winning trade
        # Day 1: 2026-03-01 (liquidity reference)
        # Day 2: 2026-03-02 (setup triggers in London and hits 2R TP)
        m5_records = []
        base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        
        # Day 1: Asian H=2030, L=2020. Day 1 H=2050, L=2000.
        for i in range(288):
            ts = base_time + timedelta(minutes=i*5)
            h = 2050.0 if i == 100 else 2030.0
            l = 2000.0 if i == 80 else 2020.0
            m5_records.append({"time": ts, "open": 2025.0, "high": h, "low": l, "close": 2025.0, "tick_volume": 100})
            
        # Day 2: Asian H=2040, L=2010 (hours 0-6)
        day2_base = datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)
        for i in range(288):
            ts = day2_base + timedelta(minutes=i*5)
            hour = ts.hour
            minute = ts.minute
            
            if hour < 7:
                o = 2020.0
                h = 2040.0 if hour == 3 and minute == 0 else 2035.0
                l = 2010.0 if hour == 5 and minute == 0 else 2015.0
                c = 2020.0
            elif hour == 7 and minute < 50:
                o = 2011.5
                h = 2014.0 if minute == 25 else 2012.0
                l = 2011.0
                c = 2011.5
            elif hour == 7 and minute == 50:
                # Sweep Asian Low (2010.0) -> wick 2008.5, close 2011.0
                o = 2011.0
                h = 2011.5
                l = 2008.5
                c = 2011.0
            elif hour == 7 and minute == 55:
                o = 2011.0
                h = 2013.0
                l = 2010.8
                c = 2012.8
            elif hour == 8 and minute == 0:
                # MSS Displacement Candle: close 2016.0 > 2014.0
                o = 2012.8
                h = 2016.2
                l = 2012.7
                c = 2016.0
            elif hour == 8 and minute == 5:
                # FVG confirmation bar: low 2015.0 > 2013.0. FVG 2013-2015 -> 50% CE = 2014.0
                o = 2016.0
                h = 2018.0
                l = 2015.0
                c = 2017.5
            elif hour == 8 and minute == 10:
                # Price retraces to 2013.5 -> fills Limit order at 2014.0!
                o = 2017.5
                h = 2017.5
                l = 2013.5
                c = 2015.0
            elif hour == 8 and minute == 15:
                # Price rallies to 2030.0 -> hits TP (2025.60)
                o = 2015.0
                h = 2030.0
                l = 2014.5
                c = 2028.0
            else:
                o = 2022.0
                h = 2025.0
                l = 2020.0
                c = 2022.0
                
            m5_records.append({"time": ts, "open": o, "high": h, "low": l, "close": c, "tick_volume": 100})
            
        self.df_m5 = pd.DataFrame(m5_records)

        # H1 DataFrame (Bullish, 250 bars > EMA 200)
        h1_records = []
        for i in range(250):
            ts = datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc) + timedelta(hours=i)
            h1_records.append({
                "time": ts,
                "open": 2000.0 + i * 0.1,
                "high": 2005.0 + i * 0.1,
                "low": 1995.0 + i * 0.1,
                "close": 2002.0 + i * 0.1,
                "tick_volume": 1000
            })
        self.df_h1 = pd.DataFrame(h1_records)

    def test_backtest_execution_and_summary(self):
        backtester = SMCBacktester(initial_balance=10000.0, require_choch=False)
        summary = backtester.run(self.df_m5, self.df_h1)
        
        self.assertIsInstance(summary, BacktestSummary)
        self.assertGreaterEqual(summary.total_trades, 1)
        self.assertEqual(summary.winning_trades, 1)
        self.assertEqual(summary.losing_trades, 0)
        self.assertGreater(summary.net_profit, 0.0)
        self.assertEqual(summary.win_rate, 100.0)

    def test_cash_uses_filled_volume(self):
        trade = SMCBacktester(require_choch=False).run(self.df_m5, self.df_h1).trades_df.iloc[0]
        expected = (trade.exit_price - trade.entry_price) * trade.lot_size * 100
        self.assertAlmostEqual(trade.pnl_dollar, expected, places=2)

    def test_dual_touch_without_ticks_is_ambiguous(self):
        bars = self.df_m5.copy()
        mask = (bars.time.dt.day == 2) & (bars.time.dt.hour == 8) & (bars.time.dt.minute == 15)
        bars.loc[mask, "low"] = 2000.0
        result = SMCBacktester(require_choch=False).run(bars, self.df_h1)
        trade = result.trades_df.iloc[0]
        self.assertEqual(trade.exit_reason, "AMBIGUOUS")
        self.assertTrue(trade.sl_touched)
        self.assertTrue(trade.tp_touched)
        self.assertTrue(pd.isna(trade.pnl_dollar) or trade.pnl_dollar is None)
        self.assertEqual(result.losing_trades, 0)
        self.assertEqual(result.winning_trades, 0)
        self.assertEqual(result.net_profit, 0.0)

    def test_dual_touch_with_tick_feed_takes_tp_first(self):
        bars = self.df_m5.copy()
        mask = (bars.time.dt.day == 2) & (bars.time.dt.hour == 8) & (bars.time.dt.minute == 15)
        bars.loc[mask, "low"] = 2000.0
        # Ordered ticks: TP before SL on the dual-touch bar.
        ticks = pd.DataFrame(
            [
                {"time": "2026-03-02T08:15:05Z", "bid": 2015.0, "ask": 2015.2},
                {"time": "2026-03-02T08:15:10Z", "bid": 2026.0, "ask": 2026.2},
                {"time": "2026-03-02T08:15:20Z", "bid": 2000.0, "ask": 2000.2},
            ]
        )
        result = SMCBacktester(require_choch=False).run(bars, self.df_h1, df_ticks=ticks)
        trade = result.trades_df.iloc[0]
        self.assertEqual(trade.exit_reason, "TP")
        self.assertTrue(trade.sl_touched)
        self.assertTrue(trade.tp_touched)
        self.assertGreater(trade.pnl_dollar, 0)
        self.assertEqual(result.winning_trades, 1)
        self.assertEqual(result.losing_trades, 0)

    def test_fill_and_stop_in_same_bar_is_recorded(self):
        bars = self.df_m5.copy()
        mask = (bars.time.dt.day == 2) & (bars.time.dt.hour == 8) & (bars.time.dt.minute == 10)
        bars.loc[mask, "low"] = 2000.0
        result = SMCBacktester(require_choch=False).run(bars, self.df_h1)
        self.assertEqual(result.total_trades, 1)
        self.assertLess(result.final_balance, result.initial_balance)
        trade = result.trades_df.iloc[0]
        self.assertEqual(trade.entry_time, trade.exit_time)
        self.assertEqual(trade.exit_reason, "SL")

    def test_detector_only_sees_closed_h1_and_confirmed_fractals(self):
        from unittest.mock import patch
        from scripts.smc.structure import find_fractals_5bar
        from scripts.smc.types import SetupDecision
        calls = []

        def inspect(h1, m5, liquidity, now, **kwargs):
            self.assertTrue((h1.time + pd.Timedelta(hours=1) <= now).all())
            self.assertEqual(kwargs["precomputed_swings"], find_fractals_5bar(m5))
            calls.append(now)
            return SetupDecision(None, "mocked_reject")

        with patch("scripts.smc.backtester.evaluate_smc_setup", side_effect=inspect):
            SMCBacktester(require_choch=False).run(self.df_m5, self.df_h1)
        self.assertTrue(calls)

    def test_partial_and_tp_cash_conserve_filled_volume(self):
        result = SMCBacktester(partial_tp_enabled=True, partial_tp_r=1.0, require_choch=False).run(self.df_m5, self.df_h1)
        trade = result.trades_df.iloc[0]
        partial_lots = round(trade.lot_size * 0.5, 2)
        expected = (partial_lots * trade.initial_sl_dist +
                    (trade.lot_size - partial_lots) * (trade.exit_price - trade.entry_price)) * 100
        self.assertAlmostEqual(trade.pnl_dollar, expected, places=2)
        self.assertAlmostEqual(result.net_profit, expected, places=2)

    def test_default_replay_labeled_theoretical_not_usd500(self):
        from scripts.smc.replay_report import ReplayKind

        result = SMCBacktester(require_choch=False).run(self.df_m5, self.df_h1)
        self.assertIsNotNone(result.replay_report)
        self.assertEqual(result.replay_report.kind, ReplayKind.THEORETICAL_TAPE)
        self.assertIn("theoretical_tape_not_account_performance", result.replay_report.notes)

    def test_usd500_executable_replay_labeled(self):
        from scripts.smc.replay_report import EXECUTABLE_DEMO_BALANCE, ReplayKind

        result = SMCBacktester(
            initial_balance=EXECUTABLE_DEMO_BALANCE,
            replay_kind=ReplayKind.EXECUTABLE_USD500,
            require_choch=False,
        ).run(self.df_m5, self.df_h1)
        self.assertEqual(result.replay_report.kind, ReplayKind.EXECUTABLE_USD500)
        self.assertIsNotNone(result.replay_report.affordability)

    def test_cost_layers_separate_operating_from_trading(self):
        from scripts.smc.cost_accounting import expectancy_hides_operating_loss

        result = SMCBacktester(
            require_choch=False,
            operating_costs=500.0,
            fees_and_swap=1.0,
        ).run(self.df_m5, self.df_h1)
        self.assertIsNotNone(result.cost_report)
        self.assertAlmostEqual(result.cost_report.operating_costs, 500.0)
        self.assertAlmostEqual(
            result.cost_report.net_trading_profit,
            result.net_profit - 1.0,
            places=2,
        )
        # Positive trade expectancy must not hide ops burn when ops dominate.
        if result.net_profit > 1.0:
            self.assertTrue(
                expectancy_hides_operating_loss(
                    positive_trade_expectancy=True,
                    net_operating_profit=result.cost_report.net_operating_profit,
                )
            )

    def test_few_trades_sample_verdict_is_inconclusive(self):
        result = SMCBacktester(require_choch=False).run(self.df_m5, self.df_h1)
        self.assertEqual(result.sample_verdict, "INCONCLUSIVE")
        if result.winning_trades + result.losing_trades + result.be_trades > 0:
            self.assertIsNotNone(result.wilson)


if __name__ == "__main__":
    unittest.main()
