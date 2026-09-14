# Gold Playbook plan review — 2026-09-07

Verdict: **REWORK before implementation as a profitability foundation.** Keep the single-play research scope; add trustworthy measurement and predefined acceptance gates. Neither this plan nor current tests establish profitable trading or a win probability above 50%.

Reviewed plan: [gold_playbook_structure_418dfd58.plan.md](/Users/nopparuj/.cursor/plans/gold_playbook_structure_418dfd58.plan.md:29).

Goal: establish whether one reproducible XAUUSD play has positive net expectancy and a win probability above 50%, then validate its executable version before real capital is used.

Simpler alternative: retain existing pure detection/structure/liquidity functions after causal validation; add a small offline R-tape with explicit lifecycle events and a frozen configuration. Defer Pine synchronization until the Python baseline passes measurement checks. Do not build a broad TradeEngine to answer the initial research question. Do not use the existing dollar backtester as a correctness oracle.

## 1. Blocker — profitability and win-rate acceptance are undefined

**Evidence:** Plan lines 45, 51, 61–63 measure filled-trade ExpectancyR and say TIME_EXIT is not a win. Lines 82–83 use the subjective gate “พอเชื่อ” followed by changing TP/skip rules. No net-cost criterion, win-rate denominator, confidence interval, drawdown threshold, or protected evaluation sample is specified.

**Consequence:** A gross-positive result can pass despite negative net performance. A positive TIME_EXIT is incorrectly excluded from wins if exit reason controls outcome classification. Repeatedly adjusting TP on the same year selects historical noise.

**Minimal change:** Freeze hypotheses, parameter candidates, costs, and chronological development/validation/untouched test periods before evaluating performance. Record every trial; never tune on the final test. Define `net_R = net_PnL / initial_risk`, with consistent units and initial risk frozen at entry. Separate `exit_reason` from `outcome = WIN | LOSS | FLAT` determined by net PnL. Report wins/all closed fills and wins/(wins+losses), with flat counts explicit. NO_FILL stays outside return averages but gets count, fill rate, and reason. Open/censored trades at dataset end must be visible.

**Proposed gates, requiring product agreement:** net expectancy > 0, net profit factor > 1, win rate > 50% on a frozen denominator, drawdown within an agreed limit, and sufficient precision to support those claims. For a strong statistical claim, require lower 95% confidence bounds above 0 for expectancy and 50% for win probability; account for serial dependence using day/week blocks where appropriate. A fixed number of months or trades alone is not proof. Show monthly/session results, consecutive losses, cost sensitivity, and forward-demo results. If evidence is insufficient, return INCONCLUSIVE, not PASS.

Winning more often is a separate constraint from earning money: 60% wins at +0.5R and 40% losses at -1R gives -0.1R before costs. A 1.5R TP threshold does not establish the achieved win rate or realized net payoff.

Methodological source: [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) explains selection risk from testing strategy variants on historical data.

## 2. Blocker — closed-bar replay lacks a causal data contract

**Evidence:** [backtester.py:135](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:135) includes H1 rows with `time <= bar_time`; [detection.py:101](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py:101) uses the final H1 close without checking its completion. [mt5_connector.py:56](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/mt5_connector.py:56) obtains MT5 bars from position zero, and [smc_main.py:163](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:163) passes the full H1 frame to detection. MT5 timestamps represent UTC bar **open** time ([official documentation](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py)). Thus historical H1 07:00 close is available to the current replay during that hour, before its actual 08:00 completion.

[backtester.py:101](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:101) precomputes five-bar fractals on the full dataset and passes sliced flags at line 171. [structure.py:22](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/structure.py:22) requires two future bars to confirm a pivot. Slicing flags does not remove that future knowledge. Reproduced: highs `[1,2,5,2,1]` yield prefix flags `[False,False,False]` when evaluated on the first three bars, but `[False,False,True]` when full-series flags are sliced to three bars. This confirms the precomputed input is noncausal; it does not independently prove every leaked flag changes a complete setup.

**Consequence:** Replay can trade information unavailable at decision time; historical and live signals differ.

**Minimal change:** Specify `bar_open_time`, `bar_close_time`, and `decision_time`; accept H1/M5 data only after close. Track pivot `confirmed_at` and require confirmation by the relevant MSS decision. Place orders after FVG confirmation, never retroactively. Define whether 20:55 exit uses the opening quote at 20:55 or a completed earlier bar; the close of a bar opened at 20:55 is not available until 21:00. Add prefix-invariance tests: changing future bars cannot change earlier decisions. Export matching H1 history plus EMA warmup, validate UTC, ordering, duplicates, gaps, and complete session ranges. Current `data/` contains H1 and M15 CSVs, no M5 dataset.

## 3. Blocker — inherited lifecycle accounting can erase losses or turn them into wins

**Evidence:** [orchestrator.py:70](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py:70) checks SL first. [backtester.py:213](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:213) reconstructs the result with TP first. Entry logging at line 185 requires an open position after `on_bar`; closure logging at line 208 requires a position before it. A fill and close inside the same call satisfies neither condition.

**Executed synthetic reproductions:** real `SMCBacktester` and orchestrator; only detector patched to emit one deterministic BUY setup (entry 100, SL 99, TP 102).

- Fill bar low 98.8: expected one SL trade, observed `total_trades=0`, `avg_r=0.0`, empty trade records.
- Fill survives, next bar low 98.8/high 102.2: expected SL at -1R under plan priority, observed one TP at +2R and +$100.

**Consequence:** Current summary cannot validate the new tape. Existing tests can pass while losses vanish.

**Minimal change:** Tape records explicit SUBMITTED/FILLED/EXITED/EXPIRED events and derives summaries from those events once. Add regression cases for both reproductions before production changes. Define entry-bar ordering, TP touches before entry, gaps through stops, TTL final-bar touch, session cutoff, duplicate setup resubmission, missing bars at rollover, and terminal open trades. Use lower-resolution ambiguity labels or finer data where M5 cannot establish order; SL-first alone does not solve every entry/exit ambiguity. Do not silently exclude ambiguous trades.

## 4. Major — SL buffer is not a transaction-cost model

**Evidence:** Plan lines 40–51 provide a $0.30 SL buffer and high/low touches but no bid/ask fill contract, commission, slippage, or cost stress. [detection.py:256](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py:256) moves the stop by the buffer; this does not charge spread on execution.

**Consequence:** A touched limit may be unfillable on the relevant quote side, and positive gross R can become negative net R. Deferring lot sizing is reasonable; deferring realistic execution costs invalidates a profitability claim.

**Minimal change:** Keep the tape lot-free, but normalize supported broker costs to R. Record quote basis, point/tick size, observed or scenario spread, commission, slippage, and gap execution rules; avoid double-charging spread already represented in bid/ask fills. Use historical news labels and spread stress to assess robustness even if the blackout rule is deferred. If quote history is insufficient, label results as conditional simulations. [NFA's discussion of hypothetical results](https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=9025&Section=9) identifies hindsight, liquidity, and slippage limitations.

## 5. Major — the “frozen” baseline still inherits contradictory behavior

**Evidence:** Plan line 74 disables partial TP, but [orchestrator.py:123](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py:123) still moves SL to BE independently. Constructor TTL is 3 at [orchestrator.py:24](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py:24), whereas plan requires 4. [detection.py:48](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py:48) defaults SL cap to $6; live supplies $25 at [smc_main.py:170](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:170). Detection still returns `risk_r=tp_r` at line 281, and backtester/live TP reporting uses fixed `tp_r`, incompatible with variable-distance opposing pools. Pine also differs in sessions, displacement, FVG gap, and TTL at [xauusd_smc_system_v1.pine:12](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_smc_system_v1.pine:12).

**Consequence:** Different runners evaluate different strategies under one baseline name; changing TP alone leaves incorrect R metadata and reporting.

**Minimal change:** Freeze every detection/lifecycle parameter in one versioned baseline configuration. Explicitly exclude BE and partial behavior from tape; define cap policy rather than inheriting defaults. Calculate reward/risk from actual target and initial stop everywhere. Specify eligible opposing highs/lows by side, already-swept pool policy, empty/tied pool handling, missing previous-day data, fixed-versus-updating target, and setup identity to prevent repeated replay of an expired FVG. Add deterministic fixtures for R just below/equal/above 1.5, long/short target selection, and London availability. Preserve explicit fixed-UTC windows unless session-clock behavior is intentionally changed.

## 6. Major — deferred safety work needs an explicit research-only boundary

**Evidence:** Plan line 35 says “ใช้จริง” while lines 49 and 88 defer circuit breakers, adapters and handoff blockers. [smc_main.py:47](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:47) enables execution when connection succeeds; account state starts at a hardcoded $10,000 at line 64. [smc_main.py:192](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:192) receives adapter result but sends setup alerts without testing `res.success`. [mt5_adapter.py:161](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/mt5_adapter.py:161) ignores cancellation retcodes; analogous update/close branches also report success without checking replies.

**Consequence:** Research success could be mistaken for live readiness. A rejected broker order can still produce a setup alert and local pending state.

**Minimal change:** Mark this phase OFFLINE RESEARCH ONLY and isolate its configuration from live defaults. Deferring execution work is acceptable for this phase. Before broker demo/real execution, require actual account/symbol sizing, broker-confirmed state and fills, rejection/retry/restart reconciliation, risk/circuit-breaker enforcement, and execution-aligned alerts. Any later MM/news/circuit-breaker version changes the trade population and requires another evaluation; baseline R cannot certify that system. Production deployment remains separately approved by the user.

## Recommended order

1. Freeze baseline rules, research-only scope, metrics, experiment protocol, and decision thresholds.
2. Export same-broker M5/H1 with warmup, provenance, hashes, quote metadata, and data-quality checks.
3. Reproduce and close measurement defects; implement deterministic lot-free tape with explicit costs and event outcomes.
4. Implement opposing TP using verified pure seams; run causal/lifecycle fixtures and cost stress.
5. Evaluate chronologically with an untouched final test; report PASS / FAIL / INCONCLUSIVE.
6. If evidence supports continuation, synchronize Pine and validate executable risk controls on broker demo, then seek production approval.

## Verification boundary

- Executed `python3 -m unittest discover -s tests`: **53 tests passed**.
- Executed two synthetic backtester reproductions and one fractal prefix demonstration described above. They expose measurement defects, not strategy profitability.
- Traced MT5 data → detection/structure/liquidity → orchestrator → adapter → notification dispatch; inspected plan, CONTEXT, handoff, Pine parameters, tests, and Git status.
- No 12-month M5 export, historical profitability validation, MT5 connection, broker execution, or Pine runtime validation performed.
- Production code, configuration, and original plan unchanged. Review document added; pre-existing untracked `docs/handoff/HANDOFF.md` preserved.

**REWORK — measurement can currently report false profits, and the plan has no objective evidence gate for net profitability plus win rate above 50%.**
