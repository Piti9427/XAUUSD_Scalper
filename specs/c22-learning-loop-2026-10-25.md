# C22 learning loop — frozen block search to convergence

Owner asks for iterative learning from downside evidence, improving strategy and
retaining a matrix against old versions. Use the smallest existing-engine
solution: exhaustive conditional parameter blocks, no production changes.

Same full-history171,171,013Exness Bid/Ask ticks through2026-10-23,49,729complete
BidM15bars. One200USD account per scenario,fixed0.01,cap10%,daily10%/count2,
single position,no recovery/top-ups/lot growth. Signal detector fixed at original
RSI7cross30/EMA50/SELL48/closedH4EMA200. Canonical replay and swap math unchanged.
Every economic scenario includes named modeled swap; missing metadata blocks.
Same base,stress,fee assumptions;COST_INCONCLUSIVE and exposed-history remain.

Native domain has5184combinations. Freeze two exhaustive conditional blocks:

- Core96: BUYTP R(1.35,1.5,2,3) × SELLTP R(1.25,1.35,1.4,1.45,1.5,2)
  × cooldown elapsedM15periods(0,1,2,4).
- Management54: BUYSL ATR(1.5,2,2.5) × SELLSL ATR(1.5,2,2.5)
  × global BEactivation R(0.5,1,1.5) × BUYprotection(off,break_even).

Each slice fixes the opposite block at its lane's incumbent. Freeze the complete
slice before outcomes. Test all raw base/stress/fee, then all raw-qualified
cent base/stress/fee. Reuse source/input/cost-identical parent cells by hashes;
do not count reused cells as new runs. Store new full cells as deterministic
compressed atomic artifacts; no omissions of failed cases.

Two separately named lanes start from latest Rules26b8bcd69e043653:

1. Profit: original matched9e511d195c52ef3d base/stress floors; all6positive net,
   modeled survival and observed equity DD<=40%. Rank rawbase net descending,
   rawstress descending,smaller maximumrawDD,as previously agreed.
2. Downside repair alternative: additionally require matched latest26b8base/
   stress profits in bothguards and every matched path's DD,recovery,severity
   and streak no worse than26b8. Rank worst6DD,then worst6recovery,then worst6
   losing-run severity,then worst6streak ascending;rawbase/stress descending
   only break remaining ties. This is an exploratory alternative,not a new
   owner-approved primary selection policy or automatic adoption decision.

Severity means worst losing-run loss% of its starting equity,not severity of the
run with longest count. Recovery means max(actual completed closing recovery,
ongoing actual closing drawdown age);display both separately and identify the
ongoing age as censored,not a forecast. Negative protected/swap exits stay losses.
Repair label requires at least one matched risk metric strictly lower;mere
profit increase with unchanged risks is not called strict downside repair.

Alternate both full blocks per lane. Promote only strictly better objective;
preserve incumbent on exact score ties. Repeat until a complete core+management
cycle makes no change. Discoveries from the other lane reopen a closed lane
if they strictly improve its eligible objective. Stop only when both lanes are
closed and remain best among all visited eligible cases. No arbitrary two-round
budget. Finite domain and strict promotion bound termination. This proves block
closure at final incumbents,not enumeration/global optimality of all5184states.
Resource failure/checkpoint interruption leaves PARTIAL,never CONVERGED.

Keep a learning ledger for each slice: incumbent downside witnesses,predeclared
parameter hypotheses,all attempted profiles,gain/regression,rejection reasons,
lane promotions. No date-specific rules or deletion of observed losers. Publish
Pareto alternatives and matched old-version comparisons; report
NO_STRICT_DOWNSIDE_IMPROVEMENT if no evaluated candidate reduces risk under the
repair conditions. Never force a winner by moving floors after outcomes.

Freeze protocol/source/input/parent hashes before new outcomes; worker count
changes runtime only. Fresh-repeat initial six parent paths and final distinct
selected paths. Independently audit cash/swap/admission and final full-tick DD.
No untouched holdout,broker cost/calendar/fill parity,future-profit or PBO claim.
Outputs runs/c22-learning-loop-2026-10-25;update CORE_STRATEGY and human review.
Current Demo,source pins,broker state and real-money prohibition unchanged.
