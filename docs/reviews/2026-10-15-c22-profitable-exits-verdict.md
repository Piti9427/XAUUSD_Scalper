# C22 profitable exits per month — 2026-10-15

**Selected modeled research case81a78454baaffcd1: RSI30 + SELL48 + SELLTP1.35R +
max_daily_losses2.** Owner clarified “เน้นที่เพิ่มไม้กำไรของเดือนขึ้น”; ranking
now prioritizes net-profitable closed positions per month, not total entries.
Both profitable-exits-first and original-tuned-profit-floor profiles select same case.
Active Demo unchanged; results remain COST_INCONCLUSIVE/not native Tester.

**Final conservative follow-up:** after both daily-count rounding models,stress
still gives8.67profitableexits/month,median9,net784.56USD,DD38.02%. Rawguard figures
below retain originalmodel history; completedroundingsensitivity section gives
fullcomparison. This is the measured case to communicate,not a broker guarantee.

Stress+swap: mean profitable exits6.96→8.71/month (+25.15%) versus previousRSI30,
median7.5→9,p25 5→7;net617.24→876.93USD,DD38.33%→36.88%.
Relative to original tuned5.83/month,profitable-exitcount rises49.29%.
Base mean6.79→8.54/month,net758.69→1186.66USD,DD32.94%→30.93%.
These are descriptive24-full-month statistics,not promised monthly minimums.

## Compared cases

All startUSD200/fixed0.01/cost-inclusive10%initialcap/daily10%,oneposition,no recovery.
Profitable positions include commission+swap;DecimalROUND_HALF_UPUSDcent>0,
attributed toUTCexitmonth. Ledger/accountcash untouched. Partialmonths excluded,
warmup/zero fullmonths included;24monthsOct2024–Sep2026.

| Case | View | Profitable exits/month | Median winning exits/month | Net USD | Final USD | Max DD | Median monthly cash USD | Positive cash months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original C22 tuned | Base+swap | 5.75 | 6 | 741.10 | 941.10 | 29.64% | 16.37 | 17/24 |
| Previous RSI30 | Base+swap | 6.79 | 7.5 | 758.69 | 958.69 | 32.94% | 11.02 | 12/24 |
| Selected RSI30/SELL48/TP1.35/daily2 | Base+swap | 8.54 | 9 | 1186.66 | 1386.66 | 30.93% | 19.61 | 16/24 |
| Original C22 tuned | Cash stress+swap | 5.83 | 6 | 603.57 | 803.57 | 36.96% | 21.95 | 16/24 |
| Previous RSI30 | Cash stress+swap | 6.96 | 7.5 | 617.24 | 817.24 | 38.33% | 4.70 | 12/24 |
| Selected RSI30/SELL48/TP1.35/daily2 | Cash stress+swap | 8.71 | 9 | 876.93 | 1076.93 | 36.88% | 13.52 | 16/24 |

Selected205/209 cent-positive exitedpositions over fullmonths(base/stress),
546/542totaltrades acrossentirerequest;546total does not mean546winningtrades.
Monthlypositivecash16/24 improvesRSI30's12/24,but stressmedianmonthlycash13.52USD
still below originaltuned21.95USD. More winners do not guarantee more cash eachmonth.
Selectedswap−58.4422USD inbothviews;model fees/base0 andstress40USDperlotRT.

## Strategy contract

Research parameters: RSI7cross30 withBUYEMA50;SELLDonchian48/EMA50;closedH4EMA200.
BUYSL1.5ATR/TP2R,SELLSL2.5ATR/TP1.35R,BE1Rbothsides;fixed0.01,riskcap10%,daily10%.
Stop new entries after2net-losingexits inUTCday;originaltuned/RSI30count0 replaced
onlyforresearch case. Guard differs from Demo's one-loss policy;no runtimepolicy,
process-scoped baseline/sourcepin change. No recovery/martingale/riskcap removal.
[Research config](../../config/research-c22-profitable-exits-81a78454baaffcd1.json).

## Bounded stages and selection

[Initial protocol](../specs/2026-10-15-c22-profitable-exits-first.md):17cases/34cells
combining priorleaders. No candidate exceededRSI30 mean+median profitableexitfloor
withinDD40% bothviews. ClosestRSI30+SELLTP1.35 hasstress8.00wins/month butDD40.19%;
RSI30+SELL48+SELLTP1.35 gives9.08wins/month butDD43.57%. Both rejected without
rounding DD threshold or changing gates.

[Daily guard follow-up](../specs/2026-10-15-c22-profitable-exits-daily-guard.md):
10cases/20cells,controlsplusfourshortTPseeds×dailycount1/2. Adaptivefollow-up,
not out-of-sample. Meanwinner>RSI30 BOTHviews,medianwinner>=RSI30,positiveoverallnet,
DD<=40%,fixedlot/risk/survival/no terminalrisklockout,medianmonthlycash>=0,
positivecashmonths>=50%. Profitfloor profile additionallynet>=originaltuned.
Primaryrankminimumacrossviewsmeanwinningexits,thenmedian,p25,monthlycashmedian,
net,lowerworstDD,stableID. Entrycount descriptive,no frequencygate.

Pairs below showbase/stress. Onlytwo follow-up candidates screenpass and freshly
repeat; others remain failed screening. Both stages retaineverycell includingfailures.

| Case | Winning exits/month pair | Median winning exits pair | Net USD pair | DD % pair | Screen |
| --- | ---: | ---: | ---: | ---: | --- |
| c22_tuned | 5.75/5.83 | 6.0/6.0 | 741.10/603.57 | 29.64/36.96 | Comparator |
| rsi30 | 6.79/6.96 | 7.5/7.5 | 758.69/617.24 | 32.94/38.33 | Comparator |
| rsi30_r135_loss1 | 5.25/5.38 | 5.5/5.5 | 457.70/325.74 | 45.81/53.55 | FAIL screening |
| rsi30_r135_loss2 | 7.54/7.75 | 8.0/8.0 | 886.56/754.74 | 32.14/35.97 | PASS + repeat |
| sell48_r135_loss1 | 5.50/5.67 | 5.5/5.0 | 527.76/512.97 | 45.96/53.08 | FAIL screening |
| sell48_r135_loss2 | 7.54/7.21 | 7.0/7.0 | 1092.00/531.89 | 31.09/45.61 | FAIL screening |
| rsi30_sell48_r135_loss1 | 6.00/4.04 | 6.0/4.0 | 576.23/-84.33 | 47.57/72.83 | FAIL screening |
| rsi30_sell48_r135_loss2 | 8.54/8.71 | 9.0/9.0 | 1186.66/876.93 | 30.93/36.88 | PASS + repeat |
| rsi30_r135_buy15_loss1 | 6.46/4.58 | 6.0/4.5 | 447.42/-110.92 | 49.64/74.17 | FAIL screening |
| rsi30_r135_buy15_loss2 | 9.12/8.58 | 10.0/10.0 | 745.45/283.59 | 35.06/63.12 | FAIL screening |

## Economic scope and costs

Same167622055pairedExnessquotes/48465completedM15bars,requested2024-09-01UTC→
2026-10-06T17:22:04.296998UTC;actualfirst2024-09-01T22:05:06.129UTC,last
2026-10-05T23:59:59.969UTC. Fullrequestedmonths also bracketedbyactualquotes;
partialSep2024/Oct2026excluded. Internalcoverage not proved byendpoints.
Reuseddiscovery throughOct5,no newmarketdata/unopenedholdout/forwardqualification.

Mandatorymodeledswaplong−567.4/short0points,point0.001,Wednesdaytriple,assumedUTC
midnight;Basecommission0/cashstress40USDperlotroundtrip(USD0.40at0.01). ActualBid/Ask
unchanged,noextraspread/slippage. Missingmetadata blocks,no no-swapscenario/zero
substitution. COST_INCONCLUSIVE:archivedrate/calendar,not currentbrokerhistory.
Canonicalfeesupfront,fee-inclusiveBEcompletedM15,strictopenmidnightbaseline;
not nativeEA raw-priceper-tickBE or Demo processbaseline parity.

## Rounding limitation found during audit

Profitable-exitmetric itself removes cent-zeroBE noise;selected winner haszero
excludedpositive-noisepositions inbothviews. Frozen daily losing-exit guard uses
rawledgernet<0. Selectedstress hasfourlosses−0.004/−0.004/−0.004/−0.002USD that
round tozero cents. On2026-02-09,realmodel loss−23.355USD plus−0.002USD consumed
count2 and blocked a21:45UTCentry. A broker rounding closingcash tocent may count
thatday differently; source/frozen ledger intentionally unchanged. Therefore
**daily-loss cash rounding and broker lifecycle parity remain unverified** before
adoption;winningcounts/repeats confirm namedmodel,not actualbrokerbehavior.
Witness retained `selected-rounding-sensitivity.json` under ignoredruns.

## Completed guard-rounding sensitivity after owner continued

[Additional frozen protocol](../specs/2026-10-15-c22-profitable-exits-rounding.md)
tested only rawlosscounter versusUSDcentROUND_HALF_UPlosscounter. Private compiled
canonicalfunctioncopy changesexactlyoneguardpredicate;rawfrozenfiles/globals remain
unchanged,ledgercash/prices/fees/swap not rounded. Cooldown0 inbothcases. This tests
dailycount sensitivity,not fullbrokerposting/nativeexecution/accounting parity.

**PASSES_BOTH_GUARD_MODELS**:all4cells and4freshwhole-resultrepeats pass,rawcontrol
entireresultmatches precedingselectedcase. Conservative stressresult retains
8.67profitableexits/month,median9,p25=7,net784.5628USD,final984.5628USD,DD38.0213%.
Rawguard stress8.71/net876.9278/DD36.8756%. Base unchanged8.54/net1186.6618/DD30.9268%.
Bothmodels stillbeat priorRSI30 mean6.96andmedian7.5 and originaltuned both-viewnet.

| Selected case guard | View | Winners/month | Median winner count | Net USD | Max DD | Positive cash months |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Raw net guard | Base+swap | 8.54 | 9 | 1186.66 | 30.93% | 16/24 |
| Cent guard | Base+swap | 8.54 | 9 | 1186.66 | 30.93% | 16/24 |
| Raw net guard | Cash stress+swap | 8.71 | 9 | 876.93 | 36.88% | 16/24 |
| Cent guard | Cash stress+swap | 8.67 | 9 | 784.56 | 38.02% | 15/24 |

Actualwitnessconfirmed:centguard admits2026-02-09T21:45:00.039UTC andsubsequent
equity/admissionpath removes2026-03-19T08:15:00.175UTCentry. Netdeclines92.365USD
andfull-monthwinnercount209→208. Roundingdetail materially affectsnet,evenwhen
winner-count qualification survives. Monthlycashmedian remains13.52USD;profitable
cashmonths15/24 undercentguard versus12/24 previousRSI30 and16/24 originaltuned.
Useconservative observed8.67/net784.56/DD38.02 when communicating selectedcase.
These bounds cover only the two testedguardmodels,not all possiblebrokerbehavior.

Independentall4cash/risk/lot/nonoverlap/swap/monthlyexitcentcount audits,scenario-
specificdailyguard checks,completedartifacthashes andpersisted4repeats PASS.
FrozenDemo pins9/9intact. Additionalartifactscampaign-03-rounding/ and
rounding-audit-final.json. Combinedsearch58economiccells and16freshrepeatcells,
includingrepeatedcontrols,not58uniqueconfigs. Modelcosts remainCOST_INCONCLUSIVE,
fullcashposting/nativeport/forward/brokerparity remainsunverified. NoDemoadoption.

## Validation and artifacts

Bothcampaigns exit0.54new economiccells (25uniqueconfigs with repeatedcontrols),
12freshwhole-result repeatcells:4stage1controls,8stage2controls/finalists. Entire
prior controls match verifiedprecedingresults exceptnames/newderivedwinmetric.
Independentall54cash/lot/risk/nonoverlap/swap/monthlycash/exit-monthcent-count audits,
all completedartifacthashes and12persistedrepeat equalities PASS. Per-admission
UTCdailyguard count auditPASS;inputhashes reverified aftercompletion.

Literal Jan-entry/Feb-exitfixture:0.004USD/subcentBE noise excluded,0.005/0.014USD
countaspositivecents only inFeb,partialMarchignored. Policycontrols show100entries
withoutmorewinningexits cannot qualify;fewerentrieswithmorewins canqualify;
onebadstressview blocks. Configcatalogunique/supported. Focusedcommand
`PYTHONPATH=.:tests .venv/bin/python -m unittest test_c22_frequency.AdapterTests
 tests.test_native_frequency_replay`:9tests,OK,exit0. No productioncode edits.

Artifacts ignored `runs/c22-profitable-exits-2026-10-15/`:campaign-01/02 protocols,
cells,repeats,source_snapshots,results,COMPLETE;adjacent audit-final.json,
policy-controls.json,research-handoff.json,roundingwitness,logs. Humanreportonly
indocs,norawrunoutputs. Source/input/runtime/config/result hashes retained.
NativeportNOT_IMPLEMENTED,newflatJSONnotrunnableMT5preset. ActiveDemounchanged;
realmoney/notifiedorders/sourcepins/baseline/attestation untouched. Completion is
bounded modeledresearch selection,not broker/native/forward/readiness qualification.
