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
