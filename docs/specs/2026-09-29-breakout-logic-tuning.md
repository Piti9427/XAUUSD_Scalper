# Breakout logic tuning loop

User request: implement a tuning loop until strategy improves risk, fees, profit,
realized RR and drawdown. User selected strict comparison against baseline:
higher net profit, lower DD, higher realized RR, and better cost-stress results.

## Scope

Offline research only. No broker connection, order, notification or runtime
configuration update. Preserve fixed 0.01 lot, 10% equity risk admission,
40% UTC day-start admission halt and single-position/no-recovery invariants.
Freeze Donchian 48, RSI/EMA off, ATR14, TP 3.0 ATR. Baseline SL 2.5 ATR;
third research batch also tests explicitly defined structural invalidation SL.

Implement a public replay(frame, ticks, broker, rules, costs, start, end)
returning metrics, admission reasons and trade ledger. All exits use available
quotes after decisions, never signal-bar-close fills. Entry quote lateness must
be <=90 seconds; protective exits use the first available quote even if late. Every completed bar can
invalidate a position, including bars without an entry signal. Position SL/TP
remain active between bar decisions. Risk admission includes declared exit
slippage and round-trip commission; quote spread is not counted twice.

Research hypotheses:
1. Exit on first closed bar back through the original breakout boundary.
2. Require two consecutive closed bars back through that boundary before exit.
3. After an exit, require a closed bar back inside the entry's frozen range
   before accepting another breakout.
4. Time exit after 4/8/16 completed bars if trade has made no net progress.
Test individual rules and predeclared combinations. No indicator optimization.

Training-only second batch, declared after the initial 23 exit/reset trials
failed training (no validation results opened): add entry modes confirm and
retest. Confirm requires the next completed bar to remain beyond the frozen
breakout boundary. Retest requires a later bar to touch that boundary and close
back beyond it, within four completed bars; cancel when a close loses boundary.
Recompute 71 total combinations (23 immediate +24 confirm +24 retest). This
training-guided expansion is disclosed as additional search, not independent evidence.

## Evaluation

Persist protocol before trials. Training March 28–June 28, validation June 28–
August 28, final diagnostic August 28–September 28, 2026, end exclusive UTC.
Each window starts at $200; do not compound independent results.

Baseline and candidate use identical data and cost assumptions. Base: saved
Bid/Ask, zero Standard commission, no added slippage/swap. Stress: declared
extra spread 0.20 USD/oz plus adverse slippage 0.10 USD/oz each market fill;
not measured broker costs. Historical swap entitlement remains unknown.

Realized RR = average winning net USD / absolute average losing net USD;
undefined if no wins or losses. Also report profit factor, net R, win rate,
MFE/MAE and total explicit modeled costs. Fees must not silently disappear.

Training gate: at least 20 trades, positive net, greater net and realized RR,
lower tick-equity DD than same-window baseline, and better stressed net with
no worse stressed DD. Rank training passers by DD then net. Evaluate a single
training-selected candidate on validation and final diagnostic; no selection
using these outcomes. At least 10 trades per validation/diagnostic window.
If no candidate passes, report NO_QUALIFIED_STRATEGY. Do not loosen gates or
add hypotheses after observing validation. Limit trial universe explicitly;
an unbounded search on reused data is not evidence of generalization.

No passing result constitutes untouched holdout evidence or live readiness.
Prior searches already inspected this tape. Never guarantee eventual success.

## Acceptance and provenance

Baseline must be compared to archived replay; report any engine discrepancy.
Audit saved raw archives/tape and canonical bars; record SHA-256 source/input,
protocol, every training trial, ledger and final status. Refuse to overwrite
an existing run. Run focused tests and full unittest suite. Review only this
work against pinned starting HEAD; preserve preexisting dirty files.

## Third training-only batch

After all 71 entry/exit variants failed training, with validation still unopened,
add structural SL as a competing hypothesis. BUY SL is one broker tick below
lowest low of original breakout and confirmation/retest entry candle; SELL is
one tick above highest high. Immediate entries use the breakout candle alone.
Do not clamp this SL to an ATR or risk budget. Invalid/nonprotective SL or risk
above 10% rejects entry. TP remains 3 ATR. Total universe now 143 configurations
(71 original +72 structural). Additional search is disclosed; not independent
validation. Freeze this universe before the next run. No further expansion
based on validation or final diagnostic results.

## Fourth training-only batch: profit protection (2026-09-30)

User requested continuation after 143 failed trials. Training baseline ledger
contains 56 losing trades, of which 19 first reached >=0.5 initial risk in MFE;
those 19 eventually lost $443.705. This motivates, but does not validate, a
profit-protection hypothesis. No candidate validation outcomes guided this batch.

`--batch protection` predeclares 18 combinations: immediate/confirm/retest entry,
ATR/structural initial stop, and break-even/candle-trail/runner protection.
Disable prior failed-close, reset and stagnation experiments for this batch.
After a completed bar, activate protection when currently executable net PnL
(after reserved commission and exit slippage) >=0.5 initial admitted USD risk.
Break-even stop covers commission plus declared exit slippage, rounded toward
protection. Candle trail uses that floor plus just-closed candle low/high ±one
tick, whichever tightens further. Never widen SL; only update if it remains on
the protective side of current executable quote. Update takes effect on later
ticks, never retroactively. Runner removes TP only after a valid protective
stop update; ordinary modes retain 3 ATR TP. Gap fills can still lose money.
Preserve initial stop/risk and stop-update count in ledger. All original
admission controls, selection gates, split dates and cost scenarios unchanged.
No eventual success is guaranteed. Record negative results and do not loosen
the user's all-metric criteria.

## Fifth training-only batch: entry quality and asymmetry

Protection batch failed training, no validation opened. Training baseline BUY
net -$44.185 (51 trades), SELL +$346.821 (63 trades). Test asymmetric exposure
explicitly as a hypothesis, not a presumed permanent market property. Include
both buy-only and sell-only controls, a breakout body >=half its range in trade
direction, a close in the outer quarter in trade direction, and agreement with
previous UTC calendar day's open-to-close direction. Previous-day bars must be
available before current UTC midnight; missing calendar days reject rather
than silently forward-fill. This is observed canonical-bar day direction,
not an assertion of complete broker daily coverage.

`--batch entry_quality`: 5 guards x immediate/confirm entry x off/break-even/
runner protection =30 candidates. ATR SL 2.5 retained; fixed TP3 until runner
activation. The guard examines the closed entry candle; direction controls
are applied at admission. No RSI/EMA optimization. All-metric gates unchanged.
Record this additional training-guided search; no validation-based retries.
