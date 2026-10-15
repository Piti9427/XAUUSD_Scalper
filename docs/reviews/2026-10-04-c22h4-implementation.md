# C22H4 Demo replacement implementation — operational gates pending

Implemented against owner-requested `.cursor/plans/c22h4_demo_replacement.plan.md`, starting commit `df8d3fcb62a53c28310368d23f286ed7a95cd23e`. Candidate contract/config ID `1af968e9ac6a26ea`, snapshot `RESEARCH-C22-H4EMA200-20261004`. Implementation authorization does not substitute for Phase7 execution approval.

## Changes

- Retired never-executable Reward156DemoRunner and misleading tests; retained frozen research `config/reward156-demo.json`; corrected CORE_STRATEGY readiness claims.
- Shared trial30 lifecycle through strategy hooks: direction-aware quote/type/geometry/risk, source/cache admission gates, candidate daily10% and one-loss circuit, BUY protection off/SELL BE1R. Original trial30 constants and rollback targets retained.
- Canonical research `prepare_candidate`/`prepare_entry` used directly with exact contract and SHA256 pins. Long completed-M15 cache bootstraps 100000 M1, then appends complete bars from5000-M1 tail; overlap changes/missing/added historical bars block and trigger next-cycle rebuild. Fewer than201 complete H4 blocks. No fallback seed selected.
- Journal implementation unchanged. Same-account guard acquired before MT5 initialization, separate strategy journals bound to snapshot. SENDING/UNKNOWN reconcile through broker deals; post-fill violation safety closes only owned ticket. Last_result stores macro/cache diagnostics. Outbox events only broker-confirmed.
- Restart-safe loss circuit uses owned opening position IDs and complete profit/commission/swap/fee ledger, independent of closing magic/comment; day is last exit UTC day.
- Candidate Wine CLI/probe/status/Makefile paths, shadow cache export, operator stop/rollback/cutover protocol and owner authorization documentation.

## Reproduction and verification

TDD at plan's cache/decision/public-cycle seams. Missing-overlap and duplicate warmup tests failed, then passed after fixes. CLI contention regression reproduced unwanted second initialize, then passed after moving guard ahead of initialization. Post-fill regression reproduced stale initial equity permitting >10% fresh-entry risk, then passed after persisting freshly verified pre-send equity. Malformed source-hash-map regression reproduced TypeError suppressing restart management; fixed to source_drift admission block while persisted trade remains MANAGING.

- Phase1 full suite after retirement: **829 tests, 21.026s, OK (2 skips)**.
- Final `make test`: **863 tests, 44.437s, OK (2 skips)**. Candidate34 tests: strategy7, public lifecycle19, CLI4, history probe4. Original27 `test_trial30_demo.py` cases pass unchanged.
- Final `make compile deps lint`: pass; `pip check` reports no broken requirements.
- Changed-Python Ruff format check: **16 files already formatted**. `git diff --check`: pass.
- Repo `make format-check`: fails on13 pre-existing files. Each compared byte-for-byte to starting commit and verified unchanged, including hash-pinned `scripts/strategy.py`. No unrelated formatting/dependency churn. Consequently aggregate `make check` is not green.
- No configured static typechecker in repo; syntax compilation run. Actual MT5 connectivity smoke/broker lifecycle not completed in this sandbox.
- `make c22h4-status`: executed; journal_missing, process inventory unavailable. This is local status only, not evidence of broker flatness.

## Code review

`code-review` Standards and Spec axes independently reviewed starting-commit working diff plus new files. Initial findings: guard acquired after broker initialization; matching parity mislabeled as prefix divergence and geometry differences not counted; BUY failure/restart coverage missing; deepest fetched history continuity not measured. All fixed and re-reviewed: **0 remaining actionable Standards findings; 0 remaining actionable Spec findings**. Standards reviewer reran CLI/probe8 tests, pass. Root's additional fresh-entry-equity risk regression fixed and verified.

## Operational gates and limitations

Phase0 probe attempted through existing Wine wrapper. Process exit1: `wine: cannot find the server port: 0x0000044c`; no MT5 initialization/rates/order APIs reached. `ps` also denied by sandbox. See [history probe report](2026-10-04-c22h4-history-probe.md). Offline implementation proceeded with broker-only bootstrap assumption; no depth/latency fallback decision made. This does not satisfy plan's Phase0 acceptance gate.

Pending: exclusive terminal read-only maximum-depth/latency and broker/archive parity review, owner-attested <=24h cost policy, >=96 completed-M15 shadow bars spanning UTC midnight with exact exported-cache replay, flat trial30/empty outbox/stopped watcher/no same-day trial30 trade, owner cutover approval. First Demo close must preserve closing magic/comment evidence E7. No strategy switched, no shadow qualification or actual Demo order claimed, no real-money authorization.

Parity probe separates directional/admission gate from geometry/indicator counters; review all differences even when modeled admission agrees. Geometry uses explicit common quote/spread/slippage/fee/equity hypotheses, not inferred historical live costs. Maximum exploration is bounded to800000 M1/60seconds and reports deepest successful continuity/M15/H4; it cannot prove unlimited broker history. Account guard is local to canonical workspace; old pre-upgrade watchers/other machines do not hold it. Stop only terminates watcher; broker SL/TP remain.

Next operational step: [C22H4 ops protocol](../ops/c22h4-demo.md), Phase0 under exclusive terminal access. Research selection and implementation review do not establish profitability or deployment readiness.

Git staging attempted after verification; sandbox denied `.git/index.lock` with Operation not permitted. No staging or commit completed, no sandbox escalation attempted. Owner approval required by supplied instructions before permission escalation for authorized commit. Original user plan remains untouched and untracked.
