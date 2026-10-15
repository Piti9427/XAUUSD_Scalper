.PHONY: all check compile deps lint format format-check test clean help guide \
	bot-status bot-once bot-run bot-execute bot-start bot-stop

PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else which python3; fi)
RUFF ?= $(shell if [ -f .venv/bin/ruff ]; then echo .venv/bin/ruff; else which ruff || echo "$(PYTHON) -m ruff"; fi)
BOT_NAME ?= c22h4
BOT_PID = data/$(BOT_NAME)-demo-watch.pid
BOT_LOG = data/$(BOT_NAME)-demo-watch.log
BOT_CACHE_ARGS = $(if $(filter c22h4,$(BOT_NAME)),--cache-output data/c22h4-shadow-bars.csv,)

all: check

help:
	@echo "Available commands:"
	@echo "  make check        - Run all checks in order (compile, deps, lint, format-check, test)"
	@echo "  make compile      - Check bytecode syntax compilation"
	@echo "  make deps         - Check dependency integrity"
	@echo "  make lint         - Run ruff linter check"
	@echo "  make format-check - Check code formatting without modifying"
	@echo "  make format       - Auto-format code with ruff"
	@echo "  make test         - Run unit tests"
	@echo "  make clean        - Clean cache artifacts"
	@echo "  make guide        - How to run, stop, and check the Demo bot"
	@echo "  make bot-status   - Journal plus local watcher process"
	@echo "  make bot-once     - One read-only cycle, no order_send"
	@echo "  make bot-run      - Foreground Demo shadow watcher (Ctrl-C stops)"
	@echo "  make bot-execute  - Foreground Demo watcher that can send orders"
	@echo "  make bot-start    - Background Demo shadow watcher, one writer"
	@echo "  make bot-stop     - Stop watcher only; broker SL/TP stay"

check: compile deps lint format-check test
	@echo "All checks passed successfully!"

compile:
	@echo "[1/5] Checking syntax compilation..."
	$(PYTHON) -m compileall -q scripts tests main.py smc_main.py test_mt5.py

deps:
	@echo "[2/5] Checking dependencies..."
	$(PYTHON) -m pip check

lint:
	@echo "[3/5] Running linter..."
	$(RUFF) check --no-cache .

format-check:
	@echo "[4/5] Checking format..."
	$(RUFF) format --check --no-cache .

format:
	$(RUFF) format --no-cache .
	$(RUFF) check --fix --no-cache .

test:
	@echo "[5/5] Running unit tests..."
	$(PYTHON) -m unittest discover -s tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

guide:
	@echo "C22 + H4 EMA200 Demo — วิธีใช้"
	@echo "ส่งออเดอร์ได้หลัง cutover gates ผ่านและ owner อนุมัติเท่านั้น. ดู docs/ops/c22h4-demo.md."
	@echo "bot-run/bot-start เริ่ม shadow โดยไม่ส่งออเดอร์. ส่งออเดอร์ใช้ make bot-execute หรือ make c22h4-run."
	@echo "trial30-status/once/run/start/stop เก็บไว้สำหรับ rollback."
	@echo ""
	@echo "รันจากโฟลเดอร์โปรเจกต์. รหัสอยู่ใน .env. MetaTrader 5 ต้องเปิดอยู่."
	@echo "บัญชีนี้มี watcher ได้ตัวเดียว. อย่าสั่ง bot-run ซ้อนกับ bot-start."
	@echo "ปิด Mac แล้วโปรเซสหยุด. เปิดเครื่องใหม่ต้องสั่งรันใหม่."
	@echo "หยุด watcher ไม่ได้ปิด SL/TP ที่โบรกเกอร์ถืออยู่แล้ว."
	@echo ""
	@echo "บอท"
	@echo "  make bot-status   ดู journal กับโปรเซส. ไม่ติดต่อโบรกเกอร์."
	@echo "  make bot-once     หนึ่งรอบแบบอ่านอย่างเดียว. ไม่ส่งออเดอร์."
	@echo "  make bot-run      เฝ้าแบบ shadow ไม่ส่งออเดอร์. ค้างที่เทอร์มินัล. Ctrl-C เพื่อหยุด."
	@echo "  make bot-execute  เฝ้าแบบส่งออเดอร์บน Demo. ค้างที่เทอร์มินัล. Ctrl-C เพื่อหยุด."
	@echo "  make bot-start    เหมือน bot-run แต่ไปรันพื้นหลัง. เขียน $(BOT_PID) และ $(BOT_LOG)."
	@echo "  make bot-stop     ส่ง SIGINT ให้ watcher. ไม่ปิดแอป MetaTrader."
	@echo ""
	@echo "ลำดับที่ใช่บ่อย"
	@echo "  make bot-status"
	@echo "  make bot-execute  # ส่งออเดอร์บน Demo เมื่อมีสัญญาณ"
	@echo "  make bot-status"
	@echo "  make bot-stop"
	@echo ""
	@echo "ตรวจโค้ด"
	@echo "  make help         รายการคำสั่งสั้น"
	@echo "  make check        compile, deps, lint, format-check, test"
	@echo "  make test         เฉพาะ unit test"

bot-status:
	$(PYTHON) -m scripts.ops.$(BOT_NAME)_status --brief

bot-once:
	$(PYTHON) -m scripts.ops.run_$(BOT_NAME)_wine --once

bot-run:
	@mode=shadow; execute=; \
	if [ "$$MT5_ENABLE_DEMO_ORDER_SEND" = "1" ]; then mode=execution; execute=--execute; fi; \
	echo "Starting $(BOT_NAME) Demo watcher: $$mode"; \
	$(PYTHON) -m scripts.ops.run_$(BOT_NAME)_wine --watch $$execute $(BOT_CACHE_ARGS)

bot-execute:
	@echo "Starting $(BOT_NAME) Demo watcher: execution"
	MT5_ENABLE_DEMO_ORDER_SEND=1 $(PYTHON) -m scripts.ops.run_$(BOT_NAME)_wine --watch --execute $(BOT_CACHE_ARGS)

bot-start:
	@if [ -f $(BOT_PID) ] && kill -0 $$(cat $(BOT_PID)) 2>/dev/null; then \
		echo "watcher already running pid $$(cat $(BOT_PID))"; exit 1; \
	fi
	@pgrep -f '[r]un_(trial30|c22h4)_wine.*--watch|[m]t5_wine_(trial30|c22h4)\.py.*--watch' >/dev/null; result=$$?; \
	if [ $$result -eq 0 ]; then echo "Demo watcher already running"; exit 1; \
	elif [ $$result -ne 1 ]; then echo "watcher inventory unavailable; start blocked"; exit 1; \
	fi
	@mode=shadow; execute=; \
	if [ "$$MT5_ENABLE_DEMO_ORDER_SEND" = "1" ]; then mode=execution; execute=--execute; fi; \
	echo "Starting $(BOT_NAME) Demo watcher: $$mode"; \
	nohup $(PYTHON) -m scripts.ops.run_$(BOT_NAME)_wine --watch $$execute $(BOT_CACHE_ARGS) >> $(BOT_LOG) 2>&1 & echo $$! > $(BOT_PID)
	@echo "started pid $$(cat $(BOT_PID))"

bot-stop:
	@if [ -f $(BOT_PID) ]; then kill -INT $$(cat $(BOT_PID)) 2>/dev/null || true; fi
	@sleep 1
	@pkill -INT -f '[r]un_$(BOT_NAME)_wine --watch' 2>/dev/null || true
	@sleep 1
	@pkill -TERM -f '[m]t5_wine_$(BOT_NAME).py --watch' 2>/dev/null || true
	@rm -f $(BOT_PID)
	@echo "watcher stop requested"

# Explicit legacy commands preserve trial30 rollback without changing its contract.
.PHONY: trial30-status trial30-once trial30-run trial30-start trial30-stop
trial30-status trial30-once trial30-run trial30-start trial30-stop:
	$(MAKE) BOT_NAME=trial30 bot-$(patsubst trial30-%,%,$@)

# bot-run and bot-start stay shadow. bot-execute and c22h4-run set the order gate.
.PHONY: c22h4-status c22h4-history-probe c22h4-once c22h4-shadow c22h4-run c22h4-stop
c22h4-status:
	$(PYTHON) -m scripts.ops.c22h4_status --brief

c22h4-history-probe:
	$(PYTHON) -m scripts.ops.run_c22h4_wine --history-probe

c22h4-once:
	$(PYTHON) -m scripts.ops.run_c22h4_wine --once

c22h4-shadow:
	$(PYTHON) -m scripts.ops.run_c22h4_wine --watch --cache-output data/c22h4-shadow-bars.csv

c22h4-run: bot-execute

c22h4-stop:
	@pkill -INT -f '[r]un_c22h4_wine --watch' 2>/dev/null || true
	@sleep 1
	@pkill -TERM -f '[m]t5_wine_c22h4.py --watch' 2>/dev/null || true
	@echo "candidate watcher stop requested; broker SL/TP remain"

.PHONY: native-frequency-check
native-frequency-check:
	$(PYTHON) -m unittest tests.test_native_frequency -v
