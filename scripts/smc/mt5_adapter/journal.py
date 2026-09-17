"""SQLite journal facade: inbox + lifecycle mixins."""

from __future__ import annotations

from .journal_inbox import JournalInboxMixin
from .journal_lifecycle import JournalLifecycleMixin


class JournalMixin(JournalInboxMixin, JournalLifecycleMixin):
    """Public journal surface used by SMCExecutionAdapter."""

    pass
