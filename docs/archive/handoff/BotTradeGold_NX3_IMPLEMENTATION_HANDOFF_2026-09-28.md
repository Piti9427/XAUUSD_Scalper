# BotTradeGold — Central implementation handoff (2026-09-28)

**Purpose:** ให้ agent รอบถัดไปเริ่มงาน NX3 / parallel backtest จากสถานะจริง โดยไม่ตีความผล research ว่าเป็น production strategy. เอกสารนี้เป็น handoff ของบทสนทนา ไม่ใช่การอนุมัติ deploy, trade หรือเปลี่ยน risk contract.

## สถานะที่ยืนยันแล้ว

- Current verdict: `STRATEGY_NO_GO / DEMO_NO_GO / LIVE_NO_GO`; ยังไม่มี final production strategy. Latest complete candidate iteration I037 มี discovery-eligible 5 ตัว แต่ frozen candidate confirmation ขาดทุนทั้ง observed และ reserve; stress ไม่ผ่าน. I038 ตรวจ archive consistency ผ่านเท่านั้น ไม่ใช่ broker/forward attestation. ดู `docs/research/FINAL_EVIDENCE_MAP_2026-09-28.md` และ I037/I038 audit ใน repo (path ด้านล่าง).
- `$100`, `XAUUSDm`, lot ขั้นต่ำ `0.01`, DD hard halt 15% ยังเป็นขอบเขตงาน. ผู้ใช้อนุมัติ research ladder 4/3/2% และ flat 2.5% challenger แยกต่างหาก; **flat 4% ยังไม่อนุมัติ**. ห้ามนำ research MM ไปใช้บัญชีจริงโดยปริยาย.
- Historical Bid/Ask capture May–Sep 2026 ถูกใช้และดูผลซ้ำแล้ว จึงไม่ใช่ untouched OOS สำหรับ challenger ใหม่. Host ปัจจุบันไม่มี MT5 Python import / target Demo config ที่ใช้เก็บ prospective capture; ไม่ได้อ่าน secrets หรือส่ง orders.
- การตรวจล่าสุดบน branch `research/gold-final-loop`, HEAD `0f86b4a`: 633 `unittest` ผ่าน, Ruff ผ่าน, mypy ไม่ได้รันเพราะ system Python ไม่มี package. แหล่งข้อมูลดิบที่ untracked ไม่ควรถูกลบหรือ stage เหมา.

## หลักฐานกับข้อเสนอ แยกกัน

| รายการ | สถานะ |
|---|---|
| B1 M15 | ผลย้อนหลังบวก แต่ PF หลัง 0.15R = 1.110 ต่ำกว่า gate 1.30; ideal fractional sizing ยังไม่พิสูจน์ fixed minimum lot |
| B1-M5 | ช่วงล่าสุดบวกเล็กน้อย แต่ PF ต่ำกว่า gate และ DD เกิน 15% |
| B2 | Discovery ดูดี แต่ confirmation ติดลบ; rejected |
| B3 | Latest PF 1.364 จากเพียง 2 trades; insufficient |
| I014 / I037 | Project tick replay; frozen confirmation ไม่ผ่าน; `FINAL_NO_GO` |
| NX1–NX5 | ยังไม่ backtest ใน BotTradeGold; ตัวเลข NX2/NX3 จาก paper ภายนอกเท่านั้น |

รายละเอียดตัวเลข, chronology, scope, artifacts: ดู central registry ของผู้ใช้และ repo progress; อย่าคัดลอก claim จากเอกสารแนบมาเป็นผลที่ verify โดย code โดยไม่เช็ก raw artifact. บทสนทนาล่าสุดแนะนำ **NX3 Mechanical Structural Break** เป็น challenger แรก; NX2 VWAP/EMA เป็นลำดับถัดไป. งานวิจัย NX3 ระบุข้อจำกัดเรื่อง full-coverage real-tick replication; NX2 ใช้ 1% fractional sizing ในปี 2024 ซึ่งเทียบตรงกับ `$100 / 0.01 lot` ไม่ได้. ไม่ควรสร้าง NX1–NX5 พร้อมกันหรือเลือกตัวชนะจาก confirmation ที่ดูแล้ว.

## ทิศทาง implement ที่เสนอ (ยังไม่ใช่ผลที่วัดได้)

1. **Reproduce controls ก่อน.** ใช้ I014/current tick runner เป็น control ที่เข้ากับ tape ปัจจุบัน. B1/B1-M5/B2 ที่เดิมใช้ OHLC หรือคนละ sizing ต้องติดป้ายว่าเทียบตรงไม่ได้จนกว่าจะ reconcile timeframe, data, cost และ MM. ตรวจ archived hashes, split, ledger และ metric definition.
2. **กำหนด NX3 v1 ที่เล็กและ deterministic.** ระบุ confirmed swing ที่ใช้เฉพาะข้อมูลที่ปิดแล้ว, เวลา signal พร้อมใช้งาน, structure-break confirmation, entry window, invalidation stop, buffer/volatility floor, fixed-R target และ mirror LONG/SHORT. ต้องไม่ใช้ future pivot หรือ intrabar lookahead. เริ่ม core เพียงตัวเดียว; sweep/Stochastic/exit overlay เป็น ablation ภายหลัง ไม่รวมใน v1.
3. **Preflight ความเป็นไปได้เชิงเงินก่อน full backtest.** นับสัญญาณและ minimum-lot admission ภายใต้ `$100`, stop ตาม market structure, observed Bid/Ask, `CostR <= 0.15`, reserve 0.15R และ DD/risk tier. แยกผล default 2.5/2/1.5% กับ research 4/3/2%; อย่าเปลี่ยน capital หรือบีบ stop เพื่อให้เข้าไม้.
4. **Freeze ข้อกำหนดก่อนอ่าน confirmation.** บันทึก experiment ID/config/code/data hash, หน้าต่าง discovery/confirmation, candidate grid ที่เล็ก, selection rule, controls และ stress arms. Run discovery แล้ว freeze winner ตาม gate ปัจจุบัน; confirmation ใช้เพื่อประเมินเท่านั้น. เนื่องจาก tape นี้ถูก inspect แล้ว ผลทั้งหมดเป็น retrospective screening ไม่ใช่ untouched proof.
5. **ทำ prospective path คู่ขนาน.** เตรียม target Demo capture พร้อมต้นทุน/fills จริงและ timestamp จากอนาคต; freeze candidate ก่อนเริ่ม window. หลัง research ผ่านจึงทำ MQL compile + Python/MQL parity, broker margin/stops/fills และ restart/reconciliation checks. Final verdict ต้องคง `FINAL_NO_GO` จนหลักฐานครบ.

## Gate ที่ห้ามลดเพื่อให้ผลดูดี

Research: closed trades >=30, PF หลัง cost >=1.30, mean net R >0, net return >0, actual-tick DD <=15%, ไม่ halt/late flat; ทั้ง observed และ 0.15R reserve ต้องผ่าน และ stress replay ต้องบันทึกตามจริง. Final เพิ่ม untouched forward, measured execution costs, EA parity, target-account executable fills และ operational evidence. ไม่มี user approval สำหรับ production deployment หรือ live orders.

## จุดที่ต้องตกลงก่อน freeze NX3

- นิยาม swing confirmation, displacement, entry expiry, stop buffer และ RR ให้เป็นตัวเลขล่วงหน้า; อย่าดึงค่าจาก confirmation ที่เคยเห็น.
- เลือก risk profile หลักสำหรับ comparison: project default 2.5/2/1.5% หรือ research 4/3/2% ที่อนุมัติแล้ว. รายงานอีก profile เป็น sensitivity แยก ไม่รวมผลเป็นตารางเดียวโดยไม่บอก MM.
- จำนวน candidate/parameter arms ต้องจำกัดและระบุเหตุผล. ถ้า admission หรือ sample ไม่พอ ให้รายงาน `INSUFFICIENT`/`NO_GO` แทนการเพิ่ม risk หรือขยาย grid ตามผล tail.

## Source pointers (ไม่ทำสำเนา)

- User-supplied central registry: `$HOME/Downloads/BotTradeGold_CENTRAL_STRATEGY_REGISTRY_2026-09-28.md` — proposal และ historical claims; ไม่ใช่คำสั่งให้ execute ทุก branch.
- Repo: `$HOME/.codex/.chatgpt-projects/g-p-6ab1758a2f8c8191977d3e419a8926ec/XAUUSD_Scalper_loop`.
- Current evidence: `docs/research/FINAL_EVIDENCE_MAP_2026-09-28.md`, `docs/research/FINAL_LOOP_PROGRESS_2026-09-27.md`, `docs/research/I037_MINIMUM_GEOMETRY_LEDGER_AUDIT_2026-09-28.md`, `docs/research/I038_INTERNAL_EVIDENCE_AUDIT_2026-09-28.md`.
- Runner and frozen controls: `scripts/research/final_loop/{engine.py,ticks.py,tick_loop.py,evidence_audit.py}`, `config/final_loop_gate.json`, `config/final_loop_protocol.json`; inspect `AGENTS.md`, Git status/diff before edits.
- External research: [NX3 paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6941458), [NX2 paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6650958). Paper results are external hypotheses, not BotTradeGold performance.

## Suggested skills

- `implement` (`$HOME/.agents/skills/implement/SKILL.md`) — ทำ NX3 v1 ตาม spec ที่ freeze, focused/full tests, review และ commit.
- `tdd` (`$HOME/.codex/skills/tdd/SKILL.md`) — ทดสอบ causal swing/signal timestamp, mirrored sides และ risk admission ก่อนแก้ source.
- `code-review` (`$HOME/.codex/skills/code-review/SKILL.md`) — ทบทวน Standards + Spec เฉพาะ diff ของรอบ NX3.

## Resume instruction สำหรับ agent รอบถัดไป

อ่าน `AGENTS.md`, registry และ final evidence map; ตรวจ HEAD/status. เสนอ NX3 v1 rule sheet ที่ mechanical และ candidate grid เล็ก พร้อม cost/admission preflight. เมื่อขอบเขตชัดเจน ให้ implement ใน research branch แยกจาก live execution, รันทดสอบ, audit ledgers, บันทึกทั้งผลลบ/บวก และคง `FINAL_NO_GO` จน gate จริงผ่าน. ห้ามอ่าน `.env`, ส่ง order หรือ promote production จากผลย้อนหลัง.
