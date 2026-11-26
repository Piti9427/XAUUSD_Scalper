# C22 ML walk-forward Round 1 — pre-registration (written before any model is fitted)

Date: 2026-11-26 (ICT). Box-only research. No Oracle VM access, no live-bot change, no git commit.
Requested by Pitiii (t218u): "ดำเนินการปรับจูนต่อเป็น ml ไปเรื่อย ๆ จนได้ตัวที่ดีกว่าที่ใช้ bot run อยู่ตอนนี้".
Goal (t215u/t216u): higher win rate (WR) AND lower Max DD than live 7fe0, net profit kept solid; improve entry / profit logic.

## 0. Base and parity (checked before this file was written, parity_check.py)
- Harness: f2f3-validate-20261124 core via sell-entry-sl-20261125/entry_sl.py (`CB = build(sell_rows())`, `portfolio2`).
  M1 2015-03 .. 2026-11-24 08:00 ICT, spread 0.24, slip 0.10, BUY swap -0.4743/night, $400 start, 0.01 lot, cap 10%,
  daily stop 10%, cooldown 30 min after a loss, F3 max 1 loss per UTC day, one position at a time, F2 (h4dist >= 10).
- Parity obtained: 2025-26 313 trades, 121W/156L/36T, WR 38.66%, net +1898.96, Max DD 224.89;
  2024-26 429 trades, 146W/237L/46T, WR 34.03%, net +1826.95, Max DD 224.89. Matches the reference -> continue.
- The ML runner re-asserts these numbers and stops if they differ.

## 1. What the ML does
A meta-label filter: at the signal bar close, a model gives P(trade net > 0). If P < threshold the candidate is skipped.
Skipping is applied INSIDE a full re-simulation of the C22 execution loop (portfolio2 copy + skip flag, applied after
all live gates: flat, cooldown, F3 at signal and fill day, daily stop, cap). A skipped candidate does not open a position,
so later candidates that live would have blocked can enter. Rows are never just dropped from the base trade list.
Label: net > 0 where net = candidate pnl (+ BUY swap nights x -0.4743). Ties (net == 0, BE exits) are label 0 (not a win).
Training rows: all F2-passing candidates of the arm (not only those live took), signal 2015-03-02 onward.

## 2. Features (all known at signal-bar close; M15 bars closed at or before the signal bar; no lookahead)
side (+1 BUY / -1 SELL); atr_pct_price = ATR14/close*100; bar_range_atr = (high-low)/ATR of signal bar;
bounce_atr = (close-low)/ATR; wfrac = (close-low)/(high-low) (0 if range 0); ext_atr = (LL48_prev - close)/ATR for SELL, 0 for BUY;
rsi7; rsi7_slope = rsi7 - rsi7[1]; ema50_dist_atr = side*(close-EMA50)/ATR; h4dist (side-signed, existing); h4slope (existing);
hour_sin, hour_cos (UTC hour of signal bar close); dow (ICT weekday of fill); vol_ratio = ATR14 / mean(ATR14, last 96 bars);
ret5_atr = side*(close - close[5])/ATR; ret20_atr = side*(close - close[20])/ATR;
State features are defined on the arm's candidate stream (path-independent, so they can be precomputed; only exits with
exit time <= signal time are used):
log_min_since_exit / log_min_since_tp / log_min_since_sl = log1p(minutes since the latest candidate exit / TP exit (why 2) /
loss exit (net < 0)) with exit time <= signal time, capped at 10080 min (7 d);
same_leg = a previous same-side candidate signalled within the previous 8 h;
prior_blocked = a previous same-side candidate signalled within the previous 8 h while another earlier candidate was still open
(its fill <= that signal < its exit).
Missing values: median imputer fitted inside the training fold only. Scaler (LR only) fitted inside the training fold only.

## 3. Arms (15) and model families
Structures:
- U  : unified model, both sides, live BUY TP 3.0R.
- S  : separate BUY and SELL models; side threshold = side training win rate + delta.
- B  : BUY-only filter (SELL untouched), model trained on BUY rows only.
- U20: unified model with BUY TP 2.0R candidates (pre-registered TP arm). U25: same with BUY TP 2.5R.
Families x hyperparameter grids (hyperparameter chosen per test year by inner validation, section 4):
- LR : StandardScaler + LogisticRegression L2, C in {0.01, 0.1, 1.0}, max_iter 2000.
- HGB: HistGradientBoostingClassifier, max_depth in {2, 3} x min_samples_leaf in {20, 50}, learning_rate 0.05, max_iter 150,
       l2_regularization 1.0, early_stopping False, random_state 0.
- RF : RandomForestClassifier, max_depth in {3, 4}, min_samples_leaf 20, n_estimators 300, max_features sqrt, random_state 0.
Arms = {U, S, B, U20, U25} x {LR, HGB, RF} = 15.

## 4. Expanding-window walk-forward, threshold/hyperparameter selection (no peeking at test year)
Test years Y in 2020, 2021, 2022, 2023, 2024, 2025, 2026 (2026 = 2026-01-01 .. 2026-11-24 08:00 ICT).
Inner validation folds V in {Y-2, Y-1}: fit on candidates with exit < Jan 1 of V (purged: a training row whose exit falls in
or after the validation year is dropped), predict V, simulate V as a calendar year from a fresh $400, and simulate base V the same way.
Threshold grid: U/B/U20/U25 absolute P in {0.150, 0.175, ..., 0.550} (17 values); S delta in {-0.100, -0.075, ..., +0.150} (11 values).
Per fold metrics: fold feasible if net >= base_net - 0.10*|base_net| and trades >= 60% of base trades.
fold score = (WR - WR_base, in pp) + 20 * (DD_base - DD)/DD_base.
(hp, thr) score = mean of the two fold scores, feasible only if feasible in both folds.
Plateau-smoothed score = mean of scores at thr-0.05, thr, thr+0.05 (those inside the grid); all of them must be feasible.
Choose argmax smoothed score with smoothed score > 0; ties -> lower thr, then earlier hp in the listed order.
If nothing qualifies, the year runs unfiltered (= base for that year).
Then refit the chosen hp on all candidates with exit < Jan 1 Y and apply the chosen thr to year-Y candidates.
2025 and 2026 test decisions never see 2025-26 outcomes in selection (2026 uses folds 2024, 2025 with models trained < V).

## 5. OOS evaluation windows (stitched OOS decisions, full re-simulation)
- 2025-26: continuous from 2025-01-01 to END (as the parity base). 2024-26: continuous from 2024-01-01 to END.
- 2020-24: calendar years with a fresh $400 each year, trades pooled; Max DD = max yearly DD (same method as earlier 2019-24 checks).
Base computed identically for each window.
Plateau check: re-run OOS with every year's chosen thr shifted by -0.05 and by +0.05 (same hp).

## 6. Pass criteria (all OOS; an arm passes only if every item passes)
P1 WR > base in 2025-26 AND 2024-26.
P2 Max DD < base in 2025-26 AND 2024-26.
P3 net > 0 and net >= 90% of base in both windows. (If P1, P2 pass and net is 80-90% of base in both -> flag "tradeoff candidate", still FAIL.)
P4 $/trade >= base $/trade - 0.5 in both windows.
P5 trades >= 60% of base trades in both windows.
P6 Plateau: both shifted runs (thr -0.05 and +0.05) also have WR > base AND Max DD < base in both windows.
P7 2020-24 OOS: WR >= base AND net >= base.
Multiple-testing note: 15 arms are tested; a single passing arm is a candidate for Round 2 confirmation, not a live change.
No result here changes the live bot; any live change needs Pitiii's approval, a new release and a review.

## 7. Interpretability (info only, not used for selection)
For each arm, the model refit for test year 2026 (trained on exits < 2026-01-01): LR standardized coefficients; HGB/RF permutation
importance on the training data (roc_auc, 10 repeats, random_state 0); RF impurity importance. Per-year OOS AUC (info).
Reference cells reported without ML: base, BUY TP 2.0R, BUY TP 2.5R (no filter).
