# Root Cause Analysis: Long-Term Multi-Year Drawdown and Account Freezing on XAUUSD

**Date:** 2026-10-04  
**Author:** Antigravity & Pair Programming Partner  
**Target:** XAUUSD M15 Breakout Strategies (Trial30 / Reward156 / Pure B1)  
**Datasets:**
- Dataset A: `data/b1_public_exness_2024_09_2025_09` (49.5M ticks, 2024-09 to 2025-09)
- Dataset B: `data/b1_public_exness_2025_10_2026_09` (104.1M ticks, 2025-10 to 2026-09)
- Total Span: 2.1 Years (153.7 Million Exness Real Ticks)

---

## 1. Executive Summary

When evaluating strategies over multi-year periods (from Day One 2024 to present late 2026), all Donchian-based breakout candidates (Trial30, Reward156, Pure B1) suffer deep drawdowns (45%–70%) and enter a **permanent account freeze** where trading completely halts for months.

Using the `/diagnosing-bugs` and `debug-mantra` discipline with a 5-second deterministic feedback loop (`docs/reviews/artifacts/repro_long_term_drawdown_root_cause.py`), we isolated the root cause to **three compounding failure mechanisms**:

1. **Micro-Capital vs Broker Lot Size Invariant ($200 Account vs 0.01 Lot)**:
   - On XAUUSD (100 oz contract), the broker minimum lot is `0.01 lot` (1 oz).
   - Risk per trade with a 2.5 ATR stop is $2.5 \times \text{ATR}$.
   - For a 10% risk cap, the mathematical condition for trade admission is:
     $$\text{ATR} \le 0.04 \times \text{Balance}$$
   - When balance drops from $200 to $110 after a drawdown, maximum allowable ATR is **$4.40**.
   - With Gold trading between $3,800 and $5,500, average ATR is **$11.20**–**$15.31** (minimum required risk is $38.28, which is **34.8%** of a $110 balance).
   - As a result, **167 out of 173 potential signals (96.5%) are mathematically rejected by `risk_cap`**. The account is permanently paralyzed.

2. **Toxic Circuit Breaker (`buy_pause_drawdown = 0.05`)**:
   - `Rules.buy_pause_drawdown` automatically locks out 100% of BUY trades when drawdown reaches 5% ($10 on a $200 account).
   - In a historic macro bull run ($2,500 to $5,500+), BUY trades were the **only profitable component** (+$262.97 in Dataset A, +$92.15 in Dataset B).
   - The circuit breaker locked out 208 profitable BUY signals and forced the system into **SELL-only mode against a parabolic bull market**, guaranteeing an inescapable death spiral.

3. **Macro Trend Blindness (Counter-Trend M15 Breakouts)**:
   - Taking M15 SELL breakdowns during a macro bull market produced a catastrophic **29.4%–38.0% win rate** and **-$334.23 to -$247.28 net losses**.
   - Conversely, testing **BUY-ONLY** over the exact same period delivered **+$367.38** (+183% profit) in the crash window and **+$260.66** in Dataset A.

---

## 2. Quantitative Evidence & Reproduction

### Repro Benchmark: Crash Window (2025-10 to 2026-03)

| Metric | Original Reward156 (`buy_pause=0.05`) | Probe: `buy_pause=0.0` (Both Sides) | Probe: BUY-ONLY (No SELL) |
| :--- | :--- | :--- | :--- |
| **Net USD** | **-$89.96** | **-$79.73** | **+$367.38** |
| **Max Drawdown** | **68.74%** | **76.90%** | **41.44%** |
| **Total Trades** | 26 (frozen on Dec 18) | 87 (frozen) | 118 (traded through) |
| **Win Rate** | 34.6% (9W / 17L) | 39.5% | 48.3% |
| **SELL Net / Losses** | -$75.56 (16 losses / 1 BUY loss) | -$247.28 (24 losses) | $0.00 (0 trades) |
| **Rejections** | `buy_pause`: 208, `risk_cap`: 113 | `buy_pause`: 0, `risk_cap`: 223 | Zero freeze |
| **Downtime / Frozen Days** | **72 Days** | **64 Days** | **0 Days** |

### Dataset A Benchmark (2024-09 to 2025-09, Full Year)

| Side | Trades | Net USD | Win Rate | Profit Factor |
| :--- | :--- | :--- | :--- | :--- |
| **BUY Trades** | 209 | **+$262.97** | 48.3% | 1.23 |
| **SELL Trades** | 166 | **-$334.23** | 38.0% | 0.75 |
| **Combined RAW** | 375 | **-$71.26** | 43.7% | 0.97 |
| **BUY-ONLY** | 225 | **+$260.66** | 46.7% | 1.18 |

---

## 3. Four Mantras Walkthrough

### 1. Reproducibility
- Script: `docs/reviews/artifacts/repro_long_term_drawdown_root_cause.py`
- Execution time: 5.1 seconds.
- Deterministic output: Reproduces 68.74% DD, 16 SELL losses, 208 `buy_pause` rejections, 113 `risk_cap` rejections, and 72-day freeze.

### 2. Know the Fail Path
1. Initial 5% DD ($10 loss) triggers `buy_pause_drawdown` in `breakout_replay.py:372`.
2. All subsequent BUY signals (208 signals) are rejected.
3. System forced to trade only SELL breakouts during macro bull run.
4. 16 SELL losses push balance from $200 down to $110.04.
5. Gold ATR expands to $11.20–$15.31 at $4,000+ price.
6. 0.01 lot minimum requires $38.28 average risk per trade (2.5 ATR stop).
7. At $110.04 balance, 10% risk cap permits only $11.00 risk.
8. 167 of 173 signals exceed $11.00 risk and are rejected by `risk_cap` (`breakout_entry.py:105`).
9. Account is completely frozen.

### 3. Falsify Hypotheses
- **H1: `buy_pause` is the sole cause.** Disproved. Disabling `buy_pause` still resulted in -$79.73 net and 76.9% DD because counter-trend SELLs continued to lose.
- **H2: Breakeven (BE) would prevent the drawdown.** Disproved. Paired test showed BE at 1.0R reduced profit by 23% and increased DD from 22.5% to 26.57% due to premature stops on noisy gold retests.
- **H3: Counter-trend SELL breakouts in macro bull regimes drive the losses.** Confirmed. Filtering out SELL trades turned -$155.12 into +$367.38 in Dataset B and -$71.26 into +$260.66 in Dataset A.
- **H4: 10% Risk Cap mathematically paralyzes $200 accounts when ATR > $8.** Confirmed. Formula $\text{ATR}_{\text{max}} = 0.04 \times \text{Balance}$ proves that on $4,000+ gold with ATR > $11, a $110 balance cannot trade 0.01 lot within 10% risk.

### 4. Every Run is a Breadcrumb
All 6 experiment runs logged and cross-referenced in `docs/reviews/artifacts/`.

---

## 4. Architectural Solutions & Next Steps

To make the strategy resilient and viable across multi-year market conditions:

1. **Remove `buy_pause_drawdown`**:
   - Invert or delete this rule. Do not pause trades in the direction of the macro trend during drawdowns.
2. **Implement Macro Trend Filter (Directional Regime Gate)**:
   - Use Daily EMA200 or H4 EMA50 to determine macro market regime.
   - In Bull Regime: Only admit BUY breakouts. Reject SELL breakouts.
   - In Bear Regime: Only admit SELL breakouts. Reject BUY breakouts.
   - In Neutral / Choppy Regime: Tighter sizing or pause breakouts.
3. **Resolve the Micro-Account ($200) Sizing Constraint**:
   - **Option A (Exness Cent Account)**: Trade on a Standard Cent account where 0.01 cent lot = 0.01 oz of gold. Risk per trade is $0.25–$0.40, allowing perfect fractional risk sizing under 10% cap even at $50 equity.
   - **Option B (Capital Scaling)**: For standard accounts (0.01 lot = 1 oz), the true mathematical minimum balance for Gold at $4,000 is **$400–$500** to safely accommodate 2.5 ATR stops under a 10% risk cap without freezing.
