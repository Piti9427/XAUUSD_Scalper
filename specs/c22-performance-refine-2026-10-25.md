# C22 performance refinement — frozen after first-stage discovery

First-stage18case results are already observed. BUY stop2.5ATR passes the owner's
base/stress profit floors and all6DD<=40% conditions; cooldown4bars improves
stress/DD but lowers base profit. This is an adaptive discovery continuation,
not an independent validation or a new holdout. Preserve Stage1outputs and pins.

Before any Stage2outcome, freeze five combinations on the original research
seed9e511d195c52ef3d: BUYstop2.5+cooldown4; BUYstop2.5+dailycount1;
BUYstop2.5+SELLtarget2R; BUYstop2.5+cooldown4+SELLtarget2R;
BUYstop2.5+cooldown4+dailycount1. SELLtarget2R and dailycount1 already have
archived evidence of stress/DD trade-offs; they are hypotheses, not assumed wins.
Total newly searched contracts across both stages is23including the baseline.

Use identical full-history ticks, original200USD, fixed0.01, single position,
initial cap10%, daily10%, no recovery, no lot increases. Every scenario includes
the same named modeled swap; require the existing input/source/cost metadata.
No broker call, deployment, active Demo edit or source-pin substitution.

Run base/stress/fee for all five; review the two best raw-qualified cases under
cent-counter sensitivity. Both base and stress must meet the matching original
research seed's raw/cent profit floors. Every reviewed scenario requires modeled
survival, positive net and observed equity DD<=40%. Keep the existing Stage1
winner as an explicitly reused, hash-verified candidate. Rank maximum base net,
then stress net, then lower maximum DD; report recovery separately. If no new
case improves the rank, retain the Stage1winner without claiming Stage2improved.
If no candidate passes full qualification, selected=null/NO_QUALIFIER; no export.
Fresh-repeat all6paths of the final selected candidate. Independent accounting,
swap calendar, daily admission and source checks remain required. Retain failed
cells, raw/cent differences and cost-inconclusive/selection-bias disclosures.
