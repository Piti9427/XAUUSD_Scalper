# XAUUSD S1–S4 Mechanical Specification v1

**Parent:** [Issue #2](https://github.com/Piti9427/XAUUSD_Scalper/issues/2) · **Ticket:** [Issue #3](https://github.com/Piti9427/XAUUSD_Scalper/issues/3)  
**Companion narrative:** [`xauusd-setup-experiment-v1.md`](xauusd-setup-experiment-v1.md)  
**Status:** Documentation artifact only — not implementation, not profitability evidence  
**Instrument tick (proposed):** `0.01` USD/oz · **Rule version:** `s1-s4-mechanical-v1`

This document completes the mechanical specification required by issue #3: decision classification, IF/THEN/INVALID tables, worked synthetic BUY/SELL examples per candidate, boundary examples, and a parent-scenario coverage map. Examples are synthetic arithmetic fixtures for implementers and manual traders; they are **not** backtest results.

---

## 1. Decision classification

### 1.1 Individually confirmed choices

| ID | Choice | Source |
| --- | --- | --- |
| C1 | Manual Signal Indicator first; Setup Signals ≠ Orders/Positions | User |
| C2 | Candidates S1–S4 as named below | User |
| C3 | H1 bias + M5 setup shared across candidates | User |
| C4 | Protected-swing CHOCH (not latest-fractal-only) | User |
| C5 | Midpoint limit entry after zone confirmation | User |
| C6 | Full High–Low OB bounds | User |
| C7 | Controlled Baseline: full-position 2R, no partial, no automatic BE | User |
| C8 | Legacy Reference retained separately (50% @ 1R, BE, 2.5R runner) | User |
| C9 | Main test seam: historical replay → setup/lifecycle ledger → summary via existing backtester/orchestrator | User 2026-09-16 |

### 1.2 Proposed v1 numerical defaults (research definitions — not individually user-optimized)

| ID | Default | Value |
| --- | --- | --- |
| P1 | Fractal | Strict 5-bar (2 left, 2 right); equals fail |
| P2 | H1 bias | Closed H1 Close vs EMA200 |
| P3 | Asian pool | 00:00–07:00 UTC exclusive end |
| P4 | London pool | 07:00–12:00 UTC exclusive end |
| P5 | Sweep penetration | `(0, 8.00]` dollars |
| P6 | Sweep→break window | Bars 1–8 after Sweep inclusive |
| P7 | Displacement | Nonzero range; body/range ≥ 0.45; BUY green / SELL red |
| P8 | FVG min width | $0.30 directional |
| P9 | FVG middle window | Break candle + next 4 bars |
| P10 | SL buffer | $0.30 beyond True Swing Extremum |
| P11 | SL distance cap | `(0, 25.00]` |
| P12 | Pending TTL | 20 minutes after zone confirmation |
| P13 | Entry sessions | 07:00–10:30 and 12:30–16:30 UTC exclusive ends |
| P14 | Time exit | 20:45 UTC |
| P15 | Risk target | 0.5%; floor volume; reject if min lot exceeds budget |
| P16 | Tick size | 0.01 |

### 1.3 Unresolved material gates (block affected downstream work — do not silent-approve)

| ID | Gate | Blocks |
| --- | --- | --- |
| U1 | Verified broker XAUUSD M5/H1 (+ execution quotes) provenance | Qualifying comparative results |
| U2 | Feed/quote sides, tick rounding, gap/stale policy | Fill realism claims |
| U3 | Pre-confirmation zone-touch / marketability policy | Pending admission edge cases |
| U4 | Sweep replacement/consumption across bars | Multi-sweep sequencing |
| U5 | Capacity + daily-risk research profile freeze | Shared vs independent capacity numbers |
| U6 | Historical news point-in-time policy | News-conditioned summaries |
| U7 | Exact date range + 60/20/20 (or other) split registration | OOS claims |
| U8 | Sample sufficiency + statistical comparison protocol | PASS/FAIL on expectancy |
| U9 | Intrabar SL/TP ordering when both touch without ticks | Must stay `AMBIGUOUS` until settled |

---

## 2. Candidate definitions (shared vs changed controls)

| Candidate | Structural trigger | Entry zone | Shared controls |
| --- | --- | --- | --- |
| **S1** | Sweep → MSS (latest opposite confirmed fractal) | First qualifying FVG midpoint | H1, pools, sessions, displacement, SL, 2R, TTL, risk |
| **S2** | Sweep → protected-swing CHOCH | First qualifying FVG midpoint | same |
| **S3** | Sweep → protected-swing CHOCH | OB midpoint (Sweep..CHOCH) | same |
| **S4** | Sweep → protected-swing CHOCH | OB∩FVG midpoint (≥ 1 tick overlap) | same |

**Legacy Reference** is intentionally multi-variable vs Controlled Baseline (partial/BE/2.5R). Never report Legacy vs S1 as a one-variable structure comparison.

---

## 3. IF / THEN / INVALID decision tables

Timestamps are timezone-aware UTC. Decisions use **closed** bars only. Preserve `event_time` and `available_at` separately.

### 3.1 Availability & fractals

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Bar closes with 2 strict left + 2 strict right confirming a pivot | Pivot `event_time` = pivot bar open; `available_at` = second-right close | Using pivot before `available_at` |
| High equals neighbor required for strict fractal | No high pivot | Promoting equals to pivots |
| Same bar qualifies as both high and low fractal | Exclude from structural sequencing | Assuming intrabar order |
| Dual candidates for protected opposite pivot | Use **latest** eligible opposite pivot between broken swing and break candle | Searching outside that interval |

### 3.2 H1 bias

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Latest **closed** H1 Close > EMA200 | BUY bias permitted | Using forming H1 |
| Latest closed H1 Close < EMA200 | SELL bias permitted | |
| Equal Close==EMA200 or insufficient warm-up | Neither direction | Fabricating bias |
| Future H1 mutate after cutoff | Prior decisions unchanged | Retroactive bias flip |

### 3.3 Pools & Sweep

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Session interval incomplete | Pool unavailable | Empty fabricated pool |
| Prior trading day incomplete | Previous-day pool unavailable | Using partial PDH/PDL as complete |
| BUY: `Low < pool` and `Close >= pool` and `0 < pool-Low <= 8` | Qualifying BUY Sweep | Close through pool = expansion breakout |
| SELL: `High > pool` and `Close <= pool` and `0 < High-pool <= 8` | Qualifying SELL Sweep | Penetration > 8 = expansion breakout |
| Multiple pools qualify same bar | Priority: Asian → previous-day → London | Iteration-order dependent choice |
| Penetration == 0 (touch only) | Not a Sweep | |

### 3.4 MSS (S1 only)

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Bars 1–8 after Sweep; close beyond latest **available** opposite fractal; color+displacement OK | MSS trigger | Bar 0 or bar ≥ 9 |
| Pivot confirms **after** candidate break | May not participate | Using future-confirmed fractal |
| body/range < 0.45 or range==0 | No MSS | Relabeling later candle as the MSS |

### 3.5 Structure state (S2–S4) — BOS / CHOCH / internal / UNKNOWN

State machine starts `UNKNOWN`.

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Close-break of confirmed swing **and** eligible opposite pivot exists between broken swing and break | Establish/update direction; that opposite pivot becomes **protected swing** (BOS when continuing) | Break without opposite pivot → stay/return `UNKNOWN` |
| Close-break of **protected** swing with qualification window+displacement | **CHOCH** (setup-eligible if bars 1–8 + color + body/range) | Minor internal break ≠ CHOCH |
| First structural break fails displacement | Structure may change; **no** eligible setup; later bars cannot retro-qualify that first break | Relabeling later close as first CHOCH |
| Broken level already consumed for same event | No repeated identical structural event | Re-firing CHOCH on same level |

### 3.6 FVG / OB / overlap

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Bullish: third Low − first High ≥ 0.30; middle in break..break+4 | First qualifying bullish FVG; wait third close | Selecting later FVG after first fails |
| Bearish: first Low − third High ≥ 0.30; middle in window | First qualifying bearish FVG | |
| BUY OB: latest non-doji **red** in `[Sweep, CHOCH)` | Freeze High–Low at CHOCH | Searching before Sweep or including CHOCH bar |
| SELL OB: latest non-doji **green** in `[Sweep, CHOCH)` | Freeze High–Low at CHOCH | |
| No eligible OB candle | S3/S4 = no setup | Expanding search window |
| S4 overlap width ≥ 1 tick | Entry = overlap midpoint | Zero / sub-tick overlap = no S4 |
| Later FVG overlaps OB but first did not | Still no S4 from later FVG | Favorable substitution |

### 3.7 Entry / SL / TP / pending / session

| IF | THEN | INVALID / else |
| --- | --- | --- |
| Zone confirmed (third FVG close or CHOCH for OB/overlap) | Limit eligible **after** confirmation bar | Same-bar retroactive fill |
| True Swing Extremum frozen over Sweep..break inclusive | SL = beyond extremum by 0.30 | Moving SL anchors later |
| Entry−SL in `(0, 25]` | Admit geometry | Shrink SL or round volume **up** to force trade |
| Controlled Baseline | TP = Entry ± 2 × initial Entry−SL; full size | Partial / BE / trail |
| 20 min TTL, session end, H1 bias invalidate, or SL before fill | Pending ends; setup identity retained | Reviving expired identity as new setup |
| New entry outside admission windows | Reject admission | |
| 20:45 UTC with missing quote | Disclose missing; do not invent exit price | Synthetic favorable exit |
| Min lot risk > 0.5% budget | Reject | Risk-increasing rounding |

### 3.8 Ledger / ambiguity

| IF | THEN | INVALID / else |
| --- | --- | --- |
| SL and TP both touch bar without tick order evidence | Flag `AMBIGUOUS`; keep both touches visible | Inventing favorable path |
| Costs applied | Charge once; keep initial R denominator fixed | Double-counting spread+fee |
| Proxy GC=F / wrong TF | Label diagnostic only | Qualifying as broker XAUUSD M5 |

---

## 4. Shared synthetic market prefix

Unless a boundary example overrides, examples reuse this M5-friendly arithmetic world:

- Tick = `0.01`
- Asian low pool `L_asia = 2650.00` (available)
- Asian high pool `H_asia = 2660.00` (available)
- H1 bias: BUY when `Close_H1=2665 > EMA200=2655`; SELL when `Close_H1=2640 < EMA200=2655`
- Admission time of confirmation/fill examples falls inside `07:00–10:30` UTC unless testing session rejection

Notation: bar `T+k` means k M5 bars after Sweep bar `T0`.

---

## 5. Complete worked examples — one BUY and one SELL per candidate

Each example lists: inputs → available_at → chosen references/zone → Entry/SL/TP → first eligible fill → lifecycle ledger → arithmetic summary.

### 5.1 S1 BUY — Sweep → MSS → FVG

**Inputs (M5):**

| Bar | Time UTC | O | H | L | C | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| T0 | 07:00 | 2650.40 | 2650.80 | 2649.50 | 2650.20 | Sweep Asian low: pen=0.50 |
| T1 | 07:05 | 2650.20 | 2652.00 | 2650.00 | 2651.50 | |
| T2 | 07:10 | 2651.50 | 2656.20 | 2651.40 | 2655.80 | MSS close > fractal 2654.00; body/range=4.30/4.80=0.895 |
| T3 | 07:15 | 2655.80 | 2657.00 | 2655.00 | 2656.50 | FVG middle (=break) |
| T4 | 07:20 | 2656.50 | 2656.80 | 2655.40 | 2655.60 | FVG third: Low 2655.40 > T2 High? use candles T2,T3,T4 → first=H T2=2656.20, third=L T4=2655.40 → **no bullish gap** |
| Alt FVG | — | — | — | — | — | Use triple F1/F2/F3 below |

**FVG triple (middle = MSS bar T2):**

| Leg | H | L |
| --- | --- | --- |
| F1 (T1) | 2652.00 | 2650.00 |
| F2 (T2 MSS) | 2656.20 | 2651.40 |
| F3 (T3) | 2657.00 | 2655.50 |

Bullish width = `2655.50 − 2652.00 = 3.50 ≥ 0.30`. Zone `[2652.00, 2655.50]`. Midpoint Entry = `2653.75`.  
Zone confirmation `available_at` = T3 close `07:15`.

**True Swing Extremum (Sweep..MSS):** Low min = `2649.50`.  
SL = `2649.50 − 0.30 = 2649.20`.  
R = `2653.75 − 2649.20 = 4.55`.  
TP = `2653.75 + 2×4.55 = 2662.85`.

**First eligible fill:** first bar **after** 07:15 whose Low ≤ 2653.75 → T4 07:20 Low 2655.40 misses; T5 07:25 Low 2653.50 fills at 2653.75.

**Lifecycle ledger:**

| t | event |
| --- | --- |
| 07:00 | SETUP_ID=S1B1 Sweep Asian |
| 07:10 | MSS @ 2655.80 vs fractal 2654.00 |
| 07:15 | FVG confirm; PENDING limit 2653.75 |
| 07:25 | FILL 2653.75 |
| later | EXIT TP 2662.85 or SL 2649.20 |

**Summary (zero costs diagnostic):** risk $4.55/oz; +2R if TP; −1R if SL. Initial R denominator fixed at 4.55.

### 5.2 S1 SELL — Sweep → MSS → FVG

| Bar | Time | O | H | L | C | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| T0 | 12:35 | 2659.60 | 2660.50 | 2659.20 | 2659.80 | Sweep Asian high; pen=0.50 |
| T2 | 12:45 | 2658.00 | 2658.20 | 2653.00 | 2653.40 | MSS close < fractal 2655.00; red; body/range OK |
| F1/F2/F3 | | F1 L=2658.50; F3 H=2655.00 | | | | Bearish width=`2658.50−2655.00=3.50` |

Zone `[2655.00, 2658.50]`; Entry mid=`2656.75`; confirm at F3 close.  
Extremum High=`2660.50`; SL=`2660.80`; R=`4.05`; TP=`2656.75−8.10=2648.65`.  
Fill: first post-confirm High ≥ 2656.75.

### 5.3 S2 BUY — Sweep → CHOCH → FVG

Same Sweep T0 as §5.1. Structure: prior protected bearish swing high `2654.20` broken with opposite pivot present → CHOCH bullish at T2 (qualified).  
Internal break of `2653.00` earlier was **not** CHOCH.  
FVG zone/Entry/SL/TP same arithmetic as §5.1; trigger reason=`CHOCH` (not `MSS`).  
Ledger: Sweep → CHOCH → FVG confirm → PENDING → FILL → EXIT.

### 5.4 S2 SELL — Sweep → CHOCH → FVG

Same Sweep T0 as §5.2. Protected bullish swing low `2655.10` close-broken at T2 with eligible opposite pivot → CHOCH sell (qualified).  
Bearish FVG `[2655.00, 2658.50]`; Entry=`2656.75`; confirm at F3 close.  
Extremum High=`2660.50`; SL=`2660.80`; R=`4.05`; TP=`2648.65`.  
First fill: first post-confirm High ≥ `2656.75`.

### 5.5 S3 BUY — Sweep → CHOCH → OB

CHOCH at T2 as §5.3. OB search `[T0, T2)`: latest red non-doji = T0 (O 2650.40, C 2650.20, H 2650.80, L 2649.50).  
OB zone `[2649.50, 2650.80]`; Entry mid=`2650.15`.  
Extremum Low=`2649.50`; SL=`2649.20`; R=`0.95`; TP=`2650.15+1.90=2652.05`.  
Confirm at CHOCH close; pending after confirm; fill when Low ≤ 2650.15.

### 5.6 S3 SELL — Sweep → CHOCH → OB

CHOCH at T2 as §5.4. OB search `[T0, T2)`: latest green non-doji = T0 (O 2659.60, C 2659.80, H 2660.50, L 2659.20).  
OB zone `[2659.20, 2660.50]`; Entry mid=`2659.85`.  
Extremum High=`2660.50`; SL=`2660.80`; R=`0.95`; TP=`2659.85−1.90=2657.95`.  
Fill when High ≥ `2659.85` after CHOCH confirm.

### 5.7 S4 BUY — Sweep → CHOCH → OB∩FVG

OB from §5.5: `[2649.50, 2650.80]`.  
First FVG from §5.1: `[2652.00, 2655.50]`.  
Overlap width = 0 → **no S4 setup** on that pair.

**Adjusted first qualifying FVG with overlap:** F1 H=`2649.80`, F3 L=`2651.00` → FVG `[2649.80, 2651.00]`.  
Overlap with OB = `[2649.80, 2650.80]`; width=`1.00` ≥ 1 tick.  
Entry mid=`2650.30`.  
SL=`2649.20`; R=`1.10`; TP=`2652.50`.

### 5.8 S4 SELL — Sweep → CHOCH → OB∩FVG

OB from §5.6: `[2659.20, 2660.50]`.  
First bearish FVG `[2655.00, 2658.50]` → overlap width 0 → no S4.  
**Adjusted first FVG:** `[2659.00, 2660.20]` ∩ OB = `[2659.20, 2660.20]`; width=`1.00`.  
Entry mid=`2659.70`.  
SL=`2660.80`; R=`1.10`; TP=`2657.50`.  
Later FVG that overlaps must **not** replace a failing first FVG.

---

## 6. Boundary / negative examples (parent scenarios 2–21)

IDs map to parent required acceptance examples in issue #2 / narrative §Testing.

| ID | Scenario | Expected |
| --- | --- | --- |
| B2 | BOS vs CHOCH vs internal; UNKNOWN init/recovery | Internal break → no CHOCH; missing opposite pivot → UNKNOWN; recovery only with eligible opposite pivot |
| B3 | Unconfirmed / equal / dual pivots | Unconfirmed unavailable; equals fail; dual high+low bar excluded; latest opposite wins |
| B4 | H1 equality / warm-up / unfinished H1 | No bias; unfinished must not change prior setup |
| B5 | Prefix + future append | Decisions at cutoff invariant under append/mutation after cutoff |
| B6 | Sweep boundaries | Close==pool → invalid; pen=0 invalid; pen=8 OK; pen=8.01 expansion; multi-pool → Asian>PD>London |
| B7 | Break window & displacement | Bars 1 & 8 OK; 0 & 9 fail; body/range=0.45 OK; `<0.45` fail; range=0 fail |
| B8 | Weak first CHOCH | Structure updates; no setup; later bar cannot qualify that first break |
| B9 | FVG edges | Width=0.30 OK; 0.29 fail; middle at break and break+4 OK; break+5 fail; third close delayed → pending only after close |
| B10 | OB bounds | Includes Sweep; excludes CHOCH bar; doji skipped; absent → no S3/S4 |
| B11 | S4 overlap | 0 fail; 0.009 fail if tick=0.01; 0.01 OK; mid ≠ either source mid when asymmetric |
| B12 | Later FVG overlaps only | S4 still fail if first FVG had no overlap |
| B13 | SL geometry | Both sides; distance≤0 reject; =25.00 OK; 25.01 reject; no SL shrink |
| B14 | Pre-confirm touch | No fill; pending starts only after confirm |
| B15 | TTL / session / bias / SL-before-fill / missing quote | Each ends pending or discloses missing exit |
| B16 | Duplicate / restart | Same SETUP_ID; no revive after expiry |
| B17 | Fill+immediate exit; ambiguous OHLC | Ledger keeps fills; dual touch → `AMBIGUOUS` |
| B18 | Fixed R denominator; single cost charge | Summary uses planned R; costs once |
| B19 | Min-lot > budget | Reject; floor only when ≤ budget; never resize open position up |
| B20 | Missing coverage / proxy / bad time / no quotes | Distinct reason codes ≠ ordinary no-setup |
| B21 | Independent candidate sims; Legacy label | S1–S4 do not consume each other’s slots; Legacy separately labeled |

### 6.1 Compact numeric sketches (selected)

**B6 penetration 8.00 BUY:** Low=`2642.00`, pool=`2650.00`, Close=`2650.10` → pen=`8.00` → Sweep OK.  
**B6 penetration 8.01:** Low=`2641.99` → expansion breakout, not Sweep.  
**B11 one-tick overlap:** OB`[100.00,100.05]` ∩ FVG`[100.04,100.10]` = `[100.04,100.05]` width=`0.01` → Entry=`100.045`.  
**B13 SL cap:** Entry=`2700`, Extremum Low=`2674.70`, SL=`2674.40`, R=`25.60` → reject (R>25).

---

## 7. Test seam contract (downstream — not claimed executed here)

**Main seam (C9):** historical replay → setup/lifecycle ledger → summary through existing `StrategyOrchestrator` / backtester path.

| Assert externally | Do not assert |
| --- | --- |
| Setup signal fields, reject reasons, `available_at` | Private method call order |
| Lifecycle event sequence | Source-string presence of identifiers |
| Cash/risk conservation; initial R fixed | Mocks that replace detector under test |
| `AMBIGUOUS` when ordering unknown | Invented favorable OHLC path |
| Independent candidate runs | Shared accidental slot coupling |

Focused detector unit tests only for fractal/CHOCH/FVG/OB boundary precision where replay would be too coarse.

---

## 8. Parent scenario coverage matrix

| Parent example # | Covered in | Artifact |
| --- | --- | --- |
| 1 Valid BUY/SELL each candidate | §5.1–5.8 | Worked ledgers |
| 2–5 Structure/H1/prefix | §6 B2–B5 | Tables + sketches |
| 6–8 Sweep/window/weak CHOCH | §6 B6–B8 | Tables + sketches |
| 9–12 FVG/OB/overlap/substitution | §3.6, §6 B9–B12 | Tables + §5.7 |
| 13–16 SL/pending/TTL/identity | §3.7, §6 B13–B16 | Tables |
| 17–21 Ambiguity/costs/risk/data/Legacy | §3.8, §6 B17–B21 | Tables |
| Unresolved empirical gates | §1.3 U1–U9 | Explicit blockers |

No parent scenario is silently marked implemented in code by this document.

---

## 9. Completion statement (issue #3)

| Acceptance criterion | Evidence |
| --- | --- |
| Record confirmed choices + Legacy retained | §1.1 C1–C9, §2 |
| Separate confirmed / proposed / unresolved | §1.1–1.3 |
| IF/THEN/INVALID for structure & sweep family | §3.1–3.5 |
| FVG/OB/overlap + inclusivity | §3.6, §5, §6 B9–B12 |
| SL/2R/TTL/session/identity/time exit | §3.7–3.8, §5 |
| BUY+SELL examples per candidate | §5.1–5.8 |
| Negative/boundary examples | §6 |
| Prefix/expiry/min-lot/ambiguous/restart | §6 B5,B14–B19 |
| Approved test seam | §7 |
| Parent mapping + shared vs changed controls | §2, §8 |
| No Pine/EA/Python/broker changes in this ticket | This file + contract test only |

**Not claimed:** unit-test green for detectors, Pine compile, broker verification, or profitability.
