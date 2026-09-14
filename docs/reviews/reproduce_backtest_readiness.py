"""Regression checks for historical accounting and H1 causality."""
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.smc import backtester


def main():
    namespace = runpy.run_path(str(ROOT / "tests/test_smc_backtester.py"))
    fixture = namespace["TestSMCBacktester"]()
    fixture.setUp()
    bars, h1 = fixture.df_m5, fixture.df_h1
    normal = backtester.SMCBacktester().run(bars, h1)
    trade = normal.trades_df.iloc[0]
    cash_from_volume = (trade.exit_price - trade.entry_price) * trade.lot_size * 100.0
    assert abs(trade.pnl_dollar - cash_from_volume) < 0.01
    print(f"PASS: volume-based PnL: reported={trade.pnl_dollar:.2f}, "
          f"price*actual_lots*contract={cash_from_volume:.2f}")

    both = bars.copy()
    mask = (both.time.dt.day == 2) & (both.time.dt.hour == 8) & (both.time.dt.minute == 15)
    both.loc[mask, "low"] = 2000.0
    summary = backtester.SMCBacktester().run(both, h1)
    assert summary.trades_df.iloc[0].exit_reason == "SL"
    print("PASS: simultaneous SL/TP records SL")

    fill_stop = bars.copy()
    mask = (fill_stop.time.dt.day == 2) & (fill_stop.time.dt.hour == 8) & (fill_stop.time.dt.minute == 10)
    fill_stop.loc[mask, "low"] = 2000.0
    summary = backtester.SMCBacktester().run(fill_stop, h1)
    assert summary.total_trades == 1 and summary.final_balance < 10000.0
    print("PASS: fill-bar stop recorded and balance reduced")

    unclosed_inputs = []
    original = backtester.detect_smc_setup

    def record(h1_rows, m5_rows, liquidity, now, **kwargs):
        if len(h1_rows) and h1_rows.time.iloc[-1] == now.floor("h"):
            unclosed_inputs.append((str(now), str(h1_rows.time.iloc[-1])))
        return original(h1_rows, m5_rows, liquidity, now, **kwargs)

    with patch.object(backtester, "detect_smc_setup", record):
        backtester.SMCBacktester().run(bars, h1)
    assert not unclosed_inputs
    print("PASS: no current-hour H1 supplied before close")


if __name__ == "__main__":
    main()
