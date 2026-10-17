"""Compatibility import for shared Demo broker."""

import sys
from scripts.demo_runtime import broker as _implementation

sys.modules[__name__] = _implementation
