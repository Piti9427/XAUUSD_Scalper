# Development candidate decisions

**Active contract update 2026-09-26: B1-FINAL-v1.** User supplied a new frozen handoff: TP 3.5R, equity-HWM DD risk tiers 1/0.75/0.5/0.25%, STOP_NEW_ENTRIES at 12%, daily hard stop disabled. This supersedes older parameter choices without erasing prior failures. Deterministic reference implemented; 553 signals all rejected by minimum-lot risk at Demo equity $1,173.46. Full execution EA, broker Tester/parity/OOS/forward gates remain pending. **NO-GO.** See [current implementation status](B1_FINAL_V1_VALIDATION_STATUS_2026-09-26.md).

**Latest 2026-09-26 comprehensive decision: NO QUALIFIED EXECUTION CANDIDATE.** 320 policies, 3,840 staged real-tick replays plus 12 stress replays; highest-base-profit B1 fails cost/DD robustness, development-only leader fails later months. See [complete selection](B1_D_COMPREHENSIVE_RESULTS_2026-09-26.md). No runtime promotion.

Decision date: 2026-09-24. User requested one strategy for serious validation toward actual use.

**Superseded 2026-09-26:** User selected B1 — Donchian30 + RSI and D — ATR1.5 + RSI + FVG, explicitly permitting versioned repository reconstruction. Active research shortlist now B1/D; historical Donchian20_H4 decision below retained for traceability. See [new contract and Demo-data results](B1_D_DEMO_BACKTEST_2026-09-26.md). Real ticks now captured; [account replay](B1_D_EXNESS_REAL_TICKS_2026-09-26.md) admitted zero trades: B1 minimum-lot risk exceeds account cap, D had no September signals. Qualification remains incomplete.

**Historical selection (superseded): `Donchian20_H4`, mode `common` (all-regime entries).** The remainder records the prior contract and evidence; active shortlist is now B1/D above.

Status: **SELECTED_FOR_VALIDATION**. Selection is complete. Demo automation qualification and real-money readiness remain unproven; this document is not deployment authorization or an executable runtime configuration.

Follow-up 2026-09-25: two separate reconstructed Relick variants (EMA20/50 + Stochastic; RSI + Martingale grid) were backtested on exposed 2025–partial 2026 data and both lost under their declared rules. See [comparison and assumptions](RELICK_TWO_VARIANTS_BACKTEST_2026-09-25.md). Neither displaces this validation challenger; this does not turn the challenger into a Demo-ready bot.

## Exact research policy to preserve

- XAUUSD; complete UTC-aligned H4 Bid bars. Signal only at bar close.
- Long when close exceeds the highest high of the previous 20 bars; short when close falls below the lowest low of the previous 20 bars. Exclude the signal bar from the channel.
- Market entry at the exact next M1 open in historical simulation: buy Ask, sell Bid. Skip missing entry minutes.
- ATR14 uses the existing Wilder implementation. SL distance = 2 × signal-bar H4 ATR14; target = 2 × original stop distance from entry.
- All regimes eligible (`common`); one position at a time; both directions. No averaging, grid, martingale, scale-out, trailing stop, or added signal filter.
- Historical simulation uses executable-side exits, adverse stop-gap fills and conservative stop-first ambiguity handling. Annual indicator resets/sample-end liquidation are properties of the historical experiment, not instructions to reset a live bot annually. A continuous prospective runner must define and freeze its warmup, position continuity, and tick execution behavior before qualifying data begins.

Source rules: `scripts/research/strategies.py` and `scripts/research/engine.py`. A change in any rule creates a new contract and requires new validation; do not silently apply `native` sideway exclusion to this candidate.

## Selection evidence and weakness

Highest historical net among the tested configurations passing the exploratory minimum of 200 trades and at least half scored years positive. This establishes the best observed cumulative net under that selector, not the best unknown future return or risk-adjusted performance.

- Shared 2011–2025 window: +1,066.74 USD/1 oz; 1,305 closed trades; 459 wins / 846 losses; win rate 35.17%; PF 1.090; 8/15 positive years.
- Full 2010–2025 check: +833.23 USD/1 oz; 1,385 trades; win rate 34.66%; PF 1.067.
- 2011–2023 net is -251.90; 2024–2025 contributes +1,318.64. Short-side net is -809.03 across 2011–2025. These weaknesses must be falsified on new data, not removed by retuning the historical sample.
- Historical spread included; extra Exness costs unmeasured. Fixed 1 oz results are not returns on a funded account.

Evidence: [selection report](BACKTEST_SELECTION_2026-09-24.md). Selection manifest SHA-256: `1d90848793b61975c41f37d9898d9d693a28e06cb9e40803bfef27290d751209`.

## Serious validation target

Use the evidence and risk requirements in [QUALIFICATION_PROTOCOL.md](QUALIFICATION_PROTOCOL.md): target Exness Demo account/symbol specs; post-freeze real Bid/Ask ticks; measured fills/costs; risk at most 0.5% of the lower balance/equity per admitted setup with valid lot flooring and rejection; continuous account equity and twice-cost replay. The existing shadow monitor only records signals for the prior cohort; it does not yet implement this common-mode policy's execution validation.

Required pass evidence includes at least 100 broker-valid simulated closed trades, PF >=1.50 after measured base costs, positive expectancy, account max DD <=5%, positive corrected weekly-block lower confidence bound, nonnegative required direction/session slices, and positive expectancy/PF >1 under twice measured costs. Preserve the protocol's conservative statistical gate pending an explicit preregistered replacement; selecting one candidate now does not erase the historical multiple-selection problem.

Missing evidence means INCONCLUSIVE. A completed valid test failing its gates means REWORK/rejection of this contract; do not lower gates or call an in-sample retune a pass. Passing this validation permits the next Demo decision; subsequent real-money deployment remains a separate user decision.

Before a qualifying run, bind the actual account/symbol, freeze the completed runner/config/code hashes and prospective statistical plan, and record its start timestamp. This selection document alone does not start that clock.
