# Why 26b8 loses in 2020, 2021, 2022, 2023 and 2024a: diagnosis (2026-11-12)

## Setup

- **Feedback loop:** `runs/c22-26b8-losing-years-diag-2026-11-12/diag.py` (about 23 s).
  - It runs native 26b8 on each yearly $313 account through the tick replay and prints RED when the year loses.
  - It also prints a per-side decomposition: TP/BE/SL rates, the TP rate needed to break even, expectancy in R, spread as a fraction of R, swap, and loser MFE.
  - All five years are RED in the base view.
- **Probes:**
  - `probe_ft.py`: follow-through of each signal against random entries in the same year.
  - `costs.json`: cost decomposition built from the per-trade ledger.
  - `trades_r.csv`: gross and net expectancy in R for every trade.

## Hypotheses tested (ranked before testing)

| # | Hypothesis | Prediction | Result |
| --- | --- | --- | --- |
| H1 | SELL breakdowns do not follow through in up-drift or range years | Rate of reaching +1R before −1R is at or below random | **Confirmed** for 2020, 2021 and 2024a |
| H2 | The BUY RSI pullback does not reach 3R in slow or range years | BUY follow-through is close to random and gross R is below 0 | **Confirmed** for 2021, 2022 and 2023 |
| H3 | BUY swap drag | Adding swap back shrinks the losses noticeably | Partly: −27 to −44 per year |
| H4 | Cost is large relative to R when ATR is low | Costs are a large fraction of R in losing years | **Confirmed**: 7–14% of R, against 1.6–4.5% in profit years |

## Evidence

### Expectancy per trade in R

Gross is before spread and swap.

| Year | Drift | Mean risk/trade | Gross R | Cost R | Net R | BUY gross R | SELL gross R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2020 | +24.7% | $8.5 | **+0.065** | 0.139 | −0.074 | +0.196 | −0.124 |
| 2021 | −4.3% | $6.1 | −0.121 | 0.082 | −0.203 | −0.109 | −0.125 |
| 2022 | −0.3% | $6.6 | **+0.029** | 0.072 | −0.042 | −0.144 | +0.115 |
| 2023 | +12.8% | $5.7 | −0.034 | 0.088 | −0.122 | −0.159 | +0.078 |
| 2024a | +21.2% | $7.8 | −0.092 | 0.073 | −0.165 | +0.069 | **−0.578** |
| 2024b25 | +72.3% | $13.0 | +0.262 | 0.045 | +0.217 | +0.366 | −0.076 |
| 2026 | −8.0% (high vol) | $26.5 | +0.216 | 0.016 | +0.200 | +0.081 | +0.288 |

### Follow-through: share of trades reaching +1R before −1R, signal vs random entry

| Year | BUY signal | BUY random | SELL signal | SELL random |
| --- | --- | --- | --- | --- |
| 2020 | 45.8 | 44.3 | **38.2** | 42.6 |
| 2021 | 48.3 | 47.5 | **41.0** | 45.1 |
| 2022 | 46.8 | 46.7 | 50.9 | 47.2 |
| 2023 | **41.0** | 49.0 | 48.9 | 45.1 |
| 2024a | **42.5** | 51.6 | **26.5** | 44.1 |
| 2024b25 | **60.7** | 55.2 | 45.6 | 46.9 |
| 2026 | 45.1 | 46.5 | **60.4** | 52.1 |

## Root cause

In the losing years **the 26b8 entry signal carries no information, and sometimes the reverse**. Costs that are fixed per lot then turn a near-zero gross result into a loss. There are three mechanisms.

1. **SELL breakdowns against the drift (2020, 2024a, and 2021).**
   - A close below the 48-bar low while under the H4 EMA200 is mostly a dip inside a rising market, and it gets bought back.
   - Follow-through is below random (26–41% vs 43–45%).
   - In 2024a alone SELL lost −$161 at −0.58R per trade.
2. **The BUY RSI pullback does not reach 3R in slow or range markets (2021, 2022, 2023).**
   - Follow-through is equal to random or worse. In 2023 it was 41% vs 49% random, even though gold rose 12.8% that year.
   - Gross BUY R ran from −0.11 to −0.16.
3. **Costs relative to R when ATR is low.**
   - Spread and swap are roughly fixed per 0.01 lot, while R is only $6–8, so each trade pays 7–14% of R.
   - BUY pays 9–20% of R because swap builds up over multi-hour holds.
   - This alone turns 2020 (gross +0.065R) and 2022 (gross +0.029R) into losses, and wipes out the positive gross BUY result in 2020 and 2024a.

**Why the profitable years win.** A real edge appears only in a strong directional move (2024b25: BUY 61% vs 55% random) or in high volatility (2026: SELL 60% vs 52%). In those years ATR is 2–4× higher, so each R is worth $13–27 and costs fall to 1.6–4.5% of R. Profit in dollars is therefore concentrated in those regimes.

## Implications

These connect to the earlier LOYO verdicts.

- Entry filters failed LOYO because the signal has no edge to select on in these years. Filtering cannot create follow-through.
- B2+maxloss_1 helps because it caps how often a near-random signal pays costs, and its BE locks in the few BUY runs. It acts on mechanism 3 and limits the losses from mechanisms 1 and 2. It does not create an edge.
- A cost-to-R floor (skip trades where costs are a large share of R) is **not** supported. The highest cost-R quartile has the *best* gross R, because long-held BUY TP trades build up swap. The variable is confounded.
- To make these years profitable, the strategy needs a signal that follows through better than random in up-drift and range markets. No signal tested so far does.

## Other finding

In the patched replay, `net_usd` and `net_before_swap_usd` are computed from the default `initial_balance` ($200), not the $313 start. Example for 2020: `net_usd` −69.65, while the ledger sum and `final_balance` both give −182.65. Every research number was built from ledger sums or `final_balance`, so the results are not affected. Do not use `net_usd` from `loopeng.xrun`.
