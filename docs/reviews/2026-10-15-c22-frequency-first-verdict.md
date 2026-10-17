# C22 frequency-first verdict — 2026-10-15

**Frequency winner: RSI threshold25→30**, research config9bb30c154de68d07.
From tuned comparatorb823f4aefe10fc72, single change raises mean monthly entries
16.79/16.71→20.96/20.83 (base/stress), profitable completed entries5.75/5.83→
6.79/6.96. Stress frequency +24.69%, profitable-entry frequency +19.29%.
Both preregistered ranking profiles select same case, including profile requiring
net not below tuned. No profit-floor tradeoff preference needed for selection.

**Tradeoff: less consistent monthly cash and higher DD.** Stress median monthly
cash21.95→4.70 USD; profitable full months16/24→12/24; stress DD36.96%→38.33%.
More net-positive trades and slightly higher total net do not mean more monthly
cash or more profitable months. DD remains below40% registered gate, close to it.

Balanced alternative: SELL lookback96→48, configd398087c22657b7b. Stress entries
18.46/month (+10.47%), winners6.42/month,net924.21USD,DD38.92%,median monthlycash
27.63USD,profitable17/24months. It improves monthly cash consistency with a
smaller frequency gain; remains lower-frequency alternative, not primary winner.

## Selected-case evidence

USD200,fixed0.01,one position,cost-inclusiveinitialcap10%,daily10%,no recovery.
All values monthly mean except median/net/DD;24 full monthsOct2024–Sep2026.

| Case | View | Final USD | Net USD | Entries/month | Winners/month | Max DD | Median monthly cash USD | Positive months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C22 tuned | Base+swap | 941.10 | 741.10 | 16.79 | 5.75 | 29.64% | 16.37 | 17/24 |
| RSI30 | Base+swap | 958.69 | 758.69 | 20.96 | 6.79 | 32.94% | 11.02 | 12/24 |
| C22 tuned | Cash stress+swap | 803.57 | 603.57 | 16.71 | 5.83 | 36.96% | 21.95 | 16/24 |
| RSI30 | Cash stress+swap | 817.24 | 617.24 | 20.83 | 6.96 | 38.33% | 4.70 | 12/24 |
| SELL48 | Cash stress+swap | 1124.21 | 924.21 | 18.46 | 6.42 | 38.92% | 27.63 | 17/24 |

RSI30 total504/501 trades versus404/402 tuned; total swap−66.9532USD versus
−55.6052USD. Net rises17.59USD base,13.67USD stress. Mean monthly figures include
warmup/zero full months, not a guarantee of20entries or7winningtrades every month.
All inherit tunedRSI7,BUYEMA50,H4EMA200,BUYSL1.5ATR/TP2R,SELLSL2.5ATR/TP2R,
BE1R both sides,unlimited daily loss count (max_daily_losses0),daily10%.
Primary changes only RSI threshold; active frozen DemoRSI14cross25 remains intact.

## Complete finite catalog summary

Cells retained including all failures. Pairs showBase/stress in this order; netUSD,
DDpercent.42 cells21 cases. Screened qualification requires both-view positive
net,DD<=40%,survival/fixedlot/cap/no terminalrisklockout,more entries AND more
profitable entries than tuned,medianmonthlycash>=0,positive-month ratio>=50%.
Profit-floor profile additionally requires net>=tuned. Rank higher minimum across
views entries,then winners,mediancash,net,lowerworstDD,stableconfigID.
Only selected top3 and comparator were repeated-qualified; all others remain
failed screening, no post-result gate relaxation.

| Case | Entries/month pair | Winners/month pair | Net USD pair | DD % pair | Screening |
| --- | ---: | ---: | ---: | ---: | --- |
| c22_tuned | 16.79/16.71 | 5.75/5.83 | 741.10/603.57 | 29.64/36.96 | Comparator |
| rsi_threshold_30 | 20.96/20.83 | 6.79/6.96 | 758.69/617.24 | 32.94/38.33 | PASS + repeated |
| rsi_threshold_35 | 23.08/18.54 | 6.83/5.67 | 150.68/-99.74 | 58.29/81.91 | FAIL: dd,median,net_positive,positive_months,winning_frequency |
| sell_lookback_48 | 18.54/18.46 | 6.33/6.42 | 1077.38/924.21 | 32.38/38.92 | PASS + repeated |
| sell_lookback_24 | 20.71/20.58 | 6.88/6.96 | 878.60/717.04 | 44.60/50.13 | FAIL: dd |
| sell_ema_0 | 16.88/16.75 | 5.75/5.83 | 688.08/585.02 | 30.37/35.35 | FAIL: winning_frequency |
| macro_span_100 | 18.29/17.21 | 6.00/5.83 | 320.19/206.82 | 44.66/61.90 | FAIL: dd,winning_frequency |
| macro_span_0 | 6.67/9.58 | 1.67/2.92 | -172.51/-147.42 | 86.42/81.49 | FAIL: dd,frequency,net_positive,positive_months,terminal,winning_frequency |
| buy_ema_0 | 28.71/28.21 | 8.62/8.88 | -117.21/-111.97 | 86.46/81.31 | FAIL: dd,median,net_positive,positive_months,terminal |
| buy_target_rr_1.5 | 16.33/15.38 | 6.50/6.38 | 223.89/112.48 | 51.63/60.09 | FAIL: dd,frequency |
| buy_target_rr_1.35 | 15.75/15.33 | 6.67/6.75 | 147.98/126.11 | 59.77/60.91 | FAIL: dd,frequency |
| sell_target_r1.35 | 17.54/17.46 | 6.75/6.88 | 843.09/712.22 | 31.56/35.08 | PASS + repeated |
| buy_stop_atr_1.0 | 16.79/13.58 | 5.71/4.75 | 240.44/-32.41 | 49.09/80.20 | FAIL: dd,frequency,median,net_positive,positive_months,winning_frequency |
| stop_atr_2.0 | 17.88/17.75 | 5.83/5.92 | 495.81/366.49 | 37.10/44.24 | FAIL: dd |
| stop_atr_1.5 | 18.79/18.71 | 6.29/6.38 | 461.28/251.80 | 41.21/49.67 | FAIL: dd |
| combined_1 | 22.75/22.62 | 7.38/7.54 | 1057.04/901.09 | 35.18/41.56 | FAIL: dd |
| combined_2 | 26.62/19.17 | 7.92/5.83 | 430.14/-99.84 | 57.02/79.56 | FAIL: dd,net_positive,positive_months,winning_frequency |
| combined_3 | 18.75/17.46 | 5.62/5.62 | -106.56/-104.16 | 83.77/82.73 | FAIL: dd,median,net_positive,positive_months,terminal,winning_frequency |
| combined_4 | 20.83/13.62 | 6.04/4.08 | -125.61/-138.36 | 86.79/85.19 | FAIL: dd,frequency,median,net_positive,positive_months,terminal,winning_frequency |
| combined_5 | 23.79/17.62 | 10.04/7.33 | 520.77/-102.97 | 48.35/79.16 | FAIL: dd,median,net_positive,positive_months |
| combined_6 | 23.58/13.83 | 9.54/5.71 | 1.86/-128.03 | 70.42/84.91 | FAIL: dd,frequency,median,net_positive,positive_months,winning_frequency |

Looser filters yielded more raw activity with large drawdowns: BUYEMAoff stress
28.21entries/8.88winners,butnet−111.97USD/DD81.31%. Threshold30+SELLlookback48
has22.63entries/7.54winners/net901.09USD but stressDD41.56%,so fails40% gate.
Risk cap remained10%; cap per entry does not cap cumulative drawdown.

## Costs, scope and reproducibility

Owner requested “เน้นเพิ่มให้มีไม้ในเดือนมากขึ้น”. [Preregistered protocol](../specs/2026-10-15-c22-frequency-first.md)
was frozen before new results; no detector/framework/native rewrite. Reuse exact
preceding proven canonical helper, public `execute_cell`/`prepare`,same immutable
167622055 paired Exness ticks and48465 completed M15 bars. Requested2024-09-01UTC
through2026-10-06T17:22:04.296998UTC,actualfirst2024-09-01T22:05:06.129UTC,last
2026-10-05T23:59:59.969UTC. PartialSep2024/Oct2026 excluded/labelled; full requested
months must also be bracketed by actual quotes. Endpoint coverage not internal
quote coverage; no new holdout/forward/current-market qualification.

Both views include modeled swap pointslong−567.4/short0,point0.001,Wednesday
triple,assumedUTC-midnight. Base commission0;cashstress40USD/lot/roundtrip
(USD0.40at0.01). ActualBid/Ask unchanged,zero extra spread/slippage. Missing
supported swap metadata blocks; no no-swap cell or silentzero substitution.
Cost statusCOST_INCONCLUSIVE: archive assumptions,not fresh broker history.
Canonical commission upfront,fee-inclusive BE on completedM15,strict open-position
midnight baseline; no native MT5 Tester or Demo process-baseline parity.

Campaign01 exit0:42 actual economic cells,8 fresh complete-object repeats
(comparator,RSI30,SELL48,SELLTP1.35 ×two views) identical. Comparator entirefresh
result equals preceding paired comparison apart from name. Independent persisted
42-cell audits recomputed cash/lot/risk/nonoverlap/swap/monthly cash/winners;
all completionartifact hashes verified,8persistedrepeatobjects equal cells.
Catalog21 unique/supported and10 one-view negative policy controls PASS;
lower-profit control passes onlyfrequencyprofile,notprofitfloor. Focused command
`PYTHONPATH=.:tests .venv/bin/python -m unittest test_c22_frequency.AdapterTests
 tests.test_native_frequency_replay`:9tests,OK,exit0. No production source edits;
previous full962-test result not rerun or presented as new validation.

Research configs:
- [Frequency RSI30](../../config/research-c22-frequency-9bb30c154de68d07.json).
- [Balanced SELL48](../../config/research-c22-balanced-d398087c22657b7b.json).

Machine artifacts ignored `runs/c22-frequency-first-2026-10-15/campaign-01/`:
`protocol.json`,`cells/`,`repeats/`,`screening.json`,`results.json`,
`source_snapshot/`,`COMPLETE.json`. Adjacent `audit-final.json`,
`policy-controls.json`,`research-handoff.json`,`focused-tests.log`,`campaign-01.log`.
No raw run dumps in docs. Sources/input/runtime/config hashes retained.

**Completion:** frequency research and config exports ready; active Demo unchanged.
Existing nativeEA has fixed tuned parameters; new RSI30/SELL48 configs are Python
research contracts,not runnable `.set` or validated native ports. Native port,
untouched forward/holdout evidence,fresh costs and separate Demo readiness/owner
cutover decision remain before adoption. No frozen source pins,baseline,lot/risk
cap,sender/account/attestation changed; real money not authorized.
