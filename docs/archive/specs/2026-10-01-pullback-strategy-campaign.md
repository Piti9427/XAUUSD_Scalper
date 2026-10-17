# Trend pullback reclaim

New logic hypothesis after wick-rejection experiments: follow trend after a pullback instead of fading extremes or chasing Donchian breakouts. Fixed EMA50, no period tuning. BUY prior completed candle red, current close above previous high and EMA50, EMA50 greater than value4 bars ago. SELL inverse. First50 bars warmup. All inputs current/past completed M15; entry first quote after close within90s. Trigger-candle stop and fixed0.01 cost-inclusive admission.

384 configs: guards4(`off/buy_only/sell_only/body_dominant`) × sessions2 × risk caps3(`2.5/5/10%`) × target choices4(`1.5/2/3R or3ATR`) × protections4. Daily loss gate5%, no recovery. Same baseline and full/half/stress gates, full-first screening; first passing discovery candidate freezes. Separate source/protocol/trade evidence.184 reused days cannot qualify Demo; independent coverage/costs/parity still missing.

Run: `--campaign pullback --screen --stop-on-pass --output data/strategy_pullback_campaign_2026_10_01`.
