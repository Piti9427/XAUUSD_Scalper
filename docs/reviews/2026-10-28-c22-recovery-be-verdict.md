# Selected26b8 B2 recovery NetBE — verified no profit improvement

**Keep native26b8.** The preregistered B2 hypothesis lowered net in every matched
cost/accounting view. It reduced DD and worst loss-run severity, but did not
improve minimum equity,11-loss streak or completed/ongoing closing-balance
recovery. Native Demo/source/config/fixed0.01/risk/BE rules were not changed.

Base/raw net: native+1,945.334USD versus B2+1,719.1624USD; difference−226.1716USD
(−11.6264%). Final balances2,145.334 versus1,919.1624 from200USD. Base full-tick
DD34.27499655% versus32.40685633% (−1.86814percentage points). Worst six-view
DD38.67102055% versus37.73864783%. All six pass DD<=40%,but lower profit cannot
be called the requested profit-maximizing improvement.

Raw stress net1,471.870→1,470.5646USD; raw fee1,464.592→1,463.3786USD.
Cent fee1,416.994→1,416.3686USD; base/stress cent match their raw values.
Minimum equity remains187.6636USD in base and146.481USD in the worst fee view.
Longest completed recovery remains125.202days in base/130.29858days in stressed
views; ongoing60.778days. These durations are closing-balance peak recovery,
not continuous equity underwater time. Worst base loss-run severity improves
17.69095%→17.00246%; the longest consecutive losing run remains11.

## What was tested and learned

The only new policy was first accrued-cost NetBE for a trade admitted while its
pre-entry-fee balance was below the previously realized closing-balance peak.
No future/floating peak, fee-created gate, new lot, budget reset or forced exit.
Native entries, initial1R/M15 trigger, fixed0.01, risk10%,daily10%/loss2/cooldown
remained. Eligibility freezes at entry; first successful adjustment freezes BE.
Later swap/gaps can still produce a net loss.

B2 base/raw had462trades versus native460. Of462B2 entries,409were in recovery;
171received the changed first NetBE. The gate therefore covered most positions,
not a rare losing subset. Earlier exits also change later capacity/equity
admission,so profit differences must be measured jointly rather than assigned
solely to one clipped winner. This hypothesis did not meet the frozen matched
native profit criterion. Do not retune its threshold after observing results.

## Reproducible evidence

Campaign `runs/c22-recovery-be-2026-10-28/` contains12fresh primary cells,two
profiles×base/stress/fee×raw/cent,plus6fresh native-winner repeats. Native
overlay-off result dictionaries exactly match all six archived controls.
Independent accounting reconstructs signed fees/swap/cash/volume/risk/daily
admission. Independent source-tick scans check full-tick DD/HWM/minimum for all12.
B2 eligibility/closing peak is rebuilt from realized price/cost cash,not copied
from candidate booleans; the BE audit reconstructs source-quote activation,
signed accrued swap,grid rounding/no-loosen and first-success behavior.

Protocol frozen28Oct14:20:49.474671UTC before economics, SHA256
f3bdfa9f1b034ab6dceb83d1786538ba9f894aa7886f0bc1dc9008a038c1d88b.
It preserves110parent pins and adds6new source/spec/test pins. Actual input hashes
were checked. Prior hypothesis and pre-economic UTC-calendar wording erratum are
retained. No gates,catalog,costs or pinned source changed after outcomes.

`independent-verification.json` PASS covers12cells,6fresh repeats and12full-tick
paths; SHA2561d5260e341e73b593abf8f50083c233caa3291eacd4e5229aa9938b181ea056f.
FINAL.json is VERIFIED_COMPLETE,strict_profit_improvement=false,retain_native=true.
The verifier uses separate cash/calendar/tape equations and never invokes the
new replay. Final code review was by root because focused agents reached their
usage limit; this is independent mathematical reconciliation,not an assertion
of a separate final human/agent review or live broker execution.

Sources:171,171,013 real Exness Bid/Ask quotes on the pinned exposed history;
requested2024-09-01 through2026-10-24exclusive. Modeled long swap−567.4POINTS,
short0,point.001,preceding-business-day UTC-midnight calendar/Wednesday triple
inherited exactly. Stress extra spread.2/slippage.1; fee adds7USD/lot roundtrip.
All scenarios include modeled swap. Current Demo−490.0 was not substituted into
history. Historical broker cost/holiday parity remains unverified and results
remain COST_INCONCLUSIVE. Six cost views reuse market data,not six independent
samples; there is no fresh holdout or forward-profit proof.

Interactive Matrix:
`/Users/nopparuj/.cursor/projects/Users-nopparuj-my-agents-XAUUSD-Scalper/canvases/C22-recovery-BE-2026-10-28.canvas.tsx`.
Strict TypeScript checkPASS0diagnostics. Source/verification hashes are retained
alongside the campaign. No raw run dump is committed under this report.
