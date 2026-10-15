# Expansion breakout review — debug recheck

**Scoped Python findings resolved locally. Master Pro v6 remains REWORK.**

Reviewed baseline: `a551b62242343d3bef1f085f68138d823ad72f84`. Subsequent debug changed two production files; no dependency, new execution engine, deployment or commit. Existing dirty/untracked files remain outside this patch.

Goal: reject older sweeps invalidated by a breakout while preserving valid sweeps of other levels; suppress placement alerts and local pending state when the broker rejects placement.

Simplest solution: prune invalid levels inside the existing scan; handle unsuccessful placement before the existing alert branch. No persistent state machine added.

## Resolved — cross-level suppression (P2)

Original `any(...)` gate stopped every level's sweep search. With Asian Low 2010 and already-broken PDL 2020, the newest close 2017.5 stopped the scan before a valid Asian sweep. Parent returned BUY entry 2014 / SL 2008.2; a551b62 returned `None`.

[Detection now removes only broken references](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py:173), retaining scan order and the nearest valid sweep. A later breakout of the actual candidate level still blocks its older sweeps. [BUY/SELL regression](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/smc/test_smc_detection.py:155) verifies exact baseline signal preservation. Separate cases preserve fresh sweeps after older breakouts.

## Resolved — body-close regression coverage gap (P2)

The original fixture combined a body breakout exceeding the wick cap with a newer wick-only breakout. Deleting body-close checks still passed it.

[Independent subcases](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/smc/test_smc_detection.py:166) now exercise body-only pierce below the cap, wick-only above $8, exactly $8, and a fresh sweep after an older breakout, in both directions. Acceptance cases assert direction, entry and SL. Runtime mutation removing body checks causes exactly two new BUY/SELL subtest failures; the old test alone still passes.

## Resolved for rejected PLACE_LIMIT — broker failure alert (P1, pre-existing)

Original loop received `success=False` from the adapter but still sent a setup alert and retained the orchestrator's pending order. Debugger observed the false result at the notification branch.

[Failure handling](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:195) now clears rejected placement state and skips chart/notification. Successful placement retains pending state and sends one setup alert. [Offline loop tests](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/smc/test_smc_live_execution.py:63) execute the real loop, orchestrator and adapter against fake broker retcodes; only external inputs/outputs and detection are stubbed. No broker order or Telegram message is sent.

## Still open / not certified

- This patch handles an explicit unsuccessful placement result. It does not implement broker reconciliation for ambiguous transport failures, partial/BE/close failures, or OHLC-inferred fill milestones. Dry-run results still use the existing notification behavior; complete simulation labeling remains separate work. Thus this is not certification of all execution/notification paths.
- Master Pine was not modified. Its prior seven counterexamples and missing native strategy validation remain separate work from this Python patch. No Pine compilation, Strategy Tester run or forward-demo evidence added.
- No live MT5 smoke test: credentials, connector code, symbol settings and timeframe handling were not changed. External readiness remains unverified.
- Full suite emitted pre-existing unclosed SQLite connection `ResourceWarning` messages. New loop tests use in-memory SQLite with registered cleanup; unrelated test resource cleanup was left out.

## Evidence

- RED: new detector regression failed both BUY and SELL; rejected-placement loop test failed with one unexpected alert. Accepted-placement control passed.
- `pdb`: detector exited at the global break with `i=18`, levels `[2010, 2020]`, close 2017.5 and no sweep; loop reached notification with `res.success=False` and pending state present.
- Differential disproof: changing only the unrelated-level gate restored the exact baseline; changing only broker retcode did not suppress alerts before the patch.
- GREEN: `python3 -m unittest discover -s tests` — **58 tests passed**.
- [Reproduction script](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/debug/reviews/reproduce_expansion_breakout_review.py:1) compares frozen pre-fix/a551b62 source with the working tree and checks the body-rule mutation. Original stale-sweep bug remains rejected; cross-level signal restored.
- `git diff --check` passed. Final production and test changes reviewed; no deployment or commit performed.
- [Experiment ledger](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-09-13-debug-ledger.md:1) records failed probes, disproofs and outcomes.

**Verdict: scoped Python fixes software-verified; Master Pro v6 remains REWORK because native strategy/lifecycle verification is unfinished.**
