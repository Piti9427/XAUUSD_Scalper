# Trial30 Demo diagnosis — 2026-10-01

**Verdict: implementation gap plus admission prerequisites; Demo automation remains NO-GO. Diagnosis complete for offline contract/gates. Current broker identity remains unverified. No strategy/runtime change, order, order check or Telegram call.**

Owner confirmed snapshot `RESEARCH-D48-SELL-BE1R-20261001-T030` in this review. This supersedes the earlier review's assumption that the request meant frozen D30 Pure B1. It does not make trial30 a qualified or adopted strategy.

## Pinned target

`data/strategy_activation_dd30_campaign_2026_10_01/trial-030/result.json` SHA256:
`55ae74395b9916dc6b29f0690ee8aef26da6d9e6352e1a786c79da86a3a1900c` — verified against daily log.

D48 prior completed Bid M15 bars, SELL only, no RSI/EMA, ATR14 SMA, immediate first quote <=90s after close, fixed0.01lot, SL2.5ATR/TP3ATR, cost-inclusive10% equity cap, UTC daily20%, cost-adjusted BE after closed-bar net executable profit>=initial1R, keep TP. No recovery, partial close, runner or rollover-forced exit. Config source: [daily snapshot](../strategy-logs/2026-10-01.md).

## Reproduce before diagnosis

```bash
.venv/bin/python scripts/debug/repro_trial30_demo_contract.py
```

Repeated twice: exit1 / `FAIL_DETECTOR_CONTRACT`, expected trial30 SELL=-1, actual Pure B1=0. Synthetic49 completed UTC bars; prior48 needs49 bars. This reaches both real detector implementations. It proves incompatibility of the current Pure B1 detector with trial30, not a failed broker order. This command intentionally remains red because replacing/adopting a strategy is outside this diagnosis.

[Captured repro](2026-10-01-trial30-demo-contract-repro.json).

## Ranked predictions and observed probes

| Hypothesis | Prediction / probe | Observed |
| --- | --- | --- |
| Different detector contract | On identical bars, D48 research features restore SELL without changing costs/account | Confirmed: `breakout_logic.features` SELL=-1; `pure_b1_bars` flat=0. RSI guard in `scripts/strategy.py:14` rejects monotonic downswing; D30 is also a different lookback. |
| Execution/lifecycle missing | Follow trial30 output to broker intent and BE update; it must exist to test this strategy | No wiring in inspected entrypoints. Research `replay` mutates local position dict; Shadow logs JSONL, `order_api_called=false`. Existing SMC adapter opens LIMIT, whereas trial30 requires immediate market entry. |
| Cost/day-start prerequisite failure | Change only time or baseline snapshot; admission reason should change | Confirmed: original policy valid at review time, invalid/stale at pinned2026-10-01; exact midnight creates baseline, five seconds late without baseline fails, valid restart works, balance change fails. |
| Host/account issue | Existing read-only Wine identity probe returns fresh Demo snapshot | Probe exit1 with Wine server-port error before account snapshot; current identity, equity, exposure and permissions remain unknown. No evidence of credential failure. |

## Blocking conditions and smallest next work

1. **Wrong strategy if using current runtime.** `main.py:34,84` calls legacy wick/MSS. Pure B1 Shadow calls D30/RSI/EMA at `scripts/pure_b1/shadow.py:127,158`. Trial30 detector exists only in research at `scripts/research/breakout_logic.py:96-110` with sell-only guard at422-442. Implement an isolated trial30 Demo/shadow entrypoint consuming the pinned rules; leave frozen core unchanged until an explicit adoption decision.
2. **TP/daily/direction mismatch.** Real `pure_b1_levels(entry100,SELL,ATR2)` gives SL105/TP87.5; trial30 requires SL105/TP94. Runtime `decide` admits BUY and also admits equity160/day-start200 at exactly20% loss; trial30 should reject there. Sources: `scripts/strategy.py:84`, `scripts/pure_b1/decision.py:107,128`. Parameter replacement alone cannot supply BE lifecycle.
3. **No market-entry and trial30 BE lifecycle integration.** Research BE at `scripts/research/breakout_logic.py:367-400` changes local stop, effective on later ticks, with modeled cost cover. Current Shadow blocks symbol exposure and has no held-position management. Existing adapter entry branch is PLACE_LIMIT (`scripts/smc/mt5_adapter/execution.py:58`); DEAL branches are partial/closing operations. Reuse broker identity/journal/reconcile infrastructure, but add/review the specific immediate-entry and closed-bar BE behavior. Do not route trial30 through SMC sizing, partial exits, rollover or recovery.
4. **Admission evidence required.** Current cost policy reviewed2026-09-29T12:00Z expires after24h (`scripts/pure_b1/cost_policy.py:49`). Shadow requires explicit policy env path (`scripts/ops/mt5_wine_pure_b1_shadow.py:81`). Verify account costs and source before refreshing; do not merely replace timestamp. Slippage remains assumed until measured. Missing UTC baseline blocks; do not synthesize later equity as day-start.
5. **Daily baseline operational incompatibility to resolve.** `_day_start` only creates state in second00 at00:00UTC and rejects changed balance (`scripts/pure_b1/shadow.py:44-51`). Watch sleeps5s (`scripts/ops/mt5_wine_pure_b1_shadow.py:113`), so exact-second capture is not guaranteed. A trade close changing balance also blocks this implementation, as reproduced. Trial30 needs persisted account-scoped daily accounting that distinguishes reconciled trading PnL from cash adjustments; preserve20% baseline and fail closed when evidence is missing. No relaxation implemented here.
6. **Host not yet verified.** Command below attempted with existing ignored-env runner. Output: `wine: cannot find the server port: 0x0000044c`; exit1; no identity JSON produced. Cause within Wine/host not isolated by this error alone. Restore existing Wine IPC then rerun read-only identity, account permissions, complete M1 history and quote capture before order testing.

```bash
.venv/bin/python -m scripts.ops.run_b1_d_wine \
  --script scripts/ops/b1_demo_readonly_identity.py \
  --output data/trial30_demo_identity_2026_10_01.json
```

Additional legitimate admission gates reproduced on synthetic broker inputs: existing symbol position/order, insufficient free margin, missing costs/day-start, fixed0.01 SL risk>10%. These are protections, not bugs to bypass. [Probe outputs](2026-10-01-trial30-demo-gate-probes.json).

## Validation and limits

- `.venv/bin/python scripts/debug/trial30_demo_gate_probes.py`: exit0; pinned time, real admission/cost/day-start functions, repository synthetic fixtures; no broker calls. Captures existing behavior, not a prospective trial30 implementation.
- Pure B1 focused suite42 passed; breakout logic suite27 passed. Diagnostic Ruff lint/format passed. These do not verify current broker connectivity, fills, stop changes, unknown-result retries, restart reconciliation or executed-only notifications.
- Trial source/result hash matched; `discovery_pass=false`, metrics contain full and first_half only. First-half profit/RR screens failed; second_half absent. No replay of184-day tape performed here. Lack of profitability qualification is a research finding, distinct from a technical reason why a Demo order cannot be sent.
- Phases5/6 production fix/regression acceptance are deferred: user requested diagnosis; there is no integrated trial30 broker seam to repair/test end-to-end yet. Repro stays red and labeled diagnostic; no temporary production instrumentation was added.

**Next implementation boundary:** explicit trial30 research-Demo contract → shared shadow/live decisions and lifecycle → offline parity/restart/error tests → restored read-only broker proof → separately authorized controlled Demo order lifecycle. Until then, enabling `dry_run:false` runs the wrong path and does not test trial30.
