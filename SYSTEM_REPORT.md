# 📊 XAUUSD Pro Sniper V2 - Project Report
- **Project Name:** XAUUSD Scalper
- **Current Status:** Phase 2 (Implementation Complete, Ready for Config & Test)
- **Last Updated:** 2026-09-29

## 🛡️ 1. System Overview
A professional-grade, multi-tool trading system for Gold (XAUUSD) designed to eliminate emotional trading through strict logic and institutional filters.

### Key Features (V2):
- **News Intelligence:** Automatic pause during high-impact economic news.
- **Dual-Trend Filter:** Alignment required between H1 and H4 trends before M15 signals.
- **Dynamic Risk Mgmt:** ATR-based Target Profit and Stop Loss calculation.
- **Portfolio Analytics:** Live-syncing of every trade to Google Sheets and Docs.

## 📈 2. Strategy Architecture (Core System)
- **Timeframe:** M15 (Execution).
- **Core Strategy:** **Pure B1 Single-Position (Donchian Breakout + RSI Guard + EMA Filter)**
    - **Logic:** Donchian 30 Breakout with RSI14 Guard + EMA 50 Trend Filter.
    - **Target (TP):** 6.25 ATR — tick-replay verified 2026-09-29.
    - **Stop Loss (SL):** 2.5 ATR — gives price room to breathe through noise.
    - **Risk Cap:** 10% of equity per trade — rejects signal if SL risk too high for current balance.
    - **Position:** Single 0.01 lot per signal. No recovery legs.
    - **Backtest:** $200 → $884 (+342%), WR 37.4%, Max DD 34.4%, 190 trades (6-month Exness tick replay).
    - **Recovery:** **DISABLED** — 6-month tick-by-tick replay proved Breakout
      entry signals never repeat while price moves against you, making
      same-direction Recovery legs mathematically impossible. (See [2026-09-28-pivot-pure-b1-logic.md](docs/post-mortem/2026-09-28-pivot-pure-b1-logic.md))
    - **Circuit Breakers:** Daily loss limit (40% of equity = $80 on $200).
    - **HWM Halt:** Disabled for $200 micro-account.
    - **Evidence:** `data/b1_tick_sweep_results.json` (280-config tick-replay sweep), `data/b1_verify_winning_config/`.

## 📁 3. File Structure & Responsibilities
- `main.py`: The system brain (Orchestrator).
- `scripts/mt5_connector.py`: Real-time market data bridge.
- `scripts/strategy.py`: Technical analysis and signal generation.
- `scripts/news_service.py`: Web-based economic calendar scanner.
- `scripts/notifier.py`: Telegram alert delivery.
- `scripts/gws_logger.py`: Google Workspace performance syncing.
- `config/settings.yaml`: Central configuration hub.

## 🚀 4. How to Start
1. **Install Dependencies:** `pip install -r requirements.txt`
2. **Setup Config:** Fill in MT5 and Telegram details in `config/settings.yaml`.
3. **Run Test:** `python test_mt5.py`
4. **Deploy sniper:** `python main.py`

## 👨‍🏫 5. Expert Consultation Notes
- **Golden Rule:** Always respect the News Filter. Trading during CPI or NFP can lead to slippage that breaks the strategy.
- **Trend is Friend:** The MTF (Multi-Timeframe) filter is our biggest edge; it ensures we only buy when the "Big Money" is also buying.

---
*Created by Gemini CLI Stock Intelligence Framework.*
