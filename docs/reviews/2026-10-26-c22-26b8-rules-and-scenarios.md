# Selected26b8: actual entry, profit, risk and response rules

Read-only review requested by owner. At 2026-10-26 02:03:17 Asia/Bangkok,
13 examined files including config match the immutable VM release
`selected-dbeffa39fccd5de9`. Snapshot `RESEARCH-C22-SELECTED-20261025-26B8`,
RulesID `26b8bcd69e043653`, symbol XAUUSDm, magic22261025. Actual mode is
execute=true on the configured Demo; no REQUEST/FILLED was recorded at that
snapshot. No strategy/config/service/account change was made by this review.

The intent is profit across a sequence of trades. There is no condition that
guarantees a profitable individual order. Use the current simple signal plus
shared admission/lifecycle as the explanation; a new engine or another backtest
is unnecessary to identify the present rules. Historical results below are
read from SHA-bound completed artifacts, not fabricated or rerun.

## Data and indicator definitions

- Bid M15 is assembled from all15 observed completed M1 bars, UTC aligned.
  An incomplete M15 is excluded. Direct terminal M15 can therefore differ.
- BUY oscillator uses RSI7 from rolling7 arithmetic mean gains/losses, not a
  generic assumption that an MT5 indicator using another smoothing will match.
  Flat gain=loss=0 maps to50. EMA50 uses EWM span50, adjust=false.
- ATR14 is rolling14 mean TrueRange, where TR=max(high−low,abs(high−priorClose),
  abs(low−priorClose)). It is not fixed pips or a fixed dollar stop.
- Macro uses EMA200 on completed H4 containing all16 M15 bars. Its value is
  published only at H4 close. Runtime requires at least201 complete H4 bars and
  a finite current macro before admission. Missing macro fails closed.

Sources: [signal formula](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/campaign_signals.py:57),
[ATR](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/strategy.py:59),
[closed H4](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_tuning.py:49),
[warmup](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:113).

## Exact BUY and SELL triggers

BUY requires every condition on the same newly completed M15:

1. RSI7(previous)&lt;30 and RSI7(current)≥30.
2. Current close&gt;previous close.
3. Current close&gt;EMA50 and EMA50(current)&gt;EMA50 four observed M15 bars earlier.
4. Current close&gt;the latest valid closed-H4 EMA200.

SELL requires every condition:

1. Current close&lt;lowest low of the preceding48 observed M15 bars, excluding
   the current signal bar.
2. Current close&lt;EMA50 and EMA50(current)&lt;EMA50 four observed bars earlier.
3. Current close&lt;the latest valid closed-H4 EMA200.

SELL does not require an RSI70 crossing. BUY does not require a high48 breakout.
Strict inequalities matter: equal EMA/macro/low does not pass. RSI at30 only
passes the crossing test when the preceding RSI was strictly below30. The
trend hypothesis is rebound continuation for BUY and downside continuation for
SELL; that explanation is a hypothesis, not proof of future price direction.

Sources: [archived signal construction](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_search.py:154),
[macro filter](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/reward156_search.py:208).

## Every admission gate before sending

Signal → exact source/config and owner review → correct connected USD hedging
Demo identity and permissions → complete exposure/history → valid full-trading
symbol and finite specifications → valid nonfuture quote no older than60seconds
→ new completed M15 after approval/start → no safety halt/duplicate bar/other
position or pending order → proven daily equity baseline → fewer than2 negative
completed positions on the UTC day → elapsed negative-net cooldown → current
account-bound cost/spec/calendar and actual-cost agreement → valid fixed0.01
lot/risk/stops/margin → broker order_check → fresh account/quote/exposure/risk
recheck → persist SENDING intent → order_send → reconcile actual broker evidence.

The entry window is90seconds after bar close. First quote must be within that
window; cooldown compares that first quote with the last negative exit+30minutes.
Entry request uses the current executable quote, not a fabricated first-tick
fill. BUY requests Ask, SELL requests Bid. Current slippage allowance is0.10 in
price units; a quote change beyond it before send blocks. This allowance is not
a guaranteed bound on actual fills. Both the pre-send checks and the order itself
can still fail. Some rejection paths consume the bar; others can retry checks
inside the remaining window. An ambiguous submitted request is never blindly
resubmitted.

Sources: [admission](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:22),
[pre-send checks and persistence](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:150),
[identity](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py:34),
[review gate](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/execution.py:118).
Broker field definitions: [MQL5 Symbol Properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants).

## Stops, targets, BE and realized profit

Fixed volume is0.01lot. At contract100oz/lot this is1oz, so a1.00 price move
corresponds to about$1 gross P/L before costs, subject to actual broker
calculation. Runtime also asks order_calc_profit and order_calc_margin.

Let d=+1 for BUY,−1 for SELL, and Eref=Ask/Buy or Bid/Sell plus d×modeled entry
slippage. Initial SL is conservative tick-grid rounding of Eref−d×2.5×ATR14.
BUY TP is Eref+3×abs(Eref−SL); SELL TP is Eref−1.35×abs(Eref−SL), tick-rounded.
These are price-target multiples, not guaranteed net-money multiples after
actual fill, costs or swap. Both stop and target accompany the initial request.

Initial money risk includes modeled adverse stop distance, commission round trip
and exit slippage allowance. Actual fill risk is recomputed and retained as the
original BE trigger risk. At a new completed-M15 boundary, gross profit from the
first executable quote minus declared commission and slippage must reach that
original risk to activate protection. This is not continuous intrabar high/low
monitoring. A favorable intrabar touch can retrace before that snapshot.

BE candidate is actual fill plus/minus commission/(volume×contract)+slippage,
rounded to tick grid. It must improve SL, clear stop/freeze distance, pass checks
and be confirmed through actual broker SL before BE_MOVED. TP remains unchanged.
PLACED/timeout/connection/no-response retains pending modification; no resend
while unresolved. After successful BE there is no additional trailing ladder.

**Neither this BE price/trigger nor the initial10% risk admission adds projected
or accumulated holding swap.** Thus BE does not guarantee net≥0 after rollover,
closing fees or a gap. Final net is the signed sum of profit+commission+swap+fee
over a completely closed owned position ledger. Spread is already reflected in
entry/exit prices; do not subtract an attribution proxy a second time.

Sources: [entry geometry](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/breakout_entry.py:28),
[initial broker risk](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:93),
[BE](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:188),
[filled risk](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:279),
[realized net](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:345).

## MM, daily loss and DD: exact limits

- Fixed0.01: no martingale, recovery basket, hedge recovery, pyramiding or
  automatic profit-compounding lot growth. Higher equity lowers risk percentage
  for the same dollar stop, and raises the cash ceiling for admission; it does
  not itself increase lot or profit per identical price move.
- Per-trade cap10% of current equity: reject an oversized0.01 risk rather than
  silently rounding lot up, shrinking native SL or relaxing the cap. The cap is
  modeled initial price/commission/slippage risk, not an all-future-cost guarantee.
- Any completed owned position with net&lt;0 triggers30 elapsed minutes cooldown,
  including BE exits made negative by swap/fees. Cooldown survives UTC reset and
  restart; a signal whose first quote is too early is consumed.
- Two negative completed positions on the UTC day block later entries. Losses
  need not be consecutive. This does not limit a multi-day losing streak to2.
- Daily equity threshold is10% below the proven day baseline. The UTC day
  resets at07:00 Asia/Bangkok. The guard blocks new entries; it does not forcibly
  close an existing position at that loss and does not reserve the risk of a
  prospective next trade.
- Concrete control-flow witness: day baseline200/equity182 means existing daily
  loss9%, so the daily check passes. Native entry geometry can still admit
  risk18.101≤18.2. If all that modeled risk materializes, total daily loss is
  approximately18.05%. This is explicitly a synthetic arithmetic witness from
  the actual admission formula, not a new backtest or reported trade result.
- DD≤40% was a historical research selection requirement. There is no live
  portfolio-DD40% kill switch, drawdown-step sizing or buy-pause drawdown rule in
  this static runtime. Historical passing DD does not enforce future DD.
- If a held-midnight baseline lacks genuine boundary proof, owned protection
  continues but later admissions can remain blocked for the UTC day. No reset
  from current/restart equity is allowed to enlarge daily allowance.

Sources: [native contract](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/strategy.py:26),
[cooldown](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/c22_selected/runner.py:30),
[daily threshold](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:71),
[daily exit count](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:206),
[arithmetic witness](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-26b8-rule-review-2026-10-26/daily-budget-witness.json).

## Existing response plans and uncovered situations

The accompanying Canvas contains40 source-linked scenarios in6 groups:
market, admission, holding/exits, risk, costs and system failures. Important
behavior across those cases:

- Wrong timeframe/incomplete bars/macro/quote, foreign exposure, missing margin,
  stops/freeze limits, expired review or cost drift block entries; no forced trade.
- False breakout/sideways losses reach planned SL and the existing cooldown/
  daily gates. No ADX/range/news classifier is present.
- Open trades are managed by TP/SL/BE. An opposite signal or EMA reversal does
  not automatically close or reverse the trade. No time stop, stagnation exit,
  partial TP, Friday flatten or maximum holding duration exists.
- News, rollover and weekend holding have no dedicated avoidance rule;
  entry_session=all. Spread has no standalone fixed max-spread filter in this
  adapter, though executable geometry/risk/margin/checks may block wide conditions.
- Unexpected lot/direction/missing or loosened SL/changed TP/excess fill risk or
  excessive entry fees invokes safety halt and an attempted close of the owned
  ticket only. Fresh identity, quote and complete exposure/ledger proof remain
  mandatory. A confirmed partial close can close the proved residual; an
  ambiguous close cannot be guessed and repeated.
- Unknown entry/BE/close responses preserve journal intent and reconcile. A
  complete broker close can be recorded despite stale quote/disabled AutoTrading
  when connected Demo identity and exposure/history are still proven. Connection
  loss or incomplete evidence can prevent confirmation and client-side action.
- Broker-held SL/TP and the client manager are distinct. Gaps, slippage, broker
  execution and outages prevent a guarantee that any modeled cap always holds.
- Restart/boot uses the same journal and single sender. Boot is configured and
  tested at unit/source/recovery seams; actual VM reboot is not yet tested. Cold
  native connection synchronization has shown transient reconnects. No bypass of
  identity/permission is permitted to make it appear healthy.
- Watchdog and backups run independently, but external notifications remain off
  by owner choice. A total VM/network outage cannot push a message without an
  external channel. Changes to parameters need a new version/cohort; the running
  strategy does not automatically learn or retune after a losing trade.

Sources: [lifecycle/safety](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/lifecycle.py:374),
[manager/read-only reconciliation](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:198),
[watchdog](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/ops/c22_selected_watchdog.py:192),
[deployed recovery review](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-10-26-c22-verdict-fixes.md).

## Cost policy and historical profit evidence

Current existing Demo policy: conservative regular swap, entitlement UNKNOWN,
commission0USD/lot round trip, slippage allowance0.10. Fresh earlier SDK POINTS
rates were long−490.8/short0,point0.001,contract100; at0.01lot modeled regular
BUY swap is approximately−$0.4908, Wednesday triple−$1.4724; SELL0 is an observed
SDK value, not a missing-data zero. Published NY17:00 rollover/holiday exceptions
remain assumptions. Policy expires1November2026 20:25:18 Asia/Bangkok, no automatic
renewal. Current closed-position cost drift tolerance is$0.02 for swap; even
lower swap than modeled can block future admissions pending review.

Archived selected Base+swap uses quoted Bid/Ask over1September2024–23October2026:
460trades,win35%,profit factor1.4336. TP161 trades total+$6,431.6116; SL/BE299
trades total−$4,486.2776. Net+$1,945.334 → balance$2,145.334 from$200. BUY266
trades net+$896.078; SELL194 net+$1,049.256. This is why that particular sequence
was profitable despite many losing/BE trades; it is not a guaranteed expectancy.

Base maxDD34.27%; stress+swap net+$1,471.87/maxDD37.73%; fee+swap raw net
+$1,464.592/maxDD38.67%, cent path+$1,416.994/maxDD38.67%. Maximum losing streak
is11 across these paths; longest completed closing-balance peak recovery is
approximately125.2–130.3days. Neither daily loss2 nor BE eliminates those risks.

One archived BUY reached TP net+$23.8576 after−$0.5674 swap; one SELL hit SL
net−$7.50. Another BUY had SL moved to its entry, but closed at−$0.027 before
swap and−$0.5944 after swap. These are timestamped, hash-verified research ledger
examples, not actual Demo orders on this VM.

All cited economic paths include modeled swap. Historical static long−567.4points
and UTC-midnight rollover assumptions differ from current Demo policy. The
finite5,184-profile domain reused the historical data; no fresh holdout or broker
economic parity is established. COST_INCONCLUSIVE remains. No new economic replay,
annual-return promise or future profitability claim is introduced by this review.

Evidence: [SHA-bound extraction and dated examples](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-26b8-rule-review-2026-10-26/historical-expectancy.json),
[live source/config snapshot](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-26b8-rule-review-2026-10-26/deployed-rule-snapshot.json).

The most material separate decisions for a next version are portfolio-DD policy,
remaining daily-risk budget, swap-aware holding/BE limits, news/shock/sideways
filters, maximum holding duration and a predeclared forward-evaluation endpoint.
None was silently enabled during this review. Verdict: the current rules and
their existing response plans are traceable; an all-situation or guaranteed-profit
readiness claim is not supported.
