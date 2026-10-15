# Profitable-exit daily guard follow-up — 2026-10-15

Ownergoal remains “เน้นที่เพิ่มไม้กำไรของเดือนขึ้น”. Initial17case/34cellcampaign
found no paired candidate aboveRSI30 winning-exits floor withinDD40%.
Closest RSI30+SELLTP1.35 stressDD40.19%;RSI30+SELL48+SELLTP1.35 stressDD43.57%.
Preserve initialfailure/gates;do not round or relax40%threshold. Adaptive second
bounded batch uses daily losing-exit guards to test safer win-count paths.

Freeze10cases/20swapcells before new results: tuned andRSI30 controls;four seeds
(RSI30+SELLTP1.35;SELL48+SELLTP1.35;RSI30+SELL48+SELLTP1.35;
RSI30+SELLTP1.35+BUYTP1.5),eachmax_daily_losses1 and2. Originaltunedcount0
onlycontrols. Dailycap10%,initialriskcap10%,fixed0.01,USD200,oneposition,no recovery
unchanged. Countguard blocks entries after namednumber of net-losingexits perUTCday,
not change to Demo process dailybaseline. All research-only;no runtimeadoption.

Same exact input,costs,cent-positiveUTC-exit metric,gates/profiles/rank/provenance
as initial [profitable exits spec](2026-10-15-c22-profitable-exits-first.md).
Primarymeanwinningexits>RSI30 BOTHviews,medianwinningexits>=RSI30,netpositive,
DD<=40%,fixedlot/risk/survival/no terminalrisklockout,medianmonthlycash>=0,
positivecashmonths>=50%. Profitfloor additionally net>=originalC22tuned.
Entryfrequency notgate/rank. Mean/median/p25 winningexitcount primary;no gate
relaxation or cherry-pickedmonthlydenominator. Bothcontrols verify entireprior
same-costresult;top3perprofile pluscontrols freshlyrepeatbeforefinalselection.
Ifnonepass reportNO_PROFITABLE_EXIT_INCREASE;currentRSI30 remains measuredsafebest
among completedcandidates,no guarantee and no newDemoqualification.

All20cells include modeledswaplong−567.4/short0,point0.001,Wednesdaytriple,
assumedUTCmidnight,commission0/40USDperlotRT withrealpairedquotesunchanged.
Missingmetadata blocks,no newno-swapscenario. COST_INCONCLUSIVE,currentbrokerhistory
unverified. Same167622055Exnessquotes through2026-10-05,reusedadaptivediscovery,
not untouchedholdout/nativeTester/forwardevidence. Canonicalfeesupfront/barBE/
strictopenmidnight differs from native/runtime. All20audited,no partialresume.
Freshoutput `runs/c22-profitable-exits-2026-10-15/campaign-02/`;artifacts ignored,
source/input/runtime/protocol/result hashes/snapshots;humanverdictMDinreviews.
