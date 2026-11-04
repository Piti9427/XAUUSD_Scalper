# C22 exhaustive tuning — verified final verdict

**Complete:5,184/5,184 profiles; independent audit PASS.** The agreed maximum
terminal-profit choice remains `26b8bcd69e043653`. Exhaustive search found no
higher-ranked qualified profile and no strict downside repair preserving the
latest matched profit floors. This verifies selection within the frozen grid;
it does not establish future profitability or authorize a Demo replacement.

Final interactive comparison:
[C22 exhaustive Matrix](/Users/nopparuj/.cursor/projects/Users-nopparuj-my-agents-XAUUSD-Scalper/canvases/C22-exhaustive-loop-2026-10-25.canvas.tsx).
All5,184 profiles, failed cases, raw/cent coverage and old Demo/original9e/
row20/latest references remain. Matrix stage is `AUDITED_EXHAUSTIVE_RESULT`.

## Coverage and independent verification

Frozen protocol: [spec](../../specs/c22-exhaustive-loop-2026-10-25.md).
Source data:171,171,013 actual Exness XAUUSDm Bid/Ask quotes and49,729 complete
UTC Bid M15 bars; actual quote interval2024-09-01T22:05:06.129Z through
2026-10-23T20:57:59.517Z. Bars require all15 observed M1 minutes; no gap filling.
Each path starts200USD once, fixed0.01lot, cost-inclusive10% initial-risk cap,
daily10%/two negative completed exits, single position, no recovery/top-ups/
lot growth. Signal recipe remains fixed during this grid.

- Grid:BUYTP4 × SELLTP6 × cooldown4 × BUYSL3 × SELLSL3 × globalBE3 ×
  BUYprotection2 =5,184;162 deterministic32-profile batches.
- Raw base/stress/fee for every profile:15,552 paths. All58 raw qualifiers got
  three cent sensitivities:174 paths.54 profiles pass all conditions;4fail cent
  review. Missing scenarios were never filled using another scenario's outcome.
- Total15,726 economic paths:15,156new +570 verified identical-context reused
  parent paths. Six fresh selected-path repeats are additional evidence.
- Independent verification PASS:7,764,913 accounting entries, required coverage,
  cash/swap/calendar/admission/cooldown/daily circuits, non-overlap, summaries,
  162 historical batch transitions, tie retention, global-grid selection and
  selected full-tick DD reconstruction on all6paths.101source pins match.
- Accounting cache14,600hits is bound to source/protocol/input/payload/proof
  hashes, which were reverified. Not every accounting calculation was repeated
  afresh. Auditor performs0economic replays; runner's6fresh repeats are separate.

Accounting entries sum across thousands of modeled paths, not millions of
independent market trades. Selected base has460trades, stress/rawfee458;
centfee457. Full-tick DD matches34.274997/37.730125/38.671021% for
base/stress/fee under both raw and cent guards.

Canonical evidence in ignored `runs/c22-exhaustive-loop-2026-10-25/`:
`COMPLETE.json`, `independent-verification.json`, `results.json`,
`final-audit-execution.log`, `final-comparison.json`, `matrix.json` and
`MATRIX-COMPLETE.json`. Results SHA256:
`bd502ce5531fea3dacb273a186916abd2468e59e2dd1e8343823dc6e7ea93cc8`.
Audit SHA256:
`151ddb8dd4107f3e7dd0bbcd934db0c6902abd00bf2b5d9e0a925d3021bfea5f`.

## Matched old-versus-selected comparison

All cells use the same archive,200USD and modeled swap. Base uses recorded
Bid/Ask; stress adds0.20USD/oz spread and0.10adverse market slippage; fee adds
hypothetical7USD/lot round-trip to stress. Historical rates/calendar/execution
remain hypotheses. Costs can change admission/equity/trade selection; a higher
fee-path profit is not a benefit of fees. Net=ending balance−200; fixed lots.

Raw results, rounded for display:

| Contract | View | Net USD | Equity DD % | Loss streak | Worst financial losing-run % | Completed recovery days | Ongoing age days |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Demo replay | base | 207.17 | 39.281 | 5 | 25.152 | 348.234 | 25.308 |
| Demo replay | stress | 194.02 | 37.823 | 6 | 21.680 | 349.319 | 115.831 |
| Demo replay | fee | 202.93 | 38.467 | 6 | 22.048 | 349.319 | 72.488 |
| Original9e | base | 1497.58 | 34.800 | 9 | 19.415 | 100.399 | 63.192 |
| Original9e | stress | 1063.10 | 35.707 | 9 | 19.995 | 101.102 | 63.192 |
| Original9e | fee | 1115.22 | 36.519 | 9 | 20.089 | 101.102 | 63.192 |
| Old row20 | base | 1652.21 | 31.658 | 11 | 16.827 | 100.400 | 73.917 |
| Old row20 | stress | 1242.26 | 35.727 | 11 | 20.545 | 133.295 | 73.915 |
| Old row20 | fee | 1231.66 | 36.708 | 11 | 21.067 | 130.299 | 73.915 |
| Selected26b8 | base | 1945.33 | 34.275 | 11 | 17.691 | 125.202 | 60.778 |
| Selected26b8 | stress | 1471.87 | 37.730 | 11 | 23.758 | 130.299 | 60.778 |
| Selected26b8 | fee | 1464.59 | 38.671 | 11 | 23.969 | 130.299 | 60.778 |

Demo is historical replay of its contract, not actual broker PnL. Original
config9e511d195c52ef3d has RulesID646690b541405adf; row20config
aab846c7292da8b6 has RulesIDc22654fea98da73e. Latest before search and final
selected26b8 are the same profile, with identical six outcomes.

Cent net/base-stress-fee,USD: Demo:207.1692/194.0212/202.9292;
original:1497.5772/1091.2444/1115.2210;
row20:1652.2064/1242.2616/1199.9536;
selected:1945.3340/1471.8700/1416.9940. Selected cent DD/streak/severity/recovery
match its raw values; all matched reference cent risk metrics remain in Matrix.

Selected ending balances:2145.3340 base,1671.8700 stress,1664.5920 rawfee,
1616.9940 centfee. Worst DD38.671021% is below40% by1.328979percentage points.
Minimum equity187.6636 base,146.9740 stress,146.4810 fee. These are model
observations, not forward capital or drawdown guarantees.

Versus row20, selected rawbase profit rises17.74% and stress18.48%; base DD
rises2.617percentage points and stress2.003points. Base completed recovery
lengthens24.802days; stress completed recovery shortens2.997days. Ongoing age
falls about73.92→60.78days. Versus original9e, streak increases9→11 and
stress/fee financial losing-run severity worsens. Higher terminal profit does
not mean every downside improved.

Severity means worst financial losing-run loss divided by its starting equity,
not severity of the longest-count streak. Negative net BE/swap exits remain
losses. Completed actual closing-balance drawdown recovery excludes idle or
monotone peak-to-peak intervals. Ongoing age is observed/censored, not forecast.
Neither recovery metric is continuous full-tick underwater time.

## Lower-risk alternatives and their trade-offs

These alternatives pass original matched profit/DD gates, but not the latest
profit-preserving repair condition. Risk columns take the worst across6paths;
profit columns remain explicitly raw. Recovery shows completed and ongoing
separately; different worst metrics can occur in different paths.

| Choice | RulesID | Raw base / stress net USD | Worst DD % | Streak | Worst financial-run % | Completed / ongoing days |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Maximum agreed profit | 26b8bcd69e043653 | 1945.33 / 1471.87 | 38.671 | 11 | 23.969 | 130.299 / 60.778 |
| Minimum worst DD | 32940ec6ebadbb6c | 1541.10 / 1319.68 | 27.889 | 21 | 20.928 | 132.784 / 78.835 |
| Minimum worst recovery | e61dd067300de253 | 1505.06 / 1282.11 | 35.391 | 20 | 18.819 | 97.001 / 78.835 |
| Minimum worst severity | 7dec196ddfe25dcf | 1532.78 / 1357.12 | 31.994 | 11 | 17.272 | 115.897 / 50.347 |
| Minimum loss streak | 8ec643ae5bec86a8 | 1562.83 / 1126.09 | 38.277 | 7 | 29.358 | 133.054 / 63.166 |

32940 lowers DD but gives up404.23USD rawbase profit and increases worst loss
count11→21. Earlier BE can create more small net losses. 7dec has every matched
risk no worse than latest, but rawbase/stress profit falls21.21%/7.80%; its
base profit cost is412.55USD. 8ec lowers streak to7 while financial severity
worsens to29.358%; loss count alone is not risk efficiency.

Strict repair0 means no candidate retains latest matched raw/cent base/stress
profit floors while every matched DD/recovery/severity/streak is no worse and
at least one risk improves. Lower-DD alternatives do exist. Owner has not
selected a new profit-versus-risk trade-off; primary choice stays26b8. Runner-up
f8b1ce950e41cf0d rawbase1943.7560 is only1.5780USD behind, but has lower stress
profit1350.1932; its worst6DD36.2963% is a separate risk trade-off.

Cent rejects:1bdb5235a9b2e259 feeDD40.216926%;56f2812d652b9898 stressDD41.679512%;
fd314a248a87a921 feeDD40.132347%;f7d79079ed32525e stressnet1083.5354 below matched
1091.2444floor. Omitting cent review would falsely qualify these four.

## Selected contract and adoption limits

Fixed entry:RSI7cross30 BUY/EMA50, SELL48-bar breakout/EMA50, closed H4EMA200.
BUY SL2.5ATR/TP3R/BE1R; SELL SL2.5ATR/TP1.35R/BE1R. Cooldown2 elapsed M15
periods after negative net exit; daily10%/two losses, fixed0.01, single position
and cost-inclusive10% initial-risk cap. No baskets, lot growth, intrabar BE
substitution, forced end-of-sample closes or capital top-ups.

Swap model:point-mode long−567.4/short0,point0.001,contract100, UTC-midnight
postings with its frozen business-day/triple calendar. Historical broker rates,
holidays/seasonal rollover, margin/HMR/stop-out, actual gaps/fills, cash posting
and provider completeness remain unqualified. These are not newly attested
costs; every economic scenario includes modeled swap.

All history is research-exposed, `holdout=false`, `COST_INCONCLUSIVE`. Enumerating
all frozen combinations does not remove selection bias or establish a new
out-of-sample edge. No PBO or future ruin probability was calculated. The10%
initial cap does not cap realized gap losses. Prospective fixed-version
assessment and operational/broker evidence remain required.

Native selected Rules are research descriptors, not a drop-in Demo config. The
offline preparation tools can preserve the final evidence; compatible runtime
adapter, independent end-to-end parity, fresh cost/feed evidence and shadow
review precede an execution-time Demo decision. Demo section6.33 is unchanged.
No broker connection, order, position change, service activation, attestation,
cutover or real-money activity occurred.

Campaign sources remain local and hash-pinned, including untracked research
files. Clean Git-only reproduction is not claimed; retain the pinned source
files and ignored run artifacts together.

Completed campaign needs no further recurring continuation. Heartbeat
`c22-exhaustive-tuning-continuation` was deleted after verified closure on
2026-10-25; all completed artifacts are retained.
