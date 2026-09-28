# BotTradeGold — Central Strategy Registry & Parallel Backtest Plan

**Document date:** 2026-09-28  
**Project:** BotTradeGold  
**Purpose:** เอกสารกลาง (Source of Truth) สำหรับ strategy, setup, risk, fee, execution, backtest, และ Final Gate  
**Primary deployment target:** Exness MT5 Standard / `XAUUSDm` / Starting Capital `$100` / Minimum lot `0.01` / Leverage `1:1000`

---

# 0. Executive Status

## Current truth

> **ยังไม่มี Final Production Strategy ที่ผ่าน gate**
>
> Current project state:
>
> - `STRATEGY_NO_GO`
> - `DEMO_NO_GO`
> - `LIVE_NO_GO`

ชื่ออย่าง `B1-FINAL-v1` เป็นชื่อ engineering baseline ที่ freeze ไว้ ไม่ใช่คำรับรองว่าใช้เงินจริงได้แล้ว

## Why this document exists

โปรเจกต์ได้ทดลองหลาย family:

- Donchian breakout
- RSI guard / momentum
- EMA regime
- Compression breakout
- Pullback / rebreak
- SMC / liquidity sweep / MSS / CHOCH / FVG / OB
- Asian range sweep
- ATR expansion
- EMA20/50 + Stochastic concept จาก YouTube
- Martingale / recovery research
- Session-based logic
- Real-tick execution modeling

ปัญหาหลักที่ผ่านมาไม่ใช่แค่ “หา indicator ที่แม่น” แต่คือ:

1. edge บางตัวดูดีใน discovery แล้วพังใน confirmation
2. `$100 + 0.01 lot` ทำให้ stop/risk geometry จำกัดมาก
3. strategy บางตัว sample ต่ำจนสรุปไม่ได้
4. transaction cost / spread / execution มีผลมาก
5. การเพิ่ม feature มากเกินไปเสี่ยง overfitting
6. ยังไม่มี untouched/future OOS + measured broker execution + EA parity ครบ

---

# 1. Non-Negotiable Project Contract

## Account / Broker assumptions

```text
Broker          Exness
Platform        MT5
Account         Standard
Symbol          XAUUSDm
Starting Equity $100
Minimum Lot     0.01
Leverage        1:1000
Martingale      OFF for production baseline
Grid            OFF for production baseline
DCA             OFF for production baseline
Max Position    1
```

Leverage ช่วยเรื่อง margin แต่ **ไม่ลด monetary loss ที่ stop**

---

# 2. Evidence Classification

ทุก strategy ต้องถูกติดป้ายหลักฐานอย่างน้อยหนึ่งประเภท

| Evidence Class | Meaning |
|---|---|
| `PROJECT-MEASURED` | มีผล backtest / replay ที่บันทึกใน project |
| `PROJECT-TICK` | ใช้ observed Bid/Ask tick ของ broker capture |
| `CHAT-REPORTED` | ผลอยู่ใน handoff/chat แต่ artifact raw ไม่ได้อยู่ใน runtime ปัจจุบัน |
| `EXTERNAL-RESEARCH` | มาจาก paper / WGC / source ภายนอก |
| `YOUTUBE-OBSERVED` | มาจาก transcript/ประสบการณ์ในคลิป |
| `HYPOTHESIS` | มี logic แล้ว แต่ยังไม่ได้ backtest ของเรา |
| `REJECTED` | ทดสอบแล้วไม่ผ่าน |
| `INSUFFICIENT` | sample หรือ evidence ไม่พอ |
| `FINAL_NO_GO` | ไม่ผ่าน Final Gate |

**ห้าม**เอา `EXTERNAL-RESEARCH` หรือ `YOUTUBE-OBSERVED` มารายงานเป็น performance ของ BotTradeGold

---

# 3. Current Baseline Strategy Registry

## 3.1 B1 M15 — Donchian30 + RSI14

### Logic

```text
TF = M15

LONG
Close > previous Donchian High(30)
AND RSI14 <= 75

SHORT
Close < previous Donchian Low(30)
AND RSI14 >= 25

SL = 2.5 ATR(14)
TP = 3.5R
```

### Primary research result

**Window:** 2026-06-26 00:00 UTC → 2026-09-26 00:00 exclusive

| Cost | Trades | WR | Exp R | PF | Total R | Return | DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10R | 87 | 27.59% | +0.141 | 1.177 | +12.30R | +11.83% | 10.04% |
| 0.15R | 87 | 27.59% | +0.091 | 1.110 | +7.95R | +6.84% | 10.31% |

### Longer robustness record

หลัง warmup ประมาณ 7.4 เดือน:

| Cost | Trades | PF | Exp R | Return |
|---:|---:|---:|---:|---:|
| 0.10R | 208 | 1.224 | +0.176 | +19.65% |
| 0.15R | 208 | 1.153 | +0.126 | +10.23% |

### Important limitation

ผลนี้ใช้ ideal fractional sizing และไม่ได้พิสูจน์ว่า `$100 / 0.01 lot` execute ได้จริงทุก signal

**Status:** `PROJECT-MEASURED / RESEARCH BASELINE / NOT PRODUCTION`

---

## 3.2 B1-M5-MICRO-RC1 — Donchian40 + RSI14

### Frozen logic

```text
TF          M5
Donchian    40
RSI         14
LONG        breakout + RSI <= 75
SHORT       breakout + RSI >= 25
SL          0.5 ATR(14)
TP          3R
Lot         0.01
Max pos     1
Martingale  OFF
Grid        OFF
DCA         OFF
```

### Data

```text
35,954 M5 bars
2026-03-26 02:30 UTC
→ 2026-09-25 20:40 UTC

Pinned blob:
f1496e97c406794e4a1287dfdb7d0058407c8c61
```

### Discovery — $100

| Cost | Trades | Return | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|
| 0R | 78 | +43.28% | 1.306 | +0.231 | 18.99% |
| 0.10R | 39 | +19.28% | 1.252 | +0.233 | 16.66% |

### Primary latest ~3M — $100

**Window:** 2026-06-25 20:40 UTC → 2026-09-25 20:40 UTC

| Cost | Trades | Return | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|
| 0R | 19 | +6.56% | 1.228 | -0.158 | 18.56% |
| 0.05R | 18 | +5.65% | 1.195 | -0.161 | 18.75% |
| 0.10R | 17 | +6.07% | 1.217 | -0.159 | 17.92% |

### $200 sensitivity

| Cost | Trades | Return | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|
| 0R | 53 | -8.16% | 0.821 | -0.170 | 20.43% |
| 0.05R | 45 | -8.86% | 0.774 | -0.250 | 20.76% |
| 0.10R | 43 | -9.12% | 0.766 | -0.263 | 20.71% |

### Interpretation

- practical กับ `$100` มากกว่า B1 M15
- แต่ Return ล่าสุด ~3M แค่ประมาณ +6%
- Expectancy R ติดลบ
- DD ~18%
- `$200` แย่ลงเมื่อ admission ยอมให้เข้า trade มากขึ้น
- raw signal quality ยังไม่ robust

**Status:** `PROJECT-MEASURED / $100 BENCHMARK / NO_GO`

---

## 3.3 B2-BALANCED-INTRADAY-RC1 — EMA200 + Donchian20

### Frozen tested logic

```text
M15 EMA200 direction
M5 Donchian20 breakout
Session 12:00–16:00 UTC
SL 0.5 ATR(14)
TP 2.5R
0.01 lot
Max 1 position
No overnight
No Martingale
No Grid
```

### Discovery

| Cost | Trades | Return | WR | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0R | 25 | +22.97% | 40.00% | 1.639 | +0.400 | 9.55% |
| 0.10R | 22 | +16.17% | 40.91% | 1.458 | +0.332 | 10.73% |

### Primary

| Cost | Trades | Return | WR | PF | Exp R | DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0R | 12 | -9.84% | 16.67% | 0.491 | -0.417 | 11.03% |
| 0.05R | 8 | -9.45% | 12.50% | 0.366 | -0.613 | 10.36% |
| 0.10R | 8 | -10.27% | 12.50% | 0.342 | -0.663 | 10.89% |
| 0.15R | 11 | -10.96% | 18.18% | 0.449 | -0.514 | 11.28% |

### Interpretation

Discovery ดูดี แต่ confirmation collapse

**Status:** `PROJECT-MEASURED / REJECTED`

---

## 3.4 B3-ASIAN-SWEEP-RC1

### Logic

```text
Asian range:
23:00 previous day → 06:00 UTC

Scan:
07:45 → 14:30 UTC

M15:
sweep high/low
→ close back inside range within <=3 bars
→ entry next M15

SL = sweep extreme ± $0.30 research buffer
TP = 2R
Lot = 0.01
Max 1 trade/day
Force flat 19:30 UTC
```

### Data

```text
11,989 M15 bars
2026-03-26 02:30 UTC
→ 2026-09-25 20:30 UTC

Pinned blob:
1a30da07131271a3198452014b87452700d0b8e0
```

### Result

| Window | Cost | Setups / rejects / trades | Return | PF | Exp R | DD |
|---|---:|---|---:|---:|---:|---:|
| Discovery | 0 | 42 / 41 / 1 | -2.31% | 0 | -1.00 | 2.31% |
| Discovery | .10 | 42 / 41 / 1 | -2.54% | 0 | -1.10 | 2.54% |
| Latest3M | 0 | 49 / 47 / 2 | +0.72% | 1.364 | +0.50 | 1.98% |
| Latest3M | .10 | 49 / 47 / 2 | +0.39% | 1.178 | +0.40 | 2.18% |

### Interpretation

DD ต่ำเพราะแทบไม่เปิด trade  
sample 1–2 trades ไม่สามารถพิสูจน์ edge

**Status:** `PROJECT-MEASURED / INSUFFICIENT / NO_GO`

---

## 3.5 I014 — M1 Compression Pullback

### Data quality

```text
31,780,274 verified observed Bid/Ask ticks
2026-05-07 → 2026-09-25

139,625 observed M1 bars
```

### Frozen candidate

```text
M1 compression breakout
Lookback = 12
Fixed stop = $2
RR = 2
Session = 07:00–13:00 UTC
Trend filter = OFF

Conditional pullback:
wait = 0.25 ATR
TTL = 60s
first adverse-inclusive entry-side quote crossing
```

### Discovery

| Arm | Trades | Return | PF | Mean R | DD |
|---|---:|---:|---:|---:|---:|
| Observed | 35 | +25.087% | 1.645 | — | 7.554% |
| Reserve | 35 | +14.587% | 1.327 | +0.208 | 8.838% |

### Frozen confirmation

| Arm | Trades | Return | PF | Mean R | DD |
|---|---:|---:|---:|---:|---:|
| Observed | 15 | -0.571% | 0.972 | — | — |
| Reserve | 14 | -2.696% | 0.873 | -0.096 | 11.080% |

Spread×2 / combined had zero admitted trades

**Status:** `PROJECT-TICK / FINAL_NO_GO`

---

# 4. Existing Research Branches That Stay Preserved

## D — ATR Expansion1.5 + RSI + FVG

เคยถูกตั้งเป็น Secondary candidate หลัง B1

```text
ATR Expansion1.5
+
RSI
+
FVG
```

แต่ไม่มี comparable final evidence ในเอกสารกลางที่ยืนยันว่าผ่าน production gate

**Status:** `PRESERVED / NOT PROMOTED`

---

## SMC families studied previously

```text
Sweep → MSS → FVG
Sweep → CHOCH → FVG
Sweep → CHOCH → OB
Sweep → CHOCH → OB + FVG
```

ปัญหาเดิม:

- variable เยอะ
- definition subjective
- attribution ยาก
- backtest อาจดูดีเพราะ pattern interpretation
- ยังไม่มีตัวที่ผ่าน final evidence

**Status:** `RESEARCH ONLY`

---

# 5. YouTube-Derived Strategy Ideas

Source: `Nopparuj - บันทึกจาก Youtube-transcript.txt`

## 5.1 EMA20 + EMA50 + Stochastic

ผู้ทำคลิปรายงานว่า:

- ใช้ EMA20 / EMA50
- ใช้ Stochastic Oscillator
- หลังปรับ entry บน M15 เคยเห็น win rate ประมาณ 63%
- แต่ signal น้อยจนหลายวันไม่มี trade

ข้อจำกัด:

```text
Exact EMA touch line ไม่ชัดจาก transcript
Stochastic K/D parameters ไม่ครบ
OB/OS thresholds ไม่ครบ
SL/TP ไม่ครบ
Sample size ไม่ครบ
PF/DD/cost ไม่ครบ
```

**Status:** `YOUTUBE-OBSERVED / HYPOTHESIS`

---

## 5.2 RSI + Recovery / Martingale

ในคลิปมี ladder:

```text
0.01
→ 0.02
→ 0.04
→ 0.08
```

และ basket hard stop ลดจาก `$80` เป็น `$55`

บน starting capital `$200` คลิปรายงาน ending equity ประมาณ `$279.81`

แต่:

```text
$55 / $200 = 27.5%
$55 / $100 = 55%
```

จึงไม่เหมาะเป็น production baseline ของเรา

**Status:** `RESEARCH ONLY / MARTINGALE OFF FOR PRODUCTION`

---

# 6. New Strategy Universe — Additive Only

**ข้อกำหนดสำคัญ:**  
ห้าม overwrite ของเดิม  
ทุก setup ใหม่ต้องสร้างเป็น branch/candidate ใหม่ และ backtest ควบคู่กับ control เดิม

---

# 7. NX1 — Hybrid Continuation State Machine

## Thesis

รวมสิ่งที่มีเหตุผลจากของเดิม แต่แยกหน้าที่ชัดเจน:

```text
Higher-TF Regime
      ↓
Pullback / Liquidity Event
      ↓
Momentum Recovery
      ↓
Price Confirmation
      ↓
Cost / Risk Gate
      ↓
Entry
```

## Core roles

| Component | Role |
|---|---|
| EMA200 | Macro regime |
| EMA20/50 | Local trend/pullback zone |
| RSI14 | Momentum recovery / extreme guard |
| Donchian / local break | Price confirmation |
| Liquidity sweep | Optional quality event |
| Stochastic | Optional timing challenger |
| ATR | Volatility / stop geometry |
| Final-loop risk engine | Admission |

## NX1-A — Core

### LONG

```text
M15 Close > EMA200
AND
M5 EMA20 > EMA50
AND
price pulls back toward EMA20–EMA50
AND
50 < RSI14 <= 75
AND
local structure rebreak OR Donchian20 high break
→ LONG candidate
```

### SHORT

```text
M15 Close < EMA200
AND
M5 EMA20 < EMA50
AND
price pulls back toward EMA20–EMA50
AND
25 <= RSI14 < 50
AND
local structure rebreak OR Donchian20 low break
→ SHORT candidate
```

## Ablation arms

```text
NX1-A = core
NX1-B = NX1-A + Stochastic timing
NX1-C = NX1-A + mechanical liquidity sweep
NX1-D = NX1-A + Sweep + Stochastic
```

**Status:** `HYPOTHESIS / NOT YET TESTED`

---

# 8. NX2 — VWAP + EMA Pullback

## External rationale

2026 SSRN paper:

**A Regime-Filtered Intraday Trading Framework for Gold: Integrating VWAP Microstructure and EMA-Based Dynamic Exit Mechanisms**

Reported XAU/USD M15 simulation, Jan–Dec 2024:

```text
247 trades
Win rate     45.3%
Expectancy   +0.414R
PF           1.76
Max DD       5.1%
```

These are **external paper results**, not BotTradeGold results.

Source:  
https://papers.ssrn.com/sol3/Delivery.cfm/6650958.pdf?abstractid=6650958&mirid=1&type=2

## BotTradeGold adaptation

```text
M15 EMA200 = regime
Session VWAP = value / microstructure reference
EMA50 = pullback reference
M5 structure break = confirmation
ATR = stop geometry
Final cost/risk gate = admission
```

### LONG concept

```text
M15 > EMA200
AND
price > session VWAP
AND
pullback toward EMA50
AND
bullish rejection / M5 structure reclaim
→ candidate
```

**Status:** `EXTERNAL-RESEARCH / HYPOTHESIS`

---

# 9. NX3 — Mechanical Structural Break

## External rationale

2026 SSRN paper:

**Structural-Break Entry and the Disposition Effect in a Commercial XAUUSD Strategy: A Tick-Level Decomposition**

Reported:

```text
XAUUSD
2024–2026
1,571 trades
tick-level decomposition
structural-break entry = main source of risk-adjusted alpha
annualized Sharpe reported ~2.6–3.1
```

External paper result only.

Source:  
https://papers.ssrn.com/sol3/Delivery.cfm/6941458.pdf?abstractid=6941458&mirid=1

## BotTradeGold adaptation

Mechanical, not discretionary SMC:

### LONG

```text
1. confirmed short-term swing structure
2. pullback / optional liquidity sweep
3. close above last confirmed swing high
4. minimum displacement condition
5. bounded retrace / entry window
6. SL below structural invalidation
```

### SHORT

Mirror logic

This is conceptually close to:

```text
MSS / CHOCH
```

but must use deterministic swing definitions

**Status:** `EXTERNAL-RESEARCH / HIGH-PRIORITY HYPOTHESIS`

---

# 10. NX4 — Session-Conditioned Momentum

## External rationale

World Gold Council 2026 notes:

- a large share of gold movement occurred during Asian and US hours
- many pullbacks occurred in US hours
- rebounds often occurred during Asian hours
- 2026 gold volatility remained elevated
- bid-ask spread widening was episodic and often outside standard trading hours

Sources:

- https://www.gold.org/goldhub/research/gold-mid-year-outlook-2026
- https://www.gold.org/goldhub/gold-focus/2026/04/you-asked-we-answered-has-golds-performance-structurally-changed

## Candidate idea

Session is no longer only an ON/OFF filter

```text
Asia
→ build directional / volatility state

Europe
→ validate hold / reversal

US
→ continuation or controlled reversal condition
```

Example research hypothesis:

```text
Asian expansion
+
Europe holds same side of VWAP
+
US does not reclaim opposite structure
→ continuation candidate
```

**Status:** `EXTERNAL-RESEARCH / HYPOTHESIS`

---

# 11. NX5 — Regime Mean Reversion

## Why include it

Most existing strategies are:

```text
breakout
trend
continuation
```

NX5 tests a different source of edge

## Candidate

```text
Low / normal volatility regime
      ↓
Price deviates from VWAP by ATR-scaled threshold
      ↓
Liquidity sweep / exhaustion
      ↓
Structural reclaim
      ↓
Mean reversion toward VWAP
```

### LONG concept

```text
ATR regime = low/normal
AND
price below VWAP - k*ATR
AND
recent low swept
AND
close reclaims
AND
local structure breaks upward
→ long toward VWAP
```

No blind:

```text
RSI oversold → BUY
```

**Status:** `HYPOTHESIS`

---

# 12. Raw ORB Is Not a Priority

2026 pre-registered SSRN study:

- 225 cells
- 9 liquid US futures markets
- 16 years of 1-minute data
- fixed exploration / confirmation / reserve
- zero of 225 cells passed the positive bar after realistic costs

Source:  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398

Therefore:

```text
Raw Opening Range Breakout
≠ priority
```

If session breakout is tested, it must include:

- regime
- cost
- volatility
- structural confirmation
- independent confirmation

---

# 13. Shared Risk Architecture for All New Candidates

Unless an experiment explicitly studies risk management, all strategies must use the same risk contract.

## HWM de-risk

| HWM DD | Max Initial Risk |
|---:|---:|
| `<5%` | 2.5% |
| `5–<10%` | 2.0% |
| `10–<15%` | 1.5% |
| `>=15%` | **Persistent HALT** |

## Daily controls

```text
Max new trades/day = 2
Max full SL/day    = 2
Daily realized loss >= 5%
→ no new trades
```

## Lot / monetary risk

```text
Minimum lot = 0.01

Calculate actual monetary loss at proposed stop

If:
0.01-lot stop risk > current risk budget
→ SKIP

Do NOT:
shrink market-valid stop merely to force the trade
```

MT5 implementation should use broker-native calculation such as `OrderCalcProfit()` / symbol specifications rather than hardcoding monetary value.

---

# 14. Shared Fee / Cost Architecture

## Cost ratio

```text
CostR =
Expected Trading Cost
/
Initial Monetary Risk
```

Expected trading cost includes where applicable:

```text
spread
+ commission
+ modeled slippage
+ swap
```

## Admission baseline

```text
CostR <= 0.15R
→ may trade

CostR > 0.15R
→ SKIP
```

Actual Bid/Ask should be used whenever tick data is available.

Do not:

```text
run gross-profit backtest
then subtract one fixed fee at the end
```

Every stress arm must re-run:

- admission
- fills
- risk
- quota
- DD halt
- equity path

---

# 15. Exit Architecture

For initial RC versions:

```text
Partial TP  OFF
Break-even  OFF
Trailing    OFF
```

Reason:

> Measure the entry edge before adding payoff engineering.

## Baseline TP

```text
TP = fixed R
```

Typical initial controlled arms:

```text
1.5R
2.0R
```

Do not sweep large RR grids after seeing confirmation results.

## Stop

Use:

```text
structure invalidation
+
volatility floor / ATR floor
```

Then check monetary feasibility

---

# 16. Session / Overnight / News

## Intraday baseline

```text
No overnight by default
Force flat before rollover
Reference cutoff = 19:30 UTC
```

## News

High-impact USD events are an admission block for baseline candidates, e.g.:

```text
CPI
NFP
FOMC / Fed rate decision
```

Research can compare news filter ON/OFF only if declared before confirmation.

---

# 17. Operational Safety Contract

Mandatory production requirements:

```text
single-instance lock
position identity
restart recovery
persistent HWM
durable event/outbox state
duplicate-order prevention
reconciliation
unknown-delivery protection
broker margin/min-lot/stops validation
```

YouTube transcript showed a real operational failure mode where two bot instances ran at the same time after restart and lot progression became incorrect.

Operational correctness is part of Final Gate, not optional engineering.

---

# 18. Parallel Backtest Architecture

Old strategy code/config remains unchanged.

```text
                    XAUUSD DATA
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
 OLD CONTROLS        TICK CONTROL       NEW BRANCHES
 B1/B1-M5/B2         I014               NX1–NX5
      │                  │                  │
      └──────────────────┼──────────────────┘
                         ▼
                SAME METRIC ENGINE
                         ▼
              SAME PROMOTION GATES
```

---

# 19. Official Parallel Test Arms

## Controls

```text
CTRL-B1-M15
CTRL-B1-M5
CTRL-B2
CTRL-I014
```

## New candidates

```text
NX1-A Hybrid Core
NX1-B + Stochastic
NX1-C + Liquidity Sweep
NX1-D + Sweep + Stochastic

NX2 VWAP + EMA Pullback

NX3 Mechanical Structural Break

NX4 Session-Conditioned Momentum

NX5 Regime Mean Reversion
```

---

# 20. Testing Order

To reduce data mining:

## Phase A — Controls reproduce

Before judging new setups:

```text
1. reproduce control outputs
2. verify source hashes
3. verify date splits
4. verify cost assumptions
5. verify trade accounting
```

## Phase B — Discovery

Evaluate new candidates on discovery data only.

## Phase C — Freeze

Freeze:

```text
logic
parameters
session
SL
TP
risk
cost
```

before confirmation

## Phase D — Confirmation

No retuning after seeing confirmation.

## Phase E — Stress

At least:

```text
observed spread
+0.15R reserve
spread ×2
2-second delay
adverse $0.10/oz entry
combined
```

## Phase F — Future / untouched OOS

Required for final promotion.

## Phase G — Broker / EA parity

Required:

```text
EA compile
Python/MQL parity
Exness Tester / broker spec
fills
margin
stop constraints
reconciliation
restart behavior
```

---

# 21. Promotion Gate

A research candidate should not be promoted unless at minimum:

```text
Closed trades >= 30
PF after cost >= 1.30
Mean net R > 0
Net return > 0
Tick / marked DD <= 15%
No persistent halt
No end-mark counted as closed
No late force-flat
Cost confirmation passes
```

For project quality target, prefer:

```text
3M Return ~12–15%+
PF >= 1.30
Exp >= +0.10R
DD <= 15%
Return/DD >= 1.0
```

These are project acceptance targets, not guaranteed market standards.

---

# 22. Final Production Gate

Research pass is not enough.

Final production additionally requires:

```text
untouched/future validation
measured execution costs
EA compile/parity
target broker/account fills
margin/stops constraints
zero reconciliation incidents
zero state/restart incidents
zero duplicate-instance/order incidents
```

Possible final verdicts:

```text
PASS
NO_GO
INSUFFICIENT
```

`NO_GO` is a valid research outcome.

---

# 23. Current Evidence Matrix

| Strategy | Source | Confirmation Return | PF | Exp R | DD | Evidence State |
|---|---|---:|---:|---:|---:|---|
| B1 M15 | Project historical | +11.83% @0.10R | 1.177 | +0.141 | 10.04% | signal evidence; ideal sizing caveat |
| B1-M5 | Project $100 | +6.56% | 1.228 | -0.158 | 18.56% | benchmark / NO_GO |
| B2 | Project $100 | -9.84% | 0.491 | -0.417 | 11.03% | rejected |
| B3 | Project OHLC | +0.72% | 1.364 | +0.50 | 1.98% | only 2 trades; insufficient |
| I014 | Project Bid/Ask tick | -0.571% observed | 0.972 | reserve -0.096 | reserve 11.08% | FINAL_NO_GO |
| NX1 | New | — | — | — | — | NOT TESTED |
| NX2 | New | — | — | — | — | NOT TESTED |
| NX3 | New | — | — | — | — | NOT TESTED |
| NX4 | New | — | — | — | — | NOT TESTED |
| NX5 | New | — | — | — | — | NOT TESTED |

---

# 24. Priority Queue

## Priority A

### NX3 — Mechanical Structural Break

Reason:

- different source of edge
- close to SMC but deterministic
- external XAUUSD tick-level evidence exists
- easy to ablate entry vs risk/exit

### NX2 — VWAP + EMA Pullback

Reason:

- pullback rather than breakout chase
- XAUUSD M15 external evidence
- clean machine-testable architecture

## Priority B

### NX1 — Hybrid Continuation

Useful synthesis of project knowledge

### NX4 — Session-Conditioned Momentum

Gold session behavior may matter, but must not be converted directly from observation into assumed edge

## Priority C

### NX5 — Mean Reversion

Useful diversification of edge source, but should be strictly regime-gated

---

# 25. What We Will NOT Do

```text
NO:
- overwrite old strategies
- delete negative backtests
- choose parameter from confirmation
- report external paper return as our return
- report YouTube result as our backtest
- add every indicator into one AND chain
- increase risk merely to force 0.01 lot admission
- use Martingale to hide weak entry edge
- promote a 1–2 trade sample
- call discovery success "production"
```

---

# 26. Required Output of Every Future Backtest

Every experiment must produce:

```text
Experiment ID
Strategy ID
Config hash
Code hash
Data source/hash
Discovery window
Confirmation window
Stress arm
Closed trades
Win/Loss
Win rate
Net P/L
Return %
PF USD
Mean R
Max DD
Max losing streak
Cost R
Risk rejects
Quota rejects
Spread rejects
Halt events
Force-flat events
Trade ledger
Equity ledger
Rejection ledger
Verdict
```

---

# 27. Naming Convention

Examples:

```text
CTRL_B1_M15_v1
CTRL_B1_M5_v1
CTRL_B2_v1
CTRL_I014_v1

NX1_A_v1
NX1_B_STOCH_v1
NX1_C_SWEEP_v1
NX1_D_SWEEP_STOCH_v1

NX2_VWAP_EMA_v1
NX3_STRUCT_BREAK_v1
NX4_SESSION_MOMENTUM_v1
NX5_REGIME_MR_v1
```

Do not reuse an ID after changing logic.

---

# 28. Data Sources

## Project historical OHLC

### M5

```text
35,954 bars
2026-03-26 02:30 UTC
→ 2026-09-25 20:40 UTC

SHA:
f1496e97c406794e4a1287dfdb7d0058407c8c61
```

### M15

```text
11,989 bars
2026-03-26 02:30 UTC
→ 2026-09-25 20:30 UTC

SHA:
1a30da07131271a3198452014b87452700d0b8e0
```

## Project captured tick data

```text
31,780,274 observed Bid/Ask ticks
2026-05-07 → 2026-09-25
139,625 observed M1 bars
```

All currently inspected history is contaminated for pristine future OOS.

---

# 29. External Research Registry

## World Gold Council — 2026 session / volatility

### Gold Mid-Year Outlook 2026

Key observations:

- realised volatility spiked above 50% during 2026 shock period then eased
- bulk of H1 movement linked to Asian and US trading hours
- many pullbacks during US hours
- rebounds often during Asian hours
- session definitions given in UTC

Source:  
https://www.gold.org/goldhub/research/gold-mid-year-outlook-2026

### Has gold's performance structurally changed?

Key observations:

- 2026 volatility elevated
- spreads increased since 2024
- largest spread spikes often around thinner/off-market periods
- spread widening appeared episodic rather than permanently structural

Source:  
https://www.gold.org/goldhub/gold-focus/2026/04/you-asked-we-answered-has-golds-performance-structurally-changed

---

## SSRN — Structural Break

**Structural-Break Entry and the Disposition Effect in a Commercial XAUUSD Strategy: A Tick-Level Decomposition**

External claims:

```text
XAUUSD 2024–2026
1,571 trades
structural-break entry identified as primary source of risk-adjusted alpha
Sharpe reported 2.6–3.1
```

Source:  
https://papers.ssrn.com/sol3/Delivery.cfm/6941458.pdf?abstractid=6941458&mirid=1

---

## SSRN — VWAP / EMA gold framework

**A Regime-Filtered Intraday Trading Framework for Gold: Integrating VWAP Microstructure and EMA-Based Dynamic Exit Mechanisms**

External simulated result:

```text
XAU/USD M15
Jan–Dec 2024
247 trades
WR 45.3%
Exp +0.414R
PF 1.76
Max DD 5.1%
```

Source:  
https://papers.ssrn.com/sol3/Delivery.cfm/6650958.pdf?abstractid=6650958&mirid=1&type=2

---

## SSRN — Opening Range Breakout caution

**Opening-Range Breakout Does Not Survive Trading Costs**

External study:

```text
225 cells
9 liquid US futures markets
16 years
zero configurations passed pre-registered positive bar after realistic costs
```

Source:  
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398

---

# 30. Current Strategic Direction

The project should now stop expanding the strategy universe indefinitely.

Official universe:

```text
Controls:
B1 M15
B1-M5
B2
I014

New:
NX1 Hybrid
NX2 VWAP + EMA
NX3 Structural Break
NX4 Session Momentum
NX5 Mean Reversion
```

Primary research priority:

```text
1. NX3
2. NX2
3. NX1
4. NX4
5. NX5
```

This is a research priority only, not a claim that these will be profitable.

---

# 31. Next Execution Plan

## Step 1 — Preserve

```text
Do not modify:
B1/B1-M5/B2/I014 artifacts/configs
```

## Step 2 — Implement NX engines

```text
NX1
NX2
NX3
NX4
NX5
```

## Step 3 — Reproduce controls

Ensure current engine/data can reproduce historical references

## Step 4 — Parallel discovery

Run same data, same risk, same fees where comparable

## Step 5 — Freeze survivors

Only candidates passing discovery are frozen

## Step 6 — Confirmation

No parameter changes

## Step 7 — Real-tick stress

Use observed Bid/Ask for shortlisted strategies where mechanics permit

## Step 8 — Future unseen

Wait for genuinely new data or collect new broker tick tape

## Step 9 — EA parity / operational proof

Only then consider Demo

---

# 32. Final Principle

The goal is **not**:

> Find a backtest that looks profitable.

The goal is:

> Find a simple enough strategy whose edge survives controlled discovery, frozen confirmation, realistic costs, broker constraints, tick replay, future unseen data, and operational execution.

Current project truth:

```text
No Final Production Strategy Yet
```

Current candidate universe is now sufficiently broad.

The next phase is **measurement and elimination**, not endless strategy invention.
