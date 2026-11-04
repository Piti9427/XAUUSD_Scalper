# C22 matrix-guided tuning — 2026-10-25

**Completed two bounded tuning rounds.** Highest-base-net fully qualified
research case is Rules ID`26b8bcd69e043653`: initial200USD→2145.334USD in base,
net1945.334USD, versus1652.2064USD for the previous matrix row20. Stress net
1242.2616→1471.8700USD. Maximum observed DD across all six reviewed paths is
38.6710%, below the owner's40% historical qualification ceiling. Profit improves;
the original streak/recovery weaknesses are not fully solved. No Demo change.

## Objective and method

Owner authorized iterative optimization of the existing matrix, maximizing
terminal profit while observed equity DD remains<=40%. Preserve original
research9e511d195c52ef3d's matched base/stress net floors, positive net and modeled
survival in all declared raw/cent base/stress/fee paths. Rank raw base net,
then raw stress net, then lower maximum raw DD; cent is a qualification
sensitivity, not a different ranking when the display is switched.

Keep fixed0.01,200USD continuous account, cap10%, daily10%/count2, one position,
no recovery/top-ups/lot increases. Use the existing canonical signals, entry and
tick replay. This smaller alternative changes native parameters without adding
a management engine, date-specific filters or production behavior.

The [frozen protocol](../../specs/c22-matrix-tuning-2026-10-25.md) declares native
BUY/SELL target, stop, cooldown, global BE activation and BUY protection domains.
Round1freezes18one-factor neighbors around row20. Round2freezes15unseen neighbors
around its observed winner, so combinations are adaptive discovery. Full Rules
identity deduplicates profiles within this campaign. All raw-qualified cases get
all three cent paths; this closes the old top2-only cent selection shortcut.

33candidate variations plus1incumbent,153economic cells (102raw/51cent),
6fresh final repeats. Some profiles already appeared in the prior matrix,
including old rows9,10and23; these are not33first-ever unseen strategies or
independent samples. Seven Round1and nine Round2changes pass all6views;
17fully reviewed qualifiers including incumbent. Failed cases remain saved.

## Actual selection and risk trade-offs

Changes from previous row20/aab846c7292da8b6:

- BUY TP2R→3R. BUY SL remains2.5ATR, thus planned TP distance is7.5ATR before
  tick-grid rounding. Fixed lot and initial risk cap remain unchanged.
- Cooldown4→2elapsedM15periods:60→30minutes after any negative net exit,
  including protected/swap losses and time spent during market closure.
- All entry RSI7cross30/EMA50, SELL48/EMA50, closed H4EMA200, SELL SL2.5ATR/
  TP1.35R/BE1R, BUY BE1R, daily-count2and other rules remain unchanged.

Raw outcomes, all swap-inclusive:

- Base: net1945.3340USD/final2145.3340,DD34.2750%,460trades,WR35.00%,PF1.4336,
  minimum observed equity187.6636USD. Net+293.1276USD/+17.74% versus row20;
  DD+2.6169percentage points.
- Price stress: net1471.8700USD/final1671.8700,DD37.7301%,458trades,
  minimum equity146.9740USD. Net+229.6084USD/+18.48%;DD+2.0034pp.
- Fee sensitivity: net1464.5920USD/final1664.5920,DD38.6710%,458trades,
  minimum equity146.4810USD. Net+232.9344USD/+18.91%;DD+1.9625pp.
- Cent base/stress match raw. Cent fee net1416.9940USD/final1616.9940,
  DD38.6710%,457trades. No selected forced END_OF_SAMPLE exits.

The gain is not an all-risk improvement. Stress minimum equity declines from
159.2720to146.9740USD;fee158.8490to146.4810USD. Maximum admitted initial risk
is9.9330% in base, within10%;swap/gaps can still make realized losses exceed
initial stop risk. Passing observed DD40does not impose a future broker loss cap.

Longest actual net-negative streak remains11in all6paths. Base run loss remains
103.0224USD but its smaller starting balance raises severity16.8273→17.6910%.
Stress run116.5104USD raises severity20.5454→20.9409%. Actual completed
closing recovery changes base100.4001→125.2020days,stress133.2954→130.2986days,
fee130.2986→130.2986days. Ongoing unrecovered closing episode shortens
73.92→60.78days at the final source quote. This is not continuous tick-equity
underwater time. Idle peak-to-peak intervals are excluded from the new actual
recovery measure; legacy intervals remain in each saved diagnostic.

No changed qualifying case simultaneously keeps streak and completed recovery
no worse than row20in all sixviews. This additional screen is diagnostic; the
owner has not adopted it as a new hard gate. Original research had nine losses;
the selected eleven does not resolve that earlier concern.

## Close alternative worth reviewing

Round1winner`f8b1ce950e41cf0d` changes only BUY TP2R→3R from row20, keeping
60minute cooldown. Base net1943.7560USD is only1.5780USD lower than selected;
worst6DD36.2963% is2.3747pp lower. However stress net1350.1932USD is121.6768USD
lower, while cent base1957.4356USD exceeds its raw base due to changed admission
paths. Do not mix raw/cent outcomes to select whichever looks best.

Selected case wins the frozen maximum-raw-base ranking. This close alternative
offers more historical DD headroom. Neither establishes universally best
MM/DD/profit trade-offs or justifies an automatic Demo replacement.

Removing the selected ledger's five largest wins leaves1282.8242USD base net,
883.7292stress and876.8012rawfee. This is descriptive profit concentration;
it is not a replay in which those trades were removed and capital/admissions
recomputed. BUY/SELL attribution and monthly exit-net curves have the same limit.

## Provenance, costs and remaining validation

Same171,171,013 Exness XAUUSDm Bid/Ask quotes,49,729complete BidM15bars,
2024-09-01T22:05:06.129Z→2026-10-23T20:57:59.517Z. No new Oct25market sample.
Input hashes, parent manifest, benchmark cells, per-round catalogs, source
snapshots and original incumbent full-result parity are checked. Full-history
source completeness remains NOT_CERTIFIED; no missing bars are invented.

Every economic cell includes static modeled swap: point-mode1,long−567.4/short0,
point0.001,contract100oz/lot,UTC-midnight prior-business-day calendar with
Wednesday triple posted at the next midnight. Base uses recorded Bid/Ask;
stress adds0.20USD/oz spread and0.10USD/oz adverse market-fill slippage;
fee adds hypothetical7USD/lot roundtrip. Higher assumed cost can alter admissions
and raise a particular ending result; this is not a causal benefit of fees.

Historical target-account rates/calendar/commission and broker margin/HMR/
stop-out/fills remain unattested: **COST_INCONCLUSIVE**. Current
[Exness rollover documentation](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours)
describes seasonal21/22UTC events, not evidence that the modeled midnight
calendar matches historical broker postings.

All history was exposed by previous searches. This campaign stops because its
two-round budget is reached while the rank still improves, not because a local
or global optimum has been proved. More searches on the same tape increase
[selection exposure](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
Year/month attribution, deterministic repeats and independent accounting do not
create an untouched holdout, certify future profit or calculate PBO/ruin risk.

## Verification and repeatable workflow

[Independent audit](../../runs/c22-matrix-tuning-2026-10-25/independent-verification.json)
PASS:153cells/72,899entries, cash/net/swap/calendar, fixedlot, initialrisk,
daily10% baseline/count2, cooldown, nonoverlap, exact source/input/snapshot
hashes, all raw-qualified cent coverage and strict objective improvement flags.
Selected six full-tick equity reconstructions match DD/minimum equity/final
cash, scanning approximately41.6–41.9million held quote observations per path.
These are checks on the same market data, not new economic replays or samples.

Initial six incumbent full results match the parent exactly; final six fresh
full-result repeats match. Resume returns `Already complete; hashes verified`.
Existing regression command ran61tests/2.219s/OK:

```bash
PYTHONPATH=. .venv/bin/python -m unittest tests.research.test_breakout_logic tests.research.test_c22_frequency
```

Native-domain one-factor isolation, DD40boundary/fail-closed selection,
idle-versus-underwater recovery fixtures and source compilation also pass.
No broker connectivity, sender lifecycle or full runtime test is newly claimed.

Local commands, using the preserved inputs/source pins:

```bash
PYTHONPATH=. .venv/bin/python scripts/research/c22_matrix_tuning.py
PYTHONPATH=. .venv/bin/python scripts/research/c22_matrix_tuning_verify.py
PYTHONPATH=. .venv/bin/python runs/c22-matrix-tuning-2026-10-25/build_matrix.py
```

First command resumes the frozen campaign; it does not silently start another
search. A subsequent tuning campaign must freeze a new parent/catalog/protocol
and retain this run, rather than overwrite completed evidence. Inputs and
artifacts live under ignored runs/; new source files are local/uncommitted, so
clean-Git-only reproduction is not claimed.

The [selected Rules descriptor](../../runs/c22-matrix-tuning-2026-10-25/selected-research.json)
is research-only, including native BUYTP3Routside the frequency adapter's
validated config domain. It requires an explicit adapter before runtime use.
This work made no active Demo config, sender, account, position or execution
authorization changes. No deployment/cutover or real-money qualification.

Matrix delivery:35rows (original benchmark plus34campaign profiles),159source
cells including the six benchmark paths,4293monthly curve points;18rows have
actual complete cent review. Embedded JSON matches matrix.json and the saved
Canvas source hash. Strict TypeScript checking exits0. No rendered screenshot
or MT5 chart inspection is claimed.

**Verdict: qualified bounded research improvement under profit/DD40; unresolved
streak/recovery, historical broker economics and forward validation prevent a
production or universal-best-strategy verdict.**
