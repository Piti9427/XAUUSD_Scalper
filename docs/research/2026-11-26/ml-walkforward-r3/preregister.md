# C22 ML walk-forward Round 3 — pre-registration (written before any model is fitted)

Date: 2026-11-26 (ICT). Box only. No Oracle VM access, no live-bot change, no git commit, Mac not touched (tar + row file only).
Request: t218u "ดำเนินการปรับจูนต่อเป็น ml ไปเรื่อย ๆ จนได้ตัวที่ดีกว่าที่ใช้ bot run อยู่ตอนนี้"; t219u "focus ml ไปที่ปรับจูนเพิ่ม".
Goal: higher WR AND lower Max DD than live 7fe0 with solid net. R1 0/15, R2 0/10 ML (OOS AUC ~0.43-0.62; best simple rule G_1.5 6/7).

## 0. Base / parity
Harness and simulator identical to R2 (entry_sl.py candidates, F2; portfolio2 copy + skip after all live gates: one position, F3 max 1 loss
per UTC day at signal and fill day, 30-min cooldown after a loss, daily stop 10%, cap 10%). Runner asserts parity before anything else:
2025-26 313 trades 121W WR 38.66% +1898.96 DD 224.89; 2024-26 429 trades 146W WR 34.03% +1826.95 DD 224.89.
Candidate sets: live (BUY TP 3.0R) and BUY TP 2.0R (same signals, aligned by signal bar + side).

## 1. Features (causal at signal-bar close; M15 bars closed at or before the signal bar; H1/D1 only completed bars)
Kept from R1/R2: log_min_since_sl, bar_range_atr, atr_pct_price, d1_ema50_slope, d1_ema20_dist, dist_lo20_d1atr, h4dist, hour_sin, hour_cos,
ext_atr, rsi7, side, d1_atr_pctile252 (definitions identical to R2 prep.py).
New:
- er10_m15, er20_m15: Kaufman efficiency ratio |close - close[n]| / sum|close diff| over n M15 bars.
- er10_h1, er20_h1: same on completed H1 bars (H1 resampled from M15; only H1 bars closed at or before the signal decision time).
- atr5_50 = ATR5 / ATR50 (M15). bbw_pctile = percentile rank of Bollinger bandwidth (20, 2 sd: 4*sd/sma) over last 1920 M15 bars.
- day_open_dist = side*(close - UTC day open)/ATR14; day_high_dist = (UTC day high so far - close)/ATR14; day_low_dist = (close - day low so far)/ATR14.
- color_run = side * signed length of the run of same-colour M15 bars ending at the signal bar (+ = run in trade direction).
- body3 = sum |close-open| / sum (high-low) over the last 3 M15 bars.
- meta_wr5, meta_wr10: win rate (net > 0) of the last 5 / 10 C22 candidates (both sides) whose exit <= signal time; meta_lstreak: current
  run of consecutive losing candidates by exit time (stream-based, path independent, causal).
Imputer / scaler / selector / GMM fitted inside each training window only.

## 2. Labels
- MFE_R / MAE_R (Arm 1): from the fill, over the window ending at the earlier of (the -1R stop being touched, fill + 72 h), on M1 bars with the
  same bid/ask convention as R2 (BUY: bid; SELL: bid + spread). MFE_R = max favourable excursion / R, capped [0, 5]; MAE_R = max adverse
  excursion / R, capped [0, 1]. R = candidate stop distance.
- y1r (Arm 3): +1R before -1R (R2 definition, 10-day horizon).
- net_est = pnl + BUY swap (for gating statistics).
Purge: a training row is used only if max(exit, fill + 72 h, label horizon end used) < Jan 1 of the target year; for y1r the 10-day horizon
is purged the same way (fill + 10 d < cutoff).

## 3. Walk-forward
Test years Y = 2020..2026 (2026 ends 2026-11-24 08:00 ICT). Rolling 4-year training window before the target year T (fills >= Jan 1 T-4,
purged as above). Inner validation folds V in {Y-2, Y-1}, each simulated as a calendar year from a fresh $400 vs base of that year.
Fold feasible if Max DD <= base DD and net >= base_net - 0.15*|base_net|. Fold score = (WR - WR_base, pp) + 20*(DD_base - DD)/DD_base.
(param) score = mean over 2 folds; feasible if both. Smoothed score = mean over the param and its grid neighbours (all must be feasible).
Forced ON: take the feasible param with the highest smoothed score; if none feasible, the highest smoothed score anyway. Ties -> first in grid order.
Refit chosen params on the rolling window before Y and apply to Y.

## 4. Arms
Arm 1 MFE-MAE-ML
- MFE-MAE-Filter-{Ridge, Huber, HGBR}-{All, BUY} (6 arms): two regressors (MFE_R, MAE_R) with the same family/hp; score form f in
  {ratio = predMFE/(predMAE+0.25), diff = predMFE - predMAE}; skip if score < quantile q of the training-window scores of the filtered side(s);
  q in {0.10, 0.15, ..., 0.40}. Grids: Ridge alpha {1, 10, 100}; Huber epsilon 1.35, alpha {0.0001, 0.01, 1}, max_iter 1000;
  HGBR max_depth {2, 3} x min_samples_leaf {20, 50}, lr 0.05, 150 iters, l2 1.0, random_state 0. Param = (hp, f, q); neighbours = q +/- 0.05 same hp, f.
- MFE-DynamicTP-{Ridge, HGBR} (2 arms): BUY only, MFE_R model on BUY rows (live TP 3.0 candidates). If predMFE < quantile q of training preds,
  the BUY uses the TP 2.0R version of the same signal, else TP 3.0R. No skipping. q in {0.2, 0.3, ..., 0.8}; neighbours q +/- 0.1.
Arm 2 Regime-GMM (4 arms): GaussianMixture (full covariance, n_init 5, random_state 0) on standardized [er20_m15, d1_atr_pctile252, atr5_50,
  d1_ema50_slope_raw (unsigned)] of all candidates in the rolling training window. Cluster x side mean net_est per candidate computed on the
  inner years Y-2, Y-1 (candidate level) using that GMM.
  - GMM-K3-Gate, GMM-K4-Gate: skip (cluster, side) with mean net_est < 0 and n >= 15.
  - GMM-K3-TPswitch, GMM-K4-TPswitch: SELL untouched; BUY in (cluster) with mean BUY net_est (TP 3.0) < 0 and n >= 15 uses the TP 2.0R version.
  No inner threshold search (rule fixed); plateau = other K with the same mode AND n_min variants 10 and 20 must also beat base WR and DD.
Arm 3 Sparse-L1-TopK (6 arms): in each training fit, rank features by L1 LogisticRegression (liblinear, standardized) on y1r with the smallest
  C in {0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1} that gives >= 5 non-zero coefficients; take the top 5 by |coef| (fewer if never 5 -> use C=1 top 5).
  Then fit on those 5 only: LR L2 C {0.01, 0.1, 1} or HGB (max_depth 2, min_samples_leaf {50, 100}, lr 0.05, 100 iters). Skip if
  P < quantile q of training preds, q in {0.10..0.40} step 0.05.
  Scopes: Sparse-{LR, HGB}-BUY (BUY rows, BUY filter), Sparse-{LR, HGB}-All (both sides), Sparse-{LR, HGB}-BUY20 (BUY TP 2.0 candidates,
  BUY filter). Selected features recorded per fold.
Benchmark (R2-Rule-Check, no fitting): G_k (skip BUY if bar_range_atr > k) and LsG_8_k (G_k OR min since stream loss < 8 h), k in
  {1.25, 1.5, 1.75}; neighbours = adjacent k. Also 2015-2019 hold-out (fresh $400 per year) and drawdown-episode analysis (top-5 equity
  drawdown episodes, base vs cell, in 2025-26 and 2024-26).

## 5. OOS windows
2025-26 continuous 2025-01-01..END; 2024-26 continuous 2024-01-01..END; 2020-24 calendar years from fresh $400, pooled, Max DD = max yearly DD.
Net/DD reported.

## 6. Pass criteria (all must pass)
P1 WR > base in 2025-26 AND 2024-26. P2 Max DD < base in both. P3 net > 0 and >= 90% base in both (P1+P2 with net 80-90% both ->
"tradeoff candidate", still FAIL). P4 $/trade >= base - 0.5 both. P5 trades >= 60% base both. P6 plateau: quantile arms -> rerun with every
year's q shifted -0.05 and +0.05 (DynamicTP: +/- 0.1), both must keep WR > base and DD < base in both windows; GMM -> section 4; rules ->
adjacent k. P7 2020-24 WR >= base AND net >= base.
Multiple testing: 18 ML arms + 6 rule cells. A pass is a confirmation candidate only (forward shadow next); no live change without
Pitiii's approval, a new release and a review.

## 7. Diagnostics (info)
Per test year: MFE/MAE OOS R2 and Spearman; y1r AUC for Sparse arms; GMM cluster stats (n, WR, mean net per side per cluster); selected top-5
features per fold; permutation importance / coefficients of 2026 models.
