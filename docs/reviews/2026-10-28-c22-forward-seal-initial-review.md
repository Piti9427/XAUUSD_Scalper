# Selected26b8 forward collector — initial independent review

**Verdict: fix before closing T16/#27.** The initial implementation truthfully labels reused data and missing financial facts, but it does not yet establish the complete source/identity/coverage contract requested by the ticket.

Reviewed `scripts/ops/c22_forward_seal.py`, `tests/demo/test_c22_forward_seal.py`, actual producer seams in `scripts/demo_runtime/{journal,admission,runner,lifecycle}.py`, and the published `T16.md`. Codegraph queried first; the new collector is absent from the index. No code, VM or GitHub mutation performed by this reviewer.

The simpler solution remains passive copies from existing ownership seams. A second SDK reader or a running-sender change is unnecessary for sealing evidence. The collector must consume available source packets and identify missing coverage rather than manufacture facts.

## Findings

1. **Source manifest is frozen without validating its declared cohort or source inventory.** `freeze_protocol` accepts any parseable JSON, including `{}`. The negative control passed an empty manifest and received a protocol. The honest `MANIFEST_BYTES_FROZEN_NOT_RUNTIME_ATTESTATION` label limits the claim, but it does not meet T16's source/config provenance requirement. Validate an explicit manifest shape and verify release/config binding; preserve the distinction from runtime attestation.

2. **Different account/new stream can be labeled prospective under the same code/config hashes.** Protocol binds release/config and a maximum audit ID, but neither account fingerprint nor the bootstrap stream prefix. A new row with `account_fingerprint=different-demo`, the same cohort, a later ID and a post-freeze timestamp was accepted by both `seal_batch` and `verify_batch` as `PROSPECTIVE_COLLECTION_ONLY`. Bind the expected account and bootstrap stream anchor; reject a replaced/reset journal. New numeric IDs alone are insufficient provenance.

3. **Coverage denominator silently excludes cohort drift.** A source-window row whose release hash changed produced `audit_records=0`, `coverage=NO_MATCHING_RECORDS`, with no excluded count or reason. Report source-window/matching/excluded denominators and applicable ID continuity/missing-record evidence. A real source change must be distinguishable from an idle window.

4. **Account cashflows and full ledger/feed evidence cannot currently be collected through the public seam.** `_report` always returns `cashflows=NOT_CAPTURED_IN_AUDIT`, `cashflow_total_usd=null`, `broker_full_history_coverage=NOT_PROVEN_BY_AUDIT_BATCH`, and tick coverage not captured. These unknown labels are correct. However, audit-only input cannot eventually satisfy T16's record categories. Add a passive optional input from existing sender broker/history evidence and available feed/cache artifacts, bind it to the cohort/observed times, and retain unknown/missing coverage when absent. Genuine fills are not mandatory for the first bounded batch; sufficient collection capability and truthful denominators are.

## Checks actually run

- Initial five tests: **5PASS,0.055seconds**.
- Actual producer review confirms SIGNAL `direction/bar`, CYCLE `result`, and LIFECYCLE `event.kind/net` match collector parsing.
- Three additional negative controls above reproduced. Machine evidence: `runs/c22-issue-closure-2026-10-28/forward-review/negative-controls.json`.
- Private raw batch files are created0600 and new batch directory0700 under ignored `runs/`; CLI emits metadata/report, not raw audit payloads. This does not authorize publishing raw captures or account data.
- No synthetic fixture result establishes genuine MT5 fill, future profitability or qualification. T21 remains a separate prospective qualification protocol.

This report describes the initial reviewed version; later source changes require re-review and repeat negative controls before claiming the findings resolved.
