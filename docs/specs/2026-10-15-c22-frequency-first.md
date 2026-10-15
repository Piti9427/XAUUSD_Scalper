# C22 frequency-first research — 2026-10-15

Owner: “เน้นเพิ่มให้มีไม้ในเดือนมากขึ้น”. Goal increases completed entries per full
month versus C22 tunedb823f4aefe10fc72, while also increasing net-positive completed
entries. Existing Demo remains unchanged. Owner preference question allows lower
net if both frequency and profitable entries increase within DD40%, or requires
net not below C22 tuned. Both profiles preregistered and reported; no live change.

Smallest change: reuse preceding proven public canonical execute/replay helper,
existing C22 parameter domains, immutable paired tape. No new detector, framework,
Python chart download, timeframe change, native EA or frozen source edits.

Freeze21 cases before new economic results: C22 tuned comparator;14 single changes
RSI threshold30/35,SELL lookback48/24,SELL EMA0,macro100/0,BUY EMA0,BUYTP1.5/1.35,
SELLTPr1.35,BUYSL1.0ATR,SELLSL2.0/1.5ATR. Six deterministic combinations:
1. threshold30+lookback48
2. threshold35+lookback24
3. threshold30+lookback48+macro100
4. threshold35+lookback24+macro100
5. threshold30+lookback48+BUYTP1.5+SELLTPr1.35
6. case5+BUYSL1.0ATR+SELLSL1.5ATR

All inheritRSI7,EMA50 where unchanged,H4EMA200 where unchanged,BE1R both sides,
max_daily_losses0,daily10%,fixed0.01,USD200,cost-inclusive10%initialriskcap,
one position,no recovery. Potential reserve for future swap/gaps not implied.

Exactly42 economic cells,21cases×Base+swap/COST_SURCHARGE_STRESS+swap.
Same immutable167622055 paired Exness ticks,48465 complete M15 bars,
requested2024-09-01UTC→2026-10-06T17:22:04.296998UTC;actual first
2024-09-01T22:05:06.129UTC,last2026-10-05T23:59:59.969UTC. Input unchanged from
preceding paired comparison. Base commission0,stress40USD/lot/roundtrip
(USD0.40at0.01),actualBid/Ask unchanged,zeroextra spread/slippage. Mandatory modeled
swap pointslong−567.4/short0,point0.001,Wednesday triple,assumedUTC-midnight.
Validate metadata/hash first; missing blocks. COST_INCONCLUSIVE: archived rates,
not broker-history verified. No no-swap scenario or zero substitution.

Monthly24 full requested+observed-bracketed months,Oct2024–Sep2026;partialmonths
excluded/labelled,warmup/zero full months included. Fees book entrymonth,
gross+swapexitmonth,net-positivecompleted positions counted entrymonth.
Internal quote coverage not proven by endpointbracketing. Fixed canonical
commissionupfront/fee-inclusiveBEcompletedM15/strict open midnightbaseline;
not native Tester/per-tick BE or Demo processbaseline parity.

Screening gates BOTH views: netpositive,DD<=40%,no bankruptcy,fixed0.01 and
admittedcap<=10%,no terminalrisk-onlylockout,mean entries>same-view C22 tuned,
mean profitableentries>same-view C22 tuned,median monthlycash>=0 and
positive-month ratio>=50%. Frequency profile accepts lower positive overallnet;
profit-floor profile additionally requires both-viewnet>=C22 tuned.
No arbitrary relaxation after results. Failure gives NO_FREQUENCY_QUALIFIER.

Rank by higher minimum across views monthlyentries,then higherminimum winners,
higherminimum medianmonthlycash,higherminimum net,lowermaximumDD,stableconfigID.
Screen all42; prior-comparison baseline must equal entire fresh result (except
case name). Only provisional screening, not qualification until repeats pass.
Repeat comparator plus top3 of each profile (deduplicate); all repeated complete
objects must match before final selection. Other candidates remain screened,
not repeated-qualified. Preserve everycell including failed/risky results.

Retain source/input/protocol/runtime hashes and exact source snapshots; verify
completedartifact hashes,persisted repeat equality,cash/risk/lot/nonoverlap/swap
andmonthly recomputation before reporting. Fresh output only. Artifacts ignored
`runs/c22-frequency-first-2026-10-15/`; synthesized report in `docs/reviews/`.
Reused discovery,not unopened holdout/future qualification.No nativeUI retries,
Demo restart/config/cost-attestation/baseline or real-money change.
