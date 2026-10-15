# Active Demo C22H4 vs C22 tuned — 2026-10-15

**MODELED_IMPROVEMENT: C22 tuned improves net profit, monthly entries, profitable
entries and maximum DD versus current frozen Demo strategy in both cost views.**
Native MT5/Wine UI retry still failed `Sky Computer Use native pipe startup failed`.
Owner explicitly selected tick replay comparison; this is not native Strategy
Tester performance and does not authorize changing Demo.

Original Demo contract `1af968e9ac6a26ea` matches normalized canonical baseline
`b86cfc2df8bf297d` exactly after explicit buy_ema50. Full historical research
frame/rules match active frozen detector across48465 bars; pinned sources9/9 PASS.
Tuned research contract `b823f4aefe10fc72` remains unadopted.

## Same-input paired results

Both start USD200/fixed0.01/cost-inclusive10% initial cap/daily10%,one position.
167622055 paired Exness ticks, identical completed M15 bars, same canonical
execution/geometry. Entire requested window2024-09-01UTC→2026-10-06T17:22:04.296998UTC;
actual first2024-09-01T22:05:06.129UTC,last2026-10-05T23:59:59.969UTC.
Monthly figures use24 full requested AND observed-bracketed months,Oct2024–Sep2026.
PartialSep2024/Oct2026 excluded,zero/warmup full months included. Internal quote
coverage not inferred from endpoint bracketing.

| Case | View | Final USD | Net USD | Max DD | Total trades | Entries/month | Winners/month | Median monthly cash USD | Positive months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| active_demo | base-swap | 497.49 | 297.49 | 39.28% | 120 | 4.96 | 2.42 | 0.00 | 11/24 |
| active_demo | cost-stress-swap | 498.64 | 298.64 | 40.63% | 118 | 4.88 | 2.46 | 0.00 | 10/24 |
| tuned_research | base-swap | 941.10 | 741.10 | 29.64% | 404 | 16.79 | 5.75 | 16.37 | 17/24 |
| tuned_research | cost-stress-swap | 803.57 | 603.57 | 36.96% | 402 | 16.71 | 5.83 | 21.95 | 16/24 |

Base net improves USD297.49→741.10 (+USD443.60); DD39.28%→29.64% (−9.64points).
Cost stress net USD298.64→603.57 (+USD304.93); DD40.63%→36.96% (−3.67points).
Net-positive completed entries/month2.42→5.75 base and2.46→5.83 stress (~2.4×).
These are mean profitable completed positions attributed to entry month, not a
promised monthly profit or a forward forecast. All preregistered gates pass both views.

Base and stress active-demo net differ non-monotonically because commission
changes cost-inclusive admission, daily blockers and equity path (120→118trades).
This is not a fees-improve-profit claim. Detailed rejections/ledgers retained.

## What changed; what remains research-only

Only four behavioral differences: RSI14→7;BUYoff→BE1R;SELLTP3ATR→2R;
max_daily_losses1→0 (removes stop after one losing exit/day).
Risk cap10%,fixed0.01,daily loss10%,no recovery remain. The loss-count change is a
material tradeoff; full change has only reused-discovery evidence, no single-factor
causal attribution or unchanged-circuit qualification. Active Demo config/sender,
source pins, process-scoped daily baseline and cost attestation unchanged.

Both views include modeled swap pointslong−567.4/short0,point0.001,Wednesday
triple,assumed UTC-midnight rollover. Base commission0USD/lot/roundtrip;
COST_SURCHARGE_STRESS40USD/lot/roundtrip (USD0.40 at0.01). Quoted Bid/Ask unchanged,
no extra spread/slippage. Archived cost metadata **COST_INCONCLUSIVE**, no fresh
broker-history proof; required metadata validated, never zero substitution.
This cash-cost stress differs from older spread/slippage stress; no mixed-stress
comparison. Modeled swap debit USD3.9718 active vs55.6052 tuned in both views.

Canonical commission fully upfront, fee-inclusive BE on completed M15 management
bars,strict open-position midnight baseline. These differ from native EA raw-price
per-tick BE and first-tick daily baseline, and from Demo process baseline. This
report compares two cases within exactly same engine; no runtime/native parity.
C22 tuned USD941.0958/803.5688 here versus shared-native-geometry USD941.1258/803.5988
in prior report differs byUSD0.03. Stop/target grid geometry differs; entry times,
directions and trade counts match, while a few exit timestamps differ. No exact
execution parity is claimed. Do not combine these runs or infer native Tester
economics. No new holdout opened/new market
period acquired; data reused from prior tuning, not out-of-sample qualification.

## Verification and provenance

Preregistered protocol: [paired spec](../specs/2026-10-15-c22-demo-vs-tuned.md).
Runner retained `runs/c22-demo-vs-tuned-2026-10-15/run_compare.py`; unchanged public
`c22_frequency_campaign.execute_cell` → `c22_frequency_adapter.prepare` → canonical
replay → cash/lot/risk/nonoverlap/swap audit → monthly cash/winner metrics.

Campaign02 exit0:4 economic cells,4 fresh whole-result repeats identical.
Independent audit recomputed all4 swap debits/monthly metrics and checked all4
persisted repeat objects; all completion artifact hashes verified. All4 economic
results also equal attempt01. Initial run failed only NumPybool final-verdict JSON
serialization, after all replays; explicit bool conversion reproducedRED→GREEN,
original incomplete directory/source/log preserved, freshcampaign02 completed.

`PYTHONPATH=.:tests .venv/bin/python -m unittest test_c22h4_strategy
 test_c22_frequency.AdapterTests tests.test_native_frequency_replay`:
18 tests,0.424s,OK,exit0. Includes frozen signal/geometry/source invariants,
adapter baseline parity and public fee+swap replay→metrics/missing metadata
controls. No production code edited; no need to repeat prior full962-test suite.

Artifacts: ignored `runs/c22-demo-vs-tuned-2026-10-15/campaign-02/`:
`protocol.json`,`input-verified.json`,`cells/`,`repeats/`,`source_snapshot/`,
`results.json`,`COMPLETE.json`. Adjacent `baseline-parity.json`,`audit-final.json`,
`focused-tests.log`,`campaign-02.log`. No raw outputs in docs.

**Decision:** measured improvement versus active Demo under named model; preserve
research-only status pending fresh costs, untouched holdout/forward evidence and
separate Demo readiness/owner cutover decision. Current Demo unchanged.
