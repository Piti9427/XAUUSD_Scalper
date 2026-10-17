# Current-equity sizing research, profit_dd_v2

Owner-approved 2026-10-03: each independent full/half window begins USD200;
compounding allowed, no top-ups. Offline risk ceiling20%; Demo trial30 retains
fixed0.01/cap10%. Public replay -> campaign qualification/resume seams; review develop.

New qualification policy profit_dd_v2: every full/half × base/stress net strictly
above max(0, trial30 net); tick-equity DD <= trial30 and <=30%; >=60 full trades,
>=20 each half; executed BUY and SELL; admitted risk <=20%. WR/realizedRR reported,
no superiority or RR floor. strict_v1 preserved separately; old artifacts immutable.

Stage1 frozen catalog annual_sizing: directional_fine7, directional_circuit22,
hybrid_unpaused28 × risk budgets0.5/1/2/2.5/5/7.5/10/12.5/15/20% × fixed0.01/risk
sizing =60. Each retains signal/exit/daily circuit, uses static risk. Existing cap10
fixed-lot controls included. Risk sizing floors affordable lot to broker step, clips
only to broker maximum, rejects below minimum, then checks cost-inclusive risk and
margin. Per-position volume drives PnL, fees, spread attribution and BE.

Actual archived Bid/Ask Oct2025–Sep2026; independently reset halves. Base actual
spread; stress additional0.20 USD/oz spread and0.10 adverse market slippage. Round-trip
commission0 assumed, swap not modeled in this admission experiment: COST_INCONCLUSIVE.
No profitability/broker parity or Demo promotion claim from this stage. Fee/swap
validation and intraday/overnight bounded holding follow before final selection.

All60 complete before ranking: full stress net descending, worst DD ascending,
trial id. Fresh whole-result repeats required. Independent sealed Jul–Sep2025
holdout remains unopened until final cost-complete contract selected; holdout
>=20 trades >=5 each side, same profit/DD policy. One use, no tuning on holdout.

If stage1 fails, inspect signal/risk/fill/exit diagnostics; next causal M15/M5
trigger research starts from a separately frozen hypothesis, not fabricated fills.

Stage1 measured:60 variants,0 qualifiers,366 exact fresh scenarios. Higher risk
increased admission but DD; low risk rejected nearly all early trades. Fine7 at
12.5% fixed admitted21 first-half base trades but net-40.90/DD60.55%. At10% risk
sizing full net1652.20/DD41.13%, fails. First-half raw signal probe: RSI14/25 has9
BUY setups, RSI14/35 has65, RSI7/25 has143 (before admission).

Stage2 frozen annual_short_buy32: RSI7/14 lower25/35 EMA50, SELL96EMA200 retained;
BUY stop0.5/0.75ATR, rounded-stop TP2/3R, off/BE1R. SELL SL2.5ATR/TP3ATR/BE1R,
fixed0.01/static10%, daily10%/one UTC loss. Hypothesis: shorter BUY geometry and
more causal BUY setups improve admission without raising cap. Same six profit_dd_v2
gates; costs remain INCONCLUSIVE and no holdout/runtime selection. Added before
opening stage2 results. An adaptive discovery experiment, not independent evidence.

Stage2 completed32/0qualifiers;198 exact whole-result fresh replays. RSI14/25
retains only12 first-half fills; more frequent BUY variants incur excessive DD.

Stage3 frozen128 variants, split into two64 catalogs `annual_m5_intraday` and
`annual_m5_bounded24`:8 M15 profiles (symmetric Donchian24/48/96 ×EMA50/200,
plus RSI14/cross25/EMA50 BUY +SELL96 EMA50/200), each ×M5 TTL2/4 ×TP1.5/2R
×off/BE1R. Actual Bid M5 assembled from all5 observed M1; missing minutes exclude
bar. Setup available only after M15 close. Eligible trigger M5 must open at/after
availability, touch boundary and close on correct side. One pending setup,
opposite setup replaces, wrong-side close/TTL cancels, new setup may rearm.
Trigger SL at Bid candle extreme plus one tick; SELL extreme converted to Ask
with entry spread. BE evaluated on completed M15 boundaries only; SL/TP each tick.
Fixed0.01/static10/daily10/one UTC loss; sizing stage gave no qualified alternative.
Intraday blocks entries>=20:30UTC and closes first actual quote>=20:45UTC.
Bounded24 closes first actual quote at/after entry+24h. Gaps never fabricate fills.
Both costs stay INCONCLUSIVE without effective-date commission/swap evidence;
no reserve/accrual model yet, so overnight results exploratory only. Final selection
across both catalogs only after all128 and fresh verification. Holdout remains sealed.

Stage3 initial128 runs completed0 statistical qualifiers, preserved SUPERSEDED:
review proved neutral boundary closes incorrectly canceled pending setups. Public
regression RED0trades!=1 -> GREEN after strictly-negative close invalidation.
M5 prior-day future-mutation bug independently fixed (+5 availability instead+15);
current catalogs guardoff. Corrected128 runs will use fresh `_corrected_` outputs
and hashes; initial results excluded from authoritative selection/repeat counts.

Corrected stage3 completed128/0qualifiers,780 exact fresh full-result scenarios.
Actual complete M5 count70,460; both caches hash064bf2df43580ef0b770762a87da7a45ea1c54c4f4f98d1b4faf1d6cdf0a7511.
Bounded24 D24/EMA50 TTL4 TP2R BUY contributes first-half+148.11 base/+130.68stress
and second-half+47.20/+29.17. SELL contributes second-half-3.31/-34.55. This is
within-strategy attribution, not additive independent PnL under a different policy.

Stage4 frozen annual_m5_hybrid64: BUY D24/48 EMA50 M5 retest TTL2/4, trigger-low
one-tick SL/TP1.5/2R/off or BE1R; SELL D48/96 EMA200 enters immediately at completed
M15, SL2.5ATR/TP3ATR/BE1R. BUY/SELL conflict gives SELL priority and cancels pending
BUY. Common fixed0.01/static10/daily10/one UTC loss, intraday/bounded24 holding.
Same behavior across whole year/halves, no calendar switch. Hypothesis: profitable
M5 BUY participation plus preserved M15 SELL geometry improves all six scenarios;
no inference that side PnLs simply add. Public replay supports optional BUY trigger
stop while shared default ATR unchanged. M5 rejection events expose UTC/side/reason
for monthly signal->trigger->risk rejection->fill->exit audit. Costs INCONCLUSIVE,
holdout sealed, no Demo modification. Preregistered before first stage4 result.

Stage4 completed64/0qualifiers;390 exact fresh scenarios. Hybrid14 first-half
net87.82/44.88 DD28.89/29.82, second-halfnet504.03/400.04 DD26.85/26.92. Counts
pass, remaining failure is profit/DD, not insufficient participation.

Stage5 frozen annual_m5_hybrid_quality48: seedhybrid14/15 ×cap5/7.5/10% ×SELL
stop2/2.5ATR ×SELL guardoff/body_dominant ×BUY TP2/3R. Other seed behavior unchanged:
BUYD24EMA50/M5TTL4,SELLD48EMA200/TP3ATR/BE1R, seed14BUYoff/bounded24 and
seed15BUYBE1R/intraday, daily10/one loss/fixed0.01. Body-dominant SELL requires
completed M15 bearish body >=half candle range and positive range; BUY unaffected.
Test hypothesis: lower SELL cost-risk/quality filter contains false-breakout losses
while greater BUY reward preserves second-half net. Adaptive discovery, no date
switching or holdout tuning. Same six versioned gates/costINCONCLUSIVE. Frozen
before first stage5 output. Existing lower caps/shorter stop effects may conflict;
only actual complete replay decides. No fee invented or optimized to manufacture admission.

Stage5 completed48/0qualifiers,294 exact fresh scenarios. Lower shared cap suppresses
SELL participation in independently reset second half despite positive full-year
net. This distinguishes path-dependent admission from global annual profitability.

Stage6 frozen annual_m5_directional_sizing48: seeds hybrid14/15 ×BUYcap2/2.5/5%
×BUYfixed/risk-sizing ×BUYTP2/3R ×SELLstop2/2.5ATR. SELL remains fixed0.01/cap10%,
SELL TP3ATR/BE1R, BUY M5triggerSL/seedprotection/holding, unchanged detection/daily
circuits. No SELLbodyfilter. Optional buy_risk_cap/buy_sizing_mode defaultNone
inherit shared policy. Hypothesis: lower BUY current-equity risk limits DD, while
compounded BUY profits fund original SELL admission; shared cap reductions failed.
Lots floor broker steps and reject below min; all fees/PnL/BE stay per-position.
Same six gates, no fee invention, no holdout access, COST_INCONCLUSIVE.

Stage6 completed48/0qualifiers,294 exact fresh scenarios. Lower BUY risk failed to
fund robust SELL path; stage6 best fullbase500.20/DD27.76 still jointfail.

Stage7 frozen annual_m5_atr_reward64: stage3 eight M15 profiles ×M5TTL2/4 ×BUYTP1.5/2R
×BUYoff/BE1R. Both sides M5 trigger one-tick extreme stop (SELL converts Bid extreme
with entry spread); SELL target retains3ATR andBE1R instead of common1.5/2R. Common
fixed0.01/static10/daily10/one loss/bounded24. Hypothesis: M5 short SELL risk can
fund earlier admission and larger ATR payoff compensates false breakouts; BUY
retains stage3 geometry. Optional sell_stop_mode defaultsNone/shared. Same six gates,
actual annual ticks/fresh replay, costs INCONCLUSIVE/holdout sealed/noDemochange.

Implementation review checkpoint: Spec/Standards parallel reviews against develop
found neutral-boundary cancellation and M5 midnight prior-day lookahead; both
public RED->GREEN regressions fixed and reviewed0open. No deployment or financial
superiority inference. Full finalsuite792tests/790passed2skipped; scopedstrictmypy
three researchfiles and Rufffivefiles pass. Legacy18whole-result comparisons normalize
only absent defaultRules metadata (new optional overridesNone/fixed/legacy).

Finalstage7 completed64/0qualifiers/390exact fresh scenarios. Combined8catalogs444
parameter evaluations/2,712exact fresh scenarios; initial128superseded excluded.
GoalUNMET; historicalcostvalidation and independentholdout unresolved. Allfinite
workerscomplete. Versioned audit preserves source/protocol/verdict/artifact hashes,
nearest failedcontracts and hybrid14monthlyside/reason/fill/exit attribution.
