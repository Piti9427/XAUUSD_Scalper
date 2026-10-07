# PRD — Finalize B1 for Standard Demo

**Date:** 2026-09-27
**Status:** ready-for-agent — scope and ticket breakdown approved
**Target:** locked test account `Standard_demo_100` (Standard Demo in the private `.env`; broker display name `Standard_demo_100$`)
**Delivery:** executable MQL5 EA, MT5 Tester evidence, frozen release package
**Trading authorization:** this document does not enable Demo orders or authorize real-money trading.

## Problem Statement

ผู้ใช้ต้องการปิดงาน B1 ที่มีอยู่ให้ใช้งานได้จริง ไม่ต้องการหา strategy ใหม่เพิ่ม ปัจจุบันมี frozen contract, Python reference และ MQL5 parity probe แต่ยังไม่มี B1 EA ที่พิสูจน์ครบตั้งแต่รับ market data, ตรวจ signal, คำนวณ risk, ส่งคำสั่ง, reconcile broker, กู้คืนหลัง restart และแจ้งผล execution

ผลย้อนหลังบางช่วงเป็นบวก แต่ research model และ executable reference มีความต่างด้าน indicator seed, signal expiry และ HWM sampling ขณะเดียวกันผล replay ที่บันทึกไว้บน Standard Demo symbol ปฏิเสธการเปิดไม้เพราะ minimum-lot risk เกิน budget ทั้งใน scenario $100 และ snapshot Demo เดิม การปรับ exit อย่างเดียวไม่แก้ sizing constraint

ดังนั้นคำว่า final ต้องแยก implementation correctness, strategy validation และ target-account feasibility ไม่ใช้คำว่า build เสร็จแทนหลักฐานว่าบัญชีเปิดเทรดได้หรือ strategy ทำกำไร

## Solution

ต่อ deterministic B1 core เป็น executable MQL5 EA พร้อม durable execution state และ broker-confirmed lifecycle ใช้ Standard Demo ตาม local configuration เป็นบัญชีเป้าหมาย ยกเลิกเส้นทาง Standard Cent และการเลือก broker ใหม่

คง entry, initial stop geometry, target และ risk policy ของ B1 เดิม ตรวจ cost-covering stop หลัง +2R เป็น exit adjustment เพียงแบบเดียวก่อนตรึง final release หากไม่ชนะ baseline ตามเกณฑ์ที่ตกลง ให้ final implementation คง fixed exit เดิม หากบัญชีไม่รองรับ volume ภายใต้ risk cap ให้รายงาน ACCOUNT_BLOCKED ไม่บังคับเปิดไม้

## User Stories

1. As a Trader, I want the existing B1 strategy completed, so that I can use a finished implementation instead of starting another strategy search.
2. As an Operator, I want the configured Standard Demo identity verified, so that execution cannot target the wrong account.
3. As an Operator, I want account mode and symbol verified before execution, so that unexpected broker conditions block new risk.
4. As a Trader, I want actual Demo equity separated from the simulated $100 deposit, so that research inputs cannot silently override broker balance.
5. As a Trader, I want lot sizing based on broker profit calculations, so that nominal stop risk stays within the selected risk tier.
6. As a Trader, I want below-minimum volume rejected explicitly, so that a small account cannot be over-risked by rounding upward.
7. As an Auditor, I want every rejection logged with its budget and minimum-lot risk, so that zero trades have an explainable cause.
8. As a Trader, I want completed-bar B1 signals matched against the reference, so that implementation changes do not alter entry rules.
9. As an Auditor, I want timestamps recorded in UTC, so that data, signals and broker events can be reconciled.
10. As an Operator, I want indicator seed and warmup preserved across restart, so that restart cannot change future signals.
11. As a Trader, I want stale signals expired, so that a missed entry cannot turn into a late trade.
12. As a Trader, I want market entry and exits to use the executable Bid/Ask side, so that simulated fills reflect trading costs.
13. As a Trader, I want protective SL and TP attached to each entry, so that a successful fill is not left unmanaged.
14. As an Operator, I want actual fill volume and risk reconciled, so that partial fills and slippage do not bypass protection.
15. As an Operator, I want ambiguous requests reconciled before retry, so that timeouts cannot create duplicate trades.
16. As an Operator, I want duplicate instances blocked, so that two processes cannot manage the same strategy exposure.
17. As a Trader, I want foreign positions left untouched, so that the bot cannot close another strategy's trades.
18. As a Trader, I want equity-HWM risk tiers applied on actual ticks, so that drawdown changes admission immediately.
19. As an Operator, I want HWM and hard-stop state persisted, so that restart cannot erase drawdown or increase risk.
20. As an Operator, I want corrupted state to block new entries, so that missing evidence cannot reset protection.
21. As a Trader, I want cost-covering SL considered after +2R, so that profitable excursions can be protected without changing initial risk.
22. As a Trader, I want SL movement considered complete only after broker confirmation, so that rejected modifications are not presented as protection.
23. As an Auditor, I want saved losers and displaced winners reported together, so that exit benefits are not overstated.
24. As a Trader, I want net profit prioritized over win rate, so that shorter exits are not selected merely for more wins.
25. As an Operator, I want alerts generated from broker-confirmed events, so that rejected signals cannot appear as executed trades.
26. As an Operator, I want notification outages isolated from position management, so that messaging cannot interrupt protection.
27. As an Auditor, I want real-tick Tester reports and trade reconciliation, so that compilation is not mistaken for execution validation.
28. As an Operator, I want exact build and configuration hashes frozen, so that the tested release is the one later considered for deployment.
29. As a Trader, I want account feasibility, implementation readiness and profitability reported separately, so that the final verdict is actionable.
30. As an Operator, I want a start, stop and recovery runbook, so that the finished system can be operated consistently.

## Implementation Decisions

### Strategy and release identity

- Reuse the deterministic B1 detector and MQL5 indicator core. Preserve the original frozen version and its evidence.
- Baseline: completed Bid M15 bars, previous 30-bar Donchian channel excluding signal bar, RSI14 long <=75 / short >=25, ATR14 initial SL 2.5ATR, quote-anchored TP 3.5R, maximum one position.
- Indicators use arithmetic seed followed by Wilder recursion, the existing first-delta/true-range conventions and at least 100 completed bars. Seed identity and checkpoint survive restart; rolling-history reseeding is not equivalent.
- B1-FINAL-v1.1 names the +2R cost-covering exit variant. No partial close, trailing, grid, Martingale, additional indicator, direction filter or session filter is added.
- The final release chooses the exit before deployment. Runtime never switches strategies automatically based on recent PnL.

### Account, capital and architecture

- The locked test account is `Standard_demo_100`: the Standard Demo whose credentials are only in the private `.env`. Broker display name is `Standard_demo_100$`. Standard Cent and the previous ~$1,173.46 Demo are superseded for new target-account work.
- Verify expected login/server locally, Demo trade mode, hedging mode, exact symbol and current specification. Account identity and secrets stay out of published documentation and artifacts intended for sharing. A 2026-09-27 04:32 UTC read-only probe matched this identity: Demo, hedging, USD, leverage 1:1000, equity and free margin 100.00, floating PnL 0, symbol `XAUUSDm`, no exposure. Refresh that snapshot before treating equity as still $100.
- The known target symbol is XAUUSDm; confirm it from the target account rather than substituting another gold symbol. Configuration currently identifies credentials but is not proof of successful connection or current broker identity.
- Use this account's actual broker equity for account-constrained scenarios. New target-account Tester deposits use that equity in whole dollars (100 on the 2026-09-27 snapshot). The labelled hypothetical $100 deposit stays a separate research label and must not overwrite a later broker balance. Never change broker balance, deposit or risk to manufacture trades.
- Implement the B1 Tester EA as a separate path. Existing SMC Python Demo Execution Path remains governed by its accepted architecture decision; no replacement or second concurrent trading owner is deployed through this PRD.
- Default executable order mode is Strategy Tester only. Any later Demo activation requires its documented qualification gates and a separately authorized activation. Real-account order sending remains disabled.

### Timing and execution

- Process each completed M15 signal once. Entry is the first valid tick in the immediately next M15 interval; after expiry, discard the signal.
- Keep market timestamps UTC. Verify broker timezone/offset and M15 alignment; unavailable or inconsistent mapping blocks new entries.
- BUY enters Ask and exits against Bid; SELL enters Bid and exits against Ask. Initial SL/TP remain quote-anchored; actual fill never silently re-anchors them.
- Read broker volume, tick, stop, freeze, filling and margin properties. Size through broker profit/margin calculations, reserve known costs, floor volume and recheck budget before order submission.
- Use a durable deterministic signal/request identity before sending. Broker confirmation, not the return from a send call alone, establishes fill/position state.
- Reconcile actual fill and volume. Keep accepted partial volume; do not automatically top up a remainder. Reconcile any outstanding remainder before admitting new risk.
- Ambiguous timeout does not permit blind resubmission. A definitively rejected request ends that signal's entry attempt; no automatic entry retry is introduced in this release.
- If actual fill lacks protective SL or nominal stop risk plus known cost reserve exceeds its budget, close only owned B1 exposure and latch incident halt. A failed close remains an unresolved critical incident; continue protection/reconciliation and block new entries.

### Drawdown, recovery and exit adjustment

- Equity-HWM risk tiers: DD <3% -> 1%; <6% -> 0.75%; <9% -> 0.5%; <12% -> 0.25%. DD >=12% latches STOP_NEW_ENTRIES without panic-closing an otherwise protected position. Daily hard stop remains disabled; -2R/-3R daily telemetry is informational.
- Persist HWM, halt flags, processed bar/signal IDs, pending request identity, position identity, indicator checkpoint and exit state atomically with integrity checks. Broker state controls current exposure; it must not erase a valid persisted HWM. Corruption or missing historical HWM blocks new entries rather than resetting it.
- Enforce one deployment owner per account/symbol/magic/version. Foreign exposure on the target symbol blocks new B1 risk; the bot never closes foreign positions.
- After confirmed fill, freeze actual entry and its distance to the original normalized SL as position R. Log intended quote R separately; mirror this distinction in the reference comparison.
- Trigger the new exit at executable-side +2R from actual entry. Preserve original TP; request one stop modification to cover paid entry commission, configured exit-fee reserve and signed swap accrued at trigger time. Spread is already represented by Bid/Ask and is not added twice.
- Solve the stop using profit calculation in account currency; round toward sufficient cost coverage on the tick grid. Unknown required cost inputs block this exit profile's promotion; zero-cost assumptions must be explicitly labelled as test scenarios.
- Modification is monotonic and targeted. Check stop/freeze geometry, retain the old stop until confirmation and persist requested/confirmed/rejected outcomes. A definitive rejection ends the one-shot modification attempt; an ambiguous outcome must be reconciled.
- Cost coverage is an estimate at trigger time, not a guarantee of net breakeven after subsequent swap, gaps or slippage.

### Execution events and final selection

- Emit durable broker-confirmed fill, modification and close events; emit rejected/unknown requests as diagnostic events, never executed-trade cards.
- Notification consumption is idempotent for acknowledged event IDs. Persist uncertain delivery outcomes; Telegram timeout cannot guarantee exactly-once external delivery and must not affect execution.
- Compare fixed exit, entry-price BE at +2R and cost-covering BE at +2R on the same full event stream. Each replay includes changed exits, subsequent entries and continuous risk state.
- Apply the accepted profit-first gate at both 0.10R and 0.20R sensitivity reserves on top of disclosed spread/cost assumptions: total net R and portfolio return exceed baseline, expectancy >0, PF >1, tick-equity DD no worse than baseline and <12%, no hard stop, positive relative performance in at least two of three chronological blocks.
- Stress spread x2 around midpoint, 2-second modification delay, adverse entry/stop/end-mark fill of $0.10 per oz, and the combined scenario. Apply the same assumptions to each arm; stress promotion also requires positive net profit above baseline and the agreed DD limits.
- If the exit does not pass, keep it disabled and freeze the fixed-exit build. The control is not promoted as a hindsight replacement. Baseline profitability failure or lack of executable trades keeps strategy/account qualification NO-GO even when implementation tests pass.

## Testing Decisions

- Test externally observable decisions, broker requests, confirmed lifecycle, equity/risk behavior and alerts. Helper-only assertions do not prove the full path.
- Prefer existing account-preflight, B1 reference comparator, broker-adapter lifecycle and notifier seams. Introduce only the B1 market-entry and state/recovery interfaces required by the EA.
- Prior art includes deterministic B1 indicator/risk/tick-replay tests, SMC adapter execution/reconciliation tests, lifecycle notification policy tests and restart/idempotency checks.
- Verify account mismatch, real-account rejection, hedging requirements, unknown specifications, foreign exposure, insufficient margin, minimum-lot rejection and normalized budget checks without sending account orders.
- Reference/MQL5 indicator tolerance is <=1e-8; signal timestamps/directions match 100%. Intended price levels match the broker grid; unexplained extra/missing signals or trades fail validation.
- Use deterministic scenarios to exercise complete BUY/SELL, TP/SL, gap, duplicate signal, timeout-after-fill, partial fill, corrupted state and concurrent-owner behavior. Such fixtures establish implementation behavior, not historical profitability.
- Test +2R triggers, both quote sides, modification latency/rejection, TP during pending modification, commission/swap treatment and restart before/after confirmation.
- Test HWM boundaries and hard-stop latching with intratrade equity marks, recovery, and restart. Unknown/corrupted state must not restore a higher tier.
- Test broker event -> durable outbox -> notification sink, duplicate replay, uncertain delivery and messaging failure without contacting real recipients.
- Compile the EA and execute MT5 Every tick based on real ticks; preserve actual Tester report, deals and reference reconciliation. Compilation alone is insufficient.
- Historical capture scoring: May 14–September 25, 2026, with May 7–13 warmup. Report May 14–June, July–August and September 1–25 while carrying equity, HWM and positions continuously. Attribute block results through boundary equity including floating PnL.
- Audit dataset/spec/build/config hashes, UTC coverage and PnL reconciliation. Exposed historical periods are retrospective validation, not untouched OOS.
- Run the repository unit-test command and final diff checks when implementation changes land. Documentation-only creation requires link/dependency/content checks rather than trading tests.

## Out of Scope

- New strategy discovery, broad parameter sweeps, additional indicators, shortened stops to force lots, higher risk, Martingale or grid.
- Standard Cent, alternative broker selection, account creation, funding changes and secret rotation.
- Starting live monitoring, sending Demo/real orders, publishing Telegram messages or replacing the existing SMC runtime during documentation or automated tests.
- Claiming generic cost reserves are measured broker costs, fractional sizing is executable sizing, or old exposed data is untouched OOS.
- Automatically relaxing acceptance gates or changing the final exit after results are known.

## Further Notes

- The approved scope is local Markdown PRD and eight dependency-linked tickets. No GitHub issue publication is included in this document-writing step.
- ready-for-agent means work may start within the ticket scope and its gates; it does not imply profitability, account feasibility or trading activation.
- The implementation build, exit-selection result, target-account feasibility and deployment qualification receive separate verdicts. An honest final result can be IMPLEMENTATION_VERIFIED with ACCOUNT_BLOCKED or STRATEGY_NO_GO.
- Existing historical zero-trade results remain negative feasibility evidence. Refresh the Standard Demo snapshot before making current-account claims; configuration presence alone is insufficient.
- Later deployment qualification retains independently measured costs, non-overlapping post-freeze OOS >=100 closed trades, broker-ledger Monte Carlo >=50,000 paths, and Demo forward evidence >=8 weeks AND >=50 closed trades. This PRD does not declare those gates completed or require waiting for them to finish implementation.
- No account identifiers, credentials or sensitive raw broker errors belong in shared reports. Keep private account linkage local and publish sanitized evidence.
