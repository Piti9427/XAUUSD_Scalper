"""MT5 execution adapter package — public API unchanged from monolith module."""

from scripts.smc import mt5_init

from .adapter import SMCExecutionAdapter
from .models import BOT_COMMENT_PREFIX, ExecutionResult, is_bot_owned_comment
from .runtime import mt5

# Re-exports for unittest.mock.patch targets used across the suite.
initialize_mt5 = mt5_init.initialize_mt5

__all__ = [
    "BOT_COMMENT_PREFIX",
    "ExecutionResult",
    "SMCExecutionAdapter",
    "initialize_mt5",
    "is_bot_owned_comment",
    "mt5",
]
