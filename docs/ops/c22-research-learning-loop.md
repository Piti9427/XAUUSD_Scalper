# C22 offline learning loop

Research entry point: `scripts/research/c22_learning_loop.py`. This is separate
from the frozen Demo sender and does not send orders. Strategy/risk authority is
CORE_STRATEGY section6.49; frozen experiment contract is
`specs/c22-learning-loop-2026-10-25.md`.

## Run and resume

Existing local inputs and parent artifacts are required. No dependency install
or broker connection is needed for this workspace:

```bash
PYTHONPATH=. .venv/bin/python scripts/research/c22_learning_loop.py --workers 2
PYTHONPATH=. .venv/bin/python scripts/research/c22_learning_verify.py
PYTHONPATH=. .venv/bin/python scripts/research/c22_learning_report.py
```

First command acquires one campaign lock, verifies exact sources/input/parent
hashes, reuses valid parent outcomes and resumes atomic cells. A completed run
returns `Already converged; hashes verified`. Changing worker count changes
execution parallelism, not selection order or ranking. Never edit frozen pins
to bypass a mismatch; use a separately versioned protocol/campaign for changed
data, source, assumptions or domains.

## What the loop learns

Each core slice tests all96BUYTP×SELLTP×cooldown combinations with management
fixed. Each management slice tests all54BUYSL×SELLSL×globalBE×BUYprotection
combinations with core fixed. Record all alternatives before outcomes, including
combinations whose individual components previously failed. Raw base/stress/fee
for every profile; complete cent review for every raw-qualified profile.

Profit lane retains the agreed objective and DD40. Exploratory repair lane
requires latest matched base/stress profit and no matched-path risk regression;
its explicit risk priority is DD,recovery,severity,streak. Both repeatedly
reconsider discoveries from the other lane. Equal scores keep the incumbent.
Stop after both lanes have complete no-improvement core+management cycles and
no visited eligible candidate improves either final objective.

The finite domain contains5184joint configurations. Conditional block closure
does not prove all5184were enumerated or the global optimum found. The final
report must show the actual visited count and scope of the closure claim.

## Observe progress and compare

Machine outputs stay under `runs/c22-learning-loop-2026-10-25/`:

- `protocol.json` and `source_snapshot/`: frozen provenance and assumptions.
- `phases/*-catalog.json`: complete conditional alternatives and hypotheses.
- `phases/*-result.json`: strict promotions, qualification and objective deltas.
- `progress.json`: current batch; its visited count excludes the in-flight
  slice until its required reviews finish.
- `cells/*.json.gz`, `cells-integrity/`: new full results and hashes; reused
  proofs refer to immutable parent cells without copying them.
- `COMPLETE.json`: exists only after algorithmic closure and required repeats.
- `independent-verification.json`: separate accounting, policy and tick audit.
- `matrix.json`: final matched comparisons, alternatives and source witnesses.

An interim matrix can be built during the run:

```bash
PYTHONPATH=. .venv/bin/python scripts/research/c22_learning_preview.py
```

It omits incomplete raw profiles and missing cent views, and explicitly says
PARTIAL/no final winner/audit pending. It may contain more ready raw profiles
than the official visited count. Final matrix requires COMPLETE plus independent
audit PASS. Canvas sources are saved under the run; managed Canvas placement is
a separate presentation step, not another economic replay.

## Interpretation

Risk severity uses the worst financial losing run, not merely the longest run.
Recovery includes both completed actual closing drawdowns and ongoing censored
age; the latter is not a forecast. Protected exits with negative net after
cost/swap stay losses. Monthly curves attribute net to exit month and do not
show floating tick-equity excursions. Rule effects are not additive because
holding, admission, daily gates and capital paths change together.

All views include the named modeled swap. Historical broker rates/calendar,
commission, HMR/stop-out/fill parity and source completeness remain unqualified.
All available history is research-exposed. Engineering closure and more tuning
do not establish future profit or authorize Demo replacement/real-money use.
Native selected Rules still require an explicit compatible adapter and separate
broker/forward evidence. Lot growth and recovery remain disabled.

## Exhaustive continuation and unattended follow-up

The completed conditional loop did not improve the latest incumbent. Separate
`scripts/research/c22_exhaustive_loop.py` evaluated the complete previously
declared5184grid,including interactions between both blocks. Its protocol is
`specs/c22-exhaustive-loop-2026-10-25.md`;outputs and operational handoff live in
`runs/c22-exhaustive-loop-2026-10-25/`. Do not rewrite the completed block run.

```bash
PYTHONPATH=. .venv/bin/python scripts/research/c22_exhaustive_control.py status
PYTHONPATH=. .venv/bin/python scripts/research/c22_exhaustive_control.py start --workers 2
PYTHONPATH=. .venv/bin/python scripts/research/c22_exhaustive_report.py
PYTHONPATH=. .venv/bin/python scripts/research/c22_exhaustive_verify.py --checkpoint-only
```

Control uses the exclusive campaign lock as process-liveness evidence and
does not duplicate a locked or completed campaign. Source/input hashes are
rechecked on resume. `--max-new-cells` is available on the underlying runner
for bounded continuation; it leaves PARTIAL until every required result exists.
Summary checkpoints alternate two gzip slots;economic payloads stay immutable.
Completed-batch leaders are separate from in-flight ready profiles.

Completed2026-10-25:5184profiles/162batches,15726economic paths and6fresh
selected repeats. Final independent audit PASS covers7764913accounting entries
and6selectedfull-tickDD paths.54profiles pass all gates;26b8remains both lane
selections;strictdownsiderepairs0. Final Matrix isAUDITED_EXHAUSTIVE_RESULT.
See `docs/reviews/2026-10-25-c22-exhaustive-tuning.md` andCORE_STRATEGY6.50.

Heartbeat `c22-exhaustive-tuning-continuation` formerly checked every30minutes;
it was deleted after verified closure. No restart or further scheduled tuning
is needed. Preserve completed artifacts;Control refuses to start a completed
campaign. No orders or Demo state changes occurred. Never infer future profit
or optimality outside the declared grid from exhaustive historical coverage.
