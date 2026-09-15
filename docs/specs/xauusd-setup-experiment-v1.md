# XAUUSD Setup Experiment v1 — Mechanical Specification for S1–S4

**Mechanical completion (issue #3):** [`xauusd-s1-s4-mechanical-v1.md`](xauusd-s1-s4-mechanical-v1.md) — decision tables, worked BUY/SELL examples, boundary fixtures, parent coverage matrix.  
**Research handoff (issue #4):** [`xauusd-s1-s4-research-handoff-v1.md`](xauusd-s1-s4-research-handoff-v1.md).

## Problem Statement

ผู้ใช้ต้องการพัฒนา Manual Signal Indicator สำหรับบอกจุดเข้าเทรดเองก่อน และแยกระบบ Automated Trading Strategy สำหรับ bot ไว้ภายหลัง ต้องการเปรียบเทียบ Sweep → MSS → FVG กับ CHOCH, Order Block และ OB∩FVG โดยมีหลักฐาน ไม่เลือกจากความสวยของกราฟหรือ win rate อย่างเดียว

ปัจจุบันมี MSS ที่อิง latest confirmed fractal และ FVG แต่ยังไม่มี protected-swing CHOCH/OB ตามนิยามที่จะทดลอง ระบบเดิมมี partial exit และ breakeven ซึ่งต่างจาก controlled experiment แบบ 2R ข้อมูลย้อนหลังที่ตรวจพบเป็น GC=F H1/M15 ไม่ใช่หลักฐาน XAUUSD M5 ของ broker เป้าหมาย การนำผลเหล่านี้มารวมกันจะทำให้ไม่ทราบว่า logic ใดสร้างผลต่างจริง

## Solution

จัดทำ Strategy Specification v1 แบบ mechanical พร้อม IF/THEN/INVALID semantics, decision tables และ behavioral examples สำหรับ S1–S4 ก่อนแก้ Pine หรือสร้าง execution system แยกข้อเลือกที่ผู้ใช้ยืนยันออกจาก engineering defaults และ gates ที่ยังต้องปิดก่อน empirical experiment

ใช้ H1 bias และ M5 setup เหมือนกันทั้งสี่ candidate เปลี่ยนเฉพาะ structural trigger และ entry zone โดยตรึง exit ที่ 2R ไม่มี partial/BE เก็บระบบเดิมเป็น Legacy Reference แยกรายงาน งาน issue นี้ส่งมอบเอกสารและ acceptance examples ไม่ใช่ implementation ของ detector/backtester หรือผลรับรอง profitability

## User Stories

1. As a manual trader, I want an indicator-first research specification, so that development serves my manual trading workflow before bot automation.
2. As a manual trader, I want Setup Signals distinguished from Orders and Positions, so that a proposed entry is never mistaken for an executed trade.
3. As a strategy owner, I want S1–S4 named and versioned, so that each reported result identifies the rules actually tested.
4. As a strategy owner, I want Legacy Reference isolated from Controlled Baseline, so that changed exits are not attributed to changed structure logic.
5. As a researcher, I want H1 bias and M5 setup timeframes shared across candidates, so that timeframe differences do not confound the comparison.
6. As a researcher, I want identical liquidity pools and session rules, so that candidates search comparable opportunities.
7. As a researcher, I want closed H1 data only, so that an unfinished higher-timeframe candle cannot influence a historical decision.
8. As a researcher, I want pivot occurrence and confirmation times distinguished, so that future candles cannot reveal a swing early.
9. As a strategy owner, I want strict fractal and equal-price rules, so that two implementations identify the same pivots.
10. As a strategy owner, I want mechanical Sweep rules, so that wick rejection is distinguishable from expansion breakout.
11. As a strategy owner, I want deterministic selection when several pools are swept, so that iteration order cannot change the setup.
12. As a strategy owner, I want MSS retained as the S1 trigger, so that the existing concept remains an explicit control.
13. As a strategy owner, I want protected-swing CHOCH distinguished from internal breaks and BOS, so that reversal and continuation events are not mixed.
14. As a strategy owner, I want UNKNOWN structure represented explicitly, so that insufficient structure cannot produce confident CHOCH signals.
15. As a strategy owner, I want protected-swing initialization and recovery documented, so that restarts or replay prefixes do not invent structural state.
16. As a researcher, I want displacement qualification shared across S1–S4, so that structure comparisons do not also change momentum thresholds.
17. As a researcher, I want weak first breaks and consumed levels handled explicitly, so that later candles cannot be relabeled to rescue a failed setup.
18. As a strategy owner, I want exact Sweep-to-break and break-to-FVG windows, so that stale events cannot generate fresh opportunities.
19. As a strategy owner, I want FVG direction, width and confirmation defined, so that the same three candles produce the same zone.
20. As a strategy owner, I want OB selected from a bounded interval, so that an implementation cannot search arbitrarily far backward for a favorable candle.
21. As a strategy owner, I want full High–Low OB bounds and doji exclusion, so that entry geometry is reproducible.
22. As a strategy owner, I want OB∩FVG overlap and minimum width defined, so that S4 has a binary eligibility rule.
23. As a researcher, I want no fallback to a later favorable FVG after the selected zone fails, so that zone selection does not contain hidden optimization.
24. As a manual trader, I want midpoint entry available only after zone confirmation, so that a displayed historical setup was actionable when shown.
25. As a researcher, I want no same-confirmation-bar retroactive fill, so that backtests do not claim orders existed before they were knowable.
26. As a strategy owner, I want True Swing Extremum frozen at the structural trigger, so that later candles cannot move the original invalidation level.
27. As a strategy owner, I want identical structural SL rules and distance caps, so that entry-zone comparisons do not silently change stop policy.
28. As a researcher, I want a full-position 2R target without partial exits or breakeven, so that exit complexity does not obscure the first comparison.
29. As an account owner, I want risk sizing to round down or reject, so that minimum volume never increases risk beyond the configured budget.
30. As a researcher, I want pending expiry, session end and bias-change cancellation specified, so that stale setups cannot be revived.
31. As a researcher, I want one stable identity per setup, so that repeated evaluation cannot count an opportunity more than once.
32. As a researcher, I want separate candidate simulations, so that one candidate cannot consume another candidate's position capacity.
33. As a researcher, I want chronological setup and lifecycle ledgers, so that every summary value can be traced to an event sequence.
34. As a researcher, I want rejected, expired and ambiguous opportunities recorded, so that only favorable executed trades are not selectively reported.
35. As a researcher, I want initial R denominators and execution costs explicit, so that net expectancy is comparable and spread is not deducted twice.
36. As a researcher, I want data provenance and coverage checked, so that futures proxies cannot be presented as broker XAUUSD evidence.
37. As a researcher, I want missing historical news or quote ordering disclosed, so that unknown conditions are not treated as permission or favorable fills.
38. As a researcher, I want dataset splits and evaluation policies frozen before outcomes are inspected, so that out-of-sample data remain meaningfully held out.
39. As a researcher, I want expectancy, drawdown, profit factor and sample sufficiency separated from win rate, so that a visually impressive hit rate is not treated as proof of edge.
40. As a researcher, I want regime, robustness and confluence experiments versioned separately, so that additional filters do not obscure the contribution of core rules.
41. As a maintainer, I want historical replay through the existing backtester/orchestrator to be the main test seam, so that tests verify observable behavior across module boundaries.
42. As a maintainer, I want a small set of detector boundary tests alongside replay tests, so that precise rule failures remain diagnosable without duplicating implementation.
43. As a project owner, I want confirmed choices, proposed defaults and unresolved gates labeled separately, so that publication does not fabricate approval.
44. As a project owner, I want no live orders or Pine changes during this specification task, so that research planning cannot change my trading behavior unexpectedly.

## Implementation Decisions

### Delivery boundary and accepted choices

- Deliver documentation, rule tables, examples and a downstream verification contract only. No production detector, orchestration, notifier, Pine, broker adapter or database changes belong to this issue.
- User explicitly selected: 2R with Legacy Reference retained; H1 bias plus M5 setup; protected-swing CHOCH; midpoint limit entry first; full High–Low OB bounds. User confirmed the replay → setup/lifecycle ledger → summary test seam on 2026-09-16.
- Candidate definitions: S1 = Sweep → MSS → FVG; S2 = Sweep → CHOCH → FVG; S3 = Sweep → CHOCH → OB; S4 = Sweep → CHOCH → OB∩FVG.
- Controlled Baseline uses full-position 2R with no partial exit and no automatic BE. Legacy Reference preserves its existing 50% at 1R, BE and 2.5R runner profile, subject to separate correctness validation. Legacy is not a one-variable comparison against the new baseline.
- Manual Signal Indicator remains the intended first consumer. It owns manual Setup Signals, not broker-confirmed Orders or Positions. Future Automated Trading Strategy remains separate, consistent with the accepted ownership decision.

### Proposed v1 mechanical defaults

These defaults synthesize the preceding plan. They are research definitions, not universal definitions of market structure or independently confirmed optimal trading parameters. Document them as proposed v1 defaults; do not describe every number below as an individually user-approved decision.

1. **Availability and time:** All market timestamps are timezone-aware UTC. Decisions use closed bars only. Preserve event time and available-at time separately. A fractal becomes available only when its second right-hand candle closes; historical pivot location must not make it available earlier.
2. **Swing:** Use strict five-bar fractals, two left and two right candles. Equal highs/lows fail strict comparison. A candle qualifying as both high and low is excluded from structural sequencing to avoid an assumed intrabar order.
3. **H1 bias:** Compare the latest closed H1 Close with its EMA200. Above permits BUY, below permits SELL; equality or insufficient data permits neither. Indicator and replay must eventually share the same initialization and availability contract; do not claim existing parity.
4. **Pools:** Preserve Asian, previous-day and London liquidity sources. Asian interval is 00:00–07:00 UTC and London interval 07:00–12:00 UTC, with exclusive end times. Use session pools only after their interval completes; previous-day pools require a complete eligible prior trading day. Missing coverage is not an empty or fabricated pool.
5. **Sweep:** BUY requires Low below the selected low pool and Close at or above it; SELL requires High above the selected high pool and Close at or below it. Penetration must be greater than zero and at most $8. This close-return rule does not additionally constrain Open. Multiple eligible pools use Asian, previous day, then London priority. A close through the level or penetration greater than $8 is an expansion breakout, not a qualifying Sweep.
6. **MSS:** S1 requires a close beyond the latest available confirmed opposite fractal during bars 1–8 after Sweep. BUY needs a green candle; SELL a red candle. Nonzero range and body/range at least 45% are required. Do not allow pivots confirmed after the candidate break to participate.
7. **CHOCH structure:** Start UNKNOWN. A close-break of a confirmed swing can establish direction only when a confirmed opposite pivot exists between the broken swing and the break candle. Use the latest such opposite pivot as the protected swing. Continuation BOS updates the protected swing using the same rule. Breaking the protected swing is CHOCH; minor internal breaks are not CHOCH. After reversal, use the corresponding eligible opposite pivot for the new protected level; absent a valid pivot, return UNKNOWN. A broken level does not repeatedly create the same structural event.
8. **CHOCH qualification:** For S2–S4 the reversal must occur during bars 1–8 after Sweep, with the same direction, candle-color and body/range qualification as S1. A first structural break failing displacement still changes structure but does not produce an eligible setup; later closes cannot be relabeled as that first break.
9. **FVG:** Bullish zone is the interval from the first candle High to the third candle Low; bearish zone is third candle High to first candle Low. Require directional positive width of at least $0.30. The middle candle must be the structural break candle or one of its next four candles. Select the first qualifying FVG and wait for its third candle to close. Explicitly distinguish this middle-candle window from a third-candle window.
10. **OB:** For BUY choose the latest red candle, and for SELL the latest green candle, from Sweep inclusive to before CHOCH exclusive. Exclude doji. Use its full High–Low interval and freeze at CHOCH confirmation. If no eligible candle exists, S3/S4 have no setup; do not search an earlier interval.
11. **Overlap:** S4 intersects the frozen OB with the first qualifying FVG. Require at least one instrument tick of overlap. Use the midpoint of the intersection. No overlap means no S4 setup; do not select a later FVG merely to make S4 pass.
12. **Entry:** S1/S2 use the FVG midpoint, S3 the OB midpoint, S4 the overlap midpoint. Limit eligibility starts strictly after zone confirmation. No fill may be backdated into the confirmation candle. Zone confirmation is not execution confirmation.
13. **SL:** Freeze True Swing Extremum over Sweep through structural break inclusive. Place SL beyond it with a $0.30 buffer. Entry-to-SL distance must be positive and no greater than $25. Do not shrink SL or round volume up to force admission. The geometric SL buffer is not a substitute for spread/commission modeling.
14. **TP and R:** Target 2R for the entire position, with the initial planned Entry-to-SL distance defining target geometry. Keep initial monetary risk and actual fills in the ledger so costs and price improvement do not silently redefine realized R. No partial exit, trailing or BE in Controlled Baseline.
15. **Pending lifecycle:** Expire 20 minutes after zone confirmation, at session end, on H1 bias invalidation, or if SL is reached before fill. At expiry itself the order is no longer eligible. Setup identity survives repeated evaluations; expired or invalidated opportunities do not become fresh setups without a new originating event.
16. **Session:** New entries are admitted during 07:00–10:30 and 12:30–16:30 UTC, exclusive end times. Existing positions exit at SL, TP or the 20:45 UTC time exit. A missing quote at a deadline must be disclosed, not replaced with an invented executable price.

### Downstream experiment contract, not implementation authorization

- Compare candidates using identical dataset, session, HTF bias, costs, risk and lifecycle policies. Simulate each candidate independently under the same capacity policy rather than allocating shared slots across candidates.
- Store rule version, candidate, source pool and pivot references, event/confirmation times, zone bounds, proposed Entry/SL/TP, actual simulated lifecycle and reject/expiry reasons. Retain non-trade outcomes as well as fills.
- Trade reporting should support net R, net PnL, fees, spread/slippage assumptions, session, direction, MAE/MFE and regime/news metadata when available. Missing fields remain unknown. Screenshots are optional supporting references, not evidence replacing timestamped records.
- Risk target is 0.5%, with volume floored to valid increments and rejection when minimum volume exceeds budget. Operational risk controls remain binding; their exact research profile must be frozen before a later comparison, not silently inherited from whichever runner happens to be called.
- Actual XAUUSD M5/H1 and execution-data provenance must be verified before qualifying results. Existing GC=F M15-as-M5 output is diagnostic only. Missing news history or bid/ask evidence cannot silently become no-news or zero-cost assumptions.
- Dataset date range, chronological development/validation/OOS split, statistical tests, sample-sufficiency policy and stress magnitudes remain a pre-run registration gate. The discussed 3–5 years and 60/20/20 split are framework proposals, not verified available data or frozen dates.
- Preserve existing profitability-qualification requirements unless a separately recorded decision supersedes them. This research spec does not automatically replace evaluator ownership, whole-account protection or forward-demo gates.

## Testing Decisions

### Confirmed main seam

The user confirmed historical replay → setup/lifecycle ledger → summary using the existing backtester and StrategyOrchestrator, with focused detector boundary tests only where necessary. Reuse this highest practical seam; avoid a new parallel execution simulator whose behavior can diverge from orchestration.

Good tests assert observable signals, rejection reasons, available-at times, lifecycle sequence, cash/risk conservation and summaries. They must not merely assert that source strings, method names or private implementation steps exist. Mock broker side effects at the boundary; do not mock away the detector whose behavior is under evaluation.

Prior art includes existing replay tests for filled-volume accounting, fill-and-stop on the same bar, closed H1/fractal visibility, and detector integration tests for sessions, H1 bias and sweep/breakout boundaries. Existing SL-first OHLC tests demonstrate a conservative convention, not verified intrabar ordering. Future experiment results must label ambiguity even when a conservative diagnostic estimate is also shown.

### Required acceptance examples in this documentation task

Provide compact timestamped price/pivot fixtures, expected decisions and reasons for the following; executable test implementation is downstream work:

1. Valid BUY and SELL for every candidate, including their zone bounds, confirmation time, planned Entry/SL/TP and first eligible fill time.
2. BOS versus protected-swing CHOCH versus an internal break; UNKNOWN initialization and recovery with and without an eligible opposite pivot.
3. Pivot not yet confirmed, equal highs/lows, dual high/low pivots and multiple eligible protected-pivot candidates.
4. H1 equality, insufficient warm-up and unfinished H1 candle; neither unfinished nor future data affects a prior setup.
5. Prefix replay and future append/mutation preserve all decisions already available at the cutoff.
6. Sweep with exact pool close, zero penetration, $8 penetration, greater-than-$8 penetration and several pools on one candle.
7. Break on bars 1 and 8 versus bars 0 and 9; correct candle color, exactly 45% body, below 45% and zero-range candles.
8. Weak first CHOCH changes structure without qualifying a setup; a later candle cannot retroactively qualify it.
9. Bullish and bearish FVG orientation, gap exactly $0.30, narrower gap, middle-candle window endpoints and delayed third-candle availability.
10. OB selection includes Sweep but excludes the CHOCH candle; latest eligible opposite candle wins; doji and absent OB produce explicit no-setup results.
11. S4 zero overlap, less than one tick, exactly one tick and overlapping bounds with midpoint different from either source-zone midpoint.
12. First FVG has no OB overlap but a later FVG does; S4 must not substitute the later zone.
13. Frozen True Swing Extremum, both SL directions, nonpositive distance, exact $25 cap and a distance above the cap.
14. Limit touched before confirmation does not create a retroactive fill; pending starts only after its zone is known.
15. TTL at 20 minutes, session endpoints, H1 bias change, SL before fill and a missing quote at the time-exit deadline.
16. Duplicate evaluation and restart from the same history do not create a second setup identity or revive an expired setup.
17. Simulated fills and immediate exits remain in the ledger and summary; SL/TP touches without ordering evidence produce an AMBIGUOUS flag, not an invented favorable path.
18. Initial risk denominator remains fixed; costs are charged once, not hidden inside both spread and an additional duplicate fee.
19. Minimum lot exceeds budget: reject. Valid volume floors: actual configured risk is not exceeded. Existing positions are never resized upward to fit a nominal target.
20. Missing pool coverage, unknown news, proxy instrument, malformed timestamps and missing quote ordering are distinguishable from ordinary no-setup outcomes.
21. Candidate simulations cannot consume each other's slots; Legacy results remain separately labeled and cannot be treated as a single-variable structure comparison.

### Completion and verification

- The specification is complete as a documentation artifact when accepted decisions, proposed defaults, downstream gates and all required examples are explicit and internally consistent.
- A later agent must create failing observable reproductions before changing production behavior, then use repository unittest conventions. Publishing this issue is not evidence those tests were written or passed.
- No unit-test, Pine compilation, broker verification or profitability success is claimed by this documentation task.

## Out of Scope

- Implementing or changing Pine, EA, Python detection, orchestrator, execution adapters, API contracts or database schemas in this issue.
- Running a new comparative profitability experiment before the specification, data and evaluation gates are resolved.
- Bot execution, live orders, deployment, broker connectivity changes, secrets, production permissions and real-money trials.
- TSS/GSS comparison, confluence filters, rejection entries, parameter optimization, regime routing, Fibonacci/OTE filters and additional strategy families in the initial S1–S4 specification.
- Treating proxy data as broker XAUUSD evidence, promising profit, assuming win rate alone proves edge or lowering risk safeguards to obtain more trades.
- Rewriting existing ADR history or silently replacing existing profitability and operational safety policies.

## Further Notes

- Related foundation work: https://github.com/Piti9427/XAUUSD_Scalper/issues/1. This issue introduces a bounded research specification for manual-indicator development; it does not extend the foundation's execution authorization. OB was outside that earlier foundation scope and is now an explicitly separate research candidate.
- Research scope differs from the older liquidity-target baseline and the current partial-exit runner. Preserve those distinctions rather than suggesting all three are the same strategy.
- Evidence refreshed during this synthesis: GitHub tracker and ready-for-agent label exist; current replay and detector test seams exist; the local worktree already contains unrelated or preceding Pine/documentation changes that this task must preserve.
- Before an empirical experiment, resolve remaining execution-level choices in a versioned run manifest: feed/quote sides, tick rounding, gap and stale-data policy, order-marketability and pre-confirmation zone-touch handling, sweep replacement/consumption, capacity and daily-risk gates, historical news policy, exact data splits and statistical comparison protocol. Do not choose these after viewing candidate performance.
- The supplied framework's numerical performance tables are examples, not measured results. Trade-count thresholds are policies to register, not automatic proof of sufficient evidence. Sequence randomization and resampling policy must be explicit; this issue does not claim Monte Carlo proves profitability or risk of ruin.
- The ready-for-agent label authorizes work within this documentation scope and its gates only. It does not mean trading rules are implemented, data are sufficient, the statistical protocol is frozen, or the system is ready for capital.
- Synthesis date: 2026-09-16. Publication records the conversation and accepted seam; it is not a readiness certificate.
