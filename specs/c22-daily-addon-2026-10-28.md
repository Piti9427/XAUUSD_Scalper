# C22 one joint daily-profit addon — preregistered research protocol

Status: PREREGISTERED HYPOTHESIS; no addon economic outcome inspected/run.
Scope T20/GitHub#31,OFFLINE only. Native26b8 remains the Demo strategy. One addon
only; no threshold search,second sender,lot growth or daily-profit guarantee.

## Hypothesis and finite domain

Test whether the BUY-side counterpart of the existing SELL48 breakout adds net
profit/day opportunities complementary to native RSI7cross30 BUY entries.
Lookback48,EMA50/slope4,H4EMA200 and BUY execution geometry are reused from
native26b8,avoiding new fitted thresholds. This is a separate entry hypothesis,
not a B2 variation or permission to bypass native gates. Failure is acceptable.

Exactly two profiles: matched Native26b8 control and J1 joint Native26b8+BUY48.
Exactly6 cost/accounting paths each,12primary cells,then6fresh repeats of the
frozen-ranked profit leader (native wins ties/no candidate qualification).

J1 addon setup at a completed UTC Bid M15 bar:

1. `close > max(high of previous48 observed complete M15 bars)`; current high
   excluded. Repeated qualifying breakout bars are independent signals under
   the same native timing/capacity gates,not a new crossover rule.
2. `close > EMA50` and `EMA50 > EMA50.shift(4)`,adjust=False,min_periods50.
3. `close > complete closed H4 EMA200`,using exactly the frozen native research
   mapping. Only16complete M15 H4 buckets contribute; incomplete latest H4 or
   insufficient warmup yields unavailable,never carried/future-filled context.
   Historical helper uses200valid H4 closes for EMA availability; this does not
   requalify current Demo's independently documented bootstrap requirements.
4. No RSI/body/session/ATR-compression filter is added. Canonical ATR/admission
   and all native downstream rules remain. A missing prerequisite is no signal.

The source bars and frozen native frame are untouched. For addon-selected rows
only,range anchors are the actual prior48-bar high/low. Native RSI rows retain
their canonical close anchors and all native OHLC/ATR/context values.

## One shared account and deterministic arbitration

Start each path once at200USD. At every completed M15,full native signal has
priority over addon. If native direction is nonzero,choose it even if addon also
qualifies. Otherwise choose BUY addon when qualified. Never choose a lower
priority addon because a native signal later fails risk/cost/admission. A failed
native admission is not a second attempt/slot on the same bar.

Use the unchanged canonical replay once over the joint direction stream. One
position at a time; held addon cannot be preempted by native,held native cannot
be preempted by addon. Same balance/equity/HWM/daily baseline/loss count/cooldown
and costs for both. No independent profit addition,basket,top-up or hidden slot.
Initial fixed0.01,SL2.5ATR; BUYTP3R,SELLTP1.35R; nativeBE1R excluding swap at
completedM15 cadence; cost-inclusive10% entry cap,daily10%/loss2/cooldown30min.
No B2NetBE,DailySLreserve,DDpause,newforcedexit or compounding is mixed in.

Attribute each admitted position from its actual context event's signal-close
and first-quote identity. Native/addon realized contributions must sum to joint
net. Retain every rejection and shared-capacity effect. Compare control-admitted
native signal identities against joint native admissions; report missing/extra
identities and actual joint reasons,including whether busy with an addon.
Reference control PnL for a missing trade is not an additive realized loss or
estimate of money the bot would have made. No invented missed-profit claim.

## Data,costs and immutable comparator

Reuse the exact exposed Exness Bid/Ask tape/manifest from the completed parent:
requested2024-09-01T00:00:00Z through2026-10-24T00:00:00Z exclusive. Keep the
actual first/last quote and acquisition/source hashes. Do not extend or redownload
the window silently and do not call reused history fresh holdout.

All6views include modeled swap: base/stress/fee crossed raw/cent loss flags.
Base extra spread/slippage/commission0;stress.2/.1/0;fee.2/.1/7USD perlot roundtrip.
Inherited historical long−567.4POINTS,short0,point.001/contract100 and original
UTC-midnight preceding-business-day calendar,Wednesday triple,weekends0. No
replacement with currentDemo−490.0 or newly inferred DST/holiday attestation.
Missing/unsupported swap,calendar/day/input blocks economics. COST_INCONCLUSIVE.

Fresh native control result must exactly equal all6archived current-native
result dictionaries. Shared engine/source/config pins remain read-only. New
selector/report/driver/verifier/tests/spec/catalog and all parent artifacts/
inputs are frozen before first addon economic cell. No old source pin edits.

## Daily MTM and coverage — frozen definitions

Report every calendar day in the effective sample,including no-entry days and
partial edge days. Day start200USD at requested start. Each daily end is the
next UTC midnight,clipped only on the final partial day to `last_actual_tick+1ms`
or requested end,whichever is earlier. No bars or quotes are synthesized.

For mark boundary B,use completed ledger exits with `exit_ms < B`. If a trade
was entered before B and exits at/after B,it is held for that boundary. Use the
last actual executable Bid(BUY)/Ask(SELL) quote strictly before B,less declared
spread adjustment and entry commission,plus signed modeled accrued swap at
`B−1ms`. Entry slippage already resides in entry price; no extra hypothetical
exit fee/slippage is deducted from an unrealized mark. Complete closes use actual
modeled trade net. This is an executable-side MTM convention,not forced sale.

When flat,mark is reconciled realized cash,even without a quote. When held,
record actualquoteUTC/age and cutoffUTC. Age>60seconds or absent quote is
BOUNDARY_PRICE_UNVERIFIED; a carried actual price may be reported as modeled
MTM with explicit stale coverage,never an observed midnight equity proof or
fabricated candle. Missing price stays unknown. Daily net is successive marks'
difference; both boundaries must be verified for observed-price daily statistics.
Modeled daily and verified-boundary distributions are separate. Final partial
day and any modeled END_OF_SAMPLE close are flagged,not full-day evidence.

Daily rows: start/end/cutoff/quoteUTC and age,MTMequity/net,coverage,full-dayflag,
entries by source,closes,held exposure,no-entry-dayflag. Distribution: modeled and
verified-boundary positive/negative/flat/unknown counts,mean/median/worst/best,
no-entry days,entry days,held/no-entry days,partial days. Sum modeled daily net
over actual covered marks must reconcile finalbalance−200; unknown cannot become0.
No claim of all-day profit from closed-trade cash or sparse sampled equity.

## Ranking,audit and stop rules

Keep original qualification floors plus survival,positive net and full-tick
DD<=40% in all6views. Rank qualified by greater rawbase net,then rawstress net,
then lower worst6DD; native wins exact ties. An improvement additionally requires
all6nets at least matchednative within1e-7USD and strict rawbase net increase.
Lower-profit/lower-risk alternatives are separately labelled,no forced winner.
Do not add a daily-profit floor or change ranking after daily distributions.

Independent audit reconstructs addon equations/arbitration/entry identity from
causal bars and complete H4 inputs,position capacity/cash/volume/costs/full-tick
DD,minima,streak/severity/recovery and daily MTM using separate ledger/time-vector
equations. Every native/addon admission/rejection witness and all6fresh selected
repeats reconcile. Report missing/extra native identities and their reasons.
Tests cover prior48excludescurrent/future,EMA/H4warmup/unavailable,corepriority,
no fallback/no double slot,BUY/SELL shared capital,swap/fees/cooldown/dailybudget,
daily flat/held/rollover/stale/partial/timestamp identity and loss distributions.

Stop on source/input/cost/domain drift,native parity failure,accounting/capacity/
daily reconciliation failure,missing calendar/nonfinite cash or <2GiB disk.
One process,memory-map existing tape,no tape copy or old-artifact deletion.
Retain failed/partial artifacts. No Demo/real-money activation follows research.
Any selected candidate still needs a distinct prospective freeze before unseen
observations; collector counts and six reused cost views are not qualification.
