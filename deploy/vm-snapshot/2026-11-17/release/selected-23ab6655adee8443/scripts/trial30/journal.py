"""Compatibility import for shared Demo journal."""

import sys
from scripts.demo_runtime import journal as _implementation

sys.modules[__name__] = _implementation
