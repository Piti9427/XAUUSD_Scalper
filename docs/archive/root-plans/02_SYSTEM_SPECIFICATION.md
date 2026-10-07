# 📄 System Specification: XAUUSD Trading Copilot for Exness Standard

**Status:** Approved & Ready for Agent (`ready-for-agent`)  
**Domain:** Quantitative Algorithmic Trading / Smart Money Concepts (SMC)  
**Target Asset:** XAUUSD (Spot Gold)  
**Target Broker:** Exness (Standard Account, MT5)  

---

## 1. Problem Statement

Traders operating manual intraday and scalping strategies on Gold (XAUUSD) with Exness Standard accounts face severe psychological fatigue, emotional execution errors, and consistent mathematical drag from broker spread:
1. **Spread Drag on Standard Accounts:** Gold floating spreads on Exness Standard typically range from 25 to 35 points ($0.25 to $0.35). Entering trades by chasing momentum at market close severely degrades Risk/Reward (R:R), leading to negative expectancy even with >50% win rates.
2. **False Signals from Lagging Indicators:** Standard retail indicators (EMA crossovers, RSI overbought/oversold, tick-volume MFI) produce frequent whipsaws during Asian accumulation and London fakeouts, failing to capture true institutional order flow.
3. **Macro Blindspots:** Trading Gold in isolation without monitoring US Dollar Index (DXY) momentum or high-impact USD economic events (CPI, NFP, FOMC) leads to catastrophic drawdowns during institutional repricing.
4. **Platform & Hosting Friction:** The official MetaTrader 5 Python library does not run natively on macOS, while cloud hosting on Linux VMs (such as Oracle Cloud Free Tier) frequently encounters configuration hurdles and memory constraints.

---

## 2. Solution

The **XAUUSD Trading Copilot** is a 24/5 semi-automated trading assistant designed to eliminate emotional trading and maximize win rate through an institutional Smart Money Concepts (SMC) framework:
- **Precision SMC Execution:** Replaces indicator noise with time-based Killzones (London and New York opens), Asian Range (00:00–07:00 UTC) Liquidity Sweeps, true Market Structure Shifts (MSS), and Limit/Retest entries into Fair Value Gaps (FVGs) to secure 1:2.5+ R:R.
- **Exness Spread-Compensated Risk Engine:** Calculates dynamic Stop Loss and Take Profit levels that explicitly buffer for Exness floating spreads and derives exact recommended lot sizes based on live MT5 account equity and 1–2% risk rules.
- **Intermarket & News Protection:** Continuously gates signals against H1 DXY trend momentum and automatically pauses 30 minutes before and after High-Impact USD economic events.
- **Rich Telegram Interface:** Delivers actionable signal cards accompanied by in-memory generated dark-theme candlestick chart images highlighting key levels and tracks trade lifecycle milestones (TP1, Breakeven, TP2, SL) in real time.
- **Dual-Mode Architecture:** Provides seamless offline simulation/development on macOS and headless Docker + Wine containerization with 4 GB swap configuration for 24/7 deployment on Oracle Cloud Ubuntu Linux.

---

## 3. User Stories

1. As a gold trader on Exness Standard, I want the system to continuously scan M15 price action during London and New York Killzones, so that I only receive signals during peak institutional volume windows.
2. As a trader, I want the system to ignore market noise outside active Killzones, so that I avoid low-liquidity whipsaws and chop.
3. As a trader, I want the system to identify the Asian session high and low levels automatically, so that I can anticipate liquidity sweeps during the European morning.
4. As a trader, I want the system to detect when price sweeps above the Asian High or below the Asian Low and gets rejected with a long wick, so that I know institutional liquidity has been captured.
5. As a trader, I want the system to require a true Market Structure Shift (MSS) with candle body closes breaking recent swing pivots, so that I avoid entering on false wicks.
6. As a trader, I want the system to identify Fair Value Gaps (FVG) created during structural displacement, so that I can enter on a retest rather than chasing extended market prices.
7. As a trader on Exness Standard, I want entry zones placed at the 50% equilibrium of the FVG, so that my Stop Loss remains tight ($2–$3) and my Take Profit achieves at least 1:2.5 R:R after factoring in the 25–35 point spread.
8. As a trader, I want the system to monitor the H1 trend of the US Dollar Index (DXY), so that I am blocked from taking Long Gold setups when the dollar is in a strong bullish expansion.
9. As a trader, I want the system to monitor DXY momentum, so that I am blocked from taking Short Gold setups when the dollar is dumping into support.
10. As a trader, I want the system to scan an economic calendar for High-Impact USD events (CPI, NFP, FOMC, PPI), so that signals are automatically paused 30 minutes before and 30 minutes after major releases.
11. As a trader, I want an advance warning alert sent to Telegram prior to high-impact economic news, so that I am prepared for imminent market volatility.
12. As a trader, I want the system to check current floating spread on Exness MT5 before firing any signal, so that setups are discarded if spread exceeds the maximum tolerance.
13. As an account holder, I want the bot to query my live account equity from MT5, so that it calculates the exact recommended lot size matching my configured 1% or 2% risk tolerance.
14. As a mobile trader, I want to receive a clean Telegram card containing exact copyable numbers for Entry, SL, TP1, and TP2, so that I can key in orders on my Exness mobile app in seconds.
15. As a visual trader, I want each Telegram signal to include a rendered dark-theme candlestick chart showing the Asian Range box, liquidity sweep wick, FVG zone, and TP/SL levels, so that I can visually verify the setup at a glance.
16. As an active trader, I want the system to track price movement after an alert is issued, so that I receive a notification when price reaches TP1 prompting me to take 50% profit and move SL to breakeven.
17. As a trader on Exness, I want the breakeven recommendation to include a spread offset buffer, so that my trade is not prematurely stopped out by normal bid-ask fluctuations.
18. As an active trader, I want a follow-up notification when price reaches TP2 or hits Stop Loss, so that I have a complete record of trade outcome without constantly monitoring the screen.
19. As a disciplined trader, I want every signal and its resolution automatically logged to a local SQLite database, so that I can analyze historical Win Rate, Profit Factor, and Drawdown.
20. As a trader using Google Workspace, I want completed trades synced to Google Sheets, so that I can review my trading journal across devices.
21. As a developer on macOS, I want the bot to run unit tests and local simulations using historical data, so that I can develop and verify code without requiring a Windows virtual machine.
22. As a cloud administrator, I want a turnkey Docker and Wine configuration for Oracle Cloud Ubuntu VM, so that the bot runs 24/7 without manual graphical intervention.
23. As an Oracle Cloud Free Tier user, I want an automated swap configuration script, so that the bot operates safely within the 1 GB RAM limit of AMD micro instances without out-of-memory crashes.

---

## 4. Implementation Decisions

- **Dual-Mode Market Data Bridge:** `MT5Connector` dynamically detects OS. If Windows or Wine, it binds to native MT5 IPC; if macOS, it automatically routes through local CSV snapshots and `yfinance`.
- **SMC Strategy Pipeline:** Decoupled from oscillators. Strictly evaluates: Time Gate -> Macro DXY Gate -> Asian Range -> Liquidity Sweep -> MSS -> FVG 50% Equilibrium -> Spread-Compensated Dynamic SL/TP.
- **In-Memory Chart Generation:** Utilizes `matplotlib` with headless `Agg` backend, rendering dark-theme candlestick charts with colored level overlays and exporting directly to `io.BytesIO` PNG bytes without temporary file overhead.
- **Trade Lifecycle State Machine:** Decoupled asynchronous state machine tracking active setups: `IDLE` -> `WAITING_ENTRY` -> `ACTIVE` -> `TP1_REACHED` (alerts 50% partial take & SL to BE) -> `TP2_REACHED` / `SL_HIT`.

---

## 5. Testing Decisions (Testing Seams)

1. **System Orchestrator Seam (`main.py` / `tests/test_integration.py`):** Highest-level seam injecting synthetic candles, spread, and news status to assert end-to-end signal firing, chart rendering, Telegram dispatch, and lifecycle state changes.
2. **Strategy Pipeline Seam (`scripts/strategy.py` / `tests/test_strategy.py`):** Injects pre-constructed candlestick patterns (Asian range, sweep candle, MSS breakout, FVG) to assert BUY/SELL signals, FVG entry zones, and lot sizing.
3. **Data Bridge Seam (`scripts/mt5_connector.py` / `tests/test_mt5_connector.py`):** Asserts clean fallback on macOS and error resilience.
4. **Lifecycle State Machine Seam (`scripts/trade_tracker.py` / `tests/test_trade_tracker.py`):** Sequential price feed asserting `TP1_REACHED`, `TP2_REACHED`, and `SL_HIT` event emissions.

---

## 6. Out of Scope

- Direct auto-trading (automatic execution of `mt5.order_send()`) without human confirmation.
- Currency pairs other than Gold (`XAUUSD`).
- Paid proprietary data terminals (Bloomberg / Refinitiv).
- Native iOS or Android mobile application development (Telegram Bot serves as the mobile UI).
