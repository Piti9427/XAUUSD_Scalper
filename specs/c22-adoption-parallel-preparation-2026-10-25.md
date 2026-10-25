# C22 adoption preparation alongside frozen tuning

Status: offline preparation tools implemented; candidate adapter integration,
forward criteria and operational qualification pending. Prepared 2026-10-25. This document
changes no strategy, risk rule or execution authorization. Owner selected
offline preparation toward shadow, then separately reviewed Demo use. Owner
also selected a fixed candidate/cohort through agreed evaluation endpoints;
improvements belong to a separately versioned next candidate.

Implementation: `scripts/qualification/c22/`, focused public-seam tests under
`tests/qualification/c22/`, commands and artifact semantics in
`docs/ops/c22-adoption-preparation.md`. The `prepare` command creates all five
evidence reports and a self-contained Canvas source from existing local inputs.
Reports remain provisional/inconclusive where evidence is missing. The
implementation does not supply a runtime strategy adapter or start forward.

## Why preparation is possible before a winner exists

Build candidate-independent validation and evidence tooling now. Bind a final
candidate only after all 5,184 profiles, required cost/cent scenarios, fresh
repeats and independent final audit pass. An interim leader is an example input,
not an adopted strategy. Current campaign status is available from its control
CLI; this plan is not a live progress monitor.

The current Demo contract is `1af968e9ac6a26ea`, section6.33 of CORE_STRATEGY.
The current research incumbent is a different native Rules descriptor. Actual
source reveals material integration gaps:

- `scripts/c22h4/strategy.py:16-38,108`: fixed CONTRACT/CONTRACT_ID in the cache.
- `scripts/c22h4/runner.py:56-64,112`: one losing exit/day and SELL-only protection.
- `scripts/demo_runtime/admission.py:22`: current admission has no post-loss cooldown.
- `scripts/demo_runtime/lifecycle.py:180-196`: protection threshold is fixed at1R.
- `scripts/research/reward156_search.py:154`: generic candidate construction sets
  `protect_after_r=1.0`; complete native Rules must not be silently reduced to
  that adapter's narrower representation.

Changing a research config alone therefore does not establish runtime parity.

## Five parallel work packages

### P1 — Contract, compatibility and offline parity

Deliverables: versioned candidate manifest/schema; field-by-field capability
report; offline decision/event comparison harness; future integration spec.
Manifest binds complete Rules, detector/cost/data/source hashes, accounting
conventions, final audit/result hashes and explicit unsupported capabilities.
Initially use fixtures and historical descriptors, with provisional status.

Acceptance: fail closed on unknown/missing fields and hash drift. Given identical
causal bars, quote/spec/cost/account/day state, compare signals, rounded SL/TP,
admission reasons, risk, cooldown and protection events. Include BUY/SELL,
tick/cent boundaries, UTC midnight, negative net BE after swap, restart,
duplicate bars and ambiguous execution using existing fake broker patterns.
Self-comparison through one shared implementation is not independent parity.
Until a candidate runtime adapter exists, mark adapter parity NOT_TESTED or GAP.

Reuse existing C22 strategy regression fixtures; do not duplicate them. Prepare
new isolated files; edit no frozen detector/config/research or dirty shared
runtime files. Later integration must preserve original Demo regressions and
separate contract/journal/cohort identities. PARITY_PASS is code agreement,
not broker fill parity or proof of future profitability.

### P2 — Observed cost reconciliation

Deliverables: offline broker-export importer and coverage report, position/deal
ledger reconciliation, observed-versus-modeled commission/fee/swap/fill costs.
Every record carries source hash, aware UTC interval, unit and account cohort.
Reuse semantics from `scripts/demo_runtime/costs.py:51,105`.

Usable local starting evidence already exists:
`runs/c22-market-open-finalprep-2026-10-24/vm-evidence/broker-evidence-final.json`.
The read-only inventory found 38 trade deals forming19 balanced entry/exit
position ledgers dated2026-10-01 through2026-10-14, including3 nonzero-swap
closing records. These are real observed samples, not a complete historical
tariff. The nearby `cost-policy-v2.draft.json` is DRAFT_NOT_ATTESTED; its
Oct24–Nov5 calendar does not establish Oct1–14 or2024–2026 historical rates.

Acceptance: handle partial closes, complete position grouping, calendar/triple/
holiday boundaries and currency/volume units. Report open, unmatched, pre-review
and excluded positions. Do not treat current post-review closed-position checks
as full historical coverage. Slippage needs a contemporaneous decision quote;
mark unavailable rather than inventing it. Missing historical rates/calendar or
broker ledgers leave COST_INCONCLUSIVE. No attestation or timestamp renewal.

### P3 — Prospective forward protocol

Deliverables now: immutable cohort schema, observation/decision log and a draft
forward protocol naming candidate/config/source/cost versions, freeze time,
data cutoff, metrics, sample coverage, review endpoints and stop reasons.
Reuse evidence cohort conventions from `scripts/demo_runtime/evidence.py:12`.

Owner selected the fixed-version policy. Before observing outcomes, agree review horizon and what constitutes operational
failure versus insufficient economic evidence. After final binding, only newly
observed, unexposed data can form the prospective evaluation cohort. Changing
strategy opens a new version/cohort; retain losses and the prior cohort. Data
examined during continuing tuning must be recorded as exposed.

Shadow verifies decisions/plumbing; shadow admission is not a broker fill.
48hours/96bars is an existing operational qualification interval, not a
profitability sample threshold. The owner-approved Monday2026-10-26 waiting-gate
waiver belongs to the existing attended Demo procedure; do not transfer it to
an unselected research replacement. No forward runtime is started by this plan.

### P4 — Data and feed quality

Deliverables: read-only inventory and coverage audit for duplicate/order/UTC/
nonfinite/negative-spread checks, incomplete M1/M15 exclusions, explained market
closures versus unexplained gaps, and feed differences affecting signals/levels.
Start with existing hashed manifest/reports and bounded fixtures; avoid a second
full 171M-tick scan competing with the active tuning job.

Acceptance: each issue cites its interval/source/affected bars or decisions.
Never interpolate, remove or repair frozen campaign input. Complete-bar assembly
does not certify completeness of the provider history. Full input scans and
fresh broker-feed comparisons remain separate later checks; current manifest
counts alone cannot pass them.

### P5 — Read-only evidence dashboard

Deliverables: offline snapshot view joining P1–P4 outputs, with separate research,
prospective shadow and broker Demo cohorts; coverage, mismatches, timestamps,
source hashes and actionable blockers. Reuse `demo_runtime.evidence` reports
and read-only SQLite access rather than inventing another PnL calculation.

Acceptance: every metric resolves to its source ledger; missing evidence is
INCONCLUSIVE. Label sampled-equity DD separately from full-tick research DD;
show completed and ongoing recovery separately. Distinguish best-in-grid,
accounting PASS, adapter parity, broker parity and economic qualification.
No automatic strategy selection, configuration writes or execution actions.

## Integration order and ownership

P1 schema, P2 cost importer, P3 protocol, P4 audit inventory and P5 view skeleton
can be prepared concurrently. Agree one small evidence envelope first:
artifact/schema version, candidate/cohort ID, time coverage, source hashes,
status and explicit reasons. Missing evidence is explicit, never zero-filled.

P1 owns contract/parity files. P2 and P4 own separate importer/audit files.
P3 owns protocol/cohort definitions. P5 consumes snapshots and owns only its view.
Use new `scripts/qualification/c22/` and `tests/qualification/c22/` namespaces
if implementation proceeds. Current exhaustive freeze/verification iterate
explicit inherited source pins, and these namespaces have no pinned paths.
Other campaigns dynamically glob `scripts/research/*.py`; keep preparation
modules outside that directory and do not edit existing package initializers.
Generated outputs belong in `runs/c22-adoption-preparation-2026-10-25/`;
human summaries belong in `docs/reviews/*.md`.

After final audit: bind selected candidate → implement compatible adapter in a
separate reviewed change → offline end-to-end parity → fresh cost/feed evidence
→ prospective shadow review → owner execution-time Demo decision. Real-money
readiness remains outside the current contract and requires a separate scope.

## Decisions to grill before integration

Agreed: shadow→Demo scope; fixed candidate through agreed review endpoints;
an improved next version gets a new cohort. Both retain operational stop paths.

Remaining before forward activation: review/sample endpoints and operational
stopping rules; final candidate identity; fresh broker/feed/cost evidence; exact
Demo execution-time decision. Preparation assumes eventual use of the existing
Demo with one sender. A separate account would be a new explicit scope decision.
Available dated exports are listed under P2; request more only for identified
coverage gaps. Local availability is not a historical cost qualification.

The historical DD≤40% rule remains a research admission criterion. This plan
does not turn it into a guaranteed future maximum DD or add a liquidation rule.
Fixed0.01, cost-inclusive10% cap, single position, no recovery or lot growth stay
unchanged. No broker connection, order, service activation, cost attestation,
Demo cutover or deployment is performed by preparing these work packages.
