.PHONY: all check lint format format-check test clean help

PYTHON ?= $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else which python3; fi)
RUFF ?= $(shell if [ -f .venv/bin/ruff ]; then echo .venv/bin/ruff; else which ruff || echo "$(PYTHON) -m ruff"; fi)

help:
	@echo "Available commands:"
	@echo "  make check        - Run all checks (compileall, pip check, ruff check, ruff format --check, unittest)"
	@echo "  make lint         - Run ruff linter check"
	@echo "  make format-check - Check code formatting without modifying"
	@echo "  make format       - Auto-format code with ruff"
	@echo "  make test         - Run unit tests"
	@echo "  make clean        - Clean cache artifacts"

check: lint format-check test
	@echo "[1/5] Checking syntax compilation..."
	$(PYTHON) -m compileall -q scripts tests main.py smc_main.py
	@echo "[2/5] Checking dependencies..."
	$(PYTHON) -m pip check
	@echo "All checks passed successfully!"

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
