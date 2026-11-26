# C22 ML walk-forward Round 2 — pre-registration (written before any model is fitted)

Date: 2026-11-26 (ICT). Box only. No Oracle VM access, no live-bot change, no git commit. Mac offline: files kept ready for sync.
Request: t218u "ดำเนินการปรับจูนต่อเป็น ml ไปเรื่อย ๆ จนได้ตัวที่ดีกว่าที่ใช้ bot run อยู่ตอนนี้"; goal (t215u/t216u) higher WR AND lower Max DD
than live 7fe0 with solid net. Round 1 (ml-walkforward-r1-20261126): 0/15 passed; filter switched OFF in 2025-26; OOS AUC 0.43-0.58.

## 0. Base / parity
Same harness and simulator as Round 1 (f2f3-validate core via sell-entry-sl entry_sl.py; portfolio2 copy with skip applied after all live
gates: one position, F3 max 1 loss/UTC day at signal and fill day, 30-min cooldown after a loss, daily stop 10%, cap 10%; F2 h4dist >= 10).
Parity required before anything else (runner asserts, stops on mismatch): 2025-26 313 trades 121W WR 38.66% net +1898.96 DD 224.89;
2024-26 429 trades 146W WR 34.03% net +1826.95 DD 224.89.

## 1. Targets (labels)
- Target A (regression): R_mult = candidate net (pnl + BUY swap) / (R + slip 0.10). Models predict expected R.
- Target B (binary "1R"): 1 if price reaches +1R before -1R after the fill (M1 path, SL side checked first inside each M1 bar;
  BUY: stop if bid low <= entry-R, target if bid high >= entry+R; SELL: stop if bid high + spread >= entry+R, target if bid low + spread <= entry-R;
  horizon 10 days, neither -> 0). R = the candidate's own stop distance. (Live BE exits are triggered at +1R so they label 1, not a blur.)
Training rows: all F2-passing candidates of the arm (not only those live took).

## 2. Features (causal at signal-bar close)
R1 kept: side, atr_pct_price, bar_range_atr, ext_atr, rsi7, rsi7_slope, ema50_dist_atr, h4dist, h4slope, hour_sin, hour_cos, vol_ratio,
ret20_atr, log_min_since_sl, log_min_since_tp (definitions identical to R1 prep.py; stream-based state features).
New D1 regime features, UTC days, built only from COMPLETED days before the signal day:
d1_atr_pct_price = D1 ATR14 / prior-day close * 100; d1_atr_pctile252 = percentile rank of D1 ATR14 within last 252 completed days;
dist_hi20_d1atr = (20-day high - close)/D1ATR; dist_lo20_d1atr = (close - 20-day low)/D1ATR (20 completed days, close = signal bar close);
d1_ema20_slope = side*(EMA20_d1[t-1] - EMA20_d1[t-6])/D1ATR; d1_ema50_slope = same with EMA50; d1_ema20_dist = side*(close - EMA20_d1[t-1])/D1ATR.
Session one-hot on signal UTC hour: asia [0,7), london [7,12), overlap [12,16), ny [16,21), late [21,24).
Imputer (median) and scaler (linear models) fitted inside each training fold only.

## 3. Rolling walk-forward
Test years Y = 2020..2026 (2026 ends 2026-11-24 08:00 ICT). Training window = rolling 4 calendar years before the target year:
rows with fill >= Jan 1 (T-4) and exit < Jan 1 T (purged), where T is the year being predicted (inner fold year V or test year Y).
Inner validation folds V in {Y-2, Y-1}; each fold simulated as a calendar year from a fresh $400 against base for the same year.

## 4. Threshold rule (fixes the R1 "switched OFF" issue)
Threshold is a skip quantile q of the model's predictions on its own training rows of the filtered side(s): skip if pred < quantile_q(train preds).
q grid {0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40} (so the filter is always active, 10-40% of candidates targeted).
Fold feasible if Max DD <= base DD and net >= base_net - 0.15*|base_net| (= 85% of base when base > 0).
Fold score = (WR - WR_base, pp) + 20*(DD_base - DD)/DD_base. (hp, q) score = mean over the 2 folds; feasible if both folds feasible.
Smoothed score = mean score over q-0.05, q, q+0.05 inside the grid.
PRIMARY (forced ON): choose the feasible (all three smoothed points feasible) (hp, q) with the highest smoothed score; if none is feasible,
choose the highest smoothed score regardless of feasibility (filter stays ON). Ties -> lower q, then earlier hp.
SECONDARY (allow OFF, info only): as primary but if no feasible point with smoothed score > 0 the year runs unfiltered.
Refit chosen hp on the rolling window before Y, apply chosen q (quantile of that refit's training predictions) to year Y.

## 5. Arms
ML (10 arms):
- RegAll-Ridge, RegAll-HGBR: Target A, one model both sides (live BUY TP 3.0R), filters both sides.
- RegBUY-Ridge, RegBUY-HGBR: Target A, BUY rows only, filters BUY only.
- Cls1R-BUY-LR, Cls1R-BUY-HGB: Target B, BUY rows only, filters BUY only.
- Cls1R-All-LR, Cls1R-All-HGB: Target B, one model both sides, filters both sides.
- BUY20-Ridge (Target A), BUY20-Cls1R-LR (Target B): BUY TP 2.0R candidates (SELL live), BUY-only filter.
Hyperparameter grids: Ridge alpha {1, 10, 100}; HGBR/HGB max_depth {2, 3} x min_samples_leaf {20, 50}, learning_rate 0.05, max_iter 150,
l2_regularization 1.0, early_stopping False, random_state 0; LR (L2) C {0.01, 0.1, 1.0}, max_iter 2000.
Rule arm (no fitting), BUY only, live BUY TP 3.0R:
- Ls_N: skip BUY if minutes since the latest candidate-stream loss exit (exit <= signal) < N h, N in {2, 4, 8}.
- Lb_N: skip BUY if the BOT's own latest losing trade (inside the simulation) exited < N h before the signal, N in {2, 4, 8}.
- G_k: skip BUY if signal-bar range/ATR > k, k in {1.5, 2.0, 2.5}.
- LsG_N_k: skip BUY if Ls_N OR G_k (9 cells).
18 rule cells. (a) Fixed-grid: every cell evaluated on all windows; a cell passes only if it AND all its grid neighbours
(adjacent N and/or adjacent k inside the same family) pass P1-P5 and P7. (b) Rule-WF arm: per test year choose the cell with the highest
inner score (same folds/score/feasibility/forced-ON rule as ML, smoothing over the cell and its neighbours).

## 6. OOS windows (stitched OOS decisions, full re-simulation)
2025-26 continuous 2025-01-01..END; 2024-26 continuous 2024-01-01..END; 2020-24 calendar years from a fresh $400, trades pooled,
Max DD = max yearly DD. Base computed the same way. Net/DD reported.

## 7. Pass criteria (strict OOS, all must pass)
P1 WR > base in 2025-26 AND 2024-26. P2 Max DD < base in both. P3 net > 0 and >= 90% of base in both
(P1+P2 pass with net 80-90% in both -> flag "tradeoff candidate", still FAIL). P4 $/trade >= base - 0.5 in both.
P5 trades >= 60% of base in both. P6 plateau: ML -> rerun with every year's q shifted -0.05 and +0.05 (clipped to grid ends 0.05/0.45 allowed),
both must have WR > base and DD < base in both windows; rule fixed cells -> neighbours rule in section 5; Rule-WF -> fixed-grid neighbours of
the most-chosen cell. P7 2020-24: WR >= base AND net >= base.
Multiple testing: 10 ML arms + 18 rule cells + Rule-WF. A pass is a Round-3 confirmation candidate only; no live change without
Pitiii's approval, new release and review.

## 8. Interpretability (info)
Model refit for 2026: linear coefficients (standardized); HGB permutation importance on training rows (10 repeats, r2 for regressors,
roc_auc for classifiers). Per-year OOS rank correlation (Spearman, regressors) / AUC (classifiers).
