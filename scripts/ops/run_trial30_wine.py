"""Compatibility entrypoint for shared Demo host."""

import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_implementation = importlib.import_module("scripts.demo_runtime.host")

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
else:
    sys.modules[__name__] = _implementation
