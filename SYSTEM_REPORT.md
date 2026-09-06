# 📊 XAUUSD Pro Sniper V2 - Project Report
- **Project Name:** XAUUSD Scalper
- **Current Status:** Phase 2 (Implementation Complete, Ready for Config & Test)
- **Last Updated:** 2026-05-18

## 🛡️ 1. System Overview
A professional-grade, multi-tool trading system for Gold (XAUUSD) designed to eliminate emotional trading through strict logic and institutional filters.

### Key Features (V2):
- **News Intelligence:** Automatic pause during high-impact economic news.
- **Dual-Trend Filter:** Alignment required between H1 and H4 trends before M15 signals.
- **Dynamic Risk Mgmt:** ATR-based Target Profit and Stop Loss calculation.
- **Portfolio Analytics:** Live-syncing of every trade to Google Sheets and Docs.

## 📈 2. Strategy Architecture
- **Timeframe:** M15 (Execution), H1 & H4 (Trend Filters).
- **Core Logic:**
    - **Trend:** EMA 20 crossing EMA 50.
    - **Reversal:** RSI < 35 (Buy) / RSI > 70 (Sell).
    - **Volume:** MFI (Money Flow Index) for additional confirmation.
- **Risk/Reward:** Target minimum 1:1.5 using ATR scaling.

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
