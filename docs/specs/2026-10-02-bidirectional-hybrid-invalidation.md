# RSI BUY setup-invalidation continuation

Preregister108 new contracts before replay. Admission example22 improves full profit/WR/DD but realizedRR is1.10 and half DD exceeds30%, so remains rejected. Hypothesis: cut invalid/stagnant trades instead of changing gates or increasing lot.

RSI BUYperiod7/14/21, lower25/30/35, EMA50+slope4; retained unfiltered SELL D48. BUYpause5/10%, BE/trail1R, exits (one failed close), (four stagnant bars), (both). Failed close means completed close back across recorded setup anchor: RSI uses trigger close; D48 uses crossed channel. Stagnant exit requires >=4 completed held bars and executable net<=0. Both fill on first subsequent quote; entry candle is not a held bar. Exit rules apply to both legs; no widening, no resizing, no synthetic fills. TP3/SL2.5ATR/fixed0.01/maxrisk10/daily20 retained.

Existing public failed-breakout/stagnant/protection tests plus CLI frozen108/resume checks apply. Same six strict trial30 qualification gates, real Bid/Ask audit, frozen-source whole-result repetition. Discovery reused; commission0 assumption and omitted swap. No automatic promotion. Distinct from prior admission because every contract activates at least one exit rule.
