# Paired Head-to-Head Benchmark: Trial30 (Active Demo) vs Reward156 (Challenger)

**Date:** 2026-10-04  
**Audit Script:** `docs/reviews/artifacts/benchmark_trial30_vs_reward156.py`  
**Execution Environment:** 100% Identical Tick Data, Spread, Slippage, Sizing, and Risk Limits  
- **Initial Balance:** $200.00  
- **Lot Sizing:** Fixed 0.01 lot  
- **Risk Cap:** 10% of current equity  
- **Daily Loss Limit:** 20% UTC  

---

## 1. 6-Month Full Window (2026-03-28 to 2026-09-28)
*Dataset: 45,671,201 raw ticks, 12,100 complete M15 bars*

### Base Spread (Raw Exness Market Spread)
| Metric | Trial30 (Active Demo) | Reward156 (Challenger) | Difference |
|---|---|---|---|
| **Net Profit** | $465.32 | **$883.77** | **+$418.45 (+90%)** |
| **Max Drawdown** | 26.01% | **22.50%** | **-3.51% (Lower DD)** |
| **Win Rate** | 52.14% | **54.61%** | **+2.47%** |
| **Realized RR** | 1.1993 | **1.2726** | **+0.0733** |
| **Total Trades** | 140 | 152 | +12 |
| **BUY Trades** | 0 | 23 | +23 |
| **SELL Trades** | 140 | 129 | -11 |

### Stress Costs (+0.20 Spread, +0.10 Slippage)
| Metric | Trial30 (Active Demo) | Reward156 (Challenger) | Difference |
|---|---|---|---|
| **Net Profit** | $361.40 | **$742.03** | **+$380.63 (+105%)** |
| **Max Drawdown** | 29.44% | 33.97% | +4.53% |
| **Win Rate** | 50.72% | **53.42%** | **+2.70%** |
| **Realized RR** | 1.2013 | **1.2641** | **+0.0628** |
| **Total Trades** | 138 | 146 | +8 |
| **BUY Trades** | 0 | 17 | +17 |
| **SELL Trades** | 138 | 129 | -9 |

---

## 2. 6-Month Second-Half Choppy Window (2026-06-28 to 2026-09-28)
*Regime shift: Ranging/choppy gold market*

### Base Spread
| Metric | Trial30 (Active Demo) | Reward156 (Challenger) | Difference |
|---|---|---|---|
| **Net Profit** | $73.92 | **$370.61** | **+$296.69 (+401%)** |
| **Max Drawdown** | 32.93% | 34.45% | +1.52% |
| **Win Rate** | 49.02% | **55.71%** | **+6.69%** |
| **Realized RR** | 1.2075 | **1.2129** | +0.0054 |
| **Total Trades** | 51 | 70 | +19 |
| **BUY Trades** | 0 | 13 | +13 |
| **SELL Trades** | 51 | 57 | +6 |

### Stress Costs (+0.20 Spread, +0.10 Slippage)
| Metric | Trial30 (Active Demo) | Reward156 (Challenger) | Difference |
|---|---|---|---|
| **Net Profit** | $12.17 | **$335.64** | **+$323.47 (+2658%)** |
| **Max Drawdown** | 33.34% | 34.72% | +1.38% |
| **Win Rate** | 46.00% | **54.29%** | **+8.29%** |
| **Realized RR** | 1.2040 | **1.2338** | +0.0298 |
| **Total Trades** | 50 | 70 | +20 |
| **BUY Trades** | 0 | 13 | +13 |
| **SELL Trades** | 50 | 57 | +7 |

---

## 3. 1-Year Annual Second-Half Window (2026-04-01 to 2026-10-01)
*Dataset: 104,133,248 raw ticks, 23,230 complete M15 bars*

### Base Spread
| Metric | Trial30 (Active Demo) | Reward156 (Challenger) | Difference |
|---|---|---|---|
| **Net Profit** | $507.25 | **$981.95** | **+$474.70 (+94%)** |
| **Max Drawdown** | 25.99% | **22.50%** | **-3.49% (Lower DD)** |
| **Win Rate** | 53.06% | **56.41%** | **+3.35%** |
| **Realized RR** | 1.1702 | **1.2310** | **+0.0608** |
| **Total Trades** | 147 | 156 | +9 |
| **BUY Trades** | 0 | 21 | +21 |
| **SELL Trades** | 147 | 135 | -12 |

### Stress Costs (+0.20 Spread, +0.10 Slippage)
| Metric | Trial30 (Active Demo) | Reward156 (Challenger) | Difference |
|---|---|---|---|
| **Net Profit** | $452.37 | **$933.21** | **+$480.84 (+106%)** |
| **Max Drawdown** | 26.07% | **22.97%** | **-3.10% (Lower DD)** |
| **Win Rate** | 52.38% | **55.84%** | **+3.46%** |
| **Realized RR** | 1.1644 | **1.2355** | **+0.0711** |
| **Total Trades** | 147 | 154 | +7 |
| **BUY Trades** | 0 | 19 | +19 |
| **SELL Trades** | 147 | 135 | -12 |
