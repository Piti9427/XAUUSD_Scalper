# XAUUSD Master Pro v6 — logic and real-trading readiness review

**Verdict: REWORK.** Current source has Pine API incompatibilities and a lifecycle model that can report profits before entry or after an earlier stop. Neither production readiness nor a high live win rate is established. Review does not conclude that the underlying trading ideas cannot work; their edge remains unmeasured for this artifact.

## Scope and evidence

- Goal: assess whether this exact SMC/TSS/GSS indicator produces trustworthy, executable gold-trading signals and supports its profitability claims.
- Reviewed entire 643-line [Pine artifact](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:1), supplied [handoff](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/archive/handoff/2026-09-12-tradingview-master-pro-v6-hardened.md:15), AGENTS, CONTEXT, README, and relevant Python detection/orchestration/backtesting seams.
- Source is untracked. This is a full current-artifact review, using `git diff --no-index /dev/null tradingview/xauusd_master_pro_v6.pine`, not a historical branch comparison. Expected nonempty-diff exit is 1. Repository HEAD: `3f6655c12178ba6c417641557b4135b612856ed1`.
- Reviewed source SHA-256: `80a55c312e14263c0ff11472658ed768616e64cddbb2a88b6dc72fcbc8b905f9`.
- Two independent review axes below retain their own findings/order. Additional cross-cutting findings follow.
- No production source changed. No live loop, MT5 connection, broker order, Telegram message, TradingView alert, or deployment executed.

**Simpler alternative:** retain a visual copilot, label simulated events honestly, and validate one frozen engine at a time with TradingView's native strategy tools before adding filters. Existing [EMA/Chandelier strategy](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/archive/xauusd_pro_copilot.pine:2) and [SMC v1 strategy](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/archive/xauusd_smc_system_v1.pine:2) are different implementations; their results cannot certify this master indicator.

## Standards

**One documented-standard breach, three correctness findings, one heuristic.**

1. **P1 — Phantom execution alerts.** [AGENTS.md:66](/Users/nopparuj/my-agents/XAUUSD_Scalper/AGENTS.md:66) requires executed/broker-approved order notifications. [Local activation/fill](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:421) uses close/OHLC alone, then [alerts](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:565) say `ORDER_FILLED` and `Executed`. No acknowledgement path exists in this indicator. **Change:** use simulated/setup terminology in Pine; an execution adapter must own actual broker confirmation when routed to Telegram/execution systems.

2. **P1 — Entry candle reused as post-entry history.** [Market entry](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:421) occurs at close, immediately followed by [same-candle exit checks](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:460). A valid TSS buy with prior low 98.5, current low 98, high 111, close 100 produces entry 100, SL 97.7, TP2 105.75, then instantly reports TP2 using a high that preceded entry. Existing trades touching both SL and TP2 also receive TP2, regardless of order. Pending fills inherit the entire fill candle's extremes. **Change:** forbid pre-entry extremes; resolve intrabar ordering from lower-timeframe data, or record ambiguity with a conservative policy. Native strategy simulation helps but its assumptions still require verification.

3. **P1 — Alert chronology differs from trade chronology.** [Fill/management](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:434) runs intrabar; [fill alert](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:572) waits for close while [TP1/close alerts](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:584) can fire earlier. Limit touch then stop can emit close before fill notification. Ordinary `var` state rolls back between realtime updates, while alert logs persist. **Change:** define one coherent lifecycle/event timing contract; verify multiple events in a candle. Merely switching everything to `varip` would introduce a separate historical/realtime model. Sources: [execution model](https://www.tradingview.com/pine-script-docs/language/execution-model/), [alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/).

4. **Blocker — Pine API incompatibilities.** [Directional plotshape calls](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:509) pass `series string` to `style`/`location`, which require `input string`. [Timestamp formatting](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:548) calls nonexistent three-argument `str.tostring`. **Change:** split buy/sell plot calls with constant styles/locations; use `str.format_time(time, format, "UTC")`, then compile in Pine Editor. These are API-signature findings, **not observed compiler output**. Sources: [v6 reference](https://www.tradingview.com/pine-script-reference/v6/), [strings](https://www.tradingview.com/pine-script-docs/concepts/strings/), [time](https://www.tradingview.com/pine-script-docs/concepts/time/).

5. **Heuristic — Unsupported visual option.** [Full Analytics promise and unused showExtraLines](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:19) do not provide the promised boxes/history renderer. **Change:** remove unsupported wording/option until implemented. Low priority; no abstraction/refactor needed.

## Spec

**Four findings; no material scope creep identified.**

1. **P1 — MSS takes SL from a different sweep.** [CONTEXT.md:58](/Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md:58) requires extrema across Sweep→MSS. [New sweeps reset shared extrema](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:165), [old MSS persists](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:204), and [SL reads latest extrema](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:323).

   Concrete OHLC sequence, AsianLow105, prior confirmed SwingHigh109, bullish H1/session gates true:

   ```text
   O106 H108 L100   C106   sweep A
   O106 H111 L106   C110   MSS A
   O105 H106 L104   C105   sweep B
   O111 H112 L105.5 C106
   O112 H113 L110   C111   bullish FVG, no MSS B
   ```

   Output becomes BUY CE108/SL103.70 from sweep B; MSS A's structural SL was 99.70. **Change:** bind/freeze sweep identity and extrema at MSS; invalidate prior MSS when a replacement sweep cancels that setup. Scalar branch reproduction executed.

2. **P1 — Python 1:1 parity fails at FVG timing.** [Handoff:17](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/archive/handoff/2026-09-12-tradingview-master-pro-v6-hardened.md:17) claims exact parity. [Pine FVG](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:217) can use MSS as the rightmost candle; [Python](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py:238) starts with MSS as the middle candle and requires the next candle. **Change:** choose one temporal contract and compare identical event fixtures. Do not borrow Python win-rate figures before parity is demonstrated.

3. **P1 — SMT does not verify divergence.** [README:11](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/README.md:11) advertises SMT. [Rolling DXY extrema](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:80) include the current sample; [comparisons](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:180) reduce to `x <= max(x,...)` and `x >= min(x,...)`. Both always hold for valid samples. A new DXY high can still receive a bullish SMT badge. Entry conditions do not use SMT at all. **Change:** compare prior, time-aligned swing levels; label the feature informational unless a validated entry filter is intended.

4. **P2 — GSS does not qualify displacement.** [CONTEXT.md:34](/Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md:34) defines OTE on a displacement impulse. [GSS conditions](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:251) require swing order, range, wick location and candle color, but no impulse displacement. **Change:** qualify the originating impulse, or correct the stated strategy definition. Whether that additional filter improves returns requires separate measurement.

## Additional operational and measurement findings

### P1 — Confirmed HTF values still merge differently on historical bars

[H1](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:71) and [daily requests](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:91) combine `[1]` with `lookahead_off`. Historical HTF values are released at the end of the containing period; realtime requests can expose the previous confirmed period earlier. Thus prior-bar offset alone does not prove identical replay timing. This contradicts [handoff's 100% consistency claim](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/archive/handoff/2026-09-12-tradingview-master-pro-v6-hardened.md:25).

**Change:** follow the documented HTF pattern, offset expression plus `lookahead_on`, with chart timeframe validation; compare live boundaries against reload. Do not apply unoffset `lookahead_on`. Sources: [official HTF FAQ](https://www.tradingview.com/pine-script-docs/faq/other-data-and-timeframes/), [repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/).

### P1 — M15 rollover cannot meet the stated deadline; pending cancellation incomplete

[Session clock](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:39) uses bar opening time; [rollover close](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:499) waits until `inRollover`. Standard M15 bars open 20:45 then 21:00, so first realtime eligible bar is 21:00, after [ADR-007's 20:55 deadline](/Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md:46). Historical evaluation occurs at that bar's close. Rollover only clears active trades; pending logic does not recheck session/rollover. [Expiry flag](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:454) has no alert consumer.

**Change:** define a feasible pre-cutoff boundary for each timeframe; actual timed closes belong to the execution layer. Explicitly cancel pending orders and emit cancellation/expiry events. Clarify whether pending orders may fill after killzone end.

### P1 — Payload is not a JSON webhook; format templates need runtime validation

[Alert engine](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:550) sends a human card with JSON appended. The whole body is not valid JSON; a receiver expecting a JSON object cannot parse it directly. TradingView selects JSON content type only for a valid JSON body. Additionally, `str.format` templates use doubled braces, whereas Pine documents apostrophe-quoted literal braces; first-event formatting is an API-inferred runtime failure risk, not a reproduced Pine error.

**Change:** use one valid JSON object containing both event fields and human message; use Pine-correct literal brace formatting. Include setup/trade identity, unambiguous event time and exit details before claiming a reliable lifecycle webhook. Distinguish bar-open `time` from event/confirmation time. Sources: [webhook format](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/), [Pine formatting](https://www.tradingview.com/pine-script-docs/concepts/strings/).

### P1 — Price-distance controls are not account risk protection

[Risk settings](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:275) and dispatch check structural price distance only. No balance, contract size, lot step, actual spread, daily-loss counter, cooldown or news data participates in the Pine path. [Python orchestrator](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py:237) has additional account/cooldown/spread gates; [CONTEXT](/Users/nopparuj/my-agents/XAUUSD_Scalper/CONTEXT.md:49) defines news/risk requirements. Absence in a visual indicator is a scope limitation, but contradicts broad financial-safety/parity claims.

**Change:** scope documentation to copilot behavior. Account sizing and approval remain in an execution layer that has broker data. The displayed dollar risk is a price move, not necessarily dollars at risk on the account. SL buffer and BE+0.10 do not model actual spread, commission, slippage or net breakeven.

### P1 — 75% is not evidence for this master indicator

[Earlier handoff](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/archive/handoff/2026-09-07-smc-v2-backend-hardening.md:31) reports **3 wins from 4 Python trades**, PF1.49 and +$24.81. Those results were not rerun in this review. Master source is an [indicator](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:2), with no native strategy trade ledger or measured combined SMC/TSS/GSS result. [Current CSV header](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/XAUUSD_M15.csv:2) identifies `GC=F`; [loader](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/run_backtest.py:21) flattens that ticker away. This is not evidence of a matching broker Spot XAUUSD feed.

- Illustrative Wilson 95% interval for 3/4: **30.06%–95.44%**, assuming independent Bernoulli trades. Tuning on the sample, serial dependence and strategy changes prevent treating this as a validated live interval.
- With 50% closed at 1R and 50% at 2.5R, the full target outcome is **1.75R gross**, not 2.5R on the original position. [Close text](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:471) is ambiguous; labels also hardcode defaults despite configurable target inputs.
- High win rate alone does not establish profit: 75% at +0.2R and 25% at -1R gives **-0.10R before costs**.
- [Dispatcher](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:314) prioritizes whichever eligible engine triggers; it does not require agreement among all engines. Adding TSS/GSS changes the trade population, not automatically accuracy.

**Change:** remove production/win-rate certification language until supported by this exact implementation and feed. Evaluate net expectancy, profit factor, drawdown and net-winning closed-trade rate together. TradingView documents cost simulation and out-of-sample evaluation because omitted costs and overfitting distort results: [strategy testing](https://www.tradingview.com/pine-script-docs/concepts/strategies/).

## Verified positives and limits

- [Dispatcher](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:319) rejects nonpositive/over-cap distance instead of clamping SL, and prevents new setup activation while another trade/pending order occupies the slot.
- [SMC midpoint](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:322), [default targets](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:278), and [GSS swing order](/Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine:251) exist. These are implementation facts, not proof of positive expectancy.
- Ran `python3 -m unittest discover -s tests`: **53 tests passed**. These test Python; they do not compile or exercise this Pine artifact.
- Ran [counterexample script](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/debug/reviews/reproduce_master_pro_v6_review.py:1): **7 cases reproduced**: pre-entry TP, SL-first classified TP2, pre-TP1 low reused as BE, pre-fill high reused as TP2, tautological SMT, cross-sweep SL, M15 rollover delay. This is a small Python transcription of branch logic, not a Pine runtime or backtest.
- No observed Pine Editor compile, alert delivery, historical/realtime comparison, broker fill replay, out-of-sample test or forward-demo result. Profitability remains **unverified**.

## Minimum path to a defensible decision

1. Fix compile/API defects, HTF merging, setup ownership, lifecycle causality and event payloads; reproduce each failure before production edits.
2. Use a strategy version with the same detection and explicit execution assumptions. Match broker symbol, M5/M15 timing, spread/commission/slippage, partial volume constraints and fill ordering. Keep ambiguous candles visible in results.
3. Freeze a baseline and parameters. Compare SMC, TSS, GSS and their combined dispatcher separately on chronological held-out periods and multiple volatility regimes. No tuning on the final evaluation period. Use uncertainty estimates that account for clustering where needed.
4. Define wins as net-positive closed positions; include flat closes in denominator, track expired/rejected/no-fill setups separately. Record net R, PF, drawdown, losing streak and session/month breakdown.
5. Forward-demo the frozen version, comparing alerts with actual broker acknowledgements and fills. Set acceptable risk/drawdown criteria before considering real-money deployment.

**Axis summary:** Standards 5 findings (worst: compile/API incompatibilities); Spec 4 findings (worst: MSS/SL linked to different sweeps).

**Final verdict: REWORK — current lifecycle can manufacture apparent profits; highest live win rate and financial safety are not established.**
