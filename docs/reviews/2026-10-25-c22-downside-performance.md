# C22 research downside and performance review — 2026-10-25

**A bounded improvement passes the owner's agreed profit/DD conditions, but it
does not eliminate the losing-streak or recovery weaknesses.** The candidate
changes BUY SL2 to2.5ATR and cooldown0 to4elapsed M15periods after a net losing
exit. Base net rises1497.58 to1652.21USD; price-stress1063.10 to1242.26USD.
Selected observed equity DD across six cost/guard paths is31.66–36.71%, below
the new40% ceiling. However, longest loss streak becomes11 instead of9 and
stress completed closing recovery becomes133.30 instead of101.10days.

Goal: diagnose the actual historical weaknesses and improve terminal profit
without reducing matched base/stress net, keeping observed DD<=40%. Smaller
alternative used: existing canonical detector/entry/replay plus bounded rule
changes; no new execution engine, lot increase, recovery or Demo modification.
The owner explicitly approved these profit floors and DD ceiling during this
review. Whether to add hard streak/recovery gates is awaiting a separate answer.

## Evidence and scope

Same171,171,013 Exness XAUUSDm Bid/Ask ticks/49,729completed BidM15bars;
actual2024-09-01T22:05:06.129Z through2026-10-23T20:57:59.517Z. One continuous
200USD account per scenario, fixed0.01, single position, initial cost-inclusive
cap10%, daily10% new-entry gate, no top-ups/resets/recovery. Actual source and
frozen Demo/research pins were checked. All new economic scenarios include the
named modeled swap. No new October25market observations or untouched holdout.

Stage1 froze18cases before outcomes; Stage2 prospectively froze five combinations
after Stage1. This totals23distinct cases including baseline,78economic cells
(69raw plus9cent sensitivities) and12fresh full-result repeats. Stage2 also reuses
six explicitly hash-bound parent paths, not six additional new market samples.
All rejected/losing cases remain saved. Protocols and sources:

- [Stage1 protocol](../../specs/c22-performance-2026-10-25.md) and
  [harness](../../scripts/research/c22_performance_campaign.py).
- [Adaptive refinement protocol](../../specs/c22-performance-refine-2026-10-25.md)
  and [harness](../../scripts/research/c22_performance_refine.py).
- [Independent verification](../../runs/c22-performance-refine-2026-10-25/independent-verification.json):
  78cells/34,146admitted entries; independent cash/net/swap/calendar/fixedlot/
  initial-risk/daily-loss-count/daily10% admission/nonoverlap checks pass.
  Selected six full-tick reconstructions match maxDD, minimum equity and final
  cash. These reuse the observed source tape; they are not independent market data.
- Fresh existing regression command `PYTHONPATH=. .venv/bin/python -m unittest
  tests.research.test_breakout_logic`:44tests,0.186s,OK. No new broker or full
  runtime suite is claimed. Unit fixtures are not economic profit evidence.

## Major — Nine losses are a BUY cluster; count alone hides severity

The original research's longest raw-base run spans2026-02-25 through03-06:
nine BUY exits, net−166.6964USD from entry equity1085.0116USD (−15.36%).
Eight exits are about−1R; one protected exit loses0.029USD/−0.00150R.
Under stress the nine-exit run loses167.9514USD/20.00% of its starting equity.
The current Demo control's longest base run is five exits but loses20.89% of
that run's starting equity; different trade counts/capital phases matter.
Research519trades versus current130 also means different opportunity counts;
the raw9-versus5 comparison alone does not establish worse ruin probability.

Trace: BUY is an RSI7cross30 oscillator conditioned on EMA50 and closed H4EMA200,
not a Donchian breakout. [Oscillator and parent priority](../../scripts/research/campaign_signals.py#L74)
preserve distinct BUY/SELL rules. Five of these nine BUYs occur while the latest
closed H4EMA200 is not above its16M15bar lag; four have candle body<50% of range.
These are measured features, not proof those filters improve full-account profit.
[Source-bound feature rows](../../runs/c22-performance-2026-10-25/streak-signal-features.json).

Tested changes and actual consequence: BUYbody filter lowers base net to598.76USD
and raises DD to56.72%; BUY H4slope filter lowers stress net to797.79USD and raises
DD to47.29%. Both are rejected. Removing losing examples locally would have
hidden these full-path failures. Do not label higher win rate or a shorter
selected streak an improvement unless full-history profit and DD also pass.

## Major — The 100-day recovery is a different, SELL-driven episode

Original base closing-balance peak600.1518USD on2025-06-27 is recovered on10-05,
100.399days later. During72exits BUY contributes+124.1912USD while SELL contributes
−103.0320USD. Original stress has the analogous101.102day interval, BUY+136.8042
versus SELL−117.1560USD. This attribution does not prove the return of a SELL-only
filter: admissions and equity paths would change when a rule changes.

The original absolute minimum observed equity155.961USD occurs2024-11-11, before
both episodes. At that point the held SELL is eventually a+12.827USD winner;
it starts from closing balance161.171USD and temporarily loses5.21USD. Excluding
that winning trade to hide the minimum would be an invalid retrospective repair.

Tested minimal hypotheses: SELLbody lowers base/stress net to1211.53/995.21USD;
SELLdepth stress DD reaches42.33%; SELLH4slope stress net768.77USD. None qualifies.
Cooling down4elapsed15-minute periods improves stress/DD but base net1457.18USD
falls below the1497.58USD floor. It is a useful component, not a standalone winner.

## Major — BE does not imply a nonnegative net exit

One original nine-run BUY reaches observed MFE1.103R but exits near−1R with
protection inactive. [Replay management](../../scripts/research/breakout_replay.py#L354)
checks protection at completed management bars; an intrabar spike may disappear
before that decision. This is the frozen contract's timing, not a missing tick.

[BE level math](../../scripts/research/breakout_replay.py#L369) covers the modeled
commission/slippage amount but not accrued/future swap or an adverse fill gap.
Protected exits can therefore still be negative net. The new leader's longest
base11-run contains three protected exits, including swap losses; never rename
those losses as wins or discard them merely to shorten the streak.

Actual early-protection0.5R test fails: stress net279.38USD/DD59.15%. Failed-close2
and stagnant8also fail the profit/DD conditions. Suggested next hypotheses,
not implemented here: separately test accrued-swap-aware protection and a
broker-compatible management cadence. They require an explicit contract and
full replay/runtime parity; do not switch to intrabar BE just to rescue one trade.

## Major — The qualifying profit/DD improvement retains material trade-offs

Selected research-only [config aab846c7292da8b6](../../config/research-c22-performance-aab846c7292da8b6.json)
keeps the original RSI/EMA/SELL48, SELL SL2.5ATR/TP1.35R/BE1R, BUY TP2R/BE1R,
daily10%/dailycount2/staticcap10%, fixed0.01. Only BUY SL2→2.5ATR and
cooldown0→4change. [Entry math](../../scripts/research/breakout_entry.py#L32)
makes a wider SL also widen the2R target, increase planned dollar risk at the
same lot and change risk admission. It is not free protection at unchanged risk.
[Loss cooldown](../../scripts/research/breakout_replay.py#L238) starts after any
negative net close and uses4*900000elapsed milliseconds; it includes closure
time and does not mean four fully observed trading bars.

Raw base: final1852.2064USD/net1652.2064USD (+10.33% net over old research),
DD31.6581%,481trades,PF1.3634,minimum observed equity184.851USD.
Raw stress: final1442.2616/net1242.2616USD (+16.85%),DD35.7268%,480trades,
PF1.2600,minimum equity159.272USD. Raw fee sensitivity: final1431.6576/
net1231.6576USD,DD36.7085%,minimum equity158.849USD.
Cent base/stress match raw; cent fee net1199.9536USD. All six pass the specified
profit floors, positive net/modeled survival, cap/daily invariants andDD<=40%.

Counter-evidence must remain visible: stressDD35.7268% is slightly higher than
old35.7067%, and feeDD36.7085% exceeds old36.5189%; both remain below40%.
The longest loss streak is now11, from2025-07-31 through08-20, not the original
2026BUY cluster. Its base net−103.0224USD is16.83% of starting equity; stress
net−116.5104USD is20.55%. The old longest run was15.36%/20.00%; moving to a
different cluster does not remove consecutive-loss risk.

Completed base recovery remains100.400days. Stress recovery becomes133.295days,
from2026-03-23 to08-03; BUY−219.7602USD and SELL+220.2120USD now largely offset.
Fee recovery is130.299days. Still-unrecovered closing drawdown at the last source
quote lasts about73.92days, versus63.19days for the old research; do not omit
that censored episode or claim100days is an upper bound on future recovery.

The alternate SELLTP2R combination earns base1608.71/stress1305.34USD and lowers
baseDD to29.97%, but loss streak15/recovery~135–136days worsen. The predeclared
maximum-base-net ranking retains the1652.21USD case; neither is an all-risk winner.

## Blocker — Price gaps, historical costs and independent validation remain open

The new worst realized netR improves to about−1.74R partly because BUY initial
risk is larger; it must not be described as eliminating the cash gap loss.
An initial risk cap and a40% observed-history DD gate cannot guarantee fills or
future drawdown. Broker margin/HMR/stop-out/partial execution remain unqualified.

Every case includes modeled swap, but the snapshot rate and UTC-midnight calendar
are assumptions. Current [Exness hours documentation](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours)
describes seasonal21:00/22:00UTC rollover/swap events; it does not attest the
model's historical calendar. Obtain dated target-account evidence before claiming
broker parity. Unsupported economic history remains COST_INCONCLUSIVE.

The23case search follows an earlier74case discovery on already inspected history.
Fresh deterministic repeats and exact accounting do not resolve
[selection bias](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
No future edge, PBO, risk-of-ruin probability or real profit is established.
Current Demo still uses a different frozen contract; no adapter/source-pin,
sender, broker state, deployment or cutover was changed.

## Decision remaining

Confirmed: maximize terminal profit, matched base/stress floors, observedDD<=40%,
fixedlot/risk/daily protections, no recovery or lot increases. Pending: whether
loss-streak length and recovery duration must additionally never exceed their
original research values. The current candidate passes the confirmed conditions
but fails that proposed stricter requirement. No owner answer is inferred.

Delivery checks pass: the exported config reproduces the selected replay Rules
exactly; selection rejects missing scenarios, insolvency, profit below floor and
DD above40%, while accepting the40% boundary. Both completed harnesses resume
with hashes verified and no new replay. Canvas embedded JSON matches its saved
data exactly; all486monthly points reconcile to final balances and strict
TypeScript checking exits0. This is source/data validation, not a rendered MT5
chart or broker execution claim.

**Verdict: fix-then-ship. A profit/DD-qualified research improvement exists;
the original streak/recovery weaknesses remain and prevent claiming a complete
solution or approving a Demo replacement.**
