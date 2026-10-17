# B1-FINAL — Update ledger, 2026-09-27

Base commit: `6b39e89`. Scope: findings F1–F6 from `docs/reviews/B1_FINAL_SCRUTINIZE_2026-09-27.md`; exact HWM restart parity. Orders remain Tester-only. No account/risk/strategy changes authorized by this work.

## สถานะล่าสุด / อ่านส่วนนี้ก่อน — 2026-09-27

**เป้าหมาย:** ทำ B1 เดิมให้ execution/recovery ถูกต้องและปิด acceptance ตาม PRD; ยังไม่รับรองกำไรหรือพร้อม Demo deployment

**บัญชีทดสอบที่ล็อก (2026-09-27 11:40 UTC+7):** `Standard_demo_100`. ชื่อบนโบรกเกอร์ `Standard_demo_100$`, ประเภท Standard, leverage สูงสุด 1:1000, free margin 100.00 USD, floating PnL 0.00 USD. งานบัญชีเป้าหมายรอบใหม่ใช้บัญชีนี้ ไม่กลับไปใช้ Demo เก่า $1,173.46. Read-only probe `data/b1_account_check_2026-09-27.json` (04:32:04 UTC) จับคู่ identity ใน `.env` ได้: Demo, hedging, USD, equity = balance = margin free = 100, leverage 1000, `XAUUSDm`, ไม่มี position/order, `order_api_called=false`. Evaluator ให้ `VERIFIED` และ `actual_demo_equity` = `ACCOUNT_BLOCKED`. งบ 1% = $1.00; stop ของ 0.01 lot ที่ถูกสุด ≈ $15.59, median ≈ $20.34. Margin ของ 0.01 lot ≈ $4.29 จึงไม่ใช่ตัวที่บล็อก. Tick ล่าสุดค้างจากตลาดปิด จึงยัง `UNVERIFIED_NO_FRESH_TICK`. Login, server และ password อยู่เฉพาะใน `.env`. ตัวเลข equity $1,173.46 ด้านล่างเป็นบัญชี Demo ก่อนหน้า ไม่ใช่บัญชีนี้.

### Logic ที่ใช้อยู่

- **Version:** `B1-FINAL-v1`, fixed exit, `ExitMode=0`; target Standard Demo / `XAUUSDm` จาก private `.env`; executable EA ยังเป็น Tester-only
- **Signal:** ใช้ completed M15 bar; BUY เมื่อ close สูงกว่า Donchian high ของ 30 bars ก่อนหน้าและ RSI(14) ≤75; SELL เมื่อ close ต่ำกว่า Donchian low และ RSI(14) ≥25 ไม่รวม signal bar ใน channel; warmup 100 completed bars
- **Entry:** first valid tick ของ M15 ถัดไปเท่านั้น; BUY ที่ Ask / SELL ที่ Bid; หมด interval แล้วทิ้ง signal ไม่ chase
- **Exit:** SL ห่าง requested quote 2.5×ATR(14), TP 3.5R; ไม่ re-anchor SL/TP หลัง fill; position R ใช้ actual weighted fill entry ถึง initial SL; fixed exit ยังไม่ใช้ BE, trailing หรือ partial TP ส่วน +2R cost-covering BE เป็น research arm ที่ไม่ผ่าน promotion
- **Risk:** equity HWM; DD <3% ใช้ 1%, 3–<6% ใช้ 0.75%, 6–<9% ใช้ 0.5%, 9–<12% ใช้ 0.25%; DD ≥12% latch หยุด entry ใหม่ ไม่ panic-close protected position และไม่ auto-reset; daily −2R/−3R เป็น telemetry ไม่ใช่ hard stop
- **Sizing/protection:** broker profit/margin/spec checks, floor volume, reject หาก minimum lot เกิน budget; ถือได้ 1 position; later fills refresh weighted entry/R/fees; missing SL หรือ fill risk เกิน budget ปิด owned exposure และ halt
- **Recovery/events:** ใช้ stable position identifier กับ history, current ticket กับ execution; persist exact HWM และ schema-2 pending confirmed events; consumer unknown delivery ไม่ resend อัตโนมัติ

Source contract: [B1-FINAL-v1.yaml](/Users/nopparuj/my-agents/XAUUSD_Scalper/config/B1-FINAL-v1.yaml), [frozen detector](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalCore.mqh), [execution engine](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh)

### ทำถึงไหนแล้ว

- แก้ F1/F2/F3/F4/F6 และ exact HWM พร้อม regression; F5 ปิด false PASS แล้ว แต่ full replay/stress ยังไม่เสร็จ
- Python 585 tests ผ่าน; MQL 127 checks ผ่าน; EA compile 0 errors/0 warnings; actual-equity Tester parity 560/560, minimum-lot rejection 558 ครั้ง, expired 2 signals, 0 trades
- Update runbook/review/release/local tickets และ handoff ให้แยก historical evidence ออกจาก code หลังแก้; ยังไม่ commit

### ตอนนี้ติดอะไร

| สิ่งที่ติด | หลักฐาน / ผลกระทบ |
|---|---|
| Account minimum-lot risk | บัญชีปัจจุบัน equity $100 → 1% budget = $1.00; 0.01-lot stop ที่ถูกสุด ≈ $15.59 จึงยัง `RISK_BELOW_MINIMUM_LOT`. บัญชีเก่า $1,173.46 (งบ ≈ $11.73, stop ถูกสุด ≈ $12.16, Tester deposit 1173) เป็นหลักฐานรอบก่อน ไม่ใช่ equity ปัจจุบัน |
| Full replay/stress | ยังไม่มี replay cost → sizing/HWM/DD/changed entries ที่ครบ spread ×2, delay 2s, adverse $0.10/oz และ combined; ticket 08 ยัง INCOMPLETE |
| Costs/UTC evidence | ยังไม่วัด broker costs ครบ และ fresh weekday UTC probe ยังไม่ verified; weekend tick ใช้ยืนยันไม่ได้ |
| Target fill acceptance | บัญชีเป้าหมายมี 0 trades; fake-broker regressions พิสูจน์ engine correctness ได้ แต่แทน executable target-account sample ไม่ได้; $10,000 fixture เก่าไม่ใช่ accepted account qualification |

### งานถัดไปตามลำดับ

1. ทำ replay/stress ให้ recompute execution และ continuous risk state ครบ matrix; เก็บ manifest/hash และ per-position reconciliation ของแต่ละ arm ห้ามใช้ post-hoc sensitivity ปิด ticket
2. เมื่อ market เปิด เก็บ read-only fresh UTC/account/spec/cost evidence โดยใช้ inputs เดียวกับ EA
3. ปิด account feasibility/target sample ภายใน scope ที่ผู้ใช้ตัดสินใจ; การเพิ่มทุน เปลี่ยน instrument หรือเปลี่ยน risk/SL ยังไม่ถูกเลือก ห้ามทำเองเพื่อบังคับให้ได้ sample
4. Rerun acceptance และออก release verdict ใหม่เมื่อ prerequisites ครบ; OOS/forward qualification เป็นอีกขั้น ไม่เริ่มส่ง orders เพื่อปิดงานเอกสาร

**Current verdict:** fixed exit retained, BE disabled; `ACCOUNT_BLOCKED`, `STRATEGY_NO_GO`, deployment `NO_GO`; ยังไม่ final ครบ 8 tickets

## Debug ledger (append during work)

| Date | Experiment / change | Observed result | Conclusion |
|---|---|---|---|
| 2026-09-27 | Added Python regression cases: missing closes, duplicate signals, identity mismatch, ambiguous send, post-hoc promotion, health flags | RED: 5 failures + 2 errors; old fixture TestCase import also collected 10 controls, subsequently isolated | Existing gate and delivery paths fail required behavior; health function absent |
| 2026-09-27 | Pdb breakpoint at reconciliation return; empty event ledger, broker +100/-100 | ledger rows=0, deal_net=event_net=equity_change=0; gate accepts | Aggregate equality hides lost trades |
| 2026-09-27 | Positive controls: unique signal and correct per-trade identities before changing one ID | Unique signal passes; changing ID still passes before fix | Input validity alone does not explain false PASS; missing identity/uniqueness checks survive disproof |
| 2026-09-27 | Added MQL regression for later fill price+fees, server ticket replacement, failed confirmed append/restart, exact HWM | Compile succeeded; first runner invocation failed before test because parity fixture path was wrong | No MQL runtime result from that invocation; retry uses archived fixture path |
| 2026-09-27 | Re-ran RED MQL harness with valid archived parity fixture | 106 PASS / 8 FAIL; normal same-price volume-growth control still passes | New fault axes explain defects rather than a general harness failure; manifest confirms simulated orders only |
| 2026-09-27 | Python fixes: per-position reconciliation, signal duplicate rejection, mandatory health fields, fail-closed stress gate, persisted SENDING | 25 Python tests PASS including 7 new review regressions | F4/F6 regression paths corrected; missing replay/stress now remains INCOMPLETE rather than qualifying |
| 2026-09-27 | MQL changes: stable identifier, cumulative fill snapshot, exact HWM, durable event queue, idempotent JSONL append, guarded modify persistence | GREEN compile/runtime requested | Result pending; no verification claimed until observed |
| 2026-09-27 | First post-fix engine run | 112 PASS / 2 FAIL in repeated ADMISSION diagnostic assertions | New fake-sink dedupe incorrectly included diagnostics; narrowed dedupe to confirmed events only. New risk/recovery/HWM regressions passed |
| 2026-09-27 | Tried including EA into harness via callback rename macros | Compile failed: macro also renamed engine.OnTick call | Discarded include approach; moved unchanged JSONL adapter to shared B1FinalOutbox.mqh and tested same production class directly |
| 2026-09-27 | Real JSONL adapter tests, first pass | 120 PASS / 1 FAIL: append succeeded but acknowledgment falsely returned failure | FileWriteString TXT expands LF into CRLF; expected byte count was wrong. Switched to explicit CRLF and checked complete record bytes ([official API](https://www.mql5.com/en/docs/files/filewritestring)) |
| 2026-09-27 | Final MQL engine + production JSONL adapter suite | 127 PASS / 0 FAIL; terminal exit 0, no forced close | Late fill risk, stable identity, durable replay, checkpoint crash and exact HWM corrected within tested scope |
| 2026-09-27 | EA compile + actual-equity real-tick Tester replay May14–Sep26 | 0 errors / 0 warnings; 560/560 signal parity; 558 min-lot rejections + 2 expired signals; 0 trades; trusted=1, incident=0, outbox failures=0, pending events=0 | Target-account safe behavior unchanged; zero trades does not prove fill execution on target account |
| 2026-09-27 | Rechecked seven historical runs with stricter validator | Actual/$100 empty ledgers reconcile; old research runs fail POSITION_IDENTITY_UNAVAILABLE; exit validation INCOMPLETE_REPLAY_STRESS | Old events lack new stable ID field; this means insufficient coverage evidence, not proof that historical PnL was wrong. Archived results preserved |
| 2026-09-27 | Full Python suite after final changes | 585 PASS in 5.481s | Added 11 review regressions. Restored known test-generated ops JSON to pre-run bytes; no unrelated source revert |
| 2026-09-27 | Final source/manifest cross-check | All five EA source hashes match tested worktree; git diff whitespace check clean | Tested EA binary corresponds to current execution sources |

## Ranked hypotheses and disproofs

1. Aggregate-only reconciliation hides offsetting missing closes; disproof: same broker ledger with all correct IDs must pass, changing only one ID must fail.
2. Signal dictionary erases duplicate events; disproof: single event on same bars must pass while duplicate alone changes verdict.
3. Post-send persistence loses uncertainty after crash; disproof: acknowledged persisted replay must remain deduplicated, and explicit pre-send failure must remain retryable.
4. Cached first-fill price/fees bypass later-fill risk; disproof: same-price volume growth already triggers over-risk, while changed average with requested total volume must also trigger.
5. Ticket treated as lifecycle identifier; disproof: ticket replacement alone must not change ownership or prevent history close.

Python debugger used on reconciliation. MQL debugger cannot step through automated Wine Tester here; use deterministic fake-broker runtime, source trace and single-axis fault injection. Every remaining runtime result is recorded below before calling a fix verified.

## แก้ไขแล้ววันนี้ — 2026-09-27

| Finding | เปลี่ยนอะไร / เหตุผล | ผลตรวจและสถานะ |
|---|---|---|
| F1 Later partial fill | Refresh cumulative volume, weighted entry, initial-SL R และ cumulative entry commission ก่อนตรวจ budget; unavailable fees เป็น incident และปิด owned exposure | **Fixed, regression verified**: `TestReviewRegressions`, late partial price/fees และ over-budget close ผ่าน |
| F2 Ticket vs identifier | เพิ่ม persisted `pos_identifier`; matching/history ใช้ lifecycle identifier; stop/close request ใช้ current ticket ที่ reconcile ใหม่ | **Fixed, regression verified**: server ticket replacement และ subsequent history close ผ่าน ไม่ได้อ้างว่าเคยทดสอบ server rollover บน live broker |
| F3 Producer event loss | Sink คืน acknowledgment; engine persist pending confirmed events พร้อม state transition, retry ตามลำดับ; close transition เก็บ day-R และ clear position พร้อม pending event; sink dedupe stable IDs และตรวจ short write/torn tail | **Fixed, regression verified**: file lock, short write, duplicate ID, restart pending close และ append-before-checkpoint failure ผ่าน |
| F4 False implementation PASS | Reconcile position identity/count/full entry-exit volume/PnL; reject duplicate signals/close IDs; require trusted, no incident, no outbox failures/pending events; requireครบ 3 chronological blocks | **Fixed, regression verified**: missing offsetting closes, wrong IDs, duplicate close/signal และ health flags ไม่ได้ PASS |
| F5 Incomplete stress | Post-hoc metrics ระบุ `POSTHOC_SENSITIVITY_ONLY`, `replay_verified=false`; reserve/adverse และ required spread/delay/adverse/combined evidence เป็น prerequisite; missing evidence ได้ `INCOMPLETE_REPLAY_STRESS` | **Partial**: ปิด false qualification แล้ว แต่ยังไม่มี full cost/risk-path replay และ required stress matrix จึงยังไม่ปิด ticket 08 |
| F6 Consumer crash resend | Persist `SENDING` ก่อนส่ง, fsync + atomic replace, lock ให้มี consumer เดียว; restart/ambiguous exception → `DELIVERY_UNKNOWN`, ไม่ resend; retry ได้เฉพาะ sink ยืนยัน `NotSentError` | **Fixed, regression verified**: crash-after-acceptance ส่งครั้งเดียว; timeout/ambiguous error ไม่ retry; proven pre-submit failure retry ได้ |
| Exact HWM | เลิก +0.05% persistence padding; persist exact double bits และตรวจ tier หลัง restart ตรง boundary | **Fixed, regression verified**: exact HWM/risk และเหนือ 3% boundary ผ่าน |

ไฟล์หลักที่แก้:

- [B1FinalEngine.mqh](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngine.mqh): fill snapshot, stable identifier, pending queue, exact HWM และไม่ส่ง modify หลัง persist request ล้มเหลว
- [B1FinalEA.mq5](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEA.mq5): broker identifier mapping และ summary pending event count
- [B1FinalOutbox.mqh](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalOutbox.mqh): shared production JSONL sink แยกจาก EA เพื่อ fault-test class เดียวกัน
- [B1FinalState.mqh](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalState.mqh): schema 2 และ checked hex encoding สำหรับ nested pending documents
- [b1_outbox.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/b1_outbox.py): durable send state/ownership/uncertainty
- [b1_final_release.py](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/research/b1_final_release.py): coverage reconciliation, health checks และ fail-closed promotion
- [MQL regressions](/Users/nopparuj/my-agents/XAUUSD_Scalper/mql5/B1FinalEngineTests.mq5), [Python regressions](/Users/nopparuj/my-agents/XAUUSD_Scalper/tests/test_b1_final_review_regressions.py), existing release/outbox tests ปรับ fixtures ให้ตรง identity/pre-send failure contract
- Runbook, MQL README, review status และ local ticket status ปรับให้ไม่อ้างว่า historical evidence รับรอง code หลังแก้

## Verification artifacts

| Requirement | Evidence |
|---|---|
| RED ก่อนแก้ | [red_engine CSV](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/red_engine/B1_engine_tests.csv): 106 PASS / 8 FAIL |
| Engine + actual sink correctness | [final_engine CSV](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/final_engine/B1_engine_tests.csv): 127 PASS / 0 FAIL; [manifest](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/final_engine/run_manifest.json) |
| Python crash/identity/stress regressions | `ReviewRegressions.test_crash_after_acceptance_becomes_unknown_without_resend`, `test_reconciliation_checks_identity_not_only_sum`, `test_missing_offsetting_closes_fail_reconciliation`, `test_duplicate_signal_fails_parity`, `test_posthoc_reserves_cannot_qualify_replay`, plus health/concurrency/persistence cases |
| Full Python validation | `.venv/bin/python -m unittest discover -s tests`: [sanitized log](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/python_full_suite.log), 585 PASS |
| Actual EA compile | [compile log](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/ea_compile.log): 0 errors / 0 warnings |
| Target-equity EA replay | [evidence JSON](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/actual_equity_evidence.json), [manifest](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/actual_equity_fixed/run_manifest.json): source hashes, exact tested binary, no live orders |
| Historical gate audit | [recheck JSON](/Users/nopparuj/my-agents/XAUUSD_Scalper/data/b1_final_fixes_2026-09-27/historical_evidence_recheck.json): old research evidence insufficient for new per-position gate; stress remains incomplete |

ตัวอย่าง rerun MQL suite (terminal ต้องไม่กำลังทำงาน):

```bash
.venv/bin/python scripts/ops/mt5_wine_tester.py run B1FinalEngineTests \
  --sources B1FinalEngineTests.mq5 B1FinalOutbox.mqh B1FinalEngine.mqh B1FinalState.mqh B1FinalCore.mqh \
  --output data/b1_final_fixes_2026-09-27/<new-run> \
  --start 2026.09.21 --end 2026.09.22 --deposit 1173 --model ohlc_m1 \
  --input-file data/b1_final_release/engine_tests_tester_run/B1_FINAL_parity_input.csv
```

## Compatibility และงานค้าง

- **State schema 1 → 2:** เพิ่ม stable ID และ pending event journal จึงต้อง reject/preserve schema-1 state; ไม่มี silent migration, reset HWM หรือ delete evidence เก่า ถ้ามี persisted owned exposure ต้อง reconcile ภายใต้ขั้นตอนที่อนุมัติก่อนเปลี่ยน runtime
- **Sink failure contract:** `ConnectionError`/generic exception อาจเกิดหลัง remote acceptance จึงเป็น unknown; sink ที่พิสูจน์ว่าไม่ได้ submit ต้องใช้ `NotSentError` External exactly-once ไม่ได้ถูกสัญญา
- **Compile source list:** EA และ engine harness ต้องรวม `B1FinalOutbox.mqh` ทั้งคู่
- **Account:** บัญชีปัจจุบันคือ Standard Demo $100, leverage 1:1000. Tester deposit 1173 เป็น whole-dollar approximation ของ equity เก่า $1,173.46 และไม่ใช่บัญชีนี้. ทั้งสอง equity ยังเปิด minimum lot ภายใต้ risk 1% ไม่ได้ ไม่มีเพิ่มทุน/ปรับ SL/risk หรือใช้ $10,000 fixture ใหม่ในรอบแก้นี้
- **Open evidence:** full spread ×2 / delay / adverse / combined replay ที่ recompute sizing/HWM/DD, measured broker costs, fresh weekday UTC probe และ target-account executable sample ยังขาด ผล research เก่าคงเป็น historical evidence ไม่ใช่ post-fix qualification
- Real-tick Tester ยังใช้ generated ticks ใน gaps ตามข้อจำกัดเดิม ต้องอ่าน journal คู่ผล ไม่ถือว่า ticks ทุกนาทีมาจาก observed real ticks
- ไม่ deploy, ส่ง Demo/live orders, Telegram หรือ commit ในรอบนี้ Frozen `B1FinalCore.mqh` และ entry/initial-SL/TP/risk contract ไม่เปลี่ยน `.env` ไม่แก้

**Completion status:** แก้ F1/F2/F3/F4/F6 และ exact HWM พร้อม regression แล้ว; F5 ปิด false PASS แต่ full replay/stress ยัง incomplete คง fixed exit, BE disabled, `ACCOUNT_BLOCKED`, `STRATEGY_NO_GO`, deployment `NO_GO` ยังไม่ประกาศ final ครบ 8 tickets
