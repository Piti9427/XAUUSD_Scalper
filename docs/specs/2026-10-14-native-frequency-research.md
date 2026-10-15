# Native MT5 frequency research v1

Owner requested `$implement` after proposals to compare Trend Pullback M5 and
Session Breakout with C22 tuned. Research implementation only; no Demo replacement,
live chart attachment, sender restart or profitability qualification.

## Public interfaces and frozen scope

Owner accepted tests at signal → admission → order/close/report boundaries and a
native no-order test script. Implement one tester-only EA with independently
selected strategy modes. One fixed 0.01 position, USD account, 10% cost-inclusive
initial risk ceiling, 10% UTC daily-equity admission circuit. No rounding volume
up, recovery, topups or equity resets. New strategies stop entry after one losing
completed position/UTC day. C22 tuned retains its research unlimited-loss-count
rule, not the Demo rule. Demo process-scoped baseline is untouched; this standalone
tester uses first observed tick equity of each UTC day and reports that assumption.

Only completed UTC Bid bars, assembled from all constituent M1 bars, are eligible.
Explicit fixed historical server→UTC offset attestation required; no inference
from current offset. Reject invalid/duplicate chronology. EMA seeded at first
accepted bar, ATR14 is arithmetic mean of true range. No built-in Wilder ATR/RSI
substitution. Indicators retain causal state through evaluation.

## Strategy modes

1. **Trend Pullback**: closed H1 EMA50 and 4-bar slope determine direction. Two
   consecutive complete M5 bars; previous candle touches EMA20 or EMA50 and closes
   against trend; latest candle closes through previous high/low, above/below
   EMA20, with EMA20 aligned to EMA50. Stop beyond min/max of those two candles
   with 0.1 ATR14 buffer; target 2 times rounded executable risk distance; BE at1R.
2. **Session Breakout**: fixed UTC windows (defaults07:00 and13:00; explicitly
   research UTC windows, not DST-adjusted London/New York civil opens). First30
   minutes require all6 M5 bars. A later close breaks range; a subsequent distinct
   bar retests boundary and closes outside in breakout direction within6 bars.
   Stop beyond retest wick with0.1ATR; target2R; BE1R. One consumed entry attempt
   per session/day, including admission rejection. Missing bar invalidates setup;
   session ends after180 minutes. No retroactive session reconstruction.
3. **C22 tuned**: native reconstruction of `b823f4aefe10fc72` signal/geometry:
   completed M15; rolling RSI7 cross25 BUY, positive delta, EMA50/4-bar slope;
   prior96-bar-low SELL with falling EMA50; SELL precedence; closed complete
   H4EMA200 macro. BUY SL1.5ATR, SELL SL2.5ATR, TP2 rounded R, BE1R both sides;
   daily10%, unlimited losing-exit count. All gains/no losses RSI100, flat RSI50.
   Signal fixture parity required against frozen Python contract; native fills,
   daily baseline, warmup prefix and broker swap calendar are separate contracts.
   No full broker/economic parity claim from signal tests.

## Costs and outputs

Every economic evaluation must pair Base+swap and Stress+swap. Missing/unsupported
swap, commission or server-time provenance rejects initialization. Rates/calendar
are named current-spec assumptions, COST_INCONCLUSIVE without historical broker
verification. Native Tester deal commission/swap/fee feed equity and reports;
never replace missing metadata with zero or use ProfitInPips.

Owner selected native commission-surcharge Stress (2026-10-14). Base uses declared
instant commission; Stress adds40 USD/lot/roundtrip (0.40 USD at0.01), paid through
Tester advanced commission settings, not a synthetic cash deduction. Equivalent
cash burden to0.20/oz extra spread plus0.10/oz each entry/exit slippage at100oz/lot;
not equivalent prices, stop triggers or fill sequence. Name it COST_SURCHARGE_STRESS,
never quote-widening/slippage parity. EA requires explicit view and cost inputs;
complete position ledger commission+fee must match declaration, otherwise INVALID.
Both views retain native points swap with attested long/short/triple-day spec.
Never select/qualify from only Base, pips-only reports or unmatched cost settings.

Export deal ledger, observed per-month entries/winners/net (cash booked by deal
month, winners assigned entry month after complete exit), zero/warmup months,
requested-full and observed unobserved/partial/full-span labels; only months full
in both requested and observed bounds enter denominators. A full observed span
is not proof of internal quote coverage. Export tick-equity DD, worst month, median full-month net and
profitable-month ratio. One report prefix per run/optimization pass; local Tester
files only, no Telegram. A successful send response is not a confirmed fill;
partial/ambiguous execution stops new entries, never emits phantom confirmation.
Owned protection only, check volume/fill/slippage risk after fill, retain halt
until run ends. No blind resend of uncertain market requests.

## Validation and commit boundary

TDD against actual shared MQL5 core compiled under native C++ compatibility shim;
same test cases run in native tester-only MQL5 harness. MetaEditor compilation
adds MQL5 type validation when available. Public C22 signal fixture differential
uses existing frozen Python source unchanged. Broker smoke/economic tests must
not launch the terminal/data folder used by the current Demo sender.

Task-start review fixed point: `f64d7da8e10270ebb47893f2b14f48481cf8cdc6`.
Review only this implementation delta; task-start dirty worktree preserved under
ignored `runs/native-frequency-2026-10-14/before/`. Commit only this task's files
and appended documentation hunks; pre-existing runtime fixes/owner notes excluded.
Review Standards and Spec independently, then full repository test suite once.
