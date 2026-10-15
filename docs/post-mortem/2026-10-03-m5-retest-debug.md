# M5 replay review regressions

Spec review reproduced pending BUY boundary100/TTL2 with first eligible M5 close100
and second touch/close100.4. Public regression command:
`.venv/bin/python -m unittest tests.test_breakout_logic.BreakoutLogicTests.test_m5_boundary_equality_keeps_pending_until_valid_trigger`
RED: trades0 !=1, deterministic0.010s. Hypotheses: strict-side cancellation,
TTL off-by-one, setup availability. Changing only `not beyond` to strictly negative
signed close distance gave GREEN1test/0.014s; TTL/availability unchanged. Equality
is neutral, consumes one TTL bar, allows later valid trigger. Both original64-catalog
results retained as superseded; corrected campaigns use new output/source hashes.

Standards review public future-mutation repro: M5 open23:50 should become available
23:55, but prior-day mapping used +15min and selected next-day key containing
current-day future23:55 candle. Mutating only that future close102->99 changed
trade admission1->0. Public regression command:
`.venv/bin/python -m unittest tests.test_breakout_logic.BreakoutLogicTests.test_m5_prior_day_guard_does_not_read_future_midnight_bar`
RED trades1!=0/0.012s; changing only mapping duration to selected bar minutes gave
GREEN1test/0.020s. Current frozen catalogs guardoff, but public API was causal-broken.
Default M15 remains +15, optional M5 uses +5. No logs/probes added to production.

Prevention: explicit equality case for state-machine transitions and future mutation
at midnight for every supported timeframe. Known-source/whole-result repeats still
needed; successful unit fixtures alone do not prove strategy profitability.

Catalog construction follow-up: after renaming typed localprofiles toreward_profiles,
one product reference retained oldname. Actual CLI failed UnboundLocalError before
input audit/output/scenarios. Corrected reference; public campaigncatalog->Rules->
replay test now constructs all444 current configs, verifies frozen uniqueness,
counts and USD200 initialbalance. No failed result promoted or overwritten.
