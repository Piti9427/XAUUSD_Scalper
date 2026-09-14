# XAUUSD Scalper Project
- **Goal:** Implement a hybrid backtesting and real-time alert system for Gold (XAUUSD).
- **Strategy:** EMA 20/50 Crossover + RSI Exhaustion (35/70).
- **Architecture:** Python + MetaTrader 5 API + Telegram Bot.

## Project Structure
- `docs/`: System specifications, improvement plans, logic audits, and engineering handoffs.
- `config/`: Secret tokens and connection parameters.
- `scripts/`: Implementation of the Pine Script logic in Python.
- `data/`: Historical data for backtesting and performance logs.
- `main.py`: Main entry point for the live alert loop.

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
