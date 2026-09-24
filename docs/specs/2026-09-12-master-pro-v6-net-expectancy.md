# SPEC: Master Pro v6 — Simulation ที่เชื่อถือได้ และวัด Net Expectancy ได้จริง

> วันที่: 2026-09-12
> Source plan: [improvement plan](../plans/2026-09-12-master-pro-v6-improvement-plan.md)
> Source review: [Master Pro v6 logic review](../reviews/2026-09-12-master-pro-v6-logic-review.md)
> Primary artifact: [xauusd_master_pro_v6.pine](../../tradingview/xauusd_master_pro_v6.pine)
> Tickets: `.scratch/master-pro-v6/issues/`
> Status: ready-for-agent

## Problem Statement

ผมมีสคริปต์ Master Pro v6 บน TradingView ที่โฆษณาว่าพร้อมใช้จริงและ win rate สูง แต่ผมยังไม่รู้ว่ามันทำกำไรสุทธิได้หรือไม่ เพราะ:

- สคริปต์เป็น `indicator()` ที่นับ fill/TP/SL เองจากการแตะ High/Low ของแท่ง ทำให้มันรายงานกำไรจากราคาที่เกิด **ก่อน** เข้าออเดอร์ รายงาน TP ทั้งที่เส้นทางราคาชน SL ก่อน และเลื่อน Breakeven ย้อนหลัง ผมจึงเชื่อผลบนหน้าจอไม่ได้เลย
- ตัวเลข "75% win rate" มาจาก Python 4 เทรดบนฟีด `GC=F` ไม่ใช่จาก artifact นี้และไม่ใช่ฟีดโบรกเกอร์ที่ผมเทรด
- Alert บอกว่า `ORDER_FILLED` / `Executed` ทั้งที่ไม่มีใครยืนยันคำสั่งจริง และ payload ไม่ใช่ JSON ที่ระบบรับ webhook parse ได้
- Setup detection ยืม extrema จาก sweep ใหม่มาตั้ง SL ของ MSS เก่า, SMT เป็นเงื่อนไขที่เป็นจริงตลอด, GSS ไม่ตรวจ displacement ตามนิยามที่ตกลงไว้
- SL/lot ในสคริปต์เป็นระยะราคา ไม่ใช่ risk budget ของบัญชี USD500 ของผม และไม่มี daily stop / drawdown halt / news blackout
- M15 ปิดไม้ตามกำหนด 20:55 UTC ไม่ได้ เพราะแท่งแรกที่เข้าเงื่อนไขเปิด 21:00

ผมต้องการรู้ว่ากลยุทธ์ไหน (SMC / TSS / GSS / combined) มี **net expectancy** ดีที่สุดภายใต้ drawdown ที่ผมรับได้ โดยผมยังส่งคำสั่งจริงด้วยมือเอง

## Solution

เปลี่ยน `tradingview/xauusd_master_pro_v6.pine` เป็น **Pine `strategy()` ตัวเดียว** ที่ทำหน้าที่กราฟ, HUD, alerts และ Backtest พร้อมกัน โดย:

- ให้ **native strategy orders เป็นแหล่งความจริงเดียวของสถานะจำลอง** ลบ state machine ที่นับ fill/TP/SL เอง ปัญหา pre-entry TP, SL/TP ในแท่งเดียว, BE ย้อนหลัง และ pre-fill high หายไปโดยโครงสร้าง ไม่ใช่หายเพราะแก้เงื่อนไขทีละจุด
- แก้ detection ให้ตรงนิยามใน CONTEXT: freeze สวีปและ extrema ตอนยืนยัน MSS, FVG ใช้ middle-candle contract เดียวกับ Python, GSS ตรวจ displacement 45%, SMT เทียบ swing ก่อนหน้าที่ตรงช่วงเวลาและเป็นข้อมูลประกอบเท่านั้น
- เพิ่มชั้น risk ที่อ้างพอร์ตจำลองของ strategy: risk 0.5%/ไม้, lot ปัดลงตาม broker step, ข้ามเมื่อต่ำกว่า min lot, daily stop, drawdown halt 5%, news blackout ±30 นาที
- เปลี่ยน alert เป็น **version 2**: JSON object เดียว มี `simulation=true`, `SIMULATED_FILL`, setup/trade ID, cancellation/expiry event ชัดเจน
- ผ่าน **software gate** (regression จาก counterexample + Pine compile + Strategy Tester evidence) ก่อน แล้วจึงเข้า **profitability gate** (เลือกโหมดบน June–July 2026, ตัดสินบน holdout Aug 1 – Sep 11 2026 ด้วย paired weekly-block bootstrap)
- แยกสถานะ **software verified / backtest evaluated / forward verified** และห้ามประกาศว่ากำไรดีขึ้นจนกว่า holdout ผ่านเกณฑ์

ถ้าหลักฐานไม่พอ ระบบต้องรายงาน **INCONCLUSIVE** ไม่ใช่รายงานว่าดีขึ้น

## User Stories

1. As a discretionary XAUUSD trader, I want the on-chart simulated result to come from TradingView's native order emulator, so that no reported profit can originate from price action that happened before my entry existed.
2. As a trader, I want a single Pine artifact for chart, HUD, alerts and Strategy Tester, so that the numbers I evaluate and the alerts I trade from come from identical logic.
3. As a trader, I want every alert to carry `simulation=true` and the word `SIMULATED_FILL`, so that I never mistake a chart event for a broker-confirmed execution.
4. As a trader, I want each alert to be one valid JSON object containing both machine fields and a human-readable message, so that a webhook receiver can parse it and I can still read it in Telegram.
5. As a trader, I want every alert to carry a setup ID and a trade ID, so that I can match a pending setup to its fill, its exits and its cancellation.
6. As a trader, I want explicit cancellation and expiry events, so that I know when to remove an order from my terminal instead of leaving it live.
7. As a trader, I want the SMC setup's stop loss to come from the extrema frozen between its own sweep and its own MSS, so that a newer unrelated sweep cannot tighten my stop into a wrong level.
8. As a trader, I want a new sweep to replace a setup that has not yet produced an order, so that stale structure never generates an entry.
9. As a trader, I want a pending limit order cancelled when an opposite sweep or a structural invalidation occurs, so that I am not filled into a setup whose premise is already dead.
10. As a trader, I want a setup consumed once, so that the same sweep→MSS→FVG cannot re-enter repeatedly.
11. As a trader, I want the FVG's middle candle contract identical to the Python detection core, so that Python and Pine results describe the same events.
12. As a trader, I want the limit order placed only after the FVG's right-hand candle closes, so that the entry level cannot change after I have placed the order.
13. As a trader, I want MSS accepted only within 8 bars of the sweep and FVG only within 4 bars of MSS, so that unrelated later structure is not stitched into a setup.
14. As a trader, I want GSS to require a displacement impulse at the documented 45% body ratio, so that OTE pullbacks are measured against real impulses instead of any two swings.
15. As a trader, I want GSS to freeze the swing pair in true chronological order, so that a bullish OTE cannot be computed from a high that preceded its low.
16. As a trader, I want SMT compared against prior, time-aligned DXY swings that exclude the current sample, so that a fresh DXY high cannot be labelled as bullish divergence.
17. As a trader, I want SMT shown as `unavailable` when DXY data is missing, so that a blank feed never silently reads as confirmation.
18. As a trader, I want SMT treated as informational only, so that it does not silently change my trade population before it has been validated.
19. As a trader, I want H1 bias, PDH and PDL taken from the previous completed period using the documented HTF pattern, so that a chart reload does not change the historical signal set.
20. As a trader, I want the script to refuse non-standard chart types and timeframes other than M5/M15, so that Heikin-Ashi or Renko bars cannot inflate the simulated result.
21. As a trader, I want position size derived from 0.5% risk on the simulated USD500 account with estimated costs included, so that the displayed risk is money at risk rather than a price distance.
22. As a trader, I want lot size rounded **down** to the broker step, so that a rounding decision can never push a trade above my risk limit.
23. As a trader, I want the setup skipped when the computed lot falls below the broker minimum, so that the system never over-risks to satisfy a minimum volume.
24. As a trader, I want the structural stop never squeezed to make a lot size fit, so that risk control is achieved by skipping trades, not by moving stops.
25. As a trader, I want two equal halves at TP1 = 1R and a runner at TP2 = 2.5R whenever the volume splits cleanly on the lot step, so that scale-out matches ADR-018.
26. As a trader, I want breakeven moved only after the partial exit is confirmed by the emulator, so that BE is never applied to a fill that did not happen.
27. As a trader, I want a single 0.01-lot position closed fully at TP1 with no partial or runner, so that the reported outcome matches what my broker can actually execute.
28. As a trader, I want expectancy reported separately per exit mode (split vs single-lot full close), so that I do not average two structurally different payoff profiles.
29. As a trader, I want pending orders to expire 4 bars after the bar that created them, so that TTL matches ADR-005 regardless of chart timeframe.
30. As a trader, I want pending orders cancelled on TTL, killzone end, H1 bias flip, structural invalidation, news blackout or risk halt, so that no order survives the conditions that justified it.
31. As a trader, I want a fill that occurred before a cancellation to be recorded as a real simulated trade, so that the ledger is never rewritten retroactively.
32. As a trader, I want the simulated flat-close at 20:45 UTC on M15 and 20:50 UTC on M5, so that the close happens on a bar boundary that actually precedes the 20:55 deadline.
33. As a trader, I want the effective flat-close time displayed in the HUD and stated in alerts, so that I know exactly when to close my manual position.
34. As a trader, I want the daily stop to trigger after two net losing trades or a 1% equity decline in a UTC day, so that a bad day is capped.
35. As a trader, I want new setups blocked once simulated drawdown reaches 5%, so that the evaluated system respects the same limit I trade under.
36. As a trader, I want the guards described honestly as covering only the strategy's simulated portfolio, so that I do not assume the script sees my manual trades or my live account.
37. As a trader, I want to supply USD HIGH-impact event times in UTC together with a coverage date range, so that news filtering is auditable rather than implicit.
38. As a trader, I want setups and pending orders blocked ±30 minutes around those events while already-open positions keep their normal SL/TP lifecycle, so that news handling matches ADR-010.
39. As a trader, I want the system to stop accepting setups and show the reason when the news list is malformed or the tested period falls outside coverage, so that silent gaps cannot be mistaken for clean data.
40. As a trader, I want the HUD to state which verification status the artifact currently holds, so that I never trade a build believing it was validated when it was not.
41. As a reviewer, I want the seven documented counterexamples encoded as a regression suite before any production edit, so that each fix is proven against a failure that was reproduced first.
42. As a reviewer, I want the regression suite mirrored for both BUY and SELL, so that a fix applied to one direction cannot silently miss the other.
43. As a reviewer, I want added cases for TTL boundary, session cancellation, news cancellation, minimum lot, partial lot step, daily reset, risk halt and alert ordering/duplication, so that the new control surfaces are covered too.
44. As a reviewer, I want Pine compile output and Strategy Tester evidence recorded separately from Python results, so that a Python transcription is never presented as Pine runtime proof.
45. As a reviewer, I want H1 and daily boundary behaviour compared before and after a chart reload, so that replay consistency is demonstrated rather than asserted.
46. As a reviewer, I want Bar Magnifier used where intrabar data exists and the uncovered ranges disclosed, so that intrabar ambiguity is visible in the result.
47. As a reviewer, I want the comparator to be the correctness-fixed Master at baseline parameters, so that improvements are not measured against a version that simulated incorrectly.
48. As a reviewer, I want exactly four compared modes (SMC, TSS, GSS, combined dispatcher) with no parameter sweep this round, so that the first decision is not an overfitting exercise.
49. As a reviewer, I want the evaluation feed to be a named Spot XAUUSD source with stated volume specification and costs, so that results are attributable to a tradable instrument.
50. As a reviewer, I want dataset, code hash, news coverage and baseline costs frozen before testing, so that the run is reproducible.
51. As a reviewer, I want a stress run at double spread and slippage, so that the result is not conditional on optimistic costs.
52. As a reviewer, I want one position lifecycle counted as one trade with its partial exits aggregated, so that net R, PF, drawdown and losing streak are not distorted by counting exits as trades.
53. As a reviewer, I want mode selection done only on June–July 2026 and the decision confirmed on the untouched Aug 1 – Sep 11 2026 holdout, so that the final number is out of sample.
54. As a reviewer, I want the holdout status voided if it was ever inspected for tuning, so that a contaminated period cannot masquerade as a clean test.
55. As a reviewer, I want ties broken by lower drawdown and single engines preferred over the combined dispatcher, so that the selection rule is fixed in advance.
56. As a reviewer, I want the holdout gate to require positive net expectancy, PF > 1, drawdown ≤ 5% and expectancy above the comparator, so that "better" has a numeric definition.
57. As a reviewer, I want 10,000-round paired weekly-block bootstrap lower 95% bounds on expectancy and on the difference, so that clustered trades do not produce false confidence.
58. As a reviewer, I want an explicit **INCONCLUSIVE** verdict when evidence is insufficient, so that absence of proof is never reported as improvement.
59. As a trader, I want a 12-week forward demo protocol comparing simulated alerts against the orders I actually placed, reported as two separate result sets with no mid-round parameter changes, so that alert-to-execution drift is measured.
60. As a reader of the repo, I want CONTEXT.md to distinguish Setup, Simulated Fill, Executed Fill, Risk Budget and Net Winning Trade, so that documents stop conflating detection with execution.
61. As a reader of the repo, I want superseded agreements kept with an explicit note of what replaced them, so that history is auditable.
62. As a trader, I want a setup guide covering strategy properties, cost and lot calibration, news input, alert creation and simulation limits, so that I can reproduce the evaluated configuration exactly.
63. As a reader of the repo, I want the review verdict updated with code hash, commands, compile evidence and evaluation outcome, so that the artifact's claimed status is traceable.
64. As a reader of the repo, I want any missing verification (TradingView access, feed, costs, historical news) listed explicitly on delivery, so that gaps are visible instead of assumed closed.

## Implementation Decisions

**Artifact and platform**

- `tradingview/xauusd_master_pro_v6.pine` becomes a Pine v6 `strategy()` — one artifact for chart visuals, HUD, alerts and Strategy Tester. No parallel indicator variant is maintained this round.
- Simulated state is owned by `strategy.*` entries, exits and `strategy.opentrades` / `strategy.closedtrades`. The custom `pendingActive` / `tradeActive` state machine and all OHLC touch tests for fill, TP, SL and BE are removed. Bar-close detection still gates setup creation; lifecycle resolution is the emulator's.
- Existing Pine API defects fixed as part of the conversion: split BUY/SELL `plotshape` calls with constant `style`/`location`, `str.format_time(time, format, "UTC")` for timestamps, Pine-correct literal braces in `str.format`.
- Chart guard: the script refuses to produce setups unless the chart is a standard bar type on M5 or M15, and states the refusal in the HUD.

**Detection**

- HTF reads use the documented offset-plus-`lookahead_on` pattern for H1 bias and daily PDH/PDL, so historical and realtime releases align.
- SMC setup becomes an owned object: sweep identity, direction and `trueSweepExtremum` freeze at MSS confirmation. Extrema stop updating after freeze; a later sweep cannot contribute to a frozen setup's stop.
- Setup lifecycle states: `SEARCHING → SWEPT → MSS_CONFIRMED → ORDER_PLACED → (FILLED | CANCELLED | EXPIRED) → CONSUMED`. A new sweep replaces a setup in `SWEPT` or `MSS_CONFIRMED`; a setup in `ORDER_PLACED` is cancelled by opposite sweep or structural invalidation before a new search starts. A consumed setup never re-enters.
- Temporal windows unchanged from ADR-014: MSS within 8 bars of sweep; FVG on the MSS bar or within 4 bars after.
- FVG contract aligned to `scripts/smc/detection.py`: the MSS bar (or a following bar within the window) is the **middle** candle, and the right-hand candle must close before the 50% limit is placed.
- GSS requires the originating impulse to satisfy the existing 45% displacement definition and freezes the swing pair in chronological order. No ATR threshold is added this round.
- SMT compares the XAU swing against a time-aligned prior DXY swing that excludes the current sample, exposes an `unavailable` state, and remains informational — it does not gate entries.
- Distance and R parameters stay at current baseline values so the comparison isolates correctness changes.

**Risk, sizing and execution assumptions**

- Sizing inputs: simulated account currency and balance, risk percent (0.5% default), contract size, lot step, minimum lot, estimated spread/commission/slippage. Lot is rounded down to the step after cost allowance; below minimum lot the setup is skipped. Structural stops are never tightened to fit a lot.
- Scale-out: when the computed volume splits into two equal step-aligned halves, TP1 closes 50% at 1R and the runner targets 2.5R, with breakeven applied only after the emulator confirms the partial exit. When only the minimum lot is available, the position closes fully at TP1 and is tagged with a single-lot exit mode.
- Guards operate on the strategy's simulated portfolio: daily stop after two net losing trades or a 1% equity decline within a UTC day; setup intake halted at 5% simulated drawdown. Documentation states the guards do not observe manual trades or the live account.
- Session flat-close uses the last bar boundary before the 20:55 UTC deadline: 20:45 on M15, 20:50 on M5. The effective time is surfaced in HUD and alerts.
- News blackout takes a user-supplied list of USD HIGH events as UTC timestamps plus a coverage start/end date. Setups and pending orders are blocked ±30 minutes; open positions keep their lifecycle. Malformed entries or an out-of-coverage evaluation window halt setup intake with a displayed reason.

**Alert interface v2 (breaking change — users must recreate alerts)**

- One valid JSON object per alert containing: `schema:"v2"`, `simulation:true`, `event`, `setup_id`, `trade_id`, `symbol`, `timeframe`, `event_time_utc`, `bar_open_time_utc`, engine, direction, prices, volume, risk fields, and a `message` string holding the human-readable card.
- Event vocabulary: `SETUP_PENDING`, `ORDER_PLACED`, `SIMULATED_FILL`, `PARTIAL_EXIT`, `BREAKEVEN_MOVED`, `ORDER_CANCELLED`, `ORDER_EXPIRED`, `TRADE_CLOSED`, `RISK_HALT`, `NEWS_BLOCK`. `ORDER_FILLED` and "Executed" wording are removed.

**Evaluation protocol**

- Comparator: the correctness-fixed Master at baseline parameters. Modes compared: SMC only, TSS only, GSS only, combined dispatcher. No parameter sweep.
- Development window June–July 2026 selects the mode; Aug 1 – Sep 11 2026 is holdout and is not opened for tuning. Dataset, code hash, news coverage and cost baseline are frozen before any run, and a stress variant doubles spread and slippage.
- Metrics tooling is Python, consuming exported Strategy Tester trade lists: one position lifecycle aggregates to one trade, producing net R, win/loss/flat counts, PF, drawdown, losing streak, and a paired weekly-block bootstrap (10,000 rounds) reporting lower 95% bounds on expectancy and on the difference versus comparator.
- Selection rule: highest validation net expectancy within risk limits; ties resolved by lower drawdown, then single engine over combined. Holdout gate: net expectancy > 0, PF > 1, drawdown ≤ 5%, expectancy above comparator, with bootstrap support. Otherwise **INCONCLUSIVE**.

**Documentation**

- `CONTEXT.md` gains a disambiguated glossary (Setup, Simulated Fill, Executed Fill, Risk Budget, Net Winning Trade) and the three verification statuses, keeping superseded ADR text with replacement notes.
- `tradingview/README.md` documents strategy properties, cost/lot calibration, news input, alert v2 setup, and simulation limits, and stops advertising unimplemented visual options or win-rate claims.

## Testing Decisions

**What makes a good test here.** A good test states an observable outcome for a given bar sequence — a setup exists or not, an order is placed at a level, a trade closes for a reason — and never asserts on internal variable names or intermediate flags. Every counterexample is written and observed failing before the production change that fixes it.

**Seam A — pure detection (primary, automated).** `scripts/smc/detection.py` and `scripts/smc/structure.py` remain the single automated seam. Detection-level counterexamples are asserted here: cross-sweep stop loss, FVG middle-candle timing, tautological SMT, GSS displacement, temporal windows, setup replacement and consumption. Prior art: `tests/test_smc_detection.py`, `tests/test_smc_liquidity.py`, `tests/test_smc_risk.py` (`unittest`, minimal deterministic bar fixtures).

**Seam B — TradingView native strategy (manual, evidence-logged).** Lifecycle counterexamples (pre-entry TP, SL and TP in one bar, pre-fill high, retroactive breakeven, rollover timing) are resolved structurally by delegating to the emulator, then confirmed by Pine Editor compile output plus a Strategy Tester trade-list walkthrough with Bar Magnifier where intrabar data exists. Evidence is recorded verbatim in the review update; it is never substituted by Python output.

**Seam C — shared fixture corpus.** One versioned fixture set of bar sequences with expected events serves both seams: Seam A asserts against it automatically, Seam B replays the same sequences via a manual checklist. This is the parity contract that keeps Pine and Python from diverging.

Modules under automated test: `scripts/smc/detection.py`, `scripts/smc/structure.py`, `scripts/smc/risk.py` (sizing, lot step, minimum-lot skip, guards) and the new metrics/bootstrap tooling. Sizing and guard tests follow `tests/test_smc_risk.py` and `tests/test_smc_orchestrator.py`. Metrics tooling is tested with hand-computed trade ledgers, including a seeded bootstrap for determinism.

## Out of Scope

- Auto-trading, broker order routing, deployment and any real-money execution. Orders remain manual.
- Parameter sweeps, added indicators or added entry filters. SMT stays informational; no ATR threshold for GSS.
- Rewriting the Python live loop, MT5 adapter, Telegram notifier or Google Workspace logging beyond what the shared detection contract requires.
- Building a Python re-implementation of the Pine execution lifecycle. The emulator is the reference; no second execution engine is written.
- An automated Pine test runner. Pine verification stays manual with recorded evidence.
- Claiming improved profitability before the holdout gate passes, and the 12-week forward demo itself (its protocol is specified; execution follows the freeze).

## Further Notes

- The review's verdict is **REWORK**; this spec is the rework, not a defense of the current artifact. Existing win-rate language must be removed from README and handoff docs as part of the work.
- Alert v2 is a breaking change. Existing TradingView alerts stop matching and must be recreated.
- `GC=F` CSV data cannot certify an Exness Spot XAUUSD result; it may appear only as supporting evidence with the limitation stated.
- If TradingView access, a named broker feed, cost specification or historical news data is unavailable, deliver the code with the missing verification listed and the status left at **software verified** at most.
