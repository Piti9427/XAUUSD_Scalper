# Prior-range compression continuation

Preregistered before replay. Early shorter-horizon discovery shows many entries with poor DD/WR. Test whether breakouts following a narrow prior range avoid chasing extended moves. No date/return-conditioned admission; all features available at completed candle.

216 contracts: independent BUY/SELL horizons24/48/96; maximum prior range/prior ATR14 of6/9/12; trend off/EMA50; guard off/body_dominant; BE/trail1R. TP3ATR, SL2.5ATR, fixed0.01, cap10%, daily20%. BUY range is prior BUY-horizon high minus prior BUY-horizon low. SELL uses its own horizon. Divide by immediately preceding bar ATR, not trigger bar ATR. Require positive prior ATR and ratio<=threshold, missing warmup rejects. No full-sample quantiles or fitted cutoffs.

Same strict six scenarios and original trial30 benchmark; full>=60, halves>=20, each BUY+SELL, profit/WR/RR strictly higher, DD<=baseline and<=30%. Causal mathematical unit fixtures are not performance evidence. Full archived Bid/Ask replay and independent fresh whole-result comparison required. Discovery tape reused; commission0 assumed, swap omitted; no runtime authorization. Source snapshots keep each overlapping research process reproducible.
