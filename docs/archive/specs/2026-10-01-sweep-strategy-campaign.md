# Wick rejection of prior range: a separate logic family

Previous breakout-family hypotheses motivate testing rejection rather than acceptance of a level. Hypothesis: a wick pierces prior48 Donchian edge and closes back inside on same completed candle; the rejected extreme defines invalidation. Parent baseline rules unchanged.

BUY if `low<prior_low`, `close>prior_low`, `high<=prior_high`; SELL if `high>prior_high`, `close<prior_high`, `low>=prior_low`. Ambiguous candle sweeping both sides does not signal. Donchian uses prior48 bars with shift1. ATR14 remains rolling mean. No RSI/EMA filters. First quote after M15 close within90s; BUY Ask, SELL Bid. SL behind current wick by one conservative tick; cost-inclusive cap/margin checks retained. TP nominal1.5/2/3 initial stop distance, or original3ATR when nominal RR0. Closed-bar break-even/trailing/runner remain optional.

384 unique predeclared configs: guards4(`off/buy_only/sell_only/body_dominant`) × sessions2(`london_ny/all`) × risk caps3(`2.5/5/10%`) × target choices4(`1.5/2/3R or3ATR`) × protections4(`off/break_even/candle_trail/runner`). Daily admission balance-loss limit5%, fixed0.01 lot, single position, no recovery. Full-first screening; first passing discovery candidate frozen. No unseen outcomes used for selection.

Same gates against both common-engine frozen baselines, DD<=20%, net RR>=1 including stress, minimum trades. New family remains research only,184 days reused. Missing>=12months true ticks/>=3months untouched, sourced broker costs/MQL5/Shadow still blocks Demo.

Run: `--campaign sweep --screen --stop-on-pass --output data/strategy_sweep_campaign_2026_10_01`.
