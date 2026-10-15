# 📋 Strategy & System Improvement Plans (`docs/plans/`)

โฟลเดอร์นี้รวบรวมแผนการปรับปรุงระบบ (Improvement Plans), แผนการรีแฟกเตอร์ (Refactoring Plans) และแผนเชิงกลยุทธ์สำหรับระบบ **XAUUSD Scalper & TradingView Copilot**

---

## 📁 สารบัญแผนงาน (Plans Catalog)

| วันที่ | แผนงาน (Plan Document) | ขอบเขตของระบบ (System Scope) | สถานะ (Status) | Primary Artifact |
| :--- | :--- | :--- | :--- | :--- |
| **2026-09-12** | [`2026-09-12-master-pro-v6-improvement-plan.md`](2026-09-12-master-pro-v6-improvement-plan.md) | **ปรับ Master Pine ให้ทดสอบกำไรสุทธิได้ตรงกับการใช้งานจริง**<br/>• ปรับ `xauusd_master_pro_v6.pine` จาก `indicator()` สู่ `strategy()` เดี่ยว<br/>• กำจัด Synthetic Fill เสมือน และผูก SMC Lifecycle (Sweep → MSS → 50% FVG Limit)<br/>• Two-Tier Scale-out (1.0R TP1 / 2.5R Runner) พร้อม Risk Protection $25.00 Max Cap | 🟡 **Pending Implementation**<br/>*(ตกลงแผนแล้ว รอเริ่ม Implement ตามสเปก)* | [`tradingview/xauusd_master_pro_v6.pine`](../../tradingview/xauusd_master_pro_v6.pine) |

---

## 🧭 ความสัมพันธ์กับโฟลเดอร์อื่น

- **Root `/plans/`:** เป็นแผนงานตั้งต้นโครงสร้างระบบชุดแรก (Legacy Architectural Roadmap v1: ADRs, SOTA Architecture, Initial Tickets)
- **`docs/plans/`:** เป็นแผนเชิงปฏิบัติการสำหรับระบบเวอร์ชันปัจจุบัน (Active Tactical & Strategy Improvement Plans)
- **`docs/specs/`:** ข้อกำหนดทางเทคนิคและสัญญาระบบ (Specifications) ที่แปลงมาจากแผนเหล่านี้เพื่อใช้อ้างอิงในการเขียนโค้ด
- **`docs/reviews/`:** การตรวจสอบ (Audit Reviews) ก่อนและหลังการลงมือทำตามแผน
