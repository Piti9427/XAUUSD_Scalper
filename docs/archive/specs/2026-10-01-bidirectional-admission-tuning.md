# Second tuning cycle: selective BUY admission under drawdown

Preregistered before its96 evaluations. Geometry/timing/exit cycle completed288 with0qualified;1734 repeat scenario comparisons still pending while this spec is written. No frozen source edit until first-cycle repeat verification/export completes.

Hypothesis: narrower stops admitted many extra losing trades; gating capital-state exposure may preserve baseline SELL edge while retaining genuinely profitable BUY opportunities. Test existing replay risk/admission functions, no new mathematical implementation.

96 contracts: BUY pause drawdown2.5/5/10%; admission mode static/drawdown_steps; symmetric guard off/body_dominant; protection BE/candle_trail1R; TP3/6.25ATR; BUY filter off/prior_day. D48 breakout both directions, ATR14 SMA, SL2.5ATR, immediate first quote, daily20%, fixed0.01, cap10%, no recovery/reset. BUY pause means reject BUY when current flat-equity drawdown from observed all-tick peak reaches threshold; SELL remains eligible. drawdown_steps sets admissioncap<=5% atDD10% and<=2.5% atDD15%, never increases cap or changes lot. Candidate must still execute BUY and SELL in every scenario/window; an effective SELL-only strategy fails.

Same full/firsthalf/secondhalf base/stress, strict trial30 net/WR/RR improvements, DD<=trial30 and<=30%, trades60/20. Whole96 must complete before winner; exact replay on resume,582 verifiedscenarios inclbaseline. No relaxing gates, no holdout reads, no model success claim based on number of signals. Discovery tape is reused; fees/slippage/swap limitations unchanged. Previously confirmed public replay/qualification/resume seams and review base develop remain.

Output `data/strategy_bidirectional_admission_tuning_2026_10_01`; `--catalog admission`. Running trial30 Demo unchanged. If a winner exists, freeze and independently validate; rejected rows never promoted. Compare catalogs as distinct contract evaluations, never count repeat verification as new tuning.
