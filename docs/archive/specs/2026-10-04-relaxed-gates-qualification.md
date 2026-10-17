# Specification: Owner-Approved Relaxed Gates & Reward156 Qualification

**Date:** 2026-10-04  
**Status:** Research Qualified (Discovery & Relaxed Gates); Demo-readiness pending cost validation

---

## 1. Background & Owner Authorization

On 2026-10-04, following diagnosis of the systematic second-half drawdown bottleneck in XAUUSD M15 market regime transitions, the owner authorized a targeted relaxation of research qualification gates:
- **Maximum Drawdown Ceiling:** Relaxed from $\le 30.0\%$ to $\le 35.0\%$ (absolute ceiling across all 6 base/stress scenarios).
- **Half-Window Minimum Trades:** Relaxed from $\ge 20$ to $\ge 10$ trades per half-window.
- **Invariants Retained:**
  - Net Profit $>$ trial30 baseline in all 6 scenarios (full base/stress, first-half base/stress, second-half base/stress).
  - Win Rate $>$ trial30 baseline in all 6 scenarios.
  - Realized RR $>$ trial30 baseline and $> 1.0$ in all 6 scenarios.
  - Full-window trades $\ge 60$.
  - Genuine bidirectional participation: actual executed BUY $\ge 1$ and SELL $\ge 1$ in all scenarios.
  - Single-position only: fixed 0.01 lot, 10% cost-inclusive risk cap, 20% daily loss circuit.
  - No martingale, no basket recovery, timezone-aware UTC.

---

## 2. Qualified Winner: RESEARCH-HYBRID-RSI7BUY-D48SELL-T156 (Reward156)

### 2.1 Strategy Architecture
- **Timeframe:** M15 (Bid OHLC assembled from 15 complete M1 UTC bars).
- **BUY Logic (Mean-Reversion Momentum Reclaim):**
  - Indicator 1: Simple rolling 7-bar RSI:
    $$\Delta = \text{close} - \text{close}_{t-1}$$
    $$\text{gain} = \text{rolling\_mean}(\max(\Delta, 0), 7), \quad \text{loss} = \text{rolling\_mean}(\max(-\Delta, 0), 7)$$
    $$\text{RSI}_7 = 100 - \frac{100}{1 + \text{gain}/\text{loss}}$$
  - Condition: $\text{RSI}_7(t-1) < 35 \text{ and } \text{RSI}_7(t) \ge 35 \text{ and } \Delta > 0$.
  - Filter: $\text{close} > \text{EMA}_{50} \text{ and } \text{EMA}_{50}(t) > \text{EMA}_{50}(t-4)$.
- **SELL Logic (Donchian Channel Breakout):**
  - $\text{close} < \text{rolling\_min}(\text{low}, 48)_{t-1}$.
- **Conflict Resolution:** SELL breakout takes precedence if both trigger on the same bar.
- **Circuit Breaker:** BUY pause active when account equity drawdown from peak is $\ge 5.0\%$.

### 2.2 Sizing & Exit Geometry
- **Lot Size:** Fixed 0.01 lot.
- **Stop Loss:** $2.5 \times \text{ATR}_{14}$.
- **Take Profit:** $1.35 \times \text{initial rounded stop distance}$ (nominal $RR = 1.35$).
- **Protection:** None (`protect_mode = "off"`).
- **Risk Cap:** $10\%$ of current equity (reject order if risk exceeds budget).
- **Daily Loss Limit:** $20\%$ UTC daily admission halt.

---

## 3. Measured Backtest Evidence (Exness Real Tick Archive)

Dataset: 45,671,201 Bid/Ask ticks, 12,100 complete M15 bars (2026-03-28 to 2026-09-28 UTC). Initial capital: $200.

| Scenario | Baseline (Trial30) Net / DD / WR / RR | Reward156 Net / DD / WR / RR | Trades (BUY/SELL) | Status |
|---|---|---|---|---|
| **Full Base** | $465.32 / 26.01% / 52.14% / 1.1993 | **$883.77** / **22.50%** / **54.61%** / **1.2726** | 152 (23 / 129) | **PASS** |
| **Full Stress** | $361.40 / 29.44% / 50.72% / 1.2013 | **$742.03** / **33.97%** / **53.42%** / **1.2641** | 146 (17 / 129) | **PASS** |
| **First-Half Base** | $346.54 / 26.01% / 56.25% / 1.1859 | **$476.66** / **22.50%** / **56.72%** / **1.2708** | 67 (5 / 62) | **PASS** |
| **First-Half Stress** | $278.29 / 29.44% / 54.84% / 1.1757 | **$398.60** / **33.97%** / **55.22%** / **1.2462** | 67 (5 / 62) | **PASS** |
| **Second-Half Base** | $73.92 / 32.93% / 49.02% / 1.2075 | **$370.61** / **34.45%** / **55.71%** / **1.2129** | 70 (13 / 57) | **PASS** |
| **Second-Half Stress** | $12.17 / 33.34% / 46.00% / 1.2040 | **$335.64** / **34.72%** / **54.29%** / **1.2338** | 70 (13 / 57) | **PASS** |

### Key Improvements:
1. **Net Profit:** +90% on full base ($883.77 vs $465.32), +105% on full stress ($742.03 vs $361.40).
2. **Second-Half Turnaround:** From near-zero / fragile baseline ($73.92 / $12.17) to strong profitability ($370.61 / $335.64), beating baseline profit by $5\times$ to $27\times$.
3. **Drawdown:** Full base DD reduced from $26.01\%$ to $22.50\%$. All stress & second-half DDs contained within the authorized $35.0\%$ ceiling.
4. **Realized RR:** Consistent $> 1.21$ across all windows and cost models.
