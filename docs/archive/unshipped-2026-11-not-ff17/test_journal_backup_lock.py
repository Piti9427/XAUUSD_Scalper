"""F1 (2026-11-12): a ~32 s read lock from the daily journal backup must not crash the writer."""

import sqlite3
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.demo_runtime.journal import JOURNAL_BUSY_TIMEOUT_S, Journal


class JournalBackupLockTests(unittest.TestCase):
    def test_busy_timeout_covers_the_observed_backup_duration(self):
        self.assertGreaterEqual(JOURNAL_BUSY_TIMEOUT_S, 90)   # VM backup holds the read lock ~32 s

    def test_writer_waits_for_a_reader_lock_longer_than_sqlite_default(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.sqlite3"
            journal = Journal(path)
            self.addCleanup(journal.conn.close)
            self.addCleanup(journal.guard.close)
            journal.put("seed", 1)
            reader = sqlite3.connect(path, check_same_thread=False)
            reader.execute("BEGIN")
            reader.execute("SELECT count(*) FROM kv").fetchone()      # holds SHARED lock (journal_mode=delete)
            release = threading.Timer(6.0, reader.rollback)           # longer than the old 5 s default
            release.start()
            started = time.monotonic()
            journal.put("after_backup", 2)
            release.join(); reader.close()
            self.assertGreaterEqual(time.monotonic() - started, 5.5)
            self.assertEqual(journal.get("after_backup"), 2)


if __name__ == "__main__":
    unittest.main()
