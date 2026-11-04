"""Durable operation intent, separate from the read-only financial journal."""

from contextlib import contextmanager, closing
import fcntl
import os
from pathlib import Path
import sqlite3

from .model import canonical


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".controller-lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("controller_busy") from None
            try:
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
                if self.path.is_symlink() or self.path.stat().st_mode & 0o077:
                    raise ValueError("private_operation_store_required")
                with closing(sqlite3.connect(self.path)) as db:
                    db.execute("PRAGMA synchronous=FULL")
                    db.executescript("""
                        CREATE TABLE IF NOT EXISTS operations (
                            id TEXT PRIMARY KEY, document TEXT NOT NULL);
                        CREATE TABLE IF NOT EXISTS accounts (
                            account TEXT PRIMARY KEY, operation TEXT NOT NULL);
                    """)
                    yield db
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @staticmethod
    def save(db, document, *, commit=True):
        if commit:
            with db:
                Store.save(db, document, commit=False)
        else:
            db.execute("INSERT INTO operations VALUES (?,?) ON CONFLICT(id) DO UPDATE SET document=excluded.document",
                       (document["operation"], canonical(document)))

    def read(self, handle):
        # inspect must not create a database, directory, schema or lock file.
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            return self.load(db, handle)

    @staticmethod
    def load(db, handle):
        import json
        row = db.execute("SELECT document FROM operations WHERE id=?", (handle.operation,)).fetchone()
        if row is None:
            raise ValueError("operation_missing")
        result = json.loads(row[0])
        if result["digest"] != handle.digest:
            raise ValueError("operation_handle_mismatch")
        return result
