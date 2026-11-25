"""Compatibility import for shared Demo costs."""

import sys
from scripts.demo_runtime import costs as _implementation

sys.modules[__name__] = _implementation
