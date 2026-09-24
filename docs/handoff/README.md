# 📚 Engineering Handoffs Catalog (`docs/handoff/`)

สารบัญเอกสารส่งมอบงาน (Engineering Handoff Documents) สำหรับโปรเจกต์ **XAUUSD Scalper & TradingView Copilot** จัดเรียงตามลำดับเวลาและหัวข้อระบบอย่างชัดเจน

---

## 📁 สารบัญเอกสาร (Handoff Index)

| วันที่ | ชื่อไฟล์ (Descriptive Filename) | ขอบเขตของระบบ (System Scope) | สถานะ (Status) |
| :--- | :--- | :--- | :--- |
| **2026-09-12** | [`2026-09-12-tradingview-master-pro-v6-hardened.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-12-tradingview-master-pro-v6-hardened.md) | **Production-Hardened Master Copilot (`xauusd_master_pro_v6.pine`)**<br/>• แก้ไข 5 จุดบกพร่องวิกฤต: ขจัด Repaint H1, เพิ่ม Limit 50% FVG พร้อม TTL 4 บาร์<br/>• ขยาย Max SL Cap $25.00 และ Reject แทน Clamp, ตรวจสอบทิศทางสวิง GSS OTE<br/>• เพิ่ม Multi-Session London H/L, Two-Tier 1.0R/2.5R, และ Full Lifecycle Alerts | 🟢 **Production Hardened & Financial Safety Verified** |
| **2026-09-12** | [`2026-09-12-tradingview-master-copilot-indicator.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-12-tradingview-master-copilot-indicator.md) | **TradingView Master Copilot Indicator (`xauusd_master_pro_v6.pine`)**<br/>• ร่างเริ่มต้นก่อนการ Hardening (Superceded by Hardened Release)<br/>• สถาปัตยกรรม Two-Tier Scale-Out (1.5R/3.0R) และ Dual Alerts (Card + JSON) | ⚪ **Initial Draft History** |
| **2026-09-14** | [`2026-09-14-live-execution-bridge-and-risk-shield.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-14-live-execution-bridge-and-risk-shield.md) | **Live Execution Bridge & Async Risk Shield (`scripts/webhook_bridge.py`)**<br/>• FastAPI bridge, Two-tier idempotency, Dynamic equity risk sizing<br/>• Async MT5 offloading, Zero phantom alerts | 🟢 **Engineered & Fully Tested** |
| **2026-09-15** | [`2026-09-15-demo-auto-order-remediation.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-15-demo-auto-order-remediation.md) | **Exness Demo Auto-Order Remediation & Scrutinize Review**<br/>• ผล Scrutinize แผน Demo Auto-Order (Verdict: REWORK)<br/>• 1 Blocker (ขาด Reconciler daemon), 2 Major (Schema break, Capital sizing)<br/>• 1 Failing test ใน suite เดิม พร้อม Action Plan 5 ขั้นตอน | 🟡 **Plan Rework in Progress** |

---

## 🧭 คำแนะนำสำหรับ Agent หรือ Developer ที่เข้ามาทำงานต่อ

1. **หากต้องการทำงานฝั่ง TradingView / Indicator / Alerts**:
   👉 อ่าน [`2026-09-12-tradingview-master-copilot-indicator.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-12-tradingview-master-copilot-indicator.md) และเปิดดูสคริปต์มาสเตอร์ที่ [`tradingview/xauusd_master_pro_v6.pine`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/tradingview/xauusd_master_pro_v6.pine)

2. **หากต้องการทำงานฝั่ง Python Bot / MT5 Automated Execution / Cloud VM**:
   👉 อ่าน [`2026-09-07-smc-v2-backend-hardening.md`](file:///Users/nopparuj/my-agents/XAUUSD_Scalper/docs/handoff/2026-09-07-smc-v2-backend-hardening.md) และเริ่มแก้ 6 Blocker ใน Section 2 ก่อน Deploy ไปยัง Oracle Cloud ARM64

3. **หากต้องการเชื่อมต่อ TradingView Alert เข้ากับ MT5 Bot**:
   👉 ใช้ Webhook Payload โครงสร้าง JSON ที่ระบุใน `xauusd_master_pro_v6.pine` เพื่อส่งเข้า Webhook Receiver (FastAPI) ใน Python
