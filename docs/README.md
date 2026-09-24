# 📚 ศูนย์รวมเอกสารระบบ XAUUSD Scalper & Copilot (`docs/`)

ยินดีต้อนรับสู่ศูนย์รวมเอกสารเชิงวิศวกรรมสำหรับโครงการ **XAUUSD Scalper & TradingView Copilot** จัดระเบียบเอกสารตามมาตรฐานความปลอดภัยทางการเงิน (Real-Money Financial Safety) และการแบ่งลำดับชั้นบริบท (Agent Context Architecture)

---

## 🏛️ โครงสร้างหมวดหมู่เอกสาร (Documentation Taxonomy)

```text
docs/
├── README.md               # 🌟 สารบัญหลักและแนวทางการเข้าถึงเอกสารทั้งหมด (Master Index)
│
├── plans/                  # 📋 แผนการพัฒนาและปรับปรุงระบบ (Improvement & Refactoring Plans)
│   ├── README.md           # สารบัญแผนงานและสถานะการดำเนินงาน
│   └── 2026-09-12-master-pro-v6-improvement-plan.md  # แผนปรับปรุง Master Pine Strategy
│
├── specs/                  # 📐 ข้อกำหนดเชิงสัญญาระบบและกลยุทธ์ (System Specifications & Contracts)
│   ├── README.md           # สารบัญข้อกำหนดและสัญญาเชิงปริมาณ
│   ├── gold-playbook-foundation.md                   # สเปกแม่บทกลยุทธ์ทองคำ SMC + TSS + GSS
│   └── 2026-09-12-master-pro-v6-net-expectancy.md    # สเปกวัดผล Net Expectancy & Strategy Simulation
│
├── reviews/                # 🔍 รายงานการตรวจสอบความถูกต้องและสคริปต์พิสูจน์ (Audits & Reproducers)
│   ├── README.md           # สารบัญรายงานการตรวจสอบและคู่มือรันสคริปต์
│   ├── 2026-09-07-gold-playbook-plan-review.md       # Audit แผนตั้งต้น Gold Playbook
│   ├── 2026-09-12-master-pro-v6-logic-review.md      # Audit ตรรกะ Master Pro v6 บน TradingView
│   ├── 2026-09-13-debug-ledger.md                    # บันทึกประวัติการดีบักและผลการทดลอง
│   ├── 2026-09-13-exness-demo-backtest-status.md     # Audit บัญชีทดสอบและกลไกบัญชี Backtest
│   ├── 2026-09-13-expansion-breakout-scrutinize.md   # Audit การตัดสิทธิ์ Sweep และ Body rules
│   ├── 2026-09-13-python-live-readiness.md           # Audit การ Refactor ประสิทธิภาพและความพร้อม Live
│   ├── reproduce_*.py                                # สคริปต์จำลองข้อผิดพลาดเพื่อพิสูจน์ก่อนแก้
│   └── *.json / *.txt                                # ข้อมูลผลลัพธ์และหลักฐานการทดสอบ
│
└── handoff/                # 🤝 เอกสารส่งมอบงานต่อเนื่องระหว่างเซสชัน (Engineering Handoffs)
    ├── README.md           # สารบัญประวัติการส่งมอบงาน
    ├── HANDOFF.md          # สรุปภาพรวมสถานะล่าสุด
    ├── 2026-09-07-smc-v2-backend-hardening.md        # ส่งมอบงาน Python Backend SMC v2 & MT5 Seams
    ├── 2026-09-12-tradingview-master-copilot-indicator.md # ส่งมอบงาน TradingView Master Copilot (Draft)
    └── 2026-09-12-tradingview-master-pro-v6-hardened.md   # ส่งมอบงาน TradingView Master Hardened
```

---

## 🧭 ตารางสารบัญรวมเอกสารทั้งระบบ (Master Document Register)

| หมวดหมู่ | วันที่ | เอกสาร | หัวข้อ / ขอบเขต | สถานะ |
| :--- | :--- | :--- | :--- | :--- |
| **Specs** | 2026-09-07 | [`specs/gold-playbook-foundation.md`](specs/gold-playbook-foundation.md) | SMC v2, Turtle Soup (TSS), Golden Zone (GSS), SMT, Judas Swing | 🟢 **In-Effect** |
| **Specs** | 2026-09-12 | [`specs/2026-09-12-master-pro-v6-net-expectancy.md`](specs/2026-09-12-master-pro-v6-net-expectancy.md) | สเปกจำลองคำสั่งซื้อขายจริงด้วย Strategy & วัด Net Expectancy | 🟢 **In-Effect** |
| **Plans** | 2026-09-12 | [`plans/2026-09-12-master-pro-v6-improvement-plan.md`](plans/2026-09-12-master-pro-v6-improvement-plan.md) | แผนปรับ `xauusd_master_pro_v6.pine` สู่ Strategy เดี่ยว | 🟡 **Pending Work** |
| **Reviews** | 2026-09-07 | [`reviews/gold-playbook-plan-review-2026-09-07.md`](reviews/gold-playbook-plan-review-2026-09-07.md) | ตรวจสอบแผนตั้งต้น Gold Playbook (Causal contracts & Win-rate) | 🔴 **Rework** |
| **Reviews** | 2026-09-12 | [`reviews/2026-09-12-master-pro-v6-logic-review.md`](reviews/2026-09-12-master-pro-v6-logic-review.md) | ตรวจสอบ 7 ข้อผิดพลาดตรรกะใน Master Pro v6 บน TradingView | 🔴 **Rework** |
| **Reviews** | 2026-09-13 | [`reviews/2026-09-13-expansion-breakout-scrutinize.md`](reviews/2026-09-13-expansion-breakout-scrutinize.md) | ตรวจสอบและแก้ไข Sweep Invalidation เมื่อเกิด Breakout | 🟢 **Resolved** |
| **Reviews** | 2026-09-13 | [`reviews/2026-09-13-exness-demo-backtest-status.md`](reviews/2026-09-13-exness-demo-backtest-status.md) | ตรวจสอบการเชื่อมต่อ Exness Demo และสูตร Cash Conservation | 🟡 **Blocked for Live** |
| **Reviews** | 2026-09-13 | [`reviews/2026-09-13-python-live-readiness.md`](reviews/2026-09-13-python-live-readiness.md) | วัดผล Refactor สปีด Python (เร็วขึ้น 2.8x-4.1x) และความพร้อม Live | 🟢 **Code Verified**<br/>🔴 **Hold Live Money** |
| **Reviews** | 2026-09-13 | [`reviews/2026-09-13-debug-ledger.md`](reviews/2026-09-13-debug-ledger.md) | บันทึกประวัติการทดลองและการหักล้างสมมติฐานทางเทคนิค | 📝 **Audit Trail** |
| **Handoff** | 2026-09-12 | [`handoff/2026-09-12-tradingview-master-pro-v6-hardened.md`](handoff/2026-09-12-tradingview-master-pro-v6-hardened.md) | ส่งมอบสคริปต์ TradingView Copilot พร้อมระบบ Hardening | 🟢 **Delivered** |
| **Handoff** | 2026-09-12 | [`handoff/2026-09-12-tradingview-master-copilot-indicator.md`](handoff/2026-09-12-tradingview-master-copilot-indicator.md) | สคริปต์ TradingView รุ่นร่างเริ่มต้นก่อน Hardening | ⚪ **Superseded** |
| **Handoff** | 2026-09-07 | [`handoff/2026-09-07-smc-v2-backend-hardening.md`](handoff/2026-09-07-smc-v2-backend-hardening.md) | ตรรกะ SMC v2 ใน Python และ 6 Blockers ก่อนต่อ Live MT5 | 🟡 **Pending MT5 Fixes** |

---

## 🎯 เส้นทางการศึกษาเอกสารตามบทบาท (Context Routing by Role)

### 1. นักพัฒนา Pine Script / TradingView Copilot
1. ศึกษาข้อกำหนดแม่บทใน [`specs/gold-playbook-foundation.md`](specs/gold-playbook-foundation.md)
2. ศึกษาข้อกำหนดการจำลองกลยุทธ์ใน [`specs/2026-09-12-master-pro-v6-net-expectancy.md`](specs/2026-09-12-master-pro-v6-net-expectancy.md)
3. ตรวจสอบข้อผิดพลาดที่ต้องระวังจาก [`reviews/2026-09-12-master-pro-v6-logic-review.md`](reviews/2026-09-12-master-pro-v6-logic-review.md)
4. ปฏิบัติตามแผนงานใน [`plans/2026-09-12-master-pro-v6-improvement-plan.md`](plans/2026-09-12-master-pro-v6-improvement-plan.md)
5. ตรวจสอบโค้ดจริงที่ [`tradingview/xauusd_master_pro_v6.pine`](../tradingview/xauusd_master_pro_v6.pine)

### 2. นักพัฒนา Python / MT5 Automated Execution
1. ศึกษาข้อกำหนดกลยุทธ์ใน [`specs/gold-playbook-foundation.md`](specs/gold-playbook-foundation.md)
2. ตรวจสอบ 6 ประเด็นคั่งค้างก่อนต่อ Live ใน [`handoff/2026-09-07-smc-v2-backend-hardening.md`](handoff/2026-09-07-smc-v2-backend-hardening.md)
3. ศึกษารายงานความพร้อมระบบใน [`reviews/2026-09-13-python-live-readiness.md`](reviews/2026-09-13-python-live-readiness.md)
4. ศึกษากลไกบัญชีและการทดสอบใน [`reviews/2026-09-13-exness-demo-backtest-status.md`](reviews/2026-09-13-exness-demo-backtest-status.md)
5. รันชุดทดสอบความถูกต้อง: `python3 -m unittest discover -s tests`

### 3. AI Coding Agent / Pair Programmer
- **Tier 1 (Always Load):** [`AGENTS.md`](../AGENTS.md) และ [`docs/README.md`](README.md)
- **Tier 2 (Capabilities & Contracts):** เอกสารใน [`docs/specs/`](specs/README.md)
- **Tier 3 (Active Task Context):** เอกสารใน [`docs/plans/`](plans/README.md) และ [`docs/handoff/`](handoff/README.md)
- **Tier 4 (Audit & History):** เอกสารใน [`docs/reviews/`](reviews/README.md)
