# Specification: XAUUSD Trading System v1 (Liquidity Sweep + Structure + Session)

> **Status:** ready-for-agent  
> **Tracker:** Local Spec / Foundation  
> **Area:** Core Trading Engine & Risk Architecture  

---

## Problem Statement

As a quantitative gold trader on XAUUSD, existing indicator crossover strategies (like generic EMA crosses) suffer severe whipsaws during low-volume sessions, expose intraday accounts to blown margins through unrealistic fixed percentage stop losses (e.g. 5% SL on Gold = $125/oz), and fail to account for institutional liquidity traps. 

The trader needs a battle-tested, systematic trading foundation based on Smart Money Concepts (SMC):
1. Trading only when high-timeframe (H1) directional bias aligns with institutional session volume (London & New York Killzones).
2. Entering only after liquidity is swept from key pools (Asian Range H/L, Previous Day H/L) followed by a confirmed Market Structure Shift (MSS) and Fair Value Gap (FVG) retest.
3. Protecting capital with mathematical risk control (exact 0.5% risk per trade, spread compensation, news blackout windows, breakeven triggers at 1R, and daily circuit breakers).
4. Ensuring identical rules execute across manual charts, TradingView backtests, and automated MT5 bots.

---

## Solution

Build a decoupled, pure-function **SMC Strategy Engine** for XAUUSD with zero third-party platform coupling, accompanied by a cross-platform execution architecture:

1. **Pure Functional Core:** A single primary testable seam `evaluate_market(context)` that ingests standardized multi-timeframe candles (H1 & M5) and outputs deterministic order intents (`PLACE_LIMIT`, `CANCEL_LIMIT`, `MOVE_BE`, `CLOSE_MARKET`).
2. **Deterministic Setup Detection:**
   - H1 EMA 200 trend alignment.
   - Asian Range (00:00–07:00 UTC) & PDH/PDL liquidity mapping.
   - Strict Wick-only sweep verification ($\le \$5.00$).
   - 5-bar fractal M5 Swing identification and M5 Candle Body Close MSS.
   - Displacement candle verification ($\ge 60\%$ body ratio) and FVG identification ($\ge \$0.50$).
   - 50% FVG Limit order placement with 3-bar (15-min) expiration TTL.
3. **Institutional Risk Engine:**
   - 0.5% equity risk sizing based on 100 oz contract size and structure SL + $0.30 buffer.
   - Strict maximum SL distance cap of $6.00 (trades wider than $6.00 are skipped).
   - Dynamic Breakeven relocation at +1.0R.
   - Fixed 2.0R take profit.
   - Red news 30-min blackout and daily -1.0% circuit breaker.
4. **Tri-Platform Verification:**
   - Offline Python backtesting on Mac using local CSV datasets.
   - TradingView Pine Script v6 strategy and visual indicator.
   - Headless Docker/MT5 bot with Telegram Copilot card alerting and SQLite lifecycle journaling.

---

## User Stories

1. As an intraday trader, I want the system to calculate the exact Asian session High and Low between 00:00 and 07:00 UTC, so that I can anticipate liquidity sweeps during the London and New York sessions.
2. As an intraday trader, I want the system to map Previous Day High (PDH) and Previous Day Low (PDL), so that daily liquidity extremes serve as macro sweep zones.
3. As an intraday trader, I want the system to enforce an H1 EMA 200 filter, so that I only take Longs when H1 is bullish and Shorts when H1 is bearish.
4. As an algorithmic trader, I want the system to verify that a liquidity sweep only pierces with a candle wick on M5 and closes back inside the level, so that I do not enter on explosive breakout moves.
5. As an algorithmic trader, I want sweeps exceeding $5.00 (500 points) to be immediately classified as Expansion Breakouts and invalidated, so that I avoid high-velocity momentum traps.
6. As a trader, I want Market Structure Shift (MSS) on M5 to be defined by a 5-bar fractal swing point, so that noise from minor bars is filtered out.
7. As a trader, I want MSS confirmation to require a candle body close past the swing level, so that wick-only rejections are rejected as false inducement.
8. As a trader, I want displacement candles to have a body-to-range ratio of at least 60%, so that weak, indecisive candles cannot trigger setups.
9. As a trader, I want Fair Value Gaps (FVG) to be verified with a minimum opening of $0.50 (50 points), so that entries are not placed on negligible micro-gaps swallowed by spread.
10. As an automated trader, I want entry orders to be placed at the 50% Consequent Encroachment of the FVG as a Limit Order, so that I achieve optimal Risk:Reward execution.
11. As an automated trader, I want unexecuted 50% FVG Limit Orders to expire automatically after 3 M5 bars (15 minutes), so that stale orders in decaying market conditions are removed.
12. As a risk manager, I want Stop Loss to be placed at the extreme sweep wick plus a $0.30 (30-point) spread buffer, so that standard broker spreads do not prematurely knock out valid setups.
13. As a risk manager, I want any setup with an SL distance greater than $6.00 (600 points) to be skipped entirely, so that volatility expansion during unexpected surges does not distort intraday positioning.
14. As an investor, I want position sizing to strictly risk 0.5% of account balance per trade using XAUUSD 100 oz contract calculations, so that capital drawdown is bounded mathematically.
15. As a risk manager, I want the system to automatically move Stop Loss to Breakeven when unrealized profit reaches +1.0R, so that winning trades cannot turn into losses.
16. As a trader, I want Take Profit to be fixed at 2.0R, so that positive expectancy is systematically captured without discretionary doubt.
17. As an automated trader, I want trading restricted strictly to London (14:00–17:00 TH) and New York (19:30–22:30 TH) Killzones, so that low-liquidity Asian and rollover chop are eliminated.
18. As a risk manager, I want all active positions closed before 21:00 UTC (04:00 TH), so that overnight rollover spread spikes and swap fees are never incurred.
19. As a risk manager, I want a 30-minute news blackout window before and after high-impact USD economic events, so that slippage from major news releases is completely avoided.
20. As a risk manager, I want open positions evaluated 15 minutes before high-impact news to either lock at Breakeven (if $\ge 1.0R$) or market-close immediately, so that capital is protected from event risk.
21. As a risk manager, I want a daily circuit breaker to halt all trading for the day if two realized losses occur in a single UTC trading day (regardless of individual loss size), so that catastrophic compounding losses are prevented.
22. As a risk manager, I want a 30-minute cooldown enforced after any individual stop loss, so that revenge trading in consecutive bars is prohibited.
23. As a developer, I want the strategy logic implemented as a pure Python function without MT5 or broker dependencies, so that 100% of the rules can be unit-tested and backtested on macOS.
24. As a mobile trader, I want Telegram notifications containing rich cards (Entry, SL, TP, Risk $, Lot Size) and dark-theme chart snapshots, so that I can monitor trade setups visually on my phone.
25. As a record-keeper, I want every trade lifecycle event logged into SQLite and synced with Google Sheets, so that strategy performance can be audited long-term.

---

## Implementation Decisions

1. **Two-Layer Seam Design (ADR-012 + Scrutinize fix):**
   - **Layer 1 — Pure Detection (stateless):**
     - `detect_smc_setup(h1_candles, m5_candles, liquidity_levels, current_time) -> Optional[SetupSignal]`
     - `SetupSignal` contains: `direction` (BUY/SELL), `sweep_bar_index`, `mss_bar_index`, `fvg_high`, `fvg_low`, `entry_price` (50% FVG), `sl_price` (sweep wick ± $0.30 buffer), `tp_price` (2.0R), `reason` (audit trail string).
     - This function has **zero state** — given the same candle data, it always returns the same result. It checks: H1 EMA 200 bias → Session Killzone → Sweep (wick-only, ≤$5.00) → MSS within 6 bars of Sweep (ADR-014) → Displacement (body ≥60%) → FVG (≥$0.50) within 2 bars of MSS → SL distance ≤$6.00 cap.
   - **Layer 2 — Stateful Orchestrator:**
     - `StrategyOrchestrator` class with `on_bar(bar, account_state) -> List[OrderIntent]`
     - Manages: pending Limit order TTL countdown (3 bars), position lifecycle tracking, Breakeven relocation at +1.0R, Rollover flat before 21:00 UTC, News blackout evaluation and pre-news close/BE logic, Circuit Breaker (2 losses/day) and 30-min cooldown.
     - `OrderIntent` is an enum: `PLACE_LIMIT`, `CANCEL_LIMIT`, `MOVE_SL_TO_BE`, `CLOSE_MARKET`, `NO_ACTION`.
     - `AccountState` encapsulates: `balance`, `equity`, `open_position` (Optional), `daily_loss_count`, `last_loss_time`, `news_schedule`.

2. **Decoupled Architecture Layers (ADR-015):**
   - **Domain Strategy Core (`scripts/smc/`):** New package alongside existing `scripts/strategy.py`. Contains `detection.py` (Layer 1), `orchestrator.py` (Layer 2), `risk.py` (lot sizing), `liquidity.py` (Asian Range/PDH/PDL), `structure.py` (fractal, MSS, FVG).
   - **Data Fetcher Adapter:** Retrieves M5 & H1 data either from local CSV files (ADR-016: MT5 standard format `time,open,high,low,close,tick_volume`) or via MT5 API / mock connector.
   - **Execution Adapter:** Handles MT5 order placement (`order_send`), order modification (`order_modify` for BE), and order cancellation.
   - **Telegram & Logging Adapter:** Handles visual candlestick chart generation (Dark theme matplotlib/mplfinance) and async Telegram Bot API messaging.

3. **Risk Management Calculation Standard (corrected):**
   - Contract size = 100.0 oz per 1.0 lot.
   - $\text{SL Distance} = |\text{Entry} - \text{Sweep Wick}| + 0.30$.
   - $\text{Raw Lot} = \frac{\text{Balance} \times 0.005}{\text{SL Distance} \times 100}$.
   - $\text{Lot Size} = \lfloor \frac{\text{Raw Lot}}{0.01} \rfloor \times 0.01$ (floor to lot step 0.01).
   - Clamp between broker `min_lot` (0.01) and `max_lot` (10.0).

4. **FVG Indexing Convention (unambiguous):**
   - Bullish FVG: `candle[i-1].low > candle[i+1].high` where `candle[i]` is the Displacement candle.
   - Bearish FVG: `candle[i-1].high < candle[i+1].low` where `candle[i]` is the Displacement candle.
   - FVG size = gap between the two levels; must be ≥ $0.50 (50 points).

5. **Temporal Sequencing (ADR-014):**
   - MSS must occur within **6 M5 bars (30 minutes)** of the Sweep bar.
   - FVG must form on the MSS candle itself or the **2 bars immediately following** it.
   - If either window expires, the Sweep is invalidated and detection resets.


---

## Testing Decisions

1. **Behavioral Testing at the Primary Seam:**
   - Unit tests will test only through `evaluate_smc_setup(context)` by providing synthetic multi-candle scenarios.
   - No mock testing of internal private methods; tests assert whether an order is emitted, canceled, or adjusted based on candle inputs.
2. **Key Test Scenarios:**
   - *Valid Bullish Setup:* Asian Low swept with wick $\le \$5.00$ -> M5 5-bar Fractal broken by body close -> Displacement $\ge 60\%$ -> FVG $\ge \$0.50$ -> Assert `PLACE_LIMIT` at 50% FVG with SL at Wick - 0.30 and TP at 2R.
   - *Expansion Breakout Invalidation:* Sweep candle body closes below Asian Low or pierces $> \$5.00$ -> Assert `NO_TRADE`.
   - *H1 Counter-Trend Invalidation:* Bullish M5 setup occurs while H1 Close < EMA 200 -> Assert `NO_TRADE`.
   - *Out-of-Session Invalidation:* Setup occurs at 11:00 UTC (outside London and NY Killzones) -> Assert `NO_TRADE`.
   - *TTL Order Expiry:* 3 M5 bars pass after Limit order creation without price touching 50% FVG -> Assert `CANCEL_LIMIT`.
   - *Breakeven Relocation:* Active position reaches +1.0R -> Assert `MOVE_BE`.
   - *Max SL Cap Rejection:* Setup with SL distance of $6.50 -> Assert `NO_TRADE`.
   - *News Blackout Invalidation:* Setup occurs 10 minutes before USD NFP -> Assert `NO_TRADE`.
   - *Daily Circuit Breaker:* Two losses recorded on the current date -> Assert `NO_TRADE`.

---

## Out of Scope

1. Multi-pair trading (System is strictly calibrated for XAUUSD / Gold).
2. Martingale or grid averaging (Strictly 1 concurrent position, fixed 0.5% risk).
3. Automated news sentiment NLP analysis (News filtering is strictly binary time-based blackout using scheduled economic calendar times).
4. Web-based administration dashboards (Telegram Bot and Google Sheets provide all necessary observability).

---

## Further Notes

- **M5 Data Prerequisite (ADR-016):** No M5 historical data exists in `data/`. Acquiring `data/XAUUSD_M5.csv` (minimum 6 months, MT5 standard format) is a hard prerequisite for all development tickets. The existing `XAUUSD_M15.csv` and `XAUUSD_H1.csv` are yfinance `GC=F` futures data — they will not be used by the SMC system (different instrument, different format).
- **Existing v0 Coexistence (ADR-015):** The existing EMA Sniper system (`scripts/strategy.py`, `scripts/backtester.py`, `main.py`) remains untouched. The SMC v1 system lives in a new `scripts/smc/` package. No facade, no refactoring of existing code.
- **TradingView Pine Script v6:** A specialized Pine Script (`tradingview/xauusd_smc_system_v1.pine`) will be generated matching this specification. It can proceed in parallel with Python development since it shares no code — only logic parity verified against backtest results.
- **Testing architecture matches the two-layer seam:** Layer 1 (detection) is tested with synthetic candle snapshots. Layer 2 (orchestrator) is tested with bar-by-bar simulation sequences that verify TTL expiry, BE relocation, and circuit breaker state transitions.
