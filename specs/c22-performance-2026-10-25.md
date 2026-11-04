# C22 downside and performance investigation — 2026-10-25

Owner authorized offline improvement of maximum-profit research contract
9e511d195c52ef3d, retaining USD200 initial, fixed0.01, single position,
cost-inclusive initial cap10%, daily10% gate, no recovery and no lot increases.
Active Demo and frozen campaign artifacts remain unchanged.

Owner selected: base and price-stress terminal net must not decrease versus the
existing research leader, and maximum observed equity DD must not exceed40%.
Apply the DD ceiling to every declared base/stress/fee and raw/cent guard view.
This is a historical qualification condition, not a guaranteed broker loss cap.
Maximum base terminal net is primary; stress net breaks ties, then lower maximum
DD and shorter completed closing-balance recovery. No forced selection if no
improved case qualifies. Do not trade profit against an invented weighted score.

Use the same hash-bound171,171,013 public Exness Bid/Ask ticks, actual endpoints
2024-09-01 through2026-10-23, to compare full continuous accounts fairly. These
prices are already exposed research data, not holdout. Reuse canonical replay,
entry math and swap-inclusive base/stress/fee assumptions from the completed
2026-10-24 campaign; historical costs/calendar remain COST_INCONCLUSIVE.
All economic views include swap; missing metadata blocks execution.

Before changing strategy, diagnose full losing runs, protection state, dollar/R
losses, minimum equity and completed versus still-open recovery intervals.
Loss counts alone ignore severity and different numbers of trading opportunities.
Closed-ledger attribution identifies witnesses, not causal counterfactual returns.

Freeze18cases before observing new economic outcomes: baseline; BUY body>=50%
of candle range; BUY close in top25%; SELL body>=50%; SELL breakout depth>=0.15ATR;
SELL closed-H4EMA200 slope negative versus16M15bars earlier; BUY equivalent slope
positive; BUY stop2.5ATR; cooldown4bars after a loss; BE activation0.5R;
failed-close exit after2consecutive closed M15 bars; stagnant exit after8held bars;
existing drawdown_steps risk admission; and five fixed combinations:
BUYbody+SELLdepth, BUYclose+SELLdepth, BUYbody+SELLbody,
BUYstop2.5+SELLdepth, failed-close2+SELLdepth. Everything else remains baseline.
Existing failed-close anchors: BUY oscillator trigger close; SELL prior range
boundary. No future-outcome/date filters, tick deletion or synthetic gap filling.

Each new case runs base+swap, spread/slippage stress+swap and fee sensitivity+swap.
Review the best two raw-qualified improvements under cent-counter sensitivity;
their base/stress net must also match or beat the corresponding archived cent
benchmark. Require positive net and modeled survival in every reviewed view,
DD<=40%, all risk invariants and independent cash/swap/calendar checks.
Repeat all6selected economic paths fresh. A changed guard/cost can admit a
different trade set; do not interpret that difference as an isolated cost effect.
The untouched baseline must reproduce archived full results exactly.

All new execution sources/protocol/input hashes are bound before economic runs;
reusable new harness stays in scripts/research, outputs/snapshots in ignored
runs/c22-performance-2026-10-25. Preserve failed and rejected cases. A qualifying
improvement is a research result requiring a matching adapter and separate
broker/forward validation before any Demo adoption. No broker API or sender.
