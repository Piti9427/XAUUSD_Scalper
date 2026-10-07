# Follow-up: structural invalidation and profit protection

Parent campaign: `2026-09-30-strategy-campaign.md`,384 configurations, no discovery-qualified candidate. Owner requested continued research until performance targets; targets stay unchanged.

## Hypotheses frozen before execution

1. ATR2.5 stops produce high per-trade exposure and reject most fixed0.01 trades under lower caps. Replace SL with setup invalidation: BUY minimum setup/trigger low minus one tick; SELL maximum setup/trigger high plus one tick. Reject wrong-side stop, excess cost-inclusive risk or margin. This is a new research contract; frozen parents still use ATR2.5 for comparison.
2. Separate BUY/SELL and previous-day direction guard can avoid different failure behavior. Discovery history motivates this hypothesis; it is not validation.
3. Break-even/candle trailing/runner after completed-bar net>=0.5 initial cost-inclusiveR can reduce returned gains. Existing implementation used; later tick only, never widen stop.

384 unique configurations predeclared before replay: two parents × four guards (`sell_only/off/buy_only/prior_day`) × four entries (`immediate/confirm/retest/failed_reverse`) × three admission caps (`2.5/5/10%`) × four protections (`off/break_even/candle_trail/runner`). Daily realized loss admission gate5%; fixed0.01 lot, one position, no recovery. Parent indicators and TP ATR targets retained. No weighted score or relaxed metric gates.

Common base/stress cost model and full/half gates unchanged. Exact source/input hashes, formulas and candidate list in new immutable protocol. `--stop-on-pass` stops at first passing discovery candidate and freezes it before any unseen evaluation. No claim that first pass is best globally. When no pass exists, campaign exhausts384 configs; next campaign requires another documented hypothesis.

Command from repository root:

```bash
.venv/bin/python -m scripts.research.run_strategy_campaign --output data/strategy_structure_campaign_2026_09_30 --campaign structure --stop-on-pass
```

Data remains184 reused days; missing>=12months coverage,>=3months untouched, sourced all-in costs, MQL5 parity and Shadow evidence still block Demo qualification. Passing discovery ends this search stage, not independent validation.
