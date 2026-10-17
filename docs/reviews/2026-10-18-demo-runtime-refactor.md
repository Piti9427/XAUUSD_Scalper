# C22 / shared Demo runtime structural refactor

เปลี่ยนโครงสร้างเสร็จ; offline validation ผ่าน คง trading behavior และ known defects.
ไม่มี broker connection, watcher start/restart, cost renewal, order จริง หรือ deployment.
ผลนี้ไม่เปลี่ยน readiness และไม่อนุญาตเงินจริง.

## Implementation

- `scripts/demo_runtime` รวม runner, admission, lifecycle, broker, journal, costs,
  CLI, Wine host และ read-only status. `DemoRunner` รับ strategy ผ่าน constructor.
- Admission/lifecycle ใช้ composition ร่วม runner context; ไม่มี state machine,
  persistence schema หรือ copied B1/SMC implementation ใหม่.
- C22 inherits `DemoRunner` โดยตรง; trial30 adapter คง constructor/default strategy,
  public cycle/close และ attributes เดิม. Forwarding methods คง private caller seams.
- Legacy broker/journal/costs และ ops imports alias module เดียวกับชื่อกลาง จึงคง
  patch targets เดิม (`clock_now`, `ROOT`, `time.monotonic`). CLI flags/defaults,
  reason strings และ exits คงเดิม.
- เก็บ `CONTEXT.md` เดิมทุก byte ใน `docs/archive/2026-10-18-context-smc-v2.md`;
  root เป็น glossary ปัจจุบัน. ปรับ architecture map, README, runbooks, repository
  implementation references และ CORE_STRATEGY เฉพาะ implementation references.
  เพิ่ม `make test-demo`; `make test` เดิมคงเดิม.

[ขั้นตอน → module → tests → คำสั่งตรวจ](../architecture/codebase-layout.md#debug-entrypoints)
เป็นทางเข้า debug ปัจจุบัน.

## Verification

Campaign เริ่ม17ต.ค. และจบ18ต.ค.เวลาไทย; generated evidence อยู่
[`runs/demo-runtime-refactor-2026-10-17/`](../../runs/demo-runtime-refactor-2026-10-17/)
ทั้งหมด ignored และไม่มีไฟล์ใต้ `runs/` tracked.

| Requirement | Evidence |
| --- | --- |
| “Existing suite ผ่านครบ” | Baseline962 tests/78.500s, final `make test`:966 tests/79.476s, OK(skipped2); [full log](../../runs/demo-runtime-refactor-2026-10-17/final-suite.log) |
| “เพิ่ม tests เฉพาะ compatibility และ behavior parity ผ่าน public interfaces” | `DemoRuntimeCompatibilityTests.test_legacy_modules_share_implementation_and_patch_targets`, `test_runner_adapters_keep_constructor_and_direct_c22_base`, `test_legacy_monotonic_patch_reaches_both_collaborators`, `test_injected_strategy_matches_rollback_cycle_and_persistence`; four tests pass; `make test-demo`:96 tests/34.137s, OK |
| “เทียบ fixed-clock fixtures ก่อน/หลัง” | 197 public-cycle observations จาก92 existing Demo tests ตรงกัน: results/exceptions, request payloads, journal KV/outbox, Markdown/JSONL notes และ causal-cache CSV hashes; [parity](../../runs/demo-runtime-refactor-2026-10-17/parity.json) |
| “ครอบคลุม entry, shadow, rejection, ambiguous send, restart, BE, close, safety close และ single-writer guard” | Existing92 Demo fixtures/assertions คงเดิมและถูก capture ก่อน/หลัง; compatibility test เพิ่ม direct `DemoRunner` vs rollback adapter สำหรับ shadow/fill/order-check rejection/timeout/identity block พร้อม restart, journal/outbox/events เทียบกัน |
| “Fault matrix ไม่มี case หาย ไม่มีสถานะเปลี่ยนหรือ harness error ใหม่” | 112 cases:94 PASS/18 GAP/0 harness errors; JSON ก่อน/หลังตรงทั้ง document; harness/assertions เดิมไม่แก้; [after matrix](../../runs/demo-runtime-refactor-2026-10-17/after-matrix.json) |
| “Frozen paths/bytes/hashes คงเดิม” | Protected paths191ไฟล์ไม่เปลี่ยน, C22 pins9ไฟล์ตรง config; broker/journal/costs ย้ายตรงทุก byte; [structural verification](../../runs/demo-runtime-refactor-2026-10-17/structural-verification.json) |
| “ไฟล์ที่แก้ผ่าน formatting และไม่มี format failures เพิ่ม” | Changed/new Python22ไฟล์ formatผ่าน; repositoryยังมี15 failuresเดิม ชุด path ตรง baseline ไม่มีเพิ่ม; lintผ่านทั้ง repository |

ตรวจแยกชุด: phase1 broker/journal/costs ผ่าน35 tests; phase2 composition ผ่าน92
Demo tests; phase3 CLI/host/status/docs ผ่าน96 Demo testsและ966 full tests.
`make compile deps` ผ่าน; `pip check`:No broken requirements found. ไม่มี MT5 smoke
เพราะงานนี้ห้ามเชื่อม broker. Repository-wide format-check ยัง exit1 จาก15ไฟล์เดิม;
ไม่มี formatter ทั้ง repository หรือเปลี่ยน pinned files.

Capture normalization มีเพียงชื่อ shared base (`Trial30DemoRunner` → `DemoRunner`)
เป็น label เดียว; ไม่ normalize result, reason, payload, state, notes หรือ cache.
Clock inputs ใช้ fixture UTC เดิม. AST comparison ยืนยัน cycle envelope, broker-read
prefix, admission body, lifecycle bodies และ CLI/host/status body ตรงต้นฉบับหลัง
เปลี่ยนชื่อ context/import. C22 เปลี่ยนเฉพาะ import/base class; notes/cache body เดิม.
Evidence helpers `capture.py`, `compare.py`, `verify_structure.py` และ source snapshots
เก็บใน campaign เพื่อ audit; archived fault-matrix harness คงเดิม. `compare.py` และ
`verify_structure.py` exit0; matrix exit1 ตาม GAP เดิม ไม่ใช่ harness failure.

## Remaining limits

Known18 GAP คงเดิม รวม optional-note exceptions/timing และ post-fill gaps.
งานนี้ไม่ใช่ remediation, broker parity หรือ runtime reload. ต้อง review/อนุมัติ
rollout แยกก่อนเปลี่ยน process จริง. Pre-existing trade-log diff และ readiness/fault
reports ของ owner ไม่ถูกแก้; ไม่มี unrelated cleanup หรือ Git commit.
