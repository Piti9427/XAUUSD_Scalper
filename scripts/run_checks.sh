#!/usr/bin/env bash
set -euo pipefail

# Resolve repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

# Python and Ruff resolution
if [ -f "${ROOT_DIR}/.venv/bin/python" ]; then
    PYTHON="${ROOT_DIR}/.venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi

if [ -f "${ROOT_DIR}/.venv/bin/ruff" ]; then
    RUFF_CMD=("${ROOT_DIR}/.venv/bin/ruff")
elif command -v ruff >/dev/null 2>&1; then
    RUFF_CMD=("$(command -v ruff)")
else
    RUFF_CMD=("${PYTHON}" "-m" "ruff")
fi

# Visual styling
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}       XAUUSD SMC Pipeline: Running Checks       ${NC}"
echo -e "${BLUE}==================================================${NC}"

# Stage 1: Syntax compilation
echo -e "\n${BLUE}[1/5] Syntax Compilation (compileall)...${NC}"
"${PYTHON}" -m compileall -q scripts tests main.py smc_main.py test_mt5.py
echo -e "${GREEN}✓ Syntax compilation passed.${NC}"

# Stage 2: Dependency check
echo -e "\n${BLUE}[2/5] Dependency Check (pip check)...${NC}"
"${PYTHON}" -m pip check
echo -e "${GREEN}✓ Dependency check passed.${NC}"

# Stage 3: Ruff lint check
echo -e "\n${BLUE}[3/5] Lint Check (ruff check)...${NC}"
"${RUFF_CMD[@]}" check --no-cache .
echo -e "${GREEN}✓ Lint check passed.${NC}"

# Stage 4: Ruff format check
echo -e "\n${BLUE}[4/5] Format Check (ruff format --check)...${NC}"
"${RUFF_CMD[@]}" format --check --no-cache .
echo -e "${GREEN}✓ Format check passed.${NC}"

# Stage 5: Unit tests
echo -e "\n${BLUE}[5/5] Unit Tests (unittest discover)...${NC}"
"${PYTHON}" -m unittest discover -s tests
echo -e "${GREEN}✓ All unit tests passed.${NC}"

echo -e "\n${GREEN}==================================================${NC}"
echo -e "${GREEN}       All checks completed successfully!         ${NC}"
echo -e "${GREEN}==================================================${NC}"
