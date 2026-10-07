# BotTradeGold B1 validation freeze v1

**Superseded:** latest user-provided `B1_FINAL_v1_implementation_validation_handoff.md` freezes TP 3.5R, equity-HWM risk tiers and a 12% stop-new-entries latch. This document remains historical evidence, not the active contract. See `config/B1-FINAL-v1.yaml`.

User-defined contract: risk 0.5% equity; SL 2.5 ATR; baseline TP 2.5R; compare only 2/2.5/3R, preserving reconstructed B1 entry logic and all-session policy. D is unchanged. Configuration: `config/bottradegold_b1_validation_v1.yaml`. This file is research-only, not a live runtime configuration.

Soft DD 5%, hard DD 8%, emergency/reject 10%, daily loss 2%. DD is measured from equity high-water mark, not initial deposit. These supersede the previous 5% qualification threshold as the user's proposed operating policy; they do not retroactively qualify historical results. Threshold-triggered actions, daily reference/reset rules, and a stricter backtest acceptance DD remain unspecified. Existing tick replay measures DD but does not enforce these circuit breakers. No runtime change or order submission.

## Verified matching historical runs

Reused exact matching rows from completed `data/b1_d_comprehensive_2026-09-26/matrix.csv`; no new replay or broker connection claimed. Extracted 36 rows into `data/bottradegold_b1_freeze_2026-09-26/matching_historical_rows.csv`, with source/config SHA-256 provenance in `manifest.json`. Four windows, three RR values and three cost reserves. Capture: 31,780,274 Exness Bid/Ask ticks, May 7–September 25; warmup May 7–13; continuous scoring May 14–September 25, 2026.

| RR | Continuous signals rejected below minimum lot | Executed trades | Net USD | PF / expectancy |
|---|---:|---:|---:|---|
| 2.0 | 553 | 0 | 0 | Undefined |
| 2.5 | 553 | 0 | 0 | Undefined |
| 3.0 | 553 | 0 | 0 | Undefined |

Each row above holds for additional reserves 0/0.1/0.2R. Development rejects 194, validation 258, confirmation 101 per configuration. Initial Demo snapshot equity/balance $1,173.46 gives $5.8673 nominal risk budget per trade. The SL risk at minimum 0.01 lot exceeds that budget at every signal. RR changes TP, not affordability of the fixed SL. Never round up volume or raise risk silently.

Zero trades and zero DD do not demonstrate safety, profitability, or functioning circuit breakers. No RR winner can be selected. Historical data has already been exposed; July–September diagnostic splits are not pristine OOS after this freeze. Subsequent validation needs untouched data and an affordable broker/account contract, plus independently verified circuit breakers before deployment. Keep 2.5R as the user-selected baseline, not an empirically proven winner.
