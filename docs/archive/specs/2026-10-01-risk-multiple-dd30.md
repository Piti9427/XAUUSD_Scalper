# Immediate breakout with actual stop-distance TP

Research only, no live strategy change. Frozen192 contracts before trials. Hypothesis: original3ATR target ties payoff to indicator distance while rounding/spread alter true entry-to-stop distance; use immutable rounded initial entry-to-stop distance times nominalRR1.5/2/3. Existing replay implements target_rr; this catalog uses immediate entry and original2.5ATR SL unlike earlier risk_target delayed-entry structural-stop family. No period tuning or recovery.

Parents D48/core, off/sell guard, daily10/20%, BE/trail activation1/1.5R, resetfalse/true; fixed0.01, admission10%, no lot clamp.192 unique contracts. DD30 hard/25 preferred, base/stress profit/WR/RR beat both parents, full>=60/halves>=20. First replay2026 reused discovery; public10-month discovery separate, sealed3months untouched. Actual commission/swap and Demo parity unverified. Observe portfolio positive equity and broker margin, no future no-ruin guarantee.
