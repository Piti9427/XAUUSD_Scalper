# Monday attended Demo instruction and waiting-time exception

Owner request: “ถ้าวันจันทร์ตลาดเปิดให้ run bot trade ทันทีสำหรับการเข้า order
จริงในบัญชี demo แล้วใช้บัญชีนั้นในการเทรดจริง”. Scope is actual broker Demo
orders using virtual funds, not a real-money account. Frozen C22 entry/exit and
financial risk controls remain unchanged.

Asked explicitly about the conflicting original48h/96bar gate, owner selected
“ยกเว้นเวลา shadow สำหรับ Demo trial มีคนเฝ้า”. Private bound review now carries
a dated exception for Monday2026-10-26 in Asia/Bangkok, accepting removal only
of48h/96bar/UTC-midnight waiting requirements. Original review was preserved.
Other days/scopes/accounts/configs do not inherit the exception. Current healthy
observation, fresh complete closed M15 and finite macro are still required;
historical bootstrap is not represented as new market evidence.

Actual deployed read-only reporter SHA256:
`c105e5decfa2db3c3e22f9b7b51f97c6585eea0ca778bdda0f4b308ce48a7fdb`.
Updated private review SHA256:
`d1400db9d29fa7f26339f1089ca44c9cde90e09647619eda9cdf90cc1bd7f883`.
Full trading source manifest remained unchanged. At08:16:09UTC/15:16:09Bangkok,
shadow execute=false/flat, no active position/halt; execution uninstalled and
cost policy COST_INCONCLUSIVE. No broker order was sent by this task.

## What is actually scheduled

Created one local Codex heartbeat `c22-demo-monday-readiness-check`, ACTIVE.
Saved single-run recurrence plus verified Mac timezone Asia/Bangkok calculates
Monday2026-10-26T04:45:00+07:00. Its sole actions are read-only readiness inspection,
notification and inviting the owner back. Mac/app must be awake and connected.
No VM sending timer exists. No scheduled task may enable AutoTrading, install or
start execution, attest costs, mutate financial state or place/modify/close orders.

Automatic approval review rejected the initial scheduled task that could activate
Demo trading, citing missing explicit authorization for scheduled broker actions
and required attended execution-time approval. Safer read-only follow-up was
created instead; it is not an indirect cutover. At the actual session, fresh
broker/cost/identity/ledger evidence and owner-present approval remain necessary.

## Verification

| Requirement | Evidence |
| --- | --- |
| “ยกเว้นเวลา shadow สำหรับ Demo trial มีคนเฝ้า” | `test_dated_monday_attended_waiver_removes_only_shadow_time_gates`: Bangkok Monday matches despite Sunday UTC;2minute/1bar observation does not claim48h, while stale quote and pending outbox still block and execution_authorized stays false. |
| Exception limited to dated attended scope | `test_waiver_cannot_apply_on_other_day_scope_or_without_complete_bar`: other date/timezone/decision/account cannot waive; absent fresh bar/finite macro still block. |
| Existing invariants retained | All13 readiness tests and `make test-demo`:156tests/72.941s/OK. Compile/deps/lint and changed2-file format check pass. |
| Scheduled check, not scheduled trading | Created automation prompt explicitly prohibits execution/AutoTrading/order_send/state writes; saved schedule inspected and next local date calculated. |

Machine evidence is ignored under `runs/c22-monday-demo-trial-2026-10-24/`.
Current procedure: `docs/ops/c22-attended-market-open.md`.
