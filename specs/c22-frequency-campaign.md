# C22 frequency research campaign (owner approved 2026-10-06)

Research only. Retrospective reused discovery; COST_INCONCLUSIVE. No Demo,
real-money, broker parity, stop-out parity or untouched validation qualification.
Preserve frozen sources and Demo section6.33. Commit only this task, no push.

## Gates and accounting

Each candidate must pass both base+swap and stress+swap: net >0 and >= C22 H4EMA200
baseline on identical data; every-tick equity DD <=40%; mean >=15 entries per full
UTC calendar month including warmup/zero months; positive equity throughout and
no bankruptcy. USD200 once, fixed0.01, single position, cost-inclusive initial
SL admission cap <=10%, no deposits/recovery/martingale. Terminal30days with no
position/execution and nonempty admissions all rejected risk_cap fails. No-signal
and mixed reasons reported separately, not proof of future tradability.

Use quoted Bid/Ask from2024-09 through requested present; check archive and fetch
current month in new campaign. Record requested end and actual last quote; never
fill gaps. Oldest-directory claims require evidence; start date is fixed scope.
Continuous equity/peak/indicators/daily state across all years/months. Completed
UTC M15 from all15 M1, canonical closed H4. Base actual spread; stress +0.20 USD/oz
spread and adverse0.10 USD/oz slippage. Pin commission/swap metadata; missing or
unsupported swap BLOCKED. Initial cap excludes future swap reserve; gaps/swap
can exceed initial loss cap; BE can close net negative.

Cost proxy=(quoted spread proxy+modeled slippage+commission-signed swap)/trades.
Replay quote proxy already contains stressed widening; no double spread charge,
no additional subtraction from net. Debit/credit separately. WR/RR, monthly/yearly
realized net and cost/risk are diagnostics only.

## Search

Strict research challenger adapter validates all keys, maps BUY EMA to
candidate_frame.oscillator_spec.trend_span before raw signal and H4 filtering.
Separate H4 warmup, incomplete H4, directional mismatch diagnostics. Retain ATR14,
archived RSI semantics, SELL precedence, rounded fill/BE math and position management.

Ordered domains:
RSI7/14/21; cross25/30/35; BUY EMA50+slope/off; SELL Donchian24/48/96;
SELL EMAoff/50/200+slope; H4 EMA200/100/off; BUY SL1/1.5/2/2.5ATR;
BUY TP1.35/1.5/2R; BUY protection off/BE1R; SELL SL1.5/2/2.5ATR;
SELL TPatr3/1.35R/2R; SELL protection off/BE1R; daily10/20%; losing exits1/2/unlimited;
cooldown0/2/4bars; all/avoid21–24UTC entries; static/drawdown_steps cap<=10%.

Verify full frozen baseline swap results first, then latest-input baseline.
First round all one-parameter neighbors. Subsequent rounds expand top3 unexpanded
configs, changing one parameter cumulatively. Behavioral config deduplication.
Freeze each round before results; always both scenarios. Stop at300 unique
challenger variants (baseline separate) or exhaustion, never at first winner.
Final truncation frozen parent rank/parameter/value order.
Search rank: both survival passes, count of scenario hard gates passed, maximum
frequency shortfall, minimum scenario net descending, maximum DD ascending, ID.
Winner rank: minimum scenario net descending, maximum DD ascending, maximum
scenario per-trade cost proxy ascending, maximum mean admitted risk% ascending, ID.
The max aggregation for shortfall/cost/risk is conservative across two views.

## Verification and delivery

TDD seams: adapter, qualification, monthly count, cost attribution, resume.
Tests: baseline parity; signal changes; unknown keys; causal future invariance;
H4 unavailable; UTC midnight; swap/triple; BE negative net; floating DD; cap/fixed lot.
Per cell: full ledger/admission/rejection events/DD witnesses; independent
cash/risk/non-overlap checks. Baseline and top5 qualified candidates fresh replay
both views must match complete result, else BLOCKED/no winner.
Lock/checkpoint/resume; machine files runs/ only; summary docs/reviews/*.md.
Focused tests, repo typecheck if configured, final unittest discover, two-axis
code-review, final diff review and scoped commit. No gate relaxation if no winner.
