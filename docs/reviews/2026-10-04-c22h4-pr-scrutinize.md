# C22H4 readiness before PR to develop

Reviewed local HEAD `2d184b10e02486a1c206e6f9c8b4ed11dcc89d10` on `feature/smc-v2-hardening`, against develop `a24114097988e4b3669d48d6be19773c502c3924`. Review date: 2026-10-04. No broker session, order API, deployment, branch push or PR creation performed.

## Intent and simpler alternative

Goal: merge the selected frozen C22 + closed H4 EMA200 research-Demo implementation without representing it as operationally qualified. Config alone cannot implement the long causal cache, BUY geometry and strategy-specific loss circuit. Reusing trial30 lifecycle through hooks is the smaller implementation. A focused C22 change would be more reviewable than promoting the entire accumulated research branch: the actual local develop comparison contains 77 commits, 394 files, 114636 additions and 133 deletions. This review traces the C22/shared lifecycle surface, not every historical change in that comparison.

## Major: overnight position can block admission for the rest of UTC day

Finding: `scripts/trial30/broker.py:103-106` permits capturing an overnight floating equity baseline only within the first second of UTC midnight. Missing that interval makes subsequent same-day baseline reconstruction impossible. `scripts/trial30/runner.py:125-128` suppresses this error while managing an existing position; after its close, `runner.py:139` propagates it and blocks admission.

Evidence: executed public C22 cycle using existing CandidateBroker fixture, real detector/cache, temporary persisted journal, BUY fill, next UTC day at 00:00:02, complete broker exit ledger, refreshed quotes. Observed `FILLED -> MANAGING -> CLOSED -> BLOCKED(day_start_floating_unknown) -> BLOCKED(day_start_floating_unknown)` one hour later. Raw output: `runs/c22h4-pr-scrutinize-2026-10-04/midnight-reproduction.json`. No live MT5 involved.

Consequence: a normal polling delay, rollover quote delay or restart can suspend new entries for the remainder of the day. Existing broker protection/reconciliation continues in the reproduced case. This does not bypass risk; it is an operability and research/runtime behavior mismatch. Candidate all-session/overnight policy does not guarantee flat midnight.

Suggested change: define and implement a broker-evidenced UTC boundary equity capture/recovery policy, then test delayed polling, stale midnight quotes and restart with an overnight position through the public cycle. Do not fabricate floating equity, substitute balance, reset the daily circuit or widen its loss allowance. Any baseline-policy change needs owner review and CORE_STRATEGY documentation.

## Major: format gate fails before PR tests in CI

Executed `make format-check`: exit2, 13 files need formatting. `.github/workflows/ci.yml:48-49` runs the same Ruff format check before unit tests. Passing test/compile/deps/lint does not make the repository aggregate gate green. Format failures predate the C22 implementation according to its earlier report, but those files are part of the broader develop comparison.

Suggested change: resolve formatting in a separate scoped change before merge. `scripts/strategy.py` is source-hash pinned by `config/c22h4-demo.json`; formatting it changes its SHA256 and blocks C22 admission. Any source repin must be explicitly reviewed and revalidated; do not blindly run `make format` and leave the contract stale. Remote CI was not run in this review.

## Operational blocker: Demo cutover evidence remains absent

`docs/ops/c22h4-demo.md:19` records failed Wine probe; `:29-31` requires at least96 completed M15 shadow bars spanning UTC midnight; `:34-45` requires flat trial30, empty outbox, stopped watcher, no same-day trial30 trade, parity acceptance and execution-time owner approval. Local probe JSON, shadow cache export and candidate journal are missing. Local cost policy reviewed UTC2026-10-02T06:09:10.008282+00:00 is approximately57 hours old; `scripts/trial30/costs.py:29` allows <=24 hours. Broker identity, flatness and process status are not verified.

Suggested change: retain candidate shadow-only status until operational evidence and review complete. Do not edit only the cost timestamp. A merge is not cutover authorization.

## Major scope limitation: remote branch and default commands differ from intended candidate

GitHub read-only API confirms develop SHA above and remote feature HEAD `4b463194217847d3585c213be11b1a362f57b8e6`. No open PR exists for this head branch at review time. Local HEAD includes additional changes: remote-feature-to-local difference178 files,40906 additions,630 deletions. Reviewing local C22 does not validate the current remote PR payload.

`Makefile:92-103` still routes `bot-run`/`bot-start` to trial30; `:129-130` routes `c22h4-run` to C22 and requires the external execution gate. This preserves rollback intentionally; a merge does not change the running bot or generic startup strategy.

Suggested change: settle whether PR covers the accumulated branch or focused C22 implementation, publish the exact reviewed head, and use a PR title/body that explicitly states operational gates pending. Preserve trial30 rollback targets; document C22 commands in operator-facing startup guidance if replacing default workflow later.

## Trace and executed checks

- Host wrapper loads ignored `.env` into child environment and redacts credential-like values: `scripts/ops/run_trial30_wine.py:14-45`; C22 wrapper selects candidate entrypoint: `scripts/ops/run_c22h4_wine.py:7-12`.
- Candidate CLI pins contract, research-only identity and lot: `scripts/ops/mt5_wine_c22h4.py:15-29`. Shared CLI enforces explicit execution env gate and obtains account writer guard before initialize: `scripts/ops/mt5_wine_trial30.py:72-78,99-111`.
- Candidate frame verifies frozen hashes, broker M1 bootstrap and append-only cache: `scripts/c22h4/runner.py:35-53`; `scripts/c22h4/strategy.py:53-113`. Exact current contract/source hashes independently checked: PASS.
- Closed H4 mapping publishes at bucket close, requires16 M15 bars: `scripts/research/reward156_tuning.py:49-67`. Candidate uses archived detector and canonical entry geometry: `scripts/research/reward156_search.py:154-234`; `scripts/c22h4/strategy.py:116-134`.
- Demo identity, account-wide exposure, quote age and broker history checks precede admission: `scripts/trial30/broker.py:26-72,119-150`. Cost/daily circuit/fixed lot/broker risk/margin/order_check and fresh identity/equity/quote/exposure checks precede send: `scripts/trial30/runner.py:150-270`.
- Durable SENDING intent precedes send; UNKNOWN reconciles without resubmission; actual opening ledger and fill risk precede FILLED event: `scripts/trial30/runner.py:251-280,326-457`.
- BUY protection off; SELL closed-bar BE verifies broker position/quote before stop mutation and confirms broker SL before BE event: `scripts/trial30/runner.py:458-568`. Safety containment targets only owned ticket: `:570-638`.
- State and broker-confirmed outbox events commit atomically: `scripts/trial30/journal.py:42-67`. CLI enables no notifier: `scripts/ops/mt5_wine_trial30.py:121`; automatic Telegram delivery is not established by this path.
- Executed `make test compile deps lint`: exit0. 863 tests in43.654s, OK(skipped2); syntax compile PASS; pip check PASS; Ruff lint PASS. Local environment is Python3.14; CI Python3.10/3.11 matrix not executed here.
- Executed `make format-check`: FAIL,13 files. Executed develop comparison whitespace check: reports trailing whitespace/EOF errors. No runtime source or config edited in this review.

Verdict: **fix-then-ship implementation; Demo execution NO-GO**. Biggest runtime reason: UTC-midnight baseline recovery can block normal next-day admission; operational parity/shadow gates also remain unpassed. Full394-file PR has not received an end-to-end review.

## Subsequent owner-requested default runner change

Owner requested changing the default runner to C22H4. Working-tree Makefile now routes `bot-*` to C22H4 and retains explicit `trial30-*` rollback targets. Candidate PID/log are separate; execution gate is operator-supplied rather than implicitly set by Make. Background launch checks for both strategy watchers and fails when process inventory errors. Existing watcher not stopped, new watcher not launched. Earlier default-command finding above describes reviewed HEAD, superseded by this working-tree change. Frozen source/contract hashes PASS; all ten default/rollback target routes verified with `make -n`; `bot-run` and `bot-start` without gate executed and rejected before Wine; `make bot-status` executed and reports candidate journal_missing/process inventory unavailable. `git diff --check` PASS. Strategy runtime code unchanged; no new full-suite run for Make/docs-only change. Operational and formatting blockers remain.
