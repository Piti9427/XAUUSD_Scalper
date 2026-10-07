# Strategy discovery campaign, parity and Demo gates

Owner-approved scope: improve net profit, win rate and drawdown over **both** frozen Pure B1 and Donchian48 parents, using common ticks, costs and account simulation. Absolute DD <=20%, realized RR >=1 and net >0 under base and stress. Fixed 0.01 lot, single position, no recovery, admission cap <=10%. A breakeven trade is not a win; undefined RR fails.

## Frozen discovery protocol

Public seams: `breakout_logic.replay(frame, ticks, broker, rules, costs, start=..., end=...)` and `strategy_campaign.qualifies(base, stress, baselines, min_trades=...)`. The runner persists exact source/input hashes, candidate list, rules, costs and formulas before evaluating candidates.

384 predeclared candidates, batches <=48. Parents retain original indicators, SL2.5ATR and TP6.25ATR/core or TP3ATR/Donchian48. Hypotheses: breakout depth, next-close confirmation, boundary retest within4 bars, reverse a failed breakout within2 bars; fixed exits, failed close, stagnant8 bars or candle trail after .5 initial net R. Reduce admission caps to2.5/5/10% and daily loss thresholds5/10/20/40%. Originating setup must pass parent filters; delayed trigger uses frozen setup boundary. Failed reversal uses originating guards and reverses direction only after close inside original range. Trailing never widens and acts on later ticks.

All discovery windows must independently pass: full >=60 trades; each chronological half >=20. Compare each cost scenario against both parents, requiring higher net and WR and lower DD. Rank passing candidates by lower full base DD, higher full stress net, fewer changed rules, trial id. No validation metrics participate in selection. Campaign exhaustion produces a truthful no-candidate verdict; a new campaign requires a new documented hypothesis and protocol. No threshold relaxation.

Base: recorded Bid/Ask spread, explicitly recorded commission assumption/source. Stress: +$0.20/oz spread and $0.10/oz adverse slippage on each market fill (TP fills at target). Risk includes modeled exit slippage and round-trip commission. Swap not modeled without verified account entitlement/history; no Demo qualification from this campaign.

## Independent validation and execution

Need >=12 months actual nonempty Bid/Ask coverage and >=3 months never used for selection. Existing184 days are reused discovery; zero-tick early months do not count. Freeze one winner before unseen evaluation; require >=30 trades and same profit/WR/DD/RR/cost gates. Failure consumes that unseen window; insufficient trades means insufficient evidence.

Only a historically qualified winner proceeds to MQL5 EA port. Verify signals, first quote entry, SL/TP rounding, cost-inclusive risk, exits and restart against Python fixtures. Then real-tick MT5 tester with execution delay and broker journals. Shadow >=20 trading days and >=30 eligible decisions; zero unexplained mismatch/risk breach. Demo orders require separate owner approval.

## Artifacts and operation

Run `.venv/bin/python -m scripts.research.run_strategy_campaign --output data/<new-run> --batches 8`. Resume same campaign using `--resume`, identical source/input/protocol required. Trial completion markers hash result artifacts. New path required after source changes. Never overwrite existing completed experiment history.

Per trial: full/half base/stress metrics, trades, equity checkpoints, reasons, cost attribution. DD calculated over every observed tick; equity files retain segment endpoints/extrema and midnight marks, not every tick. Output is local ignored data; tracked review summary references hashes and verdict. Central history appends `from`, tested logic/config, evidence and verdict; frozen core changes only after separate adoption decision.

The runner currently reads the existing audited six-month archive. It deliberately does not claim unseen validation, swap qualification, MQL5 readiness or Demo readiness. Implementing the winner-dependent port requires a qualified winner and missing evidence above.
