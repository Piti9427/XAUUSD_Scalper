# XAUUSD Scalper Project
- **Goal:** Implement a hybrid backtesting and real-time alert system for Gold (XAUUSD).
- **Strategy:** Core System: **Pure B1 Single-Position** (Donchian Breakout + RSI + EMA 50) with 6.25 ATR TP, 2.5 ATR SL, and 10% Risk Cap. (See [2026-09-28 Pivot Post-Mortem](docs/post-mortem/2026-09-28-pivot-pure-b1-logic.md) and [Strategy Evolution](docs/STRATEGY_EVOLUTION.md) for details).
- **Architecture:** Python + MetaTrader 5 API / Webhook Bridge + Telegram Bot.

## 🔄 Recent Updates (2026-09-29)
- **Strategy Pivot Complete:** Transitioned from Hybrid Recovery Basket to Pure B1 Single-Position.
- **Risk Management Hardened:** Enforced a strict **10% Risk Cap** per trade to prevent $200 micro-accounts from blowing up during wide-SL drawdowns.
- **Profitability Verified:** Forward-tested 6 months of real Exness tick data (45M+ ticks, full spread/swap/commission cost). Final result: **$200 → $884 (+342%), Max DD 34.4%, Win Rate 37.4%.**
- **Test Suite Passed:** 608/608 unit tests aligned with the new strict risk parameters.

## Project Structure
- `docs/`: System specifications, improvement plans, logic audits, and engineering handoffs.
- `config/`: Secret tokens and connection parameters.
- `scripts/`: Implementation of the Pine Script logic in Python.
- `data/`: Historical data for backtesting and performance logs.
- `main.py`: Main entry point for the legacy alert loop.

`smc_main.py` is offline-only. It refuses to start when MT5 connects because its local position state and fixed-balance sizing are not broker-reconciled. Its disconnected simulation disables Telegram alerts. Use the webhook bridge in dry-run or demo testing; neither path is certified for real-money trading.

## Runtime Notes
- Keep real MT5, Telegram, and Google Workspace secrets out of `config/settings.yaml`.
- Prefer environment overrides such as `XAUUSD_MT5_LOGIN`, `XAUUSD_MT5_PASSWORD`, `XAUUSD_MT5_SERVER`, `XAUUSD_TELEGRAM_TOKEN`, and `XAUUSD_TELEGRAM_CHAT_ID`.
- Telegram, Google Workspace, and news protection are disabled by default until configured.

## Verification
- Unit tests: `python3 -m unittest discover -s tests`
- Syntax check: `python3 -m py_compile main.py test_mt5.py scripts/*.py tests/*.py`
- MT5 smoke test after credentials are configured: `python3 test_mt5.py`

## Output Style
Alerts and journals are formatted as compact insights:

```text
BUY XAUUSD - Review setup before entry
Setup: MTF align + MSS wick rejection + RSI 34.80
Levels: Entry 2400.00 | TP 2410.00 | SL 2395.00
Risk: 1:2.00 | risk 5.00 | reward 10.00 | spread 12.00
Context: RSI 34.80 | ATR 4.20
Action: Use predefined SL; do not chase if price moves beyond planned BUY entry.
```
