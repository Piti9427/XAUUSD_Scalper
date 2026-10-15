# Relick two-variant backtest — 2025 to partial 2026

## Verdict

**Reject both reconstructed contracts as the final Demo bot strategy.** Both lose in the declared base replay. The grid also fails the requested 1:2 reward:risk condition: +2 USD basket target against a 55 USD basket hard stop is nominal reward:risk **0.036:1**. High basket win rate does not repair negative expectancy. This does not rule out every possible EMA/Stochastic or RSI rule: the supplied summary omits exact triggers, grid spacing, and basket target, so these are new, explicitly frozen research assumptions.

| Variant / base case | Closed positions or baskets | Simulated order actions | Wins | Win rate | Net P&L | Profit factor | 2025 | Partial 2026 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EMA20/50 + Stochastic M15, fixed 1 oz | 194 positions | 388 | 62 | 31.96% | **−215.70 USD/oz** | 0.895 | 115 / −168.11 | 79 / −47.59 |
| RSI14 + Martingale grid, starting cash 100 USD | 31 baskets | 102 | 29 | 93.55% | **−52.00 USD** | 0.527 | 31 / −52.00 | 0 / 0.00, cash gate |

The order-action count is simulated entries plus exits, not broker-confirmed orders or fills. For the grid, a basket with four entries is counted as eight actions. The EMA result is **fixed 1 oz price exposure**, not a 100 USD account return. The grid cash ledger assumes the public Exness Standard gold specification of 100 oz/lot and 0.01 lot minimum, but the particular account's symbol specification, margin, leverage, and fills were not confirmed through MT5. [Exness metals specification](https://get.exness.help/hc/en-us/articles/17854173039388-Commodities); [Exness Standard account conditions](https://get.exness.help/hc/en-us/articles/17537782738460-Standard-account).

## Frozen rules before replay

- **EMA/Stochastic:** Complete UTC M15 Bid bars. EMA20 above EMA50 plus touch/reclaim of EMA20 for long; reverse for short. Stochastic 14/3/3 K crosses D at K≤30 long or K≥70 short. Enter next exact M1 open at Ask/Bid. SL=2×ATR14; TP=2R. One position at a time. This is a strict, specific reconstruction, not the video's unpublished code.
- **RSI/grid:** RSI14 crosses into ≤30 long or ≥70 short on complete M15 Bid bars. Initial 0.01 lot (assumed 1 oz); add at 0.02, 0.04, 0.08 lots after each adverse 4 USD price move at a subsequent M1 open. Exit whole basket at +2 USD or −55 USD cash. Hard stop wins same-minute OHLC ambiguity. If realized balance falls below 55 USD, do not open another basket. On the initial 100 USD, one hard stop is 55% of capital; gaps/slippage can lose more. No broker margin or stop-out simulation. The attachment specified the lot sequence and 55 USD hard stop, but **did not specify** the 4 USD grid or 2 USD basket target.
- Both variants use observed historical Bid/Ask M1 OHLC spread. Extra base slippage, swap, and order delay are zero **because unmeasured**, not because verified absent. Exness Standard states no trading commission; account-specific trading conditions still need confirmation. [Exness Standard account conditions](https://get.exness.help/hc/en-us/articles/17537782738460-Standard-account). A separate sensitivity replay adds 0.10 USD adverse price slippage per entry/exit fill.

## Cost sensitivity and failure mode

| Variant | Base net | +0.10 USD/fill slippage net | Base max marked-equity DD |
| --- | ---: | ---: | ---: |
| EMA/Stochastic, fixed 1 oz | −215.70 USD/oz | −273.78 USD/oz | Annual maxima: 312.59 USD/oz (2025), 471.35 USD/oz (2026) |
| RSI/grid, 100 USD cash ledger | −52.00 USD | −61.10 USD | 70.00 USD within 2025 |

Grid base recorded 29 winning baskets of +2 USD and two hard-stop baskets of −55 USD: **58 − 110 = −52 USD**. The 100 USD cash ledger ended at 48 USD on 2025-01-19; its no-new-basket gate therefore admitted no 2026 trades. The 0.10 USD slippage scenario ended at 38.90 USD. Win rate needed to break even at +2/−55 before extra costs is 55/57 = **96.49%**; observed 93.55% is below it. This cash replay can still overstate executability because margin and account stop-out were unavailable. Exness documents that stop-out conditions can vary by account and circumstances; do not substitute a generic rule for a verified terminal snapshot. [Exness stop-out conditions](https://get.exness.help/hc/en-us/articles/360014693340-Margin-call-and-stop-out-levels-by-account-type).

## Data and audit boundary

Pinned Dukascopy-derived M1 Bid/Ask CSV revision `922f83a60cc574e7395fb27397077288055a1ef6`; 2025-01-01 through 2026-08-20 23:58 UTC. 2026 is partial. These years were already exposed in prior strategy research. M1 OHLC cannot establish intra-minute ordering, real ticks, Exness fills, broker rejection, or account margin. The grid stop-first rule deliberately treats unresolved same-minute collisions adversely. Source data contains 171,213 flat Bid minutes in 2025 and 90,311 in partial 2026; they were retained and logged, not silently synthesized or removed. Historical spread is already paid in Bid/Ask execution and is not added twice.

Reproduce from repo root:

```sh
.venv/bin/python -m scripts.research.relick_variants \
  --cache data/research_cache \
  --output data/research_results/relick-two-2025-2026-20260925
```

The output directory is immutable after creation and Git ignored. Preserve `manifest.json`, `data-audit.json`, `annual.csv`, all eight trade CSVs, and `COMPLETE` together. The runner hashes source and output files, checks trade count/net/chronology for every CSV before writing `COMPLETE`, and never calls MT5 order APIs. Focused unit tests: `tests.test_research_relick_variants` (four passed). This research rejects the two *tested contracts*; it does not promote a different strategy or authorize Demo/real-money execution.
