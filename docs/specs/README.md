# 📐 System Specifications (`docs/specs/`)

โฟลเดอร์นี้รวบรวมข้อกำหนดทางเทคนิค (Specifications), กฎเกณฑ์เชิงคณิตศาสตร์และกลยุทธ์ (Quantitative Rules), และสัญญาข้อมูล (Data Contracts) ที่เป็น **Source of Truth** ของระบบ

---

## 📁 สารบัญข้อกำหนดระบบ (Specifications Catalog)

| วันที่ | ข้อกำหนด (Specification) | ขอบเขตของระบบ (System Scope) | สถานะ (Status) |
| :--- | :--- | :--- | :--- |
| **2026-09-07** | [`gold-playbook-foundation.md`](gold-playbook-foundation.md) | **Gold Playbook Foundation Specification**<br/>• คู่มือและข้อกำหนดระดับสถาบันสำหรับ XAUUSD M5/M15<br/>• นิยามกลยุทธ์หลัก 3 ชุด: SMC v2, Turtle Soup (TSS), และ Golden Zone OTE (GSS)<br/>• SMT Divergence (เทียบ DXY), Multi-session Liquidity (Asian, London, NY), และ Judas Swing<br/>• กฎการบริหารความเสี่ยงและโครงสร้างข้อมูลพื้นฐาน | 🟢 **Foundational Playbook (Active Contract)** |
| **2026-09-12** | [`2026-09-12-master-pro-v6-net-expectancy.md`](2026-09-12-master-pro-v6-net-expectancy.md) | **Master Pro v6 — Simulation & Net Expectancy Specification**<br/>• ข้อกำหนดการจำลองการส่งคำสั่งจริงด้วย Native TradingView `strategy()`<br/>• ขจัด Synthetic Fill และการ Repaint บน High/Low<br/>• สเปก Two-Tier Scale-out: 1.0R TP1 (ปิด 50% เลื่อน BE) + 2.5R Runner TP2<br/>• Risk Gate: Max SL Cap $25.00 (Reject ไม่บีบ SL) และ Daily Loss Circuit Breakers<br/>• สัญญาส่งสัญญาณแจ้งเตือน Alert v2 JSON Structure | 🟢 **Active Engineering Spec** |
| **2026-09-14** | [`2026-09-14-live-execution-bridge-and-risk-shield-spec.md`](2026-09-14-live-execution-bridge-and-risk-shield-spec.md) | **Live Execution Bridge & Real-Money Risk Shield Specification (Phase 2 & 3)**<br/>• สเปก Webhook Bridge (`POST /webhook/tradingview`) เชื่อม TradingView สู่ MT5<br/>• ถอดรหัส Event: SETUP_PENDING, ORDER_FILLED, TP1_HIT_MOVE_BE, ORDER_CANCELED, TRADE_CLOSED<br/>• ผูกติด Deterministic `order_id` และป้องกัน Idempotency<br/>• ผสาน Risk Shield: Dynamic Lot Sizing, Small-Account Gate (ADR-020), Daily Circuit Breaker (ADR-011), และ Rollover Flat (ADR-007) | 🟢 **Ready For Agent (`ready-for-agent`)** |
| **2026-09-16** | [`xauusd-setup-experiment-v1.md`](xauusd-setup-experiment-v1.md) | **XAUUSD Setup Experiment v1 (S1–S4 narrative)** — Manual Signal Indicator research boundary; Legacy vs Controlled Baseline | 🟢 **Active research contract** |
| **2026-09-16** | [`xauusd-s1-s4-mechanical-v1.md`](xauusd-s1-s4-mechanical-v1.md) | **S1–S4 mechanical tables + synthetic examples** (issue #3) | 🟢 **Documentation complete** |
| **2026-09-16** | [`xauusd-s1-s4-research-handoff-v1.md`](xauusd-s1-s4-research-handoff-v1.md) | **Research readiness & implementation handoff** (issue #4) | 🟡 **Gates open — not experiment-ready** |

---

## 🧭 ความสัมพันธ์กับโฟลเดอร์อื่น

- **Root `/specs/`:** ข้อกำหนดเริ่มต้นของระบบรุ่นแรก (`specs/xauusd_system_v1_spec.md`)
- **`docs/plans/`:** แผนการพัฒนาที่นำมาแปลงเป็นสเปกในโฟลเดอร์นี้
- **`docs/reviews/`:** เอกสาร Audit ตรวจสอบว่าโค้ดจริงทำงานตรงตามข้อกำหนดในโฟลเดอร์นี้หรือไม่
