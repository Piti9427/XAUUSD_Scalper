# 🔍 Audits, Reviews & Reproducers (`docs/reviews/`)

โฟลเดอร์นี้รวบรวมรายงานการตรวจสอบโค้ดอย่างเข้มงวด (Rigorous Code & Logic Audits), บันทึกการแก้บัก (Debug Ledgers), สคริปต์จำลองข้อผิดพลาดเพื่อการพิสูจน์ (Reproduction Scripts), และหลักฐานการวัดผล (Verification Artifacts) เพื่อความปลอดภัยของเงินทุนจริง (Real-Money Financial Safety)

---

## 📁 สารบัญรายงานการตรวจสอบ (Audit Reviews)

| วันที่ | รายงาน (Review Document) | ขอบเขตการตรวจสอบ (Audit Scope) | ผลการตรวจ (Verdict) |
| :--- | :--- | :--- | :--- |
| **2026-09-07** | [`gold-playbook-plan-review-2026-09-07.md`](gold-playbook-plan-review-2026-09-07.md) | **Gold Playbook Plan Review**<br/>• ตรวจสอบแผนตั้งต้น Gold Playbook เพื่อประเมินความพร้อมก่อนใช้เงินจริง<br/>• พบปัญหา Closed-bar replay ขาด Causal contract และนิยาม Win-rate ไม่รัดกุม | 🔴 **REWORK**<br/>*(ต้องนิยาม Causal Replay & Net Expectancy ก่อน)* |
| **2026-09-12** | [`2026-09-12-master-pro-v6-logic-review.md`](2026-09-12-master-pro-v6-logic-review.md) | **Master Pro v6 Logic & Financial Safety Audit**<br/>• ตรวจสอบสคริปต์ TradingView [`xauusd_master_pro_v6.pine`](../../tradingview/xauusd_master_pro_v6.pine)<br/>• พิสูจน์ 7 Counterexamples: Pre-entry TP, SL ชนก่อนแต่บันทึก TP, ยืมจุดเลื่อน BE ย้อนหลัง, SMT ผิดช่วงเวลา | 🔴 **REWORK**<br/>*(ห้ามใช้เงินจริงจนกว่าจะปรับเป็น Strategy ตามสเปก)* |
| **2026-09-13** | [`2026-09-13-expansion-breakout-scrutinize.md`](2026-09-13-expansion-breakout-scrutinize.md) | **Expansion Breakout Review & Sweep Invalidation**<br/>• ตรวจสอบตรรกะ Cross-level sweep suppression และ Body-close regression<br/>• ยืนยันการตัดเฉพาะเลเวลที่ทะลุจริง ไม่ให้กระทบ Sweep เลเวลอื่น | 🟢 **RESOLVED**<br/>*(แก้ไขใน Python Detection ผ่านชุดทดสอบ 100%)* |
| **2026-09-13** | [`2026-09-13-exness-demo-backtest-status.md`](2026-09-13-exness-demo-backtest-status.md) | **Exness Demo Web & Backtester Accounting Audit**<br/>• ตรวจสอบสภาพแวดล้อม Exness Demo Pro และแก้ไขสูตรคำนวณเงินสดจริง<br/>• แก้ปัญหา Cash conservation, Same-bar closure, และ H1/Fractal causality | 🟡 **BLOCKED for Live Money**<br/>*(ยังขาด Historic Data Export จาก Broker จริง)* |
| **2026-09-13** | [`2026-09-13-python-live-readiness.md`](2026-09-13-python-live-readiness.md) | **Python Refactor & Exness Live Readiness Audit**<br/>• วัดผลประสิทธิภาพ Refactor SMC Detection (เร็วขึ้น 2.86x – 4.16x)<br/>• ตรวจสอบความพร้อมของ MT5 Engine ก่อนต่อพอร์ตจริง | 🟢 **Refactor Verified**<br/>🔴 **NOT Ready for Live Money** |
| **2026-09-13** | [`2026-09-13-debug-ledger.md`](2026-09-13-debug-ledger.md) | **Engineering Debug Ledger**<br/>• บันทึกตารางการทดลอง, สมมติฐาน, การหักล้าง (Disproofs), และผลลัพธ์ของแต่ละ Fix | 📝 **Audit Trail Ledger** |

---

## 🧪 สคริปต์จำลองข้อผิดพลาดและการพิสูจน์ (Reproduction Scripts)

ตามหลักวิศวกรรมการเงินขั้นสูง **"Reproduce First before modifying code"** โค้ดทดสอบเหล่านี้ใช้พิสูจน์ความบกพร่องทางตรรกะ:

| สคริปต์ | วัตถุประสงค์ | คำสั่งสำหรับรัน (Execution Command) |
| :--- | :--- | :--- |
| [`reproduce_master_pro_v6_review.py`](reproduce_master_pro_v6_review.py) | พิสูจน์ 7 Counterexamples ของตรรกะ TradingView Master Pro v6 | `python3 docs/reviews/reproduce_master_pro_v6_review.py` |
| [`reproduce_expansion_breakout_review.py`](reproduce_expansion_breakout_review.py) | ตรวจสอบการ Invalidate Sweep เลเวลต่าง ๆ เมื่อเกิด Breakout | `python3 docs/reviews/reproduce_expansion_breakout_review.py` |
| [`reproduce_backtest_readiness.py`](reproduce_backtest_readiness.py) | ตรวจสอบข้อผิดพลาดทางบัญชี Cash Accounting 4 จุดใน Backtester เก่า | `python3 docs/reviews/reproduce_backtest_readiness.py` |
| [`compare_python_refactor.py`](compare_python_refactor.py) | วัดความเร็วและ Hash Output เทียบก่อน/หลังการ Refactor ตรวจจับสัญญาณ | `python3 docs/reviews/compare_python_refactor.py --baseline <baseline_path> --output <json_out>` |

---

## 📊 หลักฐานผลลัพธ์การวัดผล (Verification Data Fixtures)

- [`2026-09-13-python-refactor-results.json`](2026-09-13-python-refactor-results.json): บันทึก SHA-256 Hashes, ตารางเวลาประมวลผล (Median 3 runs), และผลลัพธ์ทุกสัญญาณเทรด ยืนยันผลตรวจจับตรงกัน 100% บิตต่อบิต
- [`2026-09-13-corrected-proxy-backtest.txt`](2026-09-13-corrected-proxy-backtest.txt): บันทึกผลการรัน Backtest ด้วยกลไกบัญชีที่ถูกต้องบนชุดข้อมูล Proxy M15
