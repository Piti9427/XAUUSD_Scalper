# Horizon candle-quality continuation

Preregistered while horizon/trend campaign runs, before this catalog's replay. Earlier D48 symmetric body filter passed second-half alone; early short-horizon rows show high DD and low WR. Hypothesis: require directional candle commitment, retaining short target3ATR, to reduce weak breakouts at different horizons. No outcome/date-specific switching.

128 contracts: BUY/Sell horizons independently12/24/48/96, symmetric body_dominant or close_extreme, BE or candle_trail at1/1.5R. EMA off, TP3ATR, SL2.5ATR, ATR14, daily20%, risk<=10%, fixed0.01. Body is signed close-open >= half full range. Extreme is upper/lower quarter, not newer BUY-only20% filter. Eight D48/D48 controls repeat prior symmetric catalog;120 new versus first five catalogs and horizon/trend cycle. Repeat controls never count as new hypotheses.

Same six full/half base/stress strict trial30 net/WR/RR/DD/trade-count/both-side gates. Frozen catalogs, raw-input audit, complete ledgers and exact fresh replay required. Use existing public guard/replay tests and extended CLI freeze/resume test. No runtime promotion, no gate relaxation, no untouched-validation claim, no swap-complete claim. Continue further hypotheses based on actual results.
