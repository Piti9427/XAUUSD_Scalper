"""Compatibility entrypoint for shared Demo status."""

import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_implementation = importlib.import_module("scripts.demo_runtime.status")

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
