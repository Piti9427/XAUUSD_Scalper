# Oracle ARM64 Runtime Compatibility Experiment

Parent: Issue #1  
Status: Checklist only — not an executed soak result

## Bound

One engineering day for Box64 → Wine64 → MT5 / Windows Python compatibility, then 48h soak/restart/reconnect on Demo after identity gate passes.

## Steps

1. Record VM image / CPU / RAM / OS.
2. Attempt MT5 path under documented stack; stop when timebox expires.
3. If MT5 works: 48h soak with reconnect + process restart tests.
4. File result as `PASS_INFRA` / `FAIL_INFRA` / `INCONCLUSIVE_INFRA` separate from strategy PnL.
5. On FAIL: do not buy paid infra; return to platform review.

## Evidence required

- Broker identity smoke JSON: `python3 scripts/smoke_broker_identity.py --out docs/ops/<date>-exness-smoke.json`
- Commands run + timestamps
- Screenshot or log of MT5 login to Demo
- Restart/reconnect outcomes
- Explicit statement that strategy losses are not infra failures and vice versa
