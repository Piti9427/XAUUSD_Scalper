# Profit-protection state transition after full R

Prior historical SELL-only runner improved profit/DD but mean winning net / mean losing net RR0.832 failed RR>=1. Hypothesis: halfR activation clips winners; activation only after1R/1.5R/2R preserves winning distribution. Standard risk-unit thresholds frozen before replay, not fitted to a winning result.

288 new configs, excluding already-used0.5R: parents2 × guards2(`sell_only/off`) × stop modes2(`atr/boundary`) × risk caps2(`5/10%`) × daily loss admission gates2(`5/20%`) × activations3(`1/1.5/2R`) × protections3(`runner/candle_trail/break_even`). Parent indicators/ATR targets retained. Risk immutable after entry; activation uses executable net after fee/adverse exit allowance at completed bar, later quote effect, stops only tighten. Runner disables target only after valid stop update. Above-target thresholds can simply never activate; not silently changed.

Same profit/WR/DD/RR/stress and sample gates, source snapshots, full-first screening, first passing discovery freeze. Runner now derives exhaustion from actual unique count; campaign cap384 remains. Fixed0.01, no recovery, cap<=10%, no Demo adoption.184 days reused discovery; missing independent history, all-in broker costs, MQL5/Shadow still block readiness.

Run: `--campaign activation --screen --stop-on-pass --output data/strategy_activation_campaign_2026_10_01`.
