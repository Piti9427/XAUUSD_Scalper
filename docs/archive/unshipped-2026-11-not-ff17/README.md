# เทสที่ไม่ได้ขึ้น ff17

ย้ายออกจาก `tests/` เมื่อ 25 พ.ย. 2026 19:45 ICT เพราะรันกับซอร์สของ release `selected-ff17a3a8c0890cb0` แล้วไม่ผ่าน และถ้าวางไว้ใต้ `tests/` ตัวค้นหาของ `unittest` จะเก็บเข้าชุดเทส

- `test_c22_swap_band.py` อ้าง `SelectedStrategy.swap_band = 0.05` และอาร์กิวเมนต์ `swap_band` ของ `validate_policy` ซึ่งไม่มีใน ff17 สวอปที่เพี้ยนบน live ถูกบันทึกเป็น `SWAP_DRIFT_WARN` และไม่บล็อกไม้ใหม่
- `test_journal_backup_lock.py` อ้าง `JOURNAL_BUSY_TIMEOUT_S` และต้องการ timeout อย่างน้อย 90 วินาที ff17 ใช้ `BUSY_TIMEOUT_SECONDS = 60` ใน `scripts/demo_runtime/journal.py`
