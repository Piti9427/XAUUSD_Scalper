# Scrutinize: SMC implementation + unified-core plans — 2026-10-08

ผล: **rework** ทั้งสองแผนก่อน implementation. SMC research ทำได้ แต่ unified plan ผูกงานวิจัยกับการเปลี่ยน Demo admission และอ้าง day-start behavior เก่า.

เป้าหมาย: ทดสอบว่า standalone SMC เพิ่ม admitted frequency และผลตอบแทนหลังต้นทุนเทียบ frozen C22H4 โดยใช้ข้อมูลและ accounting เดียวกัน.
ทางเลือกเล็กกว่า: adapter ใหม่บน tick replay/swap/input infrastructure ที่มีอยู่; เลื่อน `scripts/core/` และแยก Demo policy ออก. ไม่จำเป็นต้อง refactor sender เพื่อทดลองสมมติฐาน SMC.

## Artifacts reviewed

ต้นฉบับ Antigravity ทั้งสองอยู่ใน `/Users/nopparuj/.gemini/antigravity-cli/brain/1ae3cc1d-25d1-4117-a5c5-0608b393cccb/`:

- `smc_strategy_implementation_plan.md` (SMC plan)
- `unified_core_and_smc_refactor_plan.md` (unified plan)

SHA-256 ณ review: SMC `b4de53fb10b09dfa42d522049c7ad5045e396d259f9a62a14ac1ad49dfc322fd`; unified `1e8bff11a6ba9caeb43d2424f67c06c072ba9dbfab90fd6b35a30f12411b11a8`.

ฉบับปรับปรุงอยู่ใน repository เพื่อรักษาต้นฉบับและส่งต่อ review ได้:

- [SMC implementation plan](../specs/2026-10-08-smc-strategy-implementation-plan.md)
- [Shared infrastructure plan](../specs/2026-10-08-unified-core-and-smc-refactor-plan.md)

## Blocker 1 — Embedded cost fallback bypasses evidence gate

**Finding:** unified plan:121 เสนอใช้ default cost policy เมื่อ JSON หมดอายุ.
**Why:** เปลี่ยนจาก account-bound, evidence-backed admission เป็นค่าคาดเดา; default commission0 อาจรับ trade ด้วย risk ต่ำกว่าต้นทุนจริง.
**Evidence:** `Trial30DemoRunner._cycle` ตรวจ `validate_policy` ก่อน levels/risk (`scripts/trial30/runner.py:161–168`). Validator ต้องมี account fingerprint, evidence hash, units, named source และ UTC review<=24h (`scripts/trial30/costs.py:15–34`). Numeric tariff object ไม่ทดแทนเงื่อนไขเหล่านี้.
**Change:** ตัด fallback. รักษา fail-closed; re-attest ด้วยหลักฐานตาม `docs/ops/c22h4-demo.md:25`. การเปลี่ยนอายุ policy เป็นข้อเสนอ policy แยกต่างหาก.

## Blocker 2 — Preserving source hashes does not preserve execution contract

**Finding:** unified plan:119–120 เปลี่ยน daily loss เป็น realized-only และขยาย90s เป็นแท่ง15นาที ภายใต้คำอ้าง zero source drift.
**Why:** Detector hash ผ่านได้ แต่ admitted trades/equity path เปลี่ยน; realized-only ไม่รวม floating drawdown. Regression เดิมและ archived replay ไม่ได้พิสูจน์ contract ใหม่.
**Evidence:** equity gate คือ `baseline-account.equity` (`scripts/trial30/runner.py:164–166`), one losing completed exit เป็นอีก gate (`:149–154,288–307`).90s ถูกตรวจทั้ง admission และก่อนส่ง (`:155–160,239–242`). `verify_sources` ตรวจ9ไฟล์และ exact detector contract (`scripts/c22h4/strategy.py:40–71`); ไม่ได้ตรวจทุก operational file.
**Change:** แยก Demo policy review; ตัด gate relaxation จาก SMC/core plan. หากต้องศึกษา late entries ให้เป็น versioned research scenario พร้อม parity/expiry/risk tests ไม่เปลี่ยน frozen runner.

## Major 3 — Midnight diagnosis is stale

**Finding:** unified plan:119 เสนอแก้ C22 overnight lock โดยยังไม่รับรู้ implementation7Oct.
**Why:** อาจ override `_cycle()` โดยไม่จำเป็น และเปลี่ยน behavior ที่เจ้าของเลือกไว้แล้ว.
**Evidence:** `C22H4DemoRunner.__init__` ตั้ง `restart_unknown_baseline=True` (`scripts/c22h4/runner.py:161`). `BrokerView._baseline` ตรวจ history/position consistency แล้ว latch current equity สำหรับ process restart ที่เคยถือข้าม midnight (`scripts/trial30/broker.py:78–115`); cycle ถัดไปใช้ journal baseline (`:116–119`). `CORE_STRATEGY.md:504` และ ops:5 ระบุ process ใหม่ latch ใหม่ ส่วน Trial30 ยังใช้ strict default. ไม่ใช่หลักฐานว่าทุก midnight/restart case ผ่าน broker จริง.
**Change:** บันทึก current behavior; reproduce rejection ที่มี timestamp/process/journal evidence ก่อนเสนอแก้. ไม่เปลี่ยนเป็น realized-only หรือ persisted restart baseline โดยอ้างว่า equivalent.

## Major 4 — Wrong replay engine and redundant core

**Finding:** SMC plan:75 เสนอ candidate compatible กับ `engine.py`; unified plan สร้าง market/cost/risk implementations ใหม่ก่อนพิสูจน์ seam.
**Why:** ผลเปรียบเทียบอาจมาจาก execution/accounting คนละระบบ; additive core เพิ่ม authoritative implementations แทนลด duplication.
**Evidence:** `engine.py:48–66` เป็น M1 OHLC execution, balanceเริ่ม0 (`:56`), swapคิด elapsed calendar nights (`:110–126`) ไม่ใช่ signed points/triple calendar. Existing campaign โหลด mmap tapeและเรียก `replay` พร้อม `SwapPolicy` (`scripts/research/c22_frequency_campaign.py:66–86`). Tick replayเริ่มUSD200และมี admission/circuit diagnostics (`scripts/research/breakout_replay.py:108–132`).
**Change:** ใช้ new adapter บน canonical tick replay. Assert Rules/columns และ neutralize breakout defaults. เลื่อน extraction จนมี consumer และ differential evidence; frozen paths/pins ไม่ย้าย.

## Major 5 — Legacy SMC is H1/M5, not interchangeable M15

**Finding:** ทั้งสองแผนระบุ bridging existing detection แต่ไม่ระบุ hidden gates หรือ causal publication.
**Why:** เอา M15 เสียบ API เดิมจะรับ H1 EMA/session/spread behavior โดยไม่ตั้งใจ; session pools/FVG/pivots อาจใช้ข้อมูลที่ยังไม่ปิด.
**Evidence:** `evaluate_smc_setup` รับ H1/M5 (`scripts/smc/detection.py:74–95`), gate spread/session/H1warmup (`:112–142`), แยก CHoCHจากBOS (`:291–346`). Fractalใช้สองแท่งขวา (`scripts/smc/structure.py:331–354`); FVGต้องมี third candle (`:409–435`). `pivot_confirmation_time` คืนเวลาที่ผู้เรียกส่งมา ไม่มีบวก duration (`:77–89`). Legacy liquidity ใช้ M5 coverage และ London07–12 (`scripts/smc/liquidity.py:48–101`); callerต้องจำกัด prefix ไม่ให้ future session data เข้า.
**Change:** reuse pure structural helpers; ทำ M15-specific state machine. ระบุ close timestamps, i+2 confirmation, third-candle publication, pool availability, sweep->CHoCH->FVG->later retest, expiry/invalidation/dedup. BOSไม่ fallback CHoCH. เพิ่ม prefix/future-mutation และ chunk tests.

## Major 6 — Cost/calendar and SELL geometry underspecified

**Finding:** `holding_days` กับ hardcoded -567.4/0 ไม่พอสำหรับ swap-inclusive replay; swing stopยังไม่ระบุ executable side.
**Why:** พลาด triple/weekend/exact rollover ทำให้ equity/circuit/admission หลังถือ position เปลี่ยน; SELL stop จาก Bid swing อาจวางใน Ask wick และผิด R.
**Evidence:** signed swapใช้ points*point*contract_size*volume และ schedule boundary (`scripts/research/rollover.py:11–60`, `breakout_replay.py:159–164`). `prepare_entry` เพิ่ม SELL Ask spread ให้ structure anchor เฉพาะ `m5=True` (`scripts/research/breakout_entry.py:48–66`); M15 adapterต้องระบุ geometry เอง. Canonical riskใช้ modeled entry/rounded stop+exit slippage+commission (`:102–106`), spreadอยู่ใน quotesแล้ว.
**Change:** require metadata+source+calendar; no missing-to-zero fallback. Short rate0ที่ระบุจริงใช้ได้. เพิ่ม swap boundary/triple/weekend และ SELL Ask-stop fixtures. แยก initial modeled admission cap จาก realized loss; future swap/gapsไม่ถูก guaranteeด้วย10%cap. คง `COST_INCONCLUSIVE`.

## Major 7 — Fill, baseline and selection claims exceed evidence

**Finding:** SMC plan:37 อ้าง100%fill; baseline frequencyโดยประมาณกับ DD35/38% trade-off ไม่มี same-input calculation หรือ approved selection rule.
**Why:** quote/risk/margin/busy rejectionทำให้ signal countไม่ใช่ trade count; เพิ่มความถี่หรือเลือก DD ceiling หลังเห็นผลเสี่ยงเลือกด้วย reused discovery.
**Evidence:** replay rejection categoriesรวม risk/margin/late_quote/busy/daily loss (`scripts/research/breakout_replay.py:114–132`). Broker flowมี stop geometry/margin/order_check, fresh-equity/exposure และ unresolved intent (`scripts/trial30/runner.py:199–285`); market requestไม่ guarantee fill. ต้นฉบับ unified:174–176 ให้ frequency~6/month และ DD38 concession โดยไม่มี exact common-input ledger.
**Change:** ใช้ first valid executable tick<=90s; report signal/admitted/rejection funnel. Rerun frozen comparatorบน common tape/cost/warmup/USD200; report actual coverage/full months. Freeze thresholds/catalogก่อนรัน; holdoutต้อง untouched/forward และ lock winnerก่อนเปิด. ระหว่างยังไม่มี selection contract ให้ descriptive scorecard ไม่ประกาศ qualifier.

## Verification performed and limits

Executed with repository `.venv/bin/python3`:

| Command | Observed result |
| --- | --- |
| `-m unittest discover -s tests -p 'test_c22h4_*.py'` |43 tests OK,26.288s |
| `-m unittest discover -s tests -p 'test_trial30_demo.py'` |27 tests OK,0.557s |
| `-m unittest discover -s tests -p 'test_smc_detection.py'` |18 tests OK,0.043s |
| `-m unittest discover -s tests -p 'test_reward156_tuning.py'` |9 tests OK,0.090s |

รวม97 tests ผ่าน. เรียก `verify_sources` กับ current `config/c22h4-demo.json` ผ่าน. C22 CLI fixturesพิมพ์ BLOCKED/SHADOW_ADMITจำลอง; ไม่ใช่ broker probe หรือ order execution evidence.
ไม่มี runtime/config/strategy change, ไม่รัน economic campaign, full suite, MT5 connectivity, broker parity, shadow qualification หรือ cutover. New SMC adapterยังไม่มี จึงยังไม่พิสูจน์ causal/replay parityหรือกำไร. Preserved pre-existing `CONTEXT.md` modification.

Verdict: **rework** — แยก standalone research บน accountingเดิมออกจากการเปลี่ยน Demo safety/entry policy; ฉบับปรับปรุงพร้อมใช้เป็นฐาน implementation review.
