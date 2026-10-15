# C22 profitable exits per month — 2026-10-15

Owner clarified “เน้นที่เพิ่มไม้กำไรของเดือนขึ้น”. Primary objective is higher
monthly count of closed net-profitable positions,not total entries. Re-rank using
winning exits first; prior frequency objectives/results remain frozen. Current
Demo unchanged. New adaptive follow-up uses prior leaders,reused discovery;
not unopened holdout,prospective/native/performance qualification.

Define net-profit winner: ledgernet includes commission AND swap; DecimalUSD-cent
ROUND_HALF_UP >0. Floating BE/subcent noise excluded from count only,ledger cash
unchanged. Attribute to UTC EXIT month. Monthly full scope24 monthsOct2024–Sep2026,
requested AND first/lastquote-bracketed;partial excluded/labelled,zero/warmupfull
months included. Report mean,median,p25,monthlycounts and cash. Compare current
proposal RSI30 (9bb30c154de68d07) and original tunedb823f4aefe10fc72.

Freeze17cases/34economiccells before new economics,validated existingdomains:
1 tuned;2RSI30;3SELL48;4SELLTP1.35;5RSI30+SELLTP1.35;
6SELL48+SELLTP1.35;7RSI30+SELL48+SELLTP1.35;
8RSI30+BUYTP1.5;9SELL48+BUYTP1.5;
10RSI30+SELLTP1.35+BUYTP1.5;11SELL48+SELLTP1.35+BUYTP1.5;
12RSI30+BUYTP1.35;13SELL48+BUYTP1.35;
14RSI30+SELLTP1.35+SELLSL2ATR;
15SELL48+SELLTP1.35+SELLSL2ATR;
16RSI30+SELL48+SELLTP1.35+SELLSL2ATR;
17RSI30+SELL48(priorfailedDD control).
All inherit RSI7/BUYEMA50/SELLEMA50/H4EMA200 unless noted,BUYSL1.5ATR/TP2R,
SELLSL2.5ATR/TP2R,BE1R,fixed0.01,USD200,daily10%,max_daily_losses0,
cost-inclusive10%initialcap,one position,no recovery. No cap/lot change.

Same167622055pairedExnessquotes and48465completedM15bars,canonicalpublichelper.
Requested2024-09-01UTC→2026-10-06T17:22:04.296998UTC;actualfirst
2024-09-01T22:05:06.129UTC,last2026-10-05T23:59:59.969UTC. Same archived rates:
mandatorymodeledpoints swaplong−567.4/short0,point0.001,Wednesdaytriple,
assumedUTCmidnight. Basecommission0,stress40USD/lotroundtrip(USD0.40at0.01),
quotedBid/Askunchanged,noextraspread/slippage. COST_INCONCLUSIVE,metadata validated;
missing/unsupportedblocks,no no-swap economiccell or zero substitution.
Canonicalfeeupfront/fee-inclusiveBEcompletedM15/strictopenmidnightbaseline,
not nativeper-tickBE/Testereconomics/Demoprocessbaseline parity.

Screen BOTH views: netpositive,DD<=40%,survival,fixedlot/cap<=10%,no terminalrisk
lockout,mean profitableEXITS strictly aboveRSI30,medianmonthlyprofitableEXITS
not belowRSI30,medianmonthlycash>=0 andpositivecashmonths>=50%. Total entry count
is descriptive,not admission/selection objective. Two preregisteredprofiles:
profitable-exits-first allows lower positive net;profit-floor adds net>=original
C22tuned inbothviews. Rank higherminimum both-viewmeanwinningexits,then median,
thenp25,thenmedianmonthlycash,net,lowerworstDD,stableID. If none pass,
NO_PROFITABLE_EXIT_INCREASE;do not relax gates after results.

All34cells account/lot/risk/nonoverlap/swap audits. Five prior cases/10cells must
match entire verifiedpreviousresult except newcase-name/derivedwinmetric.
Repeat tuned+RSI30+top3 eachprofile(deduplicate);selected candidates require
both fresh whole-result repeats. Others screening only. Preserveeveryresult.
Source/input/protocol/runtime hashes,snapshots,completed-artifacthashverification,
persistedmonthlycount/cash/swaprecomputation. Freshoutputonly,no unverifiedresume.
Rawartifacts ignored `runs/c22-profitable-exits-2026-10-15/`;humanMD inreviews.
No sender/config/Demobaseline/costattestation/nativeport changes or promotion.
