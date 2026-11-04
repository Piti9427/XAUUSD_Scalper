# Selected26b8 next-version risk closure

Status: OWNER-CONFIRMED RESEARCH IMPLEMENTATION (continue after Q6,2026-10-26). Native Demo recipe stays frozen. The
separate operational quote clock repair is deployed and validated. No new
candidate return/DD result exists. Preserve the completed5184-profile campaign,
its source/data/cost pins and original profit/DD gates.

Owner decisions in this chat:

1. Daily10%: reserve planned SL liability before admitting another position;
   do not change existing exit rules. For a verified flat account, B=proven UTC-day
   equity baseline,E=fresh equity,R=modeled new liability including declared
   commission/slippage. Require E-R>0.90B,alongside unchanged R<=0.10E.
2. DD40%: reject new risk before planned equity would cross the declared40%
   cohort-equity peak floor. For validated cashflow-adjusted equity peak H,require
   E-R>0.60H. This is an admission policy,not a forced close or guaranteed DD cap.
3. Owner wants automatic resume as a distinct research candidate. Q5 selects at
   least24elapsed hours pause,then a fresh native signal and all original/new
   risk checks must pass. No equity-peak reset or DD-floor relaxation is implied.
4. Net BE: first successful SL adjustment only,with the original1R activation
   definition and completed-M15 cadence. Cover costs accrued by adjustment time;
   do not introduce later rollover repricing or another trailing ladder.

Confirmed implementation interpretation:

- Peak/resume: establish H from the next version's activation equity,include
  executable floating P/L,accrued modeled swap and posted costs. Use full-tick
  equity high-water for historical replay,not closing-balance peak. Preserve H
  through pause/resume/restart; no reset or capital top-up to erase a loss.
- The24hour timer starts on the first P1 budget rejection of a native signal
  whose entry geometry/risk can be calculated. Evaluate D1/P1 budgets independently
  after native admission so their order does not hide a DD rejection. Persist
  pause_started/resume_not_before. Polls and later rejected signals do not restart
  that timer. After24hours,wait for a fresh M15 signal whose budgets pass; do not
  replay a signal seen during pause. A later separate pause gets its own timer.
- If a flat account has E<=0.60H,positive new SL risk cannot fit the unchanged DD
  floor. Automatic resume may therefore never occur. Report this stopped/censored
  interval honestly; do not reset H or insert external capital to force recovery.
- Net BE uses the signed accrued swap at the first successful adjustment. In the
  frozen research fee convention,model price offset=(round_trip_fee-accrued_swap)
  /factor+exit_slippage. Entry slippage is already in entry price and must not be
  charged twice. Round BUY up/SELL down to tick size,never loosen the current
  validated SL (broker-confirmed SL in any future Demo implementation),and
  leave TP unchanged. Price geometry/check failures can retry until the first
  successful adjustment; afterward freeze that BE level. Swap charged later can
  make final net negative; this is not a lifetime cost guarantee.
- Any holding-cost reserve requires an explicit horizon/end-handling choice;
  do not silently add zero or an arbitrary duration. The isolated D1/P1 price-risk
  candidates still include modeled swap in every economic accounting path. No
  extra future holding reserve or maximum-holding exit is selected in this round.

Confirmed bounded comparison matrix:

- Native26b8 baseline and each combination of D1 on/off,P1 on/off,B1 on/off.
- For each P1-enabled combination,compare budget-gate-only with the additional
  selected24hour pause. P1-off has no DD-pause variant. Total12 profiles.
- This retains isolated effects and combinations without inventing additional
  thresholds or tuning the24hour choice after viewing outcomes. Existing native
  cooldown30minutes,loss2,fixed0.01,SL/TP/signals remain in every profile.
- Each profile runs all6 matched base/stress/fee+swap raw/cent views:72 accounting
  paths. These are reused historical scenarios,not72 independent market samples.
- Every overlay-off path must first match its corresponding frozen reference;
  this is a parity prerequisite and produces no new profitability claim.

Implementation/evaluation contract:

- Separate candidate/source/config identity,never modify the running26b8 Rules
  ID or frozen historical replay pins. Reuse the existing simulation/admission
  seams; no second execution sender or replacement risk engine.
- Frozen breakout_replay.replay has no admission/BE policy hook. Create a new
  explicitly versioned research event loop with narrow overlay seams,reusing
  original signal,prepare_entry,tick and swap helpers read-only. Keep the frozen
  file and Rules schema intact; require overlay-off ledger/equity parity before
  measuring changed policies. Persist completed cells; no claim of mid-cell
  restart recovery unless full account/position/peak/pause/source state is stored.
- Deterministic regressions must cover exact floors,low equity,unknown baseline/
  peak,cashflows,UTC reset/restart,commission/swap accounting,and fresh pre-send
  rechecks. Do not double-count floating loss in a post-fill projection.
- Economic comparison: original continuous source interval and matched
  base/stress/fee plus modeled swap,raw/cent accounting; independent cash/volume
  audit and full-tick equity DD. Compare terminal net,DD,streak,severity,completed
  and ongoing recovery,trade rejections and stopped/censored intervals.
- No guarantee a new guard raises profit. Retain all failures and trade-offs;
  never move the profit/DD<=40% gates or reset the account/peak to manufacture a
  passing result. Qualification remains COST_INCONCLUSIVE where external cost or
  prospective forward evidence is missing.
- Demo adoption is a separate explicit decision after the matrix/review; the
  current owner's freeze/version separation preference remains in force.

Next step: implement/regress/compare the separate research candidates under the
owner-confirmed timer/accounting/matrix interpretation. No automatic
resume or Net BE code has been enabled on the running Demo by this document.
