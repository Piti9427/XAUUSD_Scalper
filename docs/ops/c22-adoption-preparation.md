# C22 offline adoption preparation

`python -m scripts.qualification.c22` prepares evidence for a later shadow →
Demo decision. It has no broker connection or order/service/configuration API.
The selected Demo contract and frozen research sources remain unchanged.
Exit0 means a report was produced, never that a strategy is qualified.

## Build the five preparation snapshots

From the repository root, with the existing virtual environment:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.qualification.c22 prepare \
  --campaign runs/c22-exhaustive-loop-2026-10-25 \
  --export runs/c22-market-open-finalprep-2026-10-24/vm-evidence/broker-evidence-final.json \
  --policy runs/c22-market-open-finalprep-2026-10-24/cost-policy-v2.draft.json \
  --data-manifest runs/c22-real-data-audit-2026-10-24/input/manifest.json \
  --bars runs/c22-real-data-audit-2026-10-24/input/bars.csv \
  --max-rows 10000 \
  --out-dir runs/c22-adoption-preparation-2026-10-25/implemented
```

Choose a new output directory for each subsequent snapshot. Existing artifacts
are never overwritten. CLI output paths must resolve under this repository's
ignored `runs/`. The five reports are `candidate.json`, `costs.json`, `data.json`,
`protocol.json`, and `dashboard.json`; `canvas-source.txt` renders that same
dashboard snapshot in the managed Canvas. Reports share a versioned evidence envelope
with identity, UTC coverage, source hashes, explicit reasons and
`execution_authorized=false`.

The data scan is bounded. Large files are not silently rehashed; report
`hash_status` and unverified declared input hashes explicitly. Full archive
coverage, feed parity and signal impact still require their own investigation.
No input is interpolated, repaired or rewritten.

## Contract and parity

`manifest --campaign ... --candidate ... --out ...` preserves every native
Rules field and reports compatibility gaps against the current Demo contract.
Partial search or an unbound/stale final audit produces `PROVISIONAL`.
Only a selected profile with complete matching research/audit bindings becomes
`RESEARCH_BOUND`; runtime parity still remains untested.

`parity --reference ... --observed ... --out ...` compares supplied event
snapshots. Each declares schema version1, candidate ID, implementation role
(`research` / `runtime_adapter`), local `source_path` and its SHA256, identical
bar/quote/spec/cost/account/day-state context hashes, plus chronological events.
Events use explicit identity/time, BUY/SELL side, entry/stop/target, admission
reason, risk, cooldown, protection and signed net fields. See the public fixtures
in `tests/qualification/c22/test_contract.py` for the complete strict schema.

Missing artifacts, self-comparison, identical implementation sources, missing
adapter or contexts never yield `PARITY_PASS`. Even a pass means supplied event
agreement, not attestation that the claimed source produced the log, broker fill
parity or future profitability. No candidate runtime adapter is installed here.

## Broker costs and existing Demo evidence

`costs --export ... [--policy ...] --out ...` reads an exported MT5 JSON history,
groups positions, preserves signed profit/commission/fee/swap and distinguishes
complete, open, orphan, invalid and excluded records. Totals cover the exported
account sample; they are not attributed to the new C22 candidate. Missing
currency does not become USD. Missing charge fields do not become zero.

Cost matching requires supported, dated tariff/spec documents and calendar
coverage of the actual positions. A current spec or draft future calendar
cannot qualify historical costs. Slippage remains `NOT_MEASURED` without a
contemporaneous decision quote. This tool never attests or renews a cost policy.

`dashboard --reports ... [--demo-report ...] --out ...` joins the preparation
snapshots. The optional Demo JSON must come from the existing read-only
`scripts.demo_runtime.evidence` report. Existing Demo cohorts remain separate;
the dashboard does not recalculate their PnL. Sampled-equity DD is labeled
separately from research full-tick DD. Missing evidence remains inconclusive.

## Fixed forward version

Owner chose a fixed candidate through agreed evaluation endpoints. Improvements
use a new version and cohort; prior losses stay recorded.

`protocol-template --manifest ... --out ...` produces an unfrozen draft with
undecided review endpoints, minimum sample and operational stopping reasons.
Decide those before observing outcomes. Edit `data.criteria` in a new copy,
including explicit `criteria_confirmed=true`, or supply that criteria object
separately. No numeric forward threshold is invented by these tools.

`freeze-cohort --manifest ... --parity ... --criteria ... --cohort-dir ...`
requires a `RESEARCH_BOUND` manifest and matching `PARITY_PASS`. The freeze must
follow all exposed data and precede the review endpoint. The resulting
definition is create-only and hash-bound; this is not runtime activation.
Freeze cannot predate actual cohort creation. Small source dependencies inside
both reports are reverified at freeze, append and review; changing an adapter
invalidates the old parity binding. Large declared inputs remain explicitly
unverified by these bounded tools.

`record-evidence --cohort-dir ... --evidence ... --kind ... --observed-utc ...`
appends a hash-chained, candidate/cohort-bound evidence snapshot. Its
`coverage.from_utc`/`until_utc` must be prospective and inside the agreed window.
Accepted kinds: `shadow`, `broker_demo`, `operational_stop`, `review`.
Shadow decisions cannot claim broker trade/PnL fields. Operational stop reasons
must have been declared in the frozen criteria. Duplicate or changed source
snapshots are rejected; investigate and preserve a partial write rather than
truncating it. `review-cohort --cohort-dir ... --out ...` checks the chain and
retains negative outcomes. It does not aggregate overlapping snapshots as
independent trades or certify profitability.

## Remaining gates

Research final audit → candidate adapter integration → end-to-end offline parity
→ fresh broker/cost/feed evidence → prospective shadow review → owner
execution-time Demo decision. The existing Monday waiting-gate waiver does not
automatically apply to a research replacement. Real money remains prohibited.

Historical DD≤40% qualification does not guarantee a future drawdown limit.
Fixed0.01, cost-inclusive10% cap, single position and no recovery/lot growth
remain unchanged. Strategy/risk modifications belong to a separate reviewed
change and require corresponding CORE_STRATEGY documentation.
