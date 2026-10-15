# BotTradeGold research v1 — frozen reconstruction contract

Offline research only. This package cannot submit orders. It does not change the existing SMC M5 live system. Source: user-provided `BotTradeGold_chat_handoff_2026-09-23.md`, 2026-09-23. Historical result tables are unverified reference claims, not imported performance.

## Scope and reproducibility

17 base configurations, five single-filter ablations of each, ten named additional configurations two Trend Structure lookback neighbors, and six H4 cross-checks (120 total). Run both common and native modes. No exhaustive filter powerset, SL/TP grid, per-year tuning, or new strategy family. Unspecified historical combinations cannot be reproduced without their configuration manifests.

Base inventory: Donchian20/30/40; State15/20/25; ATR1.25/1.5; EMA10x30/20x50; ORB30/60; AsianBreak; AsianRetest; SweepReversal; SweepMSS; GSS_OTE.

Named extras: A_TrendStructure, B_Donchian30_RSI, C_State25_RSI_FVG, D_ATR1.5_RSI_FVG, Asian_RSI_H1EMA, SweepCHOCH, SweepMSS_FVG, SweepMSS_FVG_CE50, Structure_OB, TurtleSweep20. TurtleSweep20 is an explicit alias of SweepReversal in this reconstruction, not independent evidence. Donchian30__rsi and B have identical entry logic but different native risk. H4 counterparts: Donchian20, State25, ATR1.5, EMA20x50, GSS_OTE, SweepMSS_FVG_CE50.

Historical definitions are incomplete. Most implementations are **reconstructions**, not recovered original source. A and B follow the explicit handoff rules subject to shared indicator/execution conventions. Do not label any result an exact reproduction of the prior chat. A research rejection rejects this implemented contract, not every possible implementation of a named trading concept.

Run (repository root, existing virtualenv):

```sh
.venv/bin/python -m scripts.research.run \
  --cache /absolute/path/dukascopy \
  --output /absolute/path/unique-run-directory \
  --years 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 \
  --download
```

Repeat using an existing verified cache without `--download`. `--names` selects exact registry identifiers. `--commission`, `--slippage`, `--swap`, `--delay-minutes` create explicit sensitivity scenarios. Default units=1 oz-equivalent price exposure; this is not a claim about broker lot size. All outputs use USD price P/L per configured units and original stop-distance R. Commission, swap and slippage defaults are zero/unmeasured; historical spread is naturally paid through Bid/Ask, never added twice. The slippage scenario shifts market entry and stop/end exit adversely by the configured price distance; TP is modeled as a limit fill at target and resting limit entry is not worsened. These are research assumptions, not Exness observations.

## Data contract

Public Market-Data-Lab source pinned to commit `922f83a60cc574e7395fb27397077288055a1ef6`. Monthly CSV timestamp=UTC epoch milliseconds. Download hashes are verified on cache reuse; run manifest records input hashes, source revision, configuration, library versions and implementation hashes. No fabricated or forward-filled prices. Match Bid/Ask timestamps by intersection, log unmatched counts, fail if unmatched fraction exceeds 0.1%. Reject invalid OHLC, duplicate/unordered timestamps, nonfinite/nonpositive prices and crossed simultaneous open/close quotes. Bid/Ask highs/lows need not occur simultaneously.

Only complete M15/H1/H4 bars are used (15/60/240 matched minutes). Existing flat source minutes are retained and counted, not asserted to be actual ticks or trading hours. Reject entry on missing exact next-open minute. Data audits expose gaps, flat-minute counts and coverage, including partial 2026 (through August 20 in the source). This is M1 OHLC execution, **not real tick**.

Each calendar year is a separate run: indicators warm up from that year's first valid bar; positions are liquidated at its last quote. Aggregated results concatenate these annual experiments, not a continuous multiyear account. No claim of an untouched OOS: all available historical data is research/development. A genuinely untouched future/independent sample remains required.

## Shared causal indicators

Signals use Bid OHLC. ATR14 = arithmetic seed of first 14 true ranges followed by Wilder recursion. RSI14 uses Wilder gain/loss with first delta=0; flat series RSI=50. EMA uses adjust=False with span-bar warmup. Signal bar must have positive range and positive ATR.

Donchian boundaries use only previous N bars, excluding current signal bar. A close above/below the boundary produces a signal. Repeated closes beyond each new boundary may produce another signal after the existing position exits.

Fractals are strict 2-left/2-right extrema, confirmed only at close of the second right-hand bar. Structure compares latest two confirmed highs and lows: both rising=+1; both falling=-1; otherwise neutral. H1 context is aligned on **H1 close availability**; never the unclosed H1 bar. H4 variants receive the last completed H1 context when relevant.

Filters (all evaluated on signal close): RSI long<=75 / short>=25; body/range>=0.60; current three-bar same-direction FVG>=0.05 ATR; H1 close above/below EMA200; H1 confirmed structure agrees with direction. FVG is current-bar gap, not arbitrary historical gap inventory.

## Reconstructed entry rules

- **StateN:** N-bar close breakout arms a setup. Within six subsequent signal bars, require one or two opposing candle bodies, then close beyond the original breakout candle high/low on a nonopposing candle. Third opposing candle, expiry, or penetration beyond the original seed's opposite extreme invalidates. A new seed may arm after invalidation. RSI/FVG apply at rebreak.
- **ATR expansion:** same continuation state machine, seed range>=multiplier*current ATR and body/range>=0.50; direction follows seed body.
- **EMA:** completed fast/slow crossover only, not continuous directional bias.
- **ORB30/60:** fixed UTC opening at 07:00, initial 30/60-minute range, first completed-bar breakout after range completion with signal close before 17:00. No automatic London DST claim.
- **AsianBreak:** complete UTC 00:00–07:00 range, first completed-bar breakout after 07:00 with signal close before 17:00. One raw signal/day before filters.
- **AsianRetest:** first breakout arms direction; subsequent candle touches breached range boundary and closes back outside in that direction with signal close before 17:00; one raw signal/day.
- **SweepReversal / TurtleSweep20:** wick beyond prior 20-bar low/high with both open and close strictly back inside boundary; next-open reversal. No dollar penetration thresholds inferred from separate live SMC code.
- **SweepMSS:** sweep arms the latest previously confirmed opposite pivot; within eight bars require close beyond that pivot and same-direction body. One signal, then reset.
- **SweepCHOCH:** same, but prior confirmed structure must oppose reversal direction at sweep time.
- **SweepMSS_FVG:** MSS followed by same-direction current FVG>=0.05 ATR, same bar permitted; absolute setup expiry 12 bars after sweep. Market variant enters next open. CE50 places a resting midpoint limit, valid four signal bars, using executable-side touch.
- **Structure_OB:** close crosses previously confirmed swing; find latest opposing body within prior ten bars; place midpoint-of-body limit valid four signal bars. This is one explicit order-block proxy, not a universal OB definition.
- **GSS_OTE:** with bar close inside UTC 07:00–10:30 or 12:30–16:30, a >=1.5 ATR, >=50% body displacement arms its high/low. Within eight bars, pullback overlaps its 61.8–78.6% retracement with directional candle body during those sessions. New extreme beyond seed invalidates. Entry next open. This is a displacement-candle OTE proxy.

## Comparison layers and regimes

Common: all signal variants use SL=2 ATR, TP=2R. Entry architecture/timeframe remains strategy-specific. All regimes are included as a **diagnostic of raw entry logic**, not as a proposed live policy.

Native: A 2 ATR/2R, B 2.5 ATR/2.5R, C 3 ATR/3R, D 2 ATR/3R; other configurations use explicitly reconstructed 2 ATR/2R defaults because original native risk contracts were not supplied. These other configurations are not claimed to have recovered optimal native architecture.

Native mode applies SIDEWAY=NO ENTRY. A provisional causal regime classification is frozen before results: expansion if current range>=1.5 ATR; otherwise trend if 20-bar efficiency ratio>=0.30; otherwise sideway. Efficiency ratio=absolute net 20-bar close change/sum absolute one-bar close changes. This classifier is a research assumption requiring separate validation, not a recovered handoff specification. Existing trades retain their exits during sideway periods. Matrix attribution uses entry regime.

## Execution

Maximum one open position OR pending limit per strategy/mode experiment. Strategies are tested individually; this is not a combined portfolio. Market entry at exact signal close/next-open timestamp: buy Ask, sell Bid. Long exits on Bid; short exits on Ask. Stop gaps fill at adverse opening quote. Target gaps fill at target (no favorable improvement). If both barriers touched inside one M1 and opening quote resolves neither, stop first.

Limit orders activate only after signal close. Fill via Ask low for buys / Bid high for sells. Unknown intraminute limit-fill ordering never claims same-minute TP; same-minute stop is counted conservatively. No re-entry before the prior exit minute ends. Pending orders reserve exposure until fill/expiry. Final sample liquidation is logged separately.

Drawdown: marked M1-close equity plus actual realized exits, initial zero-P/L equity included. Excludes unknowable intraminute tick-path extremes. `max_closed_dd` is realized-equity DD. `max_annual_equity_dd` is maximum among annual runs, not continuous multiyear marked DD. MAE/MFE explicitly exclude ambiguous exit-minute extremes. Swap scenario is calendar nights with a constant debit, not a broker-specific rollover model.

## Screening, not production selection

Frozen heuristic: >=5 annual samples, >=200 trades; reject if pooled net<=0 or fewer than half years positive; review candidate if >=65% years positive, largest positive-year contribution<=50% of positive-year profits, pooled PF>=1.10 and neither direction loses. Otherwise WATCH. Insufficient samples are never labeled rejected. These thresholds are research triage and are not statistical significance tests or a guarantee. Highly correlated/aliased variants are not independent discoveries.

Natural frequency is primary. Equal-N per year/mode uses evenly spaced trades across the sequence, secondary only. If any strategy has zero trades, N=0 for that comparison and metrics remain unavailable (no silent exclusion of the zero-trade strategy).

Outputs: manifest, data-audit, annual/summary/months/regimes/equal_n CSVs and complete trade logs. `COMPLETE` is written only after all requested runs finish. Existing output directories cannot be overwritten. Partial output without COMPLETE must not be used as a completed comparison.

Missing before live eligibility: verify reconstructed rules with owner/original code, cost calibration, independent feed, untouched OOS, walk-forward/parameter stability, multiple-testing correction (PBO/DSR where appropriate), portfolio correlation/exposure tests, Exness real ticks, demo forward validation. No strategy is marked production-ready by this tool.
