# 📈 TradingView Pine Script v6 Indicator & Strategy Plan

**System:** XAUUSD Pro Copilot (Pine Script v6)  
**Platform:** TradingView  
**Target Asset:** Spot Gold (XAUUSD)  
**Timeframe:** M5 / M15  

---

## 1. Upgrade Matrix: From Base Script to Institutional Gold Tool

| Feature | Base User Script | Institutional Gold Upgraded Script |
| :--- | :--- | :--- |
| **Trade Direction** | Long only (`strategy.entry("Long")`) | **Full Bidirectional (Both LONG & SHORT)** |
| **Risk Management** | Fixed % (`5.0% SL`, `15.0% TP` = $125 SL!) | **Dynamic ATR Points (1.5x ATR SL, 1.5x ATR TP1, 3.0x ATR TP2)** |
| **Session Control** | 24-hour unconstrained | **London Killzone (07:00–10:00 UTC) & NY Killzone (12:30–15:30 UTC)** |
| **Asian Range Visuals**| None | **Auto-draws Asian High and Low lines (00:00–07:00 UTC)** |
| **Chandelier Tuning** | Generic ATR Mult 3.0 | **Calibrated Gold CE (ATR Mult 2.0, Length 14/22)** |
| **Spread Simulation** | 0.00 | **Exness Standard 30 points ($0.30) modeled in strategy parameters** |
| **Alert Webhooks** | Generic alertcondition | **Structured JSON payloads ready for Python bot / Telegram** |

---

## 2. Mathematical Design

### 2.1 Dynamic ATR Stop Loss & Multi-Target Take Profit
On Gold, fixed percentage SL is catastrophic because gold price oscillates around $2,500+. A 5% move is $125.00!
- **True M15 ATR:** Typically $2.50 to $4.50.
- **Stop Loss:** Set at `1.5 * ATR(14)` or at the Chandelier Stop line (whichever is tighter).
- **Take Profit 1 (TP1):** Set at `1.5 * ATR(14)` (1:1 R:R) -> signals 50% partial close & move SL to Breakeven.
- **Take Profit 2 (TP2):** Set at `3.0 * ATR(14)` (1:2 R:R) -> full runner target.

### 2.2 Symmetric Short Logic
Gold drops violently during USD expansion or hawkish macro shifts. The Short rule requires:
1. `ta.crossunder(emaFast, emaSlow)`
2. `close < emaTrend` (Price below EMA 200)
3. `ceDir == -1` (Chandelier Exit in Bearish state)
4. Active Killzone (London or New York session)

### 2.3 Asian Session Range (00:00–07:00 UTC)
The script calculates the highest high and lowest low between 00:00 and 07:00 UTC, plotting continuous horizontal lines across the chart until the next session. This provides instant visual clarity when London open manipulates price beyond these levels to sweep liquidity.

---

## 3. Pine Script Output Architecture

The implementation will be stored in [`tradingview/xauusd_pro_copilot.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_pro_copilot.pine) with an accompanying user guide in [`tradingview/README.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/README.md).
