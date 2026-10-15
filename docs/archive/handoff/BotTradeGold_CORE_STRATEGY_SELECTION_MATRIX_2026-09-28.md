# BotTradeGold — Core Strategy Selection & Complete Candidate Matrix

**Document date:** 2026-09-28  
**Purpose:** เอกสารกลางสำหรับเลือก Core Strategy ที่มีผล backtest รองรับจริง พร้อมเก็บ strategy family อื่นทั้งหมดที่ยังมีเหตุผลให้ทดสอบ เพื่อป้องกันการตกหล่น candidate ที่อาจมี edge  
**Deployment target:** Exness MT5 Standard / `XAUUSDm` / Starting equity `$100` / Minimum lot `0.01`

---

# 0. Executive Summary

## Current project truth

ยังไม่มี strategy ใดผ่านครบทุกเงื่อนไขจนสามารถเรียกว่า **Final Production Strategy** ได้

```text
STRATEGY_NO_GO
DEMO_NO_GO
LIVE_NO_GO
```

แต่จากผลที่วัดได้จริงในโปรเจกต์ ณ ตอนนี้:

> **Core signal benchmark = `B1 M15 — Donchian30 + RSI14`**

เหตุผลคือ B1 M15 เป็นตัวที่มีข้อมูลของเราเองครบที่สุดในด้าน:

- sample มากกว่า 80 trades ใน primary
- return เป็นบวก
- expectancy เป็นบวก
- max drawdown ประมาณ 10%
- ผ่าน cost stress 0.10–0.15R แล้วยังเป็นบวก
- robustness หลัง warmup ประมาณ 7.4 เดือนยังเป็นบวกกว่า 200 trades

อย่างไรก็ตาม:

> **B1 M15 ยังไม่ใช่ Final Production สำหรับ `$100 / 0.01 lot`**

เพราะ SL 2.5 ATR ทำให้ monetary risk ของ minimum lot สูงเกิน risk budget บ่อยครั้ง

ดังนั้น strategy selection รอบต่อไปจะใช้:

```text
CORE
B1 M15
    │
    ├── NX2 VWAP + EMA Pullback
    ├── NX3 Mechanical Structural Break
    ├── NX1 Hybrid Continuation
    ├── NX4 Session Momentum
    ├── NX5 Regime Mean Reversion
    ├── NX6 EMA20/50 + Stochastic
    ├── NX7 ATR Expansion + RSI + FVG
    └── Mechanical SMC variants
```

ทุกตัวต้องถูกทดสอบแบบ parallel และใช้ gate เดียวกัน

---

# 1. Evidence Classification

เพื่อไม่ให้ external claim, YouTube claim และผลของโปรเจกต์ปนกัน ให้ใช้ป้ายดังนี้:

| Label | Meaning |
|---|---|
| `PROJECT-MEASURED` | มีผล backtest/replay ที่บันทึกในโปรเจกต์ |
| `PROJECT-TICK` | ใช้ observed Bid/Ask tick ของโปรเจกต์ |
| `EXTERNAL-RESEARCH` | มี evidence จาก paper/source ภายนอก |
| `YOUTUBE-OBSERVED` | ผู้สร้างคลิปรายงานผล แต่เราไม่ได้ reproduce |
| `HYPOTHESIS` | มี logic แล้วแต่ยังไม่ได้ backtest ของเรา |
| `REJECTED` | ทดสอบแล้วไม่ผ่าน |
| `INSUFFICIENT` | sample ไม่พอ |
| `FINAL_NO_GO` | ไม่ผ่าน Final Gate |

---

# 2. Core Strategy — B1 M15

## Strategy ID

```text
CORE_B1_M15_v1
```

## Logic

```text
Timeframe = M15

LONG
Close > Previous Donchian High(30)
AND
RSI14 <= 75

SHORT
Close < Previous Donchian Low(30)
AND
RSI14 >= 25

SL = 2.5 ATR(14)
TP = 3.5R
```

## Primary ~3-month result

**Window:** 2026-06-26 00:00 UTC → 2026-09-26 00:00 exclusive

| Cost | Trades | Win Rate | Expectancy | PF | Total R | Return | Max DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10R | **87** | 27.59% | **+0.141R** | **1.177** | +12.30R | **+11.83%** | **10.04%** |
| 0.15R | 87 | 27.59% | +0.091R | 1.110 | +7.95R | +6.84% | 10.31% |

## Longer robustness

หลัง warmup ประมาณ 7.4 เดือน:

| Cost | Trades | PF | Expectancy | Return |
|---:|---:|---:|---:|---:|
| 0.10R | **208** | **1.224** | **+0.176R** | **+19.65%** |
| 0.15R | 208 | 1.153 | +0.126R | +10.23% |

## Why this is Core

B1 M15 เป็นตัวที่มี evidence ในโปรเจกต์ดีที่สุดเมื่อดูพร้อมกัน:

```text
sample
+
positive expectancy
+
positive return
+
DD
+
cost robustness
+
multi-month robustness
```

## Limitation

ผล research ใช้ ideal fractional sizing และยังไม่ใช่หลักฐานว่า account:

```text
$100
minimum lot 0.01
```

สามารถ execute ทุก trade ได้โดยรักษา risk budget

**Status:** `PROJECT-MEASURED / CORE SIGNAL / NOT FINAL PRODUCTION`

---

# 3. Existing Project Strategy Matrix

| ID | Strategy | Core Logic | Evidence Window | Trades | Return | PF | Exp R | DD | Status |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| **CORE-1** | **B1 M15** | Donchian30 + RSI | Primary ~3M @0.10R | **87** | **+11.83%** | 1.177 | **+0.141** | **10.04%** | **Core** |
| CORE-1R | B1 M15 | same | ~7.4M robustness @0.10R | **208** | **+19.65%** | **1.224** | **+0.176** | — | Strong historical evidence |
| CTRL-2 | B1-M5 | Donchian40 + RSI | Primary ~3M `$100` | 19 | +6.56% | 1.228 | **-0.158** | 18.56% | Benchmark / NO_GO |
| CTRL-3 | B2 | EMA200 + Donchian20 | Primary | 12 | **-9.84%** | 0.491 | -0.417 | 11.03% | Reject |
| CTRL-4 | B3 | Asian Sweep | Latest 3M | 2 | +0.72% | 1.364 | +0.50 | 1.98% | Insufficient |
| CTRL-5 | I014 | M1 Compression Pullback | Tick confirmation | 15 observed | **-0.571%** | 0.972 | reserve -0.096 | reserve 11.08% | FINAL_NO_GO |
| CTRL-6 | MR2 | RSI crossback + H1 EMA200/slope | Primary @0.10R | 37 | +1.01% | 1.182 | +0.130 | 8.08% | Secondary evidence |

---

# 4. B1-M5-MICRO-RC1

## Logic

```text
TF          M5
Donchian    40
RSI         14
SL          0.5 ATR
TP          3R
Lot         0.01
Max pos     1
Martingale  OFF
Grid        OFF
DCA         OFF
```

## Discovery

| Cost | Trades | Return | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|
| 0R | 78 | +43.28% | 1.306 | +0.231 | 18.99% |
| .10R | 39 | +19.28% | 1.252 | +0.233 | 16.66% |

## Latest ~3M

| Cost | Trades | Return | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|
| 0R | 19 | +6.56% | 1.228 | -0.158 | 18.56% |
| .05R | 18 | +5.65% | 1.195 | -0.161 | 18.75% |
| .10R | 17 | +6.07% | 1.217 | -0.159 | 17.92% |

## $200 warning

เมื่อไม่ retune strategy และเพิ่มทุนเป็น `$200`:

```text
Return = -8.16%
PF     = 0.821
Exp    = -0.170R
DD     = 20.43%
Trades = 53
```

Interpretation:

> `$100` result บางส่วนสัมพันธ์กับ admission gate ที่ปฏิเสธ trade จำนวนมาก  
> เมื่อ capacity เปิด trade ได้มากขึ้น raw signal quality ดูแย่ลง

**Status:** `PROJECT-MEASURED / $100 CONTROL / NO_GO`

---

# 5. B2 — EMA200 + Donchian20

## Discovery

```text
Return +22.97%
PF      1.639
Exp     +0.400R
DD      9.55%
Trades  25
```

## Primary

```text
Return -9.84%
PF      0.491
Exp     -0.417R
DD      11.03%
Trades  12
```

Interpretation:

> strong discovery profile แต่ generalization collapse ชัดเจน

**Status:** `REJECTED`

---

# 6. B3 — Asian Sweep

## Concept

```text
Asian Range
→ Liquidity Sweep
→ Close back inside range
→ Entry next M15
→ SL beyond sweep
→ TP 2R
```

Latest ~3M:

```text
49 setups
47 risk rejects
2 trades

Return +0.72%
PF 1.364
Exp +0.50R
DD 1.98%
```

Sample 2 trades ไม่เพียงพอ

**Status:** `INSUFFICIENT / NO_GO`

Important:

> สิ่งที่ fail คือ exact B3 implementation + `$100` stop-risk geometry  
> ไม่ใช่ proof ว่า liquidity sweep หรือ SMC family ไม่มี edge

---

# 7. I014 — Compression Pullback

## Data

```text
31,780,274 observed Bid/Ask ticks
139,625 observed M1 bars
```

## Core

```text
M1 compression breakout
Lookback 12
Stop $2
RR 2
Session 07:00–13:00 UTC
Wait pullback 0.25 ATR
TTL 60s
```

## Discovery

```text
Observed:
35 trades
Return +25.087%
PF 1.645
DD 7.554%

Reserve:
35 trades
Return +14.587%
PF 1.327
Mean R +0.208
DD 8.838%
```

## Confirmation

```text
Observed:
15 trades
Return -0.571%
PF 0.972

Reserve:
14 trades
Return -2.696%
PF 0.873
Mean R -0.096
DD 11.080%
```

**Status:** `PROJECT-TICK / FINAL_NO_GO`

Compression family ยังเก็บไว้ แต่ exact I014 ไม่ promote

---

# 8. MR2 — Secondary Signal Evidence

## Logic

```text
RSI crossback 30/70
+
completed H1 EMA200/slope
SL = 2 ATR
TP = 2.5R
```

Primary @0.10R:

```text
37 trades
WR 35.14%
Exp +0.130R
PF 1.182
Return +1.01%
DD 8.08%
```

Return ต่ำ แต่ expectancy เป็นบวกและ DD ต่ำกว่า B1

**Status:** `SECONDARY / PRESERVE`

---

# 9. Candidate Universe — Complete Coverage

เป้าหมายของส่วนนี้คือป้องกันไม่ให้โปรเจกต์ “ทิ้ง candidate ดี” เพียงเพราะยังไม่ได้ priority ในรอบก่อน

---

# 10. NX1 — Hybrid Continuation

## Thesis

```text
EMA200 regime
      ↓
EMA20/50 local trend
      ↓
Pullback
      ↓
RSI momentum recovery
      ↓
Local structure / Donchian confirmation
      ↓
Risk + Cost Gate
```

## Arms

```text
NX1-A = Core
NX1-B = + Stochastic timing
NX1-C = + Liquidity Sweep
NX1-D = + Sweep + Stochastic
```

**Evidence:** `HYPOTHESIS / NOT YET TESTED`

---

# 11. NX2 — VWAP + EMA Pullback

## External research

Paper:

**A Regime-Filtered Intraday Trading Framework for Gold: Integrating VWAP Microstructure and EMA-Based Dynamic Exit Mechanisms**

Reported simulated XAU/USD M15 result:

```text
Period      Jan–Dec 2024
Trades      247
Win Rate    45.3%
Expectancy  +0.414R
PF          1.76
Sharpe      3.99
Max DD      5.1%
Risk        fixed 1% per trade
```

Paper logic:

```text
EMA200 = regime classifier
VWAP   = primary structural reference
EMA50  = pullback / rejection reference
ATR    = risk sizing
```

These are **external paper results**, not BotTradeGold results.

Source:
https://papers.ssrn.com/sol3/Delivery.cfm/6650958.pdf?abstractid=6650958&mirid=1&type=2

## BotTradeGold adaptation

```text
M15 > EMA200
AND
price > session VWAP
AND
pullback toward EMA50
AND
M5 rejection / structural reclaim
→ LONG candidate
```

Mirror for short

**Status:** `EXTERNAL-RESEARCH / PRIORITY CHALLENGER`

---

# 12. NX3 — Mechanical Structural Break

## External research

Paper:

**Structural-Break Entry and the Disposition Effect in a Commercial XAUUSD Strategy: A Tick-Level Decomposition**

Reported:

```text
XAUUSD 2024–2026
1,571 trades
tick-level study
Structural-break entry = sole source of risk-adjusted alpha in decomposed strategy
Annualised Sharpe reported 2.6–3.1
```

Robustness methods reported:

```text
random-entry placebo
multiple-testing correction
rolling windows
slippage stress
```

Paper also reports regime-conditional sizing did not outperform constant-risk sizing.

Source:
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6941458

## BotTradeGold adaptation

```text
Confirmed swing structure
      ↓
Pullback / optional sweep
      ↓
Close breaks last confirmed swing
      ↓
Minimum displacement
      ↓
Bounded retrace
      ↓
Entry
```

This is related to:

```text
BOS
MSS
CHOCH
```

but must use deterministic definitions

**Status:** `EXTERNAL-RESEARCH / HIGHEST PRIORITY CHALLENGER`

---

# 13. NX4 — Session-Conditioned Momentum

World Gold Council 2026 reports gold remained highly sensitive to geopolitical risk and investor sentiment, with elevated volatility and growing importance of Asian price discovery.

Relevant source:
https://www.gold.org/goldhub/research/gold-mid-year-outlook-2026

NX4 treats session as **information**, not only ON/OFF filter.

```text
Asia behavior
      ↓
Europe transition
      ↓
US behavior
      ↓
Continuation / reversal state
```

Example hypothesis:

```text
Asian directional expansion
+
Europe holds same side of VWAP
+
US does not reclaim opposite structure
→ continuation candidate
```

**Status:** `EXTERNAL-CONTEXT / HYPOTHESIS`

---

# 14. NX5 — Regime Mean Reversion

This tests a source of edge different from most current continuation systems.

```text
Low/normal volatility
      ↓
ATR-scaled VWAP deviation
      ↓
Liquidity exhaustion / sweep
      ↓
Structural reclaim
      ↓
Mean reversion toward VWAP
```

Do not use:

```text
RSI overbought → SELL
RSI oversold → BUY
```

without regime and structure confirmation

**Status:** `HYPOTHESIS`

---

# 15. NX6 — EMA20/50 + Stochastic Pullback

Derived from YouTube transcript

Known:

```text
EMA20
EMA50
Stochastic
M15
```

Creator reported ~63% win rate after changing the entry behavior

Unknown from transcript:

```text
exact K/D
Stochastic parameters
OB/OS thresholds
exact EMA touch line
trade count
PF
DD
cost assumptions
exact SL/TP
```

Therefore:

> 63% is **not** BotTradeGold evidence

## Reproducible version to test

```text
EMA20 > EMA50
→ bullish regime

pullback toward EMA zone
→ Stochastic oversold/recovery cross
→ structure confirmation
→ LONG
```

Mirror for short

**Status:** `YOUTUBE-OBSERVED / CHALLENGER`

---

# 16. NX7 — ATR Expansion1.5 + RSI + FVG

This was previously preserved as strategy `D`

```text
ATR Expansion 1.5
+
RSI
+
FVG
```

It was once designated as Secondary EA while B1 was Primary, but current project evidence does not show that it passed Final Gate.

Do not treat “Secondary” as proof of profitability.

**Status:** `PRESERVED / NEEDS CONTROLLED RE-TEST`

---

# 17. NX8 — Sweep → MSS → FVG

Mechanical SMC branch

```text
Liquidity sweep
      ↓
MSS
      ↓
Displacement
      ↓
FVG
      ↓
Retrace
      ↓
Entry
```

Need exact definitions for:

```text
swing
sweep distance
MSS threshold
displacement
FVG size
TTL
entry fill
SL invalidation
```

**Status:** `PRESERVED / RESEARCH`

---

# 18. NX9 — Sweep → CHOCH → OB/FVG

Includes:

```text
Sweep → CHOCH → FVG
Sweep → CHOCH → OB
Sweep → CHOCH → OB overlapped FVG
```

Problem:

- subjective definitions
- high parameter count
- easy to overfit
- difficult attribution

Do not reject permanently, but lower priority than NX3 mechanical structure

**Status:** `PRESERVED / LOW-MEDIUM PRIORITY`

---

# 19. ARCH-1 — Martingale / Recovery

Previously tested controlled combinations including:

```text
0.01 → 0.01
0.01 → 0.02
0.01 → 0.01 → 0.02
0.01 × 4
0.01 → 0.02 → 0.04 → 0.08
```

along with:

```text
RSI thresholds
grid spacing
basket stops
```

Approximately 300 combinations were tested in the research branch

Result:

> **0 configuration passed the discovery gate**

Therefore Martingale is not a missing candidate.

It was tested and rejected from the production path.

**Status:** `REJECTED`

---

# 20. ARCH-2 — Raw Opening Range Breakout

A 2026 pre-registered study tested:

```text
225 configurations
9 liquid US futures markets
16 years
```

After realistic transaction costs:

> **0 / 225 configurations passed the pre-registered positive bar**

The study reported that gross profitability disappeared after realistic round-trip costs.

Source:
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398

This is not XAUUSD-specific proof that every ORB fails, but it is strong reason not to prioritize raw ORB without extra structure/regime/cost controls.

**Status:** `LOW PRIORITY`

---

# 21. Complete Master Matrix

| ID | Family | Strategy | Project Evidence | External Evidence | Role |
|---|---|---|---|---|---|
| **CORE-1** | Breakout | **B1 Donchian30 + RSI** | **Strong positive** | — | **Core Benchmark** |
| CTRL-2 | Breakout | B1-M5 Donchian40 + RSI | Positive $, weak expectancy | — | `$100` Control |
| CTRL-3 | Trend Breakout | EMA200 + Donchian20 | Failed confirmation | — | Archive / Control |
| CTRL-4 | Compression | I014 Compression Pullback | Failed confirmation | — | Tick Control |
| CTRL-5 | Momentum/Regime | MR2 | Modest positive | — | Secondary |
| CTRL-6 | Liquidity Sweep | B3 Asian Sweep | 1–2 executable trades | — | Insufficient |
| NX1 | Hybrid | EMA + Pullback + RSI + Structure | Not tested | conceptual synthesis | Challenger |
| **NX2** | Trend Pullback | **VWAP + EMA200 + EMA50** | Not tested | **XAUUSD 247 trades paper** | **Priority** |
| **NX3** | Structure | **Mechanical Structural Break** | Not tested | **XAUUSD 1,571 trades tick study** | **Priority** |
| NX4 | Session | Session-Conditioned Momentum | Not tested | WGC context | Challenger |
| NX5 | Mean Reversion | VWAP deviation + structural reclaim | Not tested | supporting rationale | Challenger |
| NX6 | Trend Pullback | EMA20/50 + Stochastic | Not tested | YouTube observation | Challenger |
| NX7 | Volatility/SMC | ATR Expansion1.5 + RSI + FVG | incomplete | — | Preserve |
| NX8 | Mechanical SMC | Sweep → MSS → FVG | prior research | mixed | Preserve |
| NX9 | SMC | Sweep → CHOCH → OB/FVG | prior research | mixed | Preserve |
| ARCH-1 | Recovery | Martingale/Grid | **300 combos failed** | anecdotal success elsewhere | Reject |
| ARCH-2 | ORB | Raw Opening Range Breakout | not core | negative cost evidence | Low priority |

---

# 22. Three Core Edge Families We Must Not Miss

From all existing evidence, the final selection pipeline should guarantee coverage of at least these three independent sources of edge:

## A. Breakout

```text
Donchian breakout
+
RSI exhaustion guard
```

Representative:

```text
CORE-1 B1 M15
```

This has the strongest **project-owned evidence**

---

## B. Structural Break

```text
Swing structure
+
break
+
bounded retrace
```

Representative:

```text
NX3
```

This currently has the strongest **external XAUUSD tick-level evidence**

---

## C. Trend Pullback

```text
EMA200 regime
+
VWAP
+
EMA50 pullback
```

Representative:

```text
NX2
```

This has promising **external XAUUSD M15 evidence**

---

# 23. Modifiers — Do Not Treat as Independent Core Until Proven

These should initially be ablation features:

```text
RSI
Stochastic
FVG
Liquidity Sweep
Session
ATR Expansion
News Guard
```

Example:

```text
NX3
vs
NX3 + Sweep
vs
NX3 + FVG
```

rather than creating:

```text
EMA
+ RSI
+ Stochastic
+ Donchian
+ SMC
+ FVG
+ OB
+ ATR
```

all in one AND-chain

---

# 24. Shared Risk Contract

For comparable future tests:

| HWM DD | Max Initial Risk |
|---:|---:|
| `<5%` | 2.5% |
| `5–<10%` | 2.0% |
| `10–<15%` | 1.5% |
| `>=15%` | **Persistent HALT** |

Additional:

```text
Capital          $100
Minimum lot      0.01
Max positions    1
Max trades/day   2
Max full SL/day  2
Daily loss       5%
Martingale       OFF
Grid             OFF
DCA              OFF
```

---

# 25. Fee / Cost Gate

Before entry:

```text
CostR =
ExpectedTradingCost
/
InitialMonetaryRisk
```

Include:

```text
Spread
Commission
Modeled Slippage
Swap if applicable
```

Baseline:

```text
CostR <= 0.15R
→ candidate may trade

CostR > 0.15R
→ SKIP
```

When observed Bid/Ask exists, use it directly

---

# 26. Initial Exit Contract

For new candidate RC1 versions:

```text
Partial TP = OFF
BE         = OFF
Trailing   = OFF
```

Use simple exit first to identify entry edge

Suggested controlled RR:

```text
1.5R
2.0R
```

Do not large-grid optimize RR after looking at confirmation

Stop should follow:

```text
market structure invalidation
+
ATR / volatility floor
```

Then verify monetary risk at `0.01 lot`

---

# 27. Promotion Gate

At minimum:

```text
Closed trades >= 30
PF after cost >= 1.30
Mean net R > +0.10R preferred
Net return > 0
DD <= 15%
Return/DD >= 1.0 preferred
Cost stress remains positive
No persistent halt
Confirmation positive
```

A strategy that only passes discovery does not qualify

---

# 28. Final Gate

Final Production additionally requires:

```text
Observed Bid/Ask
Spread stress
2-second delay stress
Adverse fill stress
Combined stress
Future untouched OOS
Measured broker costs
EA compile
Python/MQL parity
Exness symbol specification
Margin / stop validation
Restart recovery
Single-instance protection
Reconciliation
Duplicate-order protection
```

---

# 29. Official Parallel Backtest Queue

## Group A — Controls

```text
CTRL_B1_M15
CTRL_B1_M5
CTRL_B2
CTRL_I014
CTRL_MR2
```

## Group B — Highest Priority Challengers

```text
NX3_STRUCT_BREAK
NX2_VWAP_EMA
NX1_HYBRID
```

## Group C — Coverage Challengers

```text
NX4_SESSION
NX5_MEAN_REVERSION
NX6_EMA_STOCH
NX7_ATR_RSI_FVG
NX8_SWEEP_MSS_FVG
NX9_SWEEP_CHOCH_OB_FVG
```

---

# 30. Research Priority

This is a **testing priority**, not a performance ranking.

```text
1. Reproduce CORE B1
2. NX3 Mechanical Structural Break
3. NX2 VWAP + EMA Pullback
4. NX1 Hybrid
5. NX6 EMA20/50 + Stochastic
6. NX7 ATR Expansion + RSI + FVG
7. NX8 Mechanical SMC
8. NX4 Session
9. NX5 Mean Reversion
10. NX9 OB/FVG complex SMC
```

---

# 31. Why This Coverage Is Enough

The universe now covers major independent strategy theses:

| Thesis | Candidate |
|---|---|
| Trend breakout | B1 |
| Shorter-TF breakout | B1-M5 |
| Trend-regime breakout | B2 |
| Momentum pullback | NX1 |
| VWAP trend pullback | NX2 |
| Structural break | NX3 |
| Session effect | NX4 |
| Mean reversion | NX5 |
| EMA/Stochastic pullback | NX6 |
| Volatility expansion | NX7 |
| Liquidity sweep / FVG | NX8 |
| OB / CHOCH | NX9 |
| Compression | I014 |
| RSI regime reversal | MR2 |
| Recovery / Martingale | tested/rejected |
| Raw ORB | low priority due cost evidence |

Therefore the project no longer needs to continually invent unrelated new strategy families before measuring this set.

---

# 32. Final Decision Rule

Do not select a strategy because:

```text
highest return
highest win rate
most popular on YouTube
most popular in SMC community
looks best on chart
```

Select based on:

```text
1. Positive confirmation
2. Sufficient sample
3. Positive expectancy
4. PF after realistic costs
5. Controlled DD
6. Cost resilience
7. Cross-regime stability
8. Broker feasibility
9. Tick/execution resilience
10. Future unseen performance
```

---

# 33. Current Conclusion

## Core now

```text
B1 M15
Donchian30 + RSI14
```

because it currently has the strongest project-owned historical evidence:

```text
Primary:
87 trades
+11.83%
PF 1.177
Exp +0.141R
DD 10.04%

Longer robustness:
208 trades
+19.65%
PF 1.224
Exp +0.176R
```

## But

```text
B1 M15 != Final Production
```

because `$100 / 0.01 lot` stop-risk feasibility remains unresolved

## Core challengers that must not be missed

```text
NX3 Mechanical Structural Break
NX2 VWAP + EMA Pullback
NX1 Hybrid Continuation
NX6 EMA20/50 + Stochastic
NX7 ATR Expansion + RSI + FVG
NX8 Mechanical SMC
```

The next phase should therefore be:

> **Stop expanding the strategy universe temporarily and run controlled parallel backtests across this complete set.**

---

# 34. External Source Registry

## Structural Break — SSRN

https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6941458

## VWAP + EMA Gold Framework — SSRN

https://papers.ssrn.com/sol3/Delivery.cfm/6650958.pdf?abstractid=6650958&mirid=1&type=2

## World Gold Council — Gold Mid-Year Outlook 2026

https://www.gold.org/goldhub/research/gold-mid-year-outlook-2026

## ORB Transaction-Cost Study — SSRN

https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398

---

# 35. Source-of-Truth Principle

Every future result added to this document must state:

```text
Strategy ID
Evidence type
Data source
Data hash
Date range
Config hash
Code hash
Trades
Return
PF
Expectancy
DD
Cost assumptions
Stress arm
Verdict
```

Never replace a prior negative result.  
Append new evidence and preserve chronology.

