# 05 Release ที่ทำวันที่ 24 พ.ย. 2026

บอท C22 Selected บน Exness MT5 demo (Oracle VM) เท่านั้น ไม่มีเงินจริง เวลาในเอกสารนี้เป็นเวลาไทย (ICT) ถ้าไม่ระบุอย่างอื่น
ไม่มีความลับ (credential, key, webhook secret) ในเอกสารนี้

## สรุป

| Release | สถานะ | Contract / กลยุทธ์ | Review |
|---|---|---|---|
| `selected-6d7b9c468a0947e2` | ตัวก่อนหน้า (เป้า rollback ของ swap-warn) | 26b8bcd69e043653 | renewal v5 |
| `selected-88a0a196a71f16c7` (SWAP-WARN) | **กำลังรันจริง** ตั้งแต่ 24 พ.ย. 12:46 | 26b8bcd69e043653 (26b8 เดิม) | code-only review |
| `selected-ff17a3a8c0890cb0` (F2+F3) | **วางไว้บน VM แล้ว ยังไม่ deploy** | 7fe09f7246068bc9 (26b8 + F2 + F3) | strategy-change review |

Review/cost policy ปัจจุบันหมดอายุ 2026-12-01 03:04:13 UTC = 1 ธ.ค. 10:04 ICT ต้องต่ออายุก่อนเวลานี้ (ต้องได้ข้อความอนุมัติจากเจ้าของก่อน)

## 1) SWAP-WARN `selected-88a0a196a71f16c7` (deploy แล้ว)
- ที่มา: t165u–t166u ผู้ใช้กังวลว่าการเทียบ swap แบบตายตัว (cost_spec_mismatch) จะบล็อกการเข้า order อนุมัติ deploy ผ่าน widget "อนุมัติ deploy release swap ใหม่วันนี้"
- release_hash `88a0a196a71f16c734775aabd2e04d52c64561998104b8562758383d507ca414` config เดิม (ไม่เปลี่ยน)
- ไฟล์ที่เปลี่ยน: `scripts/demo_runtime/costs.py`, `admission.py`, `runner.py` (ไม่แตะ source ที่ถูก pin)
- พฤติกรรมใหม่: ถ้า swap จาก broker ไม่ตรงกับค่าที่บันทึก จะเขียนคำเตือน `SWAP_DRIFT_WARN` ลง journal แต่ยังเข้า order ได้ ส่วนการอ่าน swap ไม่ได้ หรือ spread / ค่าคอม / สเปกสัญญาเปลี่ยน ยังบล็อกเหมือนเดิม กฎ risk 10%, daily stop 10%, cooldown ไม่เปลี่ยน
- เทสต์: ไม่มีเทสต์ที่เคยผ่านแล้วพัง เทสต์ใหม่ 16 ตัวผ่านทั้งหมด
- Deploy: 24 พ.ย. 2026 12:46 ICT (go-deploy timestamp `20261124T054615Z`) บอทหยุดประมาณ 10 วินาที ไม่ต้อง rollback swap ที่อ่านได้ −894.4 ตรงกับค่าที่บันทึก
- Kit บน VM: `~/c22-demo/state/staging-swapwarn-20261124/` (สำเนาบน box: `/workspace/c22-swap-release/`)
- รายงานสรุป 07:00 และ 21:00 รวมคำเตือน SWAP_DRIFT_WARN แล้ว
- Rollback (กลับไป `selected-6d7b9c468a0947e2` พร้อม review/policy pointer ที่บันทึกไว้ก่อนสลับ; ควรทำตอนไม่มี position และนอกช่วง 04:45–06:10 / 06:45–07:15 ICT; ไม่ปิดหรือแก้ position):
  ```bash
  bash ~/c22-demo/state/staging-swapwarn-20261124/rollback.sh 20261124T054615Z
  ```
  หมายเหตุ: บน 6d7b การเทียบ swap แบบแคบกลับมา อาจโดน cost_spec_mismatch บล็อกอีก
- ต่ออายุครั้งหน้าถ้ายังอยู่บน 88a0: ใช้ kit `staging-swapwarn-20261124/renew-v6/`

## 2) F2+F3 `selected-ff17a3a8c0890cb0` (staged ยังไม่ deploy)
- ที่มา: widget "สร้าง release F2 + แพ้วันละ 1 ไม้ ใช้จริงเลย ส่งให้อนุมัติก่อน deploy" — **การ deploy ต้องได้อนุมัติจากเจ้าของแยกอีกครั้ง** (ข้อความ verbatim ใส่ไฟล์ใหม่)
- release_hash `ff17a3a8c0890cb0b2f8e8d7512bf554de4fce9a52bd0f7edf6ab7d80e83bb1a`, config `d1607f04d6e9c06af7f2edf4aa1f23a9c386aeb8131ec6bebfc9b7ddb3fca5ad`, candidate/contract `7fe09f7246068bc9` (base 88a0) SNAPSHOT และ MAGIC ไม่เปลี่ยน
- ไฟล์ที่เปลี่ยน: `scripts/c22_selected/strategy.py`, `config/c22-selected-demo.json` (+ unit path / manifest / release.sha256)
  - **F2:** ไม้ใหม่ (BUY/SELL) จะถูกข้าม ถ้า direction × (close − H4 EMA200 ที่ปิดแล้ว) / ATR14(M15) < 10.0 (contract field `min_macro_distance_atr=10.0`) เหตุผล WAIT `macro_distance_too_small` ถ้าคำนวณระยะไม่ได้จะไม่เข้า (fail closed) ไม่แตะการจัดการ position ที่เปิดอยู่
  - **F3:** CONTRACT `max_daily_losses` 2 → 1 **นับไม้แพ้ตามวัน UTC ของเวลาปิด** (reset 00:00 UTC = 07:00 ICT) คิดจาก net รวม swap/ค่าคอม BLOCKED `max_daily_losses`
  - ไม่เปลี่ยน: risk cap 10%, daily stop 10%, cooldown 2 แท่ง, SL/TP/BE, lot 0.01, validator, cost policy, demo only
- เทสต์: ไม่มีเทสต์ที่เคยผ่านแล้วพัง เทสต์ใหม่ 15 ตัวผ่าน parity กับ backtest ตรงทุกไม้ (OPT 233 ไม้ +1608.78 DD 224.89, HOLD 80 ไม้ +290.19 DD 80.57)
- Review type: **strategy-change review** (`build_strategy_change_review.py`) เพราะ config hash และ contract_id เปลี่ยน ผูกกับ F2 research parity (parity-result.json PASS) และยอมเฉพาะ config diff ข้างต้น validator ของ live ไม่เปลี่ยน cost policy pointer ไม่เปลี่ยน
- Staging บน VM: `~/c22-demo/state/staging-f2-20261124/` (ยังไม่ได้รันอะไร) สำเนาบน box: `/workspace/c22-f2-release/kit/`
- ขั้นตอน deploy (หลังเจ้าของอนุมัติ; ต้องไม่มี position; นอก 04:45–06:10 และ 06:45–07:15 ICT; เริ่ม 1–4 นาทีหลังแท่ง M15 ปิด):
  ```bash
  cd ~/c22-demo/state/staging-f2-20261124
  bash prepare-release.sh                       # สร้าง releases/selected-ff17a3a8c0890cb0 ไม่กระทบ service
  # ใส่ข้อความอนุมัติ verbatim ของเจ้าของใน owner-deploy-approval-YYYYMMDD.txt แล้ว
  bash go-deploy.sh ff17a3a8c0890cb0 $PWD/expected-cohort.json $PWD/owner-deploy-approval-YYYYMMDD.txt
  ```
  ถ้าล้มเหลวหลังหยุด sender สคริปต์จะคืน unit + review pointer และสตาร์ทกลับบน 88a0 ให้เอง
- Rollback (กลับ 88a0 + review/policy pointer ที่บันทึกไว้; T = timestamp จาก `go-<T>.log`):
  ```bash
  bash ~/c22-demo/state/staging-f2-20261124/rollback.sh <T>
  ```
  บน 88a0 กฎ 26b8 กลับมา (ไม่มี F2, แพ้ได้วันละ 2) ถ้าต่ออายุบน F2 ไปแล้ว review ของ 88a0 อาจหมดอายุ ต้องต่ออายุด้วย renew-v6 ของ 88a0
- หลัง deploy ครั้งแรก: `history_seed_status binding_mismatch` และบอทโหลด M1 100k แท่งจาก broker ใหม่ (ปกติ เกิดครั้งเดียว)
- ต่ออายุ review ครั้งหน้า (ก่อน 1 ธ.ค. 10:04 ICT) ถ้า F2 รันอยู่ ใช้ kit **renew-v6-f2**:
  ```bash
  bash renew-v6-f2/v6/go-renew-v6.sh renew ff17a3a8c0890cb0 $PWD/renew-v6-f2/expected-cohort.json OWNER_VERBATIM.txt
  ```
  ต้องมีข้อความอนุมัติของเจ้าของในไฟล์ และ official-source review ใหม่ใน `renew-v6-f2/sources.json` (ไม่เกิน 24 ชม.) dry-run บน box: VALID
- ข้อสังเกตสำหรับ journal: WAIT `macro_distance_too_small` และ BLOCKED `max_daily_losses` เป็นการกันปกติ ไม่ใช่ incident

## เงื่อนไขที่ยังคงใช้
Demo เท่านั้น / ไม่ปิด position โดยไม่ได้รับอนุญาต / deploy เฉพาะตอนไม่มี position และนอกช่วงห้าม / เปลี่ยนกลยุทธ์ live ต้องมี release + review + อนุมัติ / อยู่ใน Oracle free tier
