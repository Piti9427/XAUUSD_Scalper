# Follow-up: retest, trigger invalidation and risk-distance targets

Owner requests continuing research until unchanged performance targets. Structural-stop campaign suggests small admissible stops with ATR targets produce few wins/too few trades. This motivates new **discovery** hypothesis, not proof.

Before replay, freeze384 configurations: two parents × two guards (`off/sell_only`) × two entries (`retest/confirm`) × two SL logics (`trigger/structure`) × two admission caps (`2.5/5%`) × three nominal target RR (`1.5/2/3`) × four profit protections (`off/break_even/candle_trail/runner`). Daily admission loss limit5%; fixed0.01 lot; no recovery. Parent detection indicators unchanged.

`trigger` stop: BUY confirming bar low−one tick; SELL confirming bar high+one tick. `structure` retains originating setup plus trigger extrema. Initial stop rounded conservatively and checked against executable quote, fees, slippage allowance and cap. TP distance uses actual entry minus initial rounded stop, multiplied by nominal RR and rounded to tick. Nominal RR is **not** realized RR; realized net RR>=1 remains mandatory. Targets are a separate research contract; baseline targets/stops unchanged.

Hypothesis: retest confirms acceptance beyond crossed level, trigger stop marks immediate invalidation, risk-distance TP improves achievable win rate without arbitrary indicator changes. Falsification: profit/WR/DD/RR gates fail under shared cost model or either chronological half.

Run with `--screen`: evaluate full base+stress first; if any required full metric fails, mark trial failed and skip remaining halves. Only full pass proceeds to halves, and any half failure rejects. Missing windows cannot qualify. Six artifacts exist only for fully evaluated candidates; protocol records this short-circuit. `--stop-on-pass` freezes first passing discovery candidate; no validation data read.

Exact source snapshots and hashes stored with protocol. Earlier in-flight structural campaign uses its frozen code snapshot; later source changes do not modify that process's imported strategy functions. Separate run directories preserve evidence.

```bash
.venv/bin/python -m scripts.research.run_strategy_campaign --output data/strategy_risk_target_campaign_2026_09_30 --campaign risk_target --screen --stop-on-pass
```

Same profit/WR improvement over both parents, lower DD and DD<=20%, realized RR>=1, positive net, stress gates and sample sizes. Existing184 days reused discovery. Missing independent data/all-in costs/MQL5/Shadow evidence still blocks Demo readiness.
