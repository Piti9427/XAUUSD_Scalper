# C22 risk closure: verified12-profile result

**Completed offline research. Native26b8 remains the profit winner within the
confirmed12-profile matrix. No tested changed-policy profile both preserves
matched native profit and strictly improves the observed risk outcomes. The
running Demo remains unchanged.** This is a bounded comparison on exposed
historical data,not an all-strategy optimum or future-profit qualification.

## Scope and evidence

Owner confirmed D1 prospective daily10% SL budget,P1 prospective equity-DD40%
budget,a separate minimum24hour resume candidate and B1 accrued-cost Net BE at
the first successful adjustment. The12 profiles enumerate D1/P1/B1 on/off,with
an additional24hour pause variant for each P1-enabled combination. Native signals,
fixed0.01,SL2.5ATR,BUY TP3R,SELL TP1.35R,native1R/M15 activation,loss2 and native
30minute cooldown remain fixed. No future-holding reserve or forced-close policy
was added.

Each profile ran base/stress/fee plus modeled swap under raw and cent loss-flag
conventions:72 matched paths. Six fresh repeats of the selected profit profile
also pass. Overlay-off reproduces the complete original native result in all6
paths,including ledger,equity,cost and rejection records. Distinct new identities
bind the native Rules and risk overlay rather than reusing a changed26b8 Rules ID.

Source input is the same hashed Exness Bid/Ask tape as the completed campaign:
171,171,013 quotes,first1September2024 22:05:06.129UTC through last23October2026
20:57:59.517UTC. Requested independent-account window is1September2024 through
24October2026 exclusive,initial$200,no top-ups. Complete causal M15 and closed-H4
signal preparation are reused. This does not add26October forward data or a new
holdout. Quotes/graphs/results are backed by saved source artifacts,not invented
returns or candle assumptions replacing the tape.

Protocol binds110 source files,including the unchanged101 frozen parent pins,
new implementation/tests/spec and parent proof/input/cost hashes. Independent
audit PASS covers all72 raw/cent paths,26,308 closed-position records across those
reused paths,full-tick equity DD/minimum/HWM for each path,prospective budgets,
pause state,Net BE costs/rounding/first adjustment,and6 exact fresh repeats.

## Matched results and decisions

The interactive
[Matrix](/Users/nopparuj/.cursor/projects/Users-nopparuj-my-agents-XAUUSD-Scalper/canvases/C22-risk-closure-2026-10-26.canvas.tsx)
contains all12 profiles and6 matched views,qualification status,net/final equity,
DD,streak,minimum equity,completed/ongoing recovery,policy rejection counts and
actual sampled equity checkpoints. The table can switch cost/accounting views;
select a row to compare its curve with native26b8. Chart lines join sampled
recorded checkpoints; exact DD/minimum are independently audited on the full tape.

Native26b8 base+swap: net+$1,945.334,final$2,145.334,DD34.2750%,460 trades.
Worst DD across all6 paths is38.6710%;stress net+$1,471.870 and fee-cent
net+$1,416.994. Base minimum equity is$187.6636;worst matched minimum is$146.481.
Worst completed closing-balance recovery is130.30days;ongoing closing drawdown
age is60.78days at the final quote. These are closing-balance recovery metrics,
not continuous tick-equity underwater duration.

**B1 only: risk reduction costs base profit.** Base net+$1,722.4984,DD32.4069%,
462 trades. Versus native:base net falls$222.8356,about11.45%,while base DD falls
1.8681percentage points. Worst6-path DD falls from38.6710% to37.4692%. Stress
net rises only$2.1276;fee-raw rises$2.1926 and fee-cent rises$2.7806. The minimum
equity and longest completed/ongoing recovery are unchanged in the matched views.
Base worst loss-run severity improves17.6910%→16.9541%,but the11-trade raw-net
loss streak remains. The base path records196 first successful Net BE adjustments.
This is a useful separately identified risk/profit trade-off,not the owner's
profit-maximizing replacement.

**D1 only: a smaller daily entry budget did not improve whole-path risk.** Base
net+$1,760.144,DD34.9368%. It rejects8 planned entries in base and23 in stress/fee.
Worst6-path DD reaches40.7161%,minimum$121.9544 and completed recovery155.62days.
It fails the unchanged40% research gate. Rejecting a trade changes later equity,
daily counts,cooldown and eligibility;subtracting a few losing trades from the
old ledger would have concealed this result.

**P1 and pause24h without D1: no empirical benefit in this sample.** P1 alone and
P1+pause24h exactly match native economics because no DD-budget rejection occurs
on those paths. Likewise P1+B1 variants match B1. Their pure/public replay tests
exercise real policy transitions,but unchanged historical outcomes do not prove
future efficacy of an untriggered guard. Baseline wins exact economic ties to
avoid claiming a new profit improvement from unused added logic.

**D1+B1: smaller base DD,but worse broader downside than B1.** Base net
+$1,709.4814,DD33.2045%;worst6-path DD38.8065%,minimum$123.7174 and completed
recovery151.36days. It passes the old qualification floors,which are lower than
the selected26b8 profit,but it does not match selected native profit or dominate
B1's major outcomes. Passing an old floor is not evidence of an improvement.

**D1+P1,with/without B1 and24h: prolonged stopped paths.** In the D1+P1+pause24h
stress path,new admissions first pause14January2025 18:30UTC. They do not resume
before the last quote because planned fixed0.01 risk never fits the unchanged
equity-peak budget. Stress ends at$125.1358(net−$74.8642);fee ends$123.0518
(net−$76.9482),with40 trades. Adding B1 to that combination permits one early
resume and then another pause;stress/fee end around$122 with41 trades. Worst
closing drawdown age reaches782.87days. This is a censored recovery age from its
recorded closing peak,not a claim the entire interval was the24hour pause.
All such combined profiles fail positive-profit/original matched profit gates.
The timer never resets equity peaks or manufactures funds to make recovery pass.

Seven of12 profiles meet all unchanged qualification gates;five fail. Among
qualified profiles,the declared raw-base profit,raw-stress profit and worst-DD
rank selects Native26b8. No positive-profit or DD gate was moved after results.
The separate matched-current-native comparison finds no strict improvement that
preserves all base/stress raw/cent profit while reducing actual downside.

## Engineering closure and limits

New research modules are
[policy](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/c22_risk_policy.py),
[versioned event loop](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/c22_risk_replay.py),
[campaign](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/c22_risk_campaign.py),
[independent verifier](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/c22_risk_verify.py).
The old replay lacks policy hooks,so the new loop is an explicit narrow fork with
overlay-off parity,not a monkeypatch of frozen sources. Completed cells and audit
records have source/payload/proof hashes and atomic checkpoints. A cell resumes
only after it is completely saved;no mid-cell account/HWM restart is claimed.

All26 new pure-policy/public replay tests pass. Full repository suite:
1,263tests/198.704seconds,OK,2existing skips. Scoped Ruff and compilation pass.
Independent audit-cache resume/tamper checks and D1/B1 full-tick synthetic verifier
checks pass. Managed Canvas strict TypeScript check has0diagnostics. A local
sandbox denied optional process inspection after launch;the exclusive campaign
lock,checkpoint progress,full72-cell completion and actual audit were verified
without launching a duplicate. This did not affect the saved economic evidence.

Requirement-to-test evidence:

- “กันงบ SL ก่อนเปิดเพิ่ม โดยไม่เปลี่ยนกฎปิดไม้เดิม”:
  test_daily_reserved_sl_blocks_a_second_trade_while_native_cap_still_passes.
- “หยุดเปิดเพิ่มก่อนความเสี่ยงถึง DD40%”:
  test_dd_budget_uses_full_tick_floating_peak_not_only_closed_balances;
  test_drawdown_budget_uses_equity_high_water_and_rejects_exact_floor.
- “เพิ่มพักอย่างน้อย24ชั่วโมง แล้วจึงตรวจว่าสัญญาณและงบความเสี่ยงผ่านครบ”:
  test_public_replay_pause_24h_keeps_peak_and_waits_for_fresh_budget_passing_signal;
  test_exact_24_hour_boundary_requires_new_signal_and_all_budgets.
- “Net BE ณครั้งแรกที่เลื่อน SL ก่อน”:
  test_net_be_covers_accrued_debit_once_and_later_rollover_can_still_lose;
  test_positive_swap_does_not_change_original_one_r_activation.

Tests:
[pure policy](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/research/test_c22_risk_policy.py),
[public replay](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/research/test_c22_risk_replay.py).

Research admission budgets are not realized-loss guarantees through gaps or
outages. Net BE covers signed modeled accrued swap at its first successful
adjustment,not future rollover costs. All historical swap rates/calendar remain
declared snapshot assumptions,not independently proven historical broker charges
or account swap-free entitlement. COST_INCONCLUSIVE remains. Exposed-history
tuning creates selection bias;72 cost/accounting paths are not72 independent
market samples. New risk policies have not been integrated into a broker sender,
forward-tested or given a production cashflow/high-water lifecycle.

**Verdict: retain current Demo26b8; keep B1 as a documented lower-DD/lower-base-profit
research alternative. Do not promote D1 or stopped combined policies under the
owner's existing profit/DD goals. The agreed12-profile experiment is complete.**

Reproducible evidence:
[protocol](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-risk-closure-2026-10-26/protocol.json),
[all72 cells and6 repeats](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-risk-closure-2026-10-26/COMPLETE.json),
[independent PASS](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-risk-closure-2026-10-26/independent-verification.json),
[Matrix JSON](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-risk-closure-2026-10-26/matrix.json),
[full test log](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-risk-closure-2026-10-26/full-unittest.log).
