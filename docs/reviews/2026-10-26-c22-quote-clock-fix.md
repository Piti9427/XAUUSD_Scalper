# Selected26b8 quote clock defect closure

Owner requested closing the entry-alignment review's confirmed implementation
defect while clarifying financial-policy changes separately. This change repairs
quote observation and the existing admission deadline,without changing native
26b8 signals,fixed0.01,SL/TP/BE,daily/cooldown,risk or cost assumptions.

## Reproduction and root cause

The public runner passed the UTC time at cycle start into BrokerView._quote after
reading account,exposure,history and symbol data. A new tick generated during
those reads was later than that old timestamp,so the strict future-price check
reported quote_stale. Sampling immediately before symbol_info_tick still omitted
latency inside that SDK call. The root cause was the observation clock,not an
inverted signal or a need to accept actual future/old prices.

Original retained differential:
`PYTHONPATH=. .venv/bin/python runs/c22-entry-alignment-recheck-2026-10-26/risk_alignment_reproduce.py`
was executed before the production fix: current-clock BLOCKED/quote_stale versus
post-observation-clock SHADOW_ADMIT,both with zero order sends. Its archived output
is a pre-fix witness,not a post-fix acceptance test. New deterministic regressions
advance monotonic time with the SDK response and exercise the actual production
runner/validator without monkeypatching the validator to force acceptance.

The tight command is:

```bash
PYTHONPATH=. .venv/bin/python -m unittest tests.demo.test_quote_observation_clock
```

Eight initial cases were run before the fix and failed reproducibly,including
BLOCKED/quote_stale instead of SHADOW_ADMIT and active MANAGING. One newly written
fixture initially mutated both the current tick and the historical first quote;
separating the real earlier first quote corrected that fixture without changing
the causal first-quote rule. Subsequent tests found another connected clock gap:
the pre-send90second check reused its pre-read time. A synthetic90second SDK read
produced FILLED in the fake broker after the window; the regression now requires
entry_window_expired and zero sends. No real order was used in these experiments.

Ranked hypotheses and falsification:

1. Old cycle/request time misclassifies newly generated ticks. Advancing only the
   observation clock changes rejection to admission: confirmed.
2. The quote is truly stale. Age60.001seconds after observation still rejects;
   exact60seconds passes. The freshness ceiling was not relaxed.
3. Broker clock is actually ahead. A tick100ms later than the post-read clock
   still rejects. Historical VM quote_stale records lack tick-age evidence,so no
   claim assigns all28 previously seen rejects to hypothesis1.

## Minimal fix and trace

- [runner.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/runner.py:225)
  passes its elapsed current UTC observation into the initial quote read. It keeps
  the original cycle clock for bar causality and UTC-day context.
- [broker.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/broker.py:180)
  adds only time spent inside that SDK call,measured with monotonic time,before
  applying the same strict0–60second age range. Invalid UTC or backwards/nonfinite
  elapsed clocks fail closed. No extra broker read or new clock tolerance exists.
  All admission,BE-modification and safety-close quote callers share this seam.
- [admission.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/demo_runtime/admission.py:153)
  re-samples elapsed time after the fresh quote read before checking the existing
  90second entry window. Later SDK stalls can still delay dispatch/fills; this is
  a sampled admission check,not an absolute exchange-fill deadline guarantee.
- Rejection records now expose quote_requested_utc,quote_observed_utc,
  quote_time_utc,quote_age_seconds and quote_rejection(future/stale/invalid/missing).
  Diagnostic state resets each cycle and is included only for quote failures.
  These permanent operational fields contain no credentials. No temporary debug
  instrumentation or alternate execution engine was added.

Why it slipped through: earlier fixtures returned a tick older than the supplied
cycle clock and did not advance SDK observation time. Freshness tests therefore
covered old/future inputs but missed a valid tick arriving during a read. The
new public-cycle and active-manager tests preserve those timing relationships.

## Validation

- New quote-clock suite:10tests,independent reviewer run5.995seconds,OK.
- Quote-clock plus UTC-boundary suite:20tests/6.316seconds,OK.
- Full repository suite:1,237tests/194.992seconds,OK;2 existing skips.
- Scoped Ruff passes. Final immutable payload differs from deployed98c only in
  shared broker.py,runner.py,admission.py and four generated service release paths.
  Runtime config is byte-identical. All19 selected source bindings pass; all101
  frozen research source hashes remain unchanged.
- Retained49,729-bar/2,751-geometry/six-path price agreement references unchanged
  detector sources. It is retained evidence,not fresh economic/clock validation.

| Requirement | Exact regression evidence |
| --- | --- |
| Fix falsely rejected fresh quotes | test_sdk_read_latency_accepts_fresh_tick_after_request_started; test_public_cycle_counts_pre_quote_sdk_latency_without_resetting_day_clock |
| Preserve real future/stale guards | test_genuinely_future_tick_is_rejected_against_post_read_clock; test_observed_age_over_60_seconds_is_rejected_after_slow_sdk_read; test_exact_60_second_observed_age_remains_valid |
| Cover the actual send/protection seams | test_presend_accepts_fresh_quote_created_during_sdk_read; test_active_manager_accepts_fresh_quote_during_read_without_new_entry |
| Reject a quote read crossing the entry deadline | test_presend_quote_read_crossing_90_second_window_never_sends |
| Disclose clock rejection without changing event/day time | test_public_cycle_reports_rejected_tick_age_without_loosening_freshness; test_quote_clock_rejects_naive_non_utc_and_backwards_elapsed_time |

Test source:
[test_quote_observation_clock.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/demo/test_quote_observation_clock.py).
Generated red/green logs,full suite,manifest,probes and backups stay under
[runs/c22-quote-clock-fix-2026-10-26](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26).

## Actual Demo cutover versus remaining evidence

Immutable release selected-9cfc54a3dc78f0ae was staged with80 verified files,
systemd verification exit0 and82.0GB available on the VM. A consistent SQLite
backup was compressed,downloaded,hash-verified and independently restored on Mac
before cutover(11kv,0events,40,765audit events). The controller revoked admissions,
waited for a completed later flat cycle,stopped only the single selected sender,
then exclusively read broker state before and after installing unit metadata.

Cutover completed26October2026 15:32:07Asia/Bangkok. Fresh probes confirmed the
same43 deals,no position/order and balance/equity$1,811.97; actual new validator
passed against the Windows SDK,with observed quote ages224ms and94ms. No order
was sent by probes/controller. The existing history CSV/sidecar stayed byte-identical
while stopped; there was no cold100k preload,cache migration,financial reset or
cost-policy renewal. Persistent terminal PID34838 was not restarted. New sender
PID52912 is active on this release; actual runtime/cohort acceptance is checked
separately before declaring its ongoing state verified.

At15:34:53Asia/Bangkok,actual new-cohort CYCLE release/config hashes and the
persisted raw review SHA match the current immutable source and review. Execution
is active,execute=true,flat,critical=false and waiting for its first post-approval
closed M15. The existing UTC-day equity baseline$1,812.21 and policy SHA remain
unchanged. Boot registration was checked/applied without restarting the sender;
watchdog and backup use the new release and external delivery remains disabled.
The new-cohort backup was independently restored on Mac:11kv,0events,40,849audit
rows,integrity/count/source-cohort/review/day/hash checks pass. Reboot recovery and
a native qualifying entry/fill are not claimed by this maintenance evidence.

Final observation at15:37:16Asia/Bangkok:79 cycles from the new release have
reached the normal armed_trial_new_closed_m15_required gate,with no quote_stale
in that short interval. This verifies the sender's ongoing clock/review path;
it is not a matched statistical before/after rate or proof that future genuine
quote staleness cannot occur. No active position,safety halt or unsent event is
present. Post15:45 detector/admission evaluation is still prospective at this
snapshot. [Observed runtime](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26/runtime-verified.json).

Follow-up15:49:42Asia/Bangkok: the15:45closed-M15 cycle restored6,597M15 bars,
had362/201completeH4 with finite macro and returned WAIT/no_signal. Subsequent
cycles return duplicate_bar,execute=true,critical=false; no active position,halt
or unsent event exists,and the watchdog reports HEALTHY. The source approval and
history gates therefore cleared as intended. This proves evaluation of a fresh
bar,not a qualifying native order/fill or improved financial performance.
[Post-close runtime proof](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26/runtime-after-fresh-m15.json).

Evidence:
[cutover](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26/cutover-result.json),
[source/cohort acceptance](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26/boot-and-watchdog.json),
[Mac restore](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26/backup-after-mac-restore.json),
[full test log](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-quote-clock-fix-2026-10-26/full-unittest.log).

The exact new source review keeps the original Monday arm_not_before and all
Demo limitations. A newly closed M15 after this source approval is still required;
next scheduled close is15:45Asia/Bangkok. This expected gate must not be bypassed
or backdated. A same-review restart does not reset approval. Current risk-policy
design selections do not alter this running native cohort.

## Separate financial-policy work

Owner selected next-version admission budgets for Daily10% and cohort-equity
DD40%,retaining existing exits. Peak/resume and net-BE choices remain in the
grilling design tree in
[risk closure spec](/Users/nopparuj/my-agents/XAUUSD_Scalper/specs/c22-risk-closure-2026-10-26.md).
These are meaningful strategy changes,not bugfixes hidden in this deployment.
No new risk-candidate profit/DD/backtest result exists yet. Future economic
comparisons must include modeled swap and independent accounting/DD verification.
The current Demo still has native daily-entry-stop,static risk and native BE;
historical DD40% is not yet a runtime DD breaker or a guaranteed realized ceiling.
