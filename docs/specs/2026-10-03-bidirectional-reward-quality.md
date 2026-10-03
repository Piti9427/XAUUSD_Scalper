# Rounded reward with symmetric candle-quality guards

Preregister108 contracts before replay. Reward156 has all six net/WR/RR improvements but four DD failures. Admission continuation has no qualifying row observed before this registration; no incomplete-catalog winner selected. Hypothesis: filter false entries on both sides rather than only suppress trade frequency with tighter caps.

RSI BUY7/lower25,30,35/EMA50, parent D48 SELL. BUYpause2.5/5/10%, target1.35/1.5 times rounded initial SL distance, protectionoff. Symmetric replay entry guards: body_dominant (signed body >= half range), close_extreme (BUY upper quarter, SELL lower quarter), prior_day (BUY after completed prior-day positive close-open, SELL after negative close-open). These are existing replay guards; oscillator BUY and breakout SELL must both satisfy chosen guard. All/avoid_rollover entry session. Fixed0.01, SL2.5ATR, maxcap10%, daily20%, no recovery. Existing formulas unchanged.

All108 full/first_half/second_half base/stress scenarios compared against unchanged trial30. Original strict profit/WR/realizedRR, DD<=baseline and<=30%, both filled directions, risk<=10%, trades>=60/20 remain. Hash/source/input freeze before evaluation; exact full-result fresh replay required. No runtime promotion or sealed-holdout tuning. Reused discovery, assumedcommission0 and omittedswap remain limitations.
