# C22 parameter and outcome matrix — 2026-10-25

The matrix reorganizes existing audited experiments so each rule can be reviewed
individually before combinations. No new economic replay, parameter change, lot
increase or Demo modification occurred. Same source tape, cost/swap assumptions,
account and research limitations as the
[downside/performance review](2026-10-25-c22-downside-performance.md).

## Stable row map and review order

24raw-counter rows: row1is the current frozen Demo contract replay; row2is the
maximum-profit research benchmark9e511d195c52ef3d; rows3–14change one research
factor each; rows15–24combine factors. This is24rows, not24new strategies or
24new economic runs. The23research cases include the unchanged benchmark.
Only five rows have all three cent-counter cost views:1,2,9,20,23. The cent
view omits untested rows rather than replacing their missing outcomes with raw.

Start with the2×2factor matrix of BUY SL and cooldown:

- Row2: BUY SL2ATR, cooldown0. Original research benchmark.
- Row9: BUY SL2.5ATR, cooldown0. Isolates the stop-distance change.
- Row10: BUY SL2ATR, cooldown4. Isolates the cooldown change.
- Row20: BUY SL2.5ATR, cooldown4. Measures their combined account path.

Then compare row20with row23, which additionally changes SELL target1.35R→2R.
Keep scenario and raw/cent counter identical when comparing rows. Row numbers
remain stable under filtering and sorting. Row1is a multi-rule reference, not a
one-factor control for a particular research change.

Other single changes, in order:3BUYbody,4BUYclose,5SELLbody,6SELLdepth,
7SELLH4slope,8BUYH4slope,11BEactivation0.5R,12failed-close2,
13stagnant8,14drawdown risk-admission steps. Rows15–19are the predeclared first
stage combinations. Rows21and24change daily-loss-count in combinations; row22
is BUY SL2.5 plus SELL target2R without cooldown.

## What each matrix shows

Factor matrix: actual full-account net, equity DD, loss streak, completed
closing recovery and minimum equity for each of four observed2×2cells. Raw only.

Outcome matrix: all three net-profit cost views together, plus DD/minimum equity/
loss streak/completed recovery/ongoing recovery for the selected cost scenario.
Each row includes the exact changes, profit/DD decision and concrete rejection
reasons. DD changes use percentage points, not relative percentage change.

Parameter matrix: RSI, SELLlookback, BUYstop, SELLtarget, BUYprotection,
BEactivation, daily loss-count, cooldown, failed/stagnant exits, risk mode and
signal filters. Shared fixedlot/singleposition/cap/daily/no-recovery invariants
remain explicit in the header.

Detail selector: one row versus the matched research benchmark, deltas and
direct source-cell link. The curve is initial200USD plus cumulative net attributed
to exit month; it is not tick-equity or an MT5 screenshot. It omits intramonth
floating excursions and entry-fee timing for trades still open at month-end.

## Reading qualification without changing the agreed objective

Confirmed screen: matched base/stress net no lower than research benchmark;
positive net/modeled survival and observed equity DD<=40% in all declared cost
views. A full reviewed PASS also requires the matched cent views; raw PASS alone
does not substitute for that sensitivity. Reference and benchmark rows are
clearly labeled rather than presented as new winning experiments.

Separate diagnostic column: would loss streak and completed recovery both be
no worse than the benchmark in every cost scenario? This is a proposed extra
condition, not an accepted new ranking rule. Across the22changed raw cases,
none simultaneously passes the confirmed profit/DD screen and this stricter
streak/recovery condition. That is a bounded-search result, not proof a better
strategy is impossible. The owner has not answered that additional-gate question.

Rule effects are not additive. In base raw, changing only BUYstop2→2.5adds
26.78USD net; cooldown alone loses40.40USD net; combining them adds154.63USD.
This reflects the model's changed holding/admission/daily-state/equity path,
not an independently attributed contribution or a guarantee in another market.

## Evidence and limits

Data source files, artifact hashes and scenario coverage are retained in
[matrix.json](../../runs/c22-performance-matrix-2026-10-25/matrix.json).
The builder verifies both completed experiment artifact sets, original control
cell hashes and the bound first-stage source files. Net curves reconcile to
stored final balances; per-row parameter values come from the actual replay
Rules and source contract, not reconstructed labels alone.

Existing independent audit covers78new saved cells/34,146entries and selected
six full-tick equity paths. This matrix uses existing results only. All scenarios
include modeled swap but historical broker costs/calendar, execution parity,
session completeness and forward profitability remain unqualified. All history
is research-exposed; current Demo remains on its separate frozen contract.

Matrix delivery checks pass:24stable rows,72raw and15cent scenario paths,
87source-cell hashes, exact embedded Canvas JSON, benchmark deltas and2349monthly
curve points. Strict TypeScript checking exits0. These are data/source checks;
no rendered MT5 chart, broker check or new economic replay is claimed.
